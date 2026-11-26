# handlers/admin/broadcast/broadcast.py
"""Админ-раздел «Рассылка»: создание и ожидание завершения.

Поток: админ вводит текст -> рассылка создаётся и запускается сразу,
экран показывает прогресс (только «Назад»). Пока идёт рассылка, новую
запустить нельзя (per-shop блокировка). По завершении бот присылает
админу разовое уведомление с итогами.

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
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.services.broadcast_service import BroadcastService

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
    broadcast_sender: BroadcastSender,
    admin_ids: list[int],
):
    """Обработка ввода текста: создание + немедленный запуск рассылки."""
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

    # Запуск фоновой отправки: БД — источник истины, рассылка переживает рестарт
    broadcast_sender.start(result.broadcast.id)
    await BroadcastUI.show_progress(
        event=message,
        locale=locale,
        broadcast=result.broadcast,
        message_id_to_edit=menu_message_id,
    )


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

