# handlers/admin/broadcast/broadcast.py
"""Админ-раздел «Рассылка»: создание, подтверждение, остановка, возобновление.

Паттерн FSM-ввода — как в разделе «Склад» (warehouse.py): промпт через
``callback.message.answer``, после ввода — удалить промпт и ввод юзера,
ошибка/успех — ``message.answer`` + ``self_destruct``, затем in-place
перерисовка экрана через ``UIManager.show``.

Отправку выполняет фоновая задача ``BroadcastSender`` (workflow data):
БД — источник истины, рассылка переживает рестарт бота.
"""
import asyncio
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.broadcast import BroadcastStatus
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.services.broadcast_service import BroadcastService

from shopcrm_bot.config import config
from shopcrm_bot.handlers.admin.utils import self_destruct
from shopcrm_bot.locales import Locale
from shopcrm_bot.services.broadcast_sender import BroadcastSender
from shopcrm_bot.states.admin_states import BroadcastState
from shopcrm_bot.ui.presenters.admin import AdminUI
from shopcrm_bot.ui.presenters.broadcast import BroadcastUI

broadcast_router = Router()


async def _show_screen(
    event: Message | CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
    message_id_to_edit: int | None = None,
) -> None:
    """Перерисовка главного экрана раздела (in-place)."""
    await BroadcastUI.show_screen(
        event=event,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        message_id_to_edit=message_id_to_edit,
        cooldown_hours=config.BROADCAST_COOLDOWN_HOURS,
    )


# ==================== ВХОД В РАЗДЕЛ ====================

@broadcast_router.callback_query(F.data == "admin_alert")
async def broadcast_open(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Кнопка «📢 Рассылка» в главном меню админки."""
    await callback.answer()
    await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)


# ==================== СОЗДАНИЕ РАССЫЛКИ ====================

@broadcast_router.callback_query(F.data == "admin_broadcast_start")
async def broadcast_start(
    callback: CallbackQuery,
    state: FSMContext,
    locale: Locale,
):
    """Запрос текста рассылки (FSM-промпт)."""
    await state.set_state(BroadcastState.text)
    await callback.answer()
    prompt_message = await callback.message.answer(
        locale.get_text("admin.broadcast.text_prompt")
    )
    await state.update_data(
        menu_message_id=callback.message.message_id,
        prompt_message_id=prompt_message.message_id,
    )


@broadcast_router.message(BroadcastState.text, F.text)
async def broadcast_text(
    message: Message,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
    broadcast_service: BroadcastService,
    admin_ids: list[int],
):
    """Обработка ввода текста: создание рассылки + экран подтверждения."""
    data = await state.get_data()
    menu_message_id = data.get("menu_message_id")
    prompt_message_id = data.get("prompt_message_id")
    await state.clear()

    # Удаляем сообщение-промпт (бот удаляет своё сообщение — работает и в личке)
    if prompt_message_id:
        with suppress(TelegramBadRequest):
            await message.bot.delete_message(message.chat.id, prompt_message_id)

    # Удаляем ввод пользователя (в личке — ограничение Telegram, в группах работает)
    with suppress(TelegramBadRequest):
        await message.delete()

    text = (message.text or "").strip()
    if not text:
        err = await message.answer(locale.get_text("admin.broadcast.error_empty"))
        asyncio.create_task(self_destruct(message=err, seconds=3))
        await _show_screen(message, admin_repo, user, locale, menu_message_id)
        return

    result = await broadcast_service.create(user.id, text, admin_ids)

    if result.error == "already_active":
        err = await message.answer(locale.get_text("admin.broadcast.error_already_active"))
        asyncio.create_task(self_destruct(message=err, seconds=5))
        await _show_screen(message, admin_repo, user, locale, menu_message_id)
        return

    if result.error == "no_recipients":
        err = await message.answer(locale.get_text("admin.broadcast.error_no_recipients"))
        asyncio.create_task(self_destruct(message=err, seconds=5))
        await _show_screen(message, admin_repo, user, locale, menu_message_id)
        return

    # Экран подтверждения (broadcast_id храним в state data;
    # состояние не ставим — подтверждение только по кнопкам)
    await state.update_data(broadcast_id=result.broadcast.id)
    await BroadcastUI.show_confirm(
        event=message,
        locale=locale,
        text=result.broadcast.text,
        recipients=result.recipients,
        skipped=result.skipped,
        message_id_to_edit=menu_message_id,
    )


# ==================== ПОДТВЕРЖДЕНИЕ / ОТМЕНА ====================

@broadcast_router.callback_query(F.data == "admin_broadcast_confirm")
async def broadcast_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
    broadcast_sender: BroadcastSender,
):
    """Подтверждение: запуск фоновой отправки."""
    data = await state.get_data()
    broadcast_id = data.get("broadcast_id")
    await state.clear()
    await callback.answer()

    broadcast = await admin_repo.get_broadcast(broadcast_id) if broadcast_id else None
    if (
        not broadcast
        or broadcast.admin_id != user.id
        or broadcast.status != BroadcastStatus.PENDING.value
    ):
        # Рассылка не найдена или уже запущена/изменена — показываем актуальный экран
        await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)
        return

    broadcast_sender.start(broadcast.id)
    await BroadcastUI.show_progress(
        event=callback,
        locale=locale,
        broadcast=broadcast,
        message_id_to_edit=callback.message.message_id,
    )


@broadcast_router.callback_query(F.data == "admin_broadcast_cancel")
async def broadcast_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
    broadcast_service: BroadcastService,
):
    """Отмена на экране подтверждения (рассылка ещё не запускалась)."""
    data = await state.get_data()
    broadcast_id = data.get("broadcast_id")
    await state.clear()
    await callback.answer()

    if broadcast_id:
        await broadcast_service.delete_pending(user.id, broadcast_id)

    msg = await callback.message.answer(locale.get_text("admin.broadcast.cancel_success"))
    asyncio.create_task(self_destruct(message=msg, seconds=3))
    await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)


# ==================== ПРОГРЕСС / ОСТАНОВКА / ВОЗОБНОВЛЕНИЕ ====================

@broadcast_router.callback_query(F.data == "admin_broadcast_progress")
async def broadcast_progress(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Обновление экрана прогресса (polling: данные всегда из БД)."""
    await callback.answer()
    active = await admin_repo.get_active_broadcast(user.id)
    if active:
        await BroadcastUI.show_progress(
            event=callback,
            locale=locale,
            broadcast=active,
            message_id_to_edit=callback.message.message_id,
        )
        return
    # Рассылка завершилась, пока админ смотрел экран — показываем результат
    last = await admin_repo.get_latest_broadcast(user.id)
    if last:
        await BroadcastUI.show_result(
            event=callback,
            locale=locale,
            broadcast=last,
            message_id_to_edit=callback.message.message_id,
        )
    else:
        await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)


@broadcast_router.callback_query(F.data == "admin_broadcast_stop")
async def broadcast_stop(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
    broadcast_service: BroadcastService,
):
    """Остановка идущей рассылки (graceful: дождётся текущего чанка)."""
    await callback.answer()
    active = await admin_repo.get_active_broadcast(user.id)
    if not active:
        await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)
        return

    await broadcast_service.cancel(user.id, active.id)
    # Перечитываем: статус сменился на cancelling
    active = await admin_repo.get_active_broadcast(user.id)
    if active:
        await BroadcastUI.show_progress(
            event=callback,
            locale=locale,
            broadcast=active,
            message_id_to_edit=callback.message.message_id,
        )
    else:
        await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)


@broadcast_router.callback_query(F.data == "admin_broadcast_resume")
async def broadcast_resume(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
    broadcast_sender: BroadcastSender,
):
    """Возобновление прерванной рассылки (после рестарта бота)."""
    await callback.answer()
    last = await admin_repo.get_latest_broadcast(user.id)
    if (
        last
        and last.admin_id == user.id
        and last.status == BroadcastStatus.INTERRUPTED.value
        and broadcast_sender.start(last.id)
    ):
        await BroadcastUI.show_progress(
            event=callback,
            locale=locale,
            broadcast=last,
            message_id_to_edit=callback.message.message_id,
        )
        return
    await _show_screen(callback, admin_repo, user, locale, callback.message.message_id)


# ==================== НАВИГАЦИЯ ====================

@broadcast_router.callback_query(F.data == "admin_broadcast_back")
async def broadcast_back(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    locale: Locale,
):
    """Возврат в главное меню админки."""
    await callback.answer()
    new_orders_count = await admin_repo.get_new_orders_count(status=OrderStatus.PENDING)
    await AdminUI.show_admin_main_menu(
        event=callback,
        new_orders_count=new_orders_count,
        locale=locale,
    )

