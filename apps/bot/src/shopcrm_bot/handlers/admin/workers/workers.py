# handlers/admin/workers/workers.py
"""Хэндлеры раздела «Работники»: список, добавление, удаление.

Callback-данные:
  - ``admin_workers``                  — корневой экран (список, 1-я страница)
  - ``admin_workers_page:{page}``      — круговая пагинация
  - ``admin_worker_add``               — FSM-добавление (ID → должность)
  - ``admin_worker_del:{telegram_id}`` — экран подтверждения удаления
  - ``admin_worker_del_confirm:{telegram_id}`` — подтверждение удаления

Система «1 сообщения»: все экраны — через ``UIManager.show`` (in-place),
FSM-ввод — по эталонному паттерну (промпт → удалить промпт и ввод →
self_destruct → in-place перерисовка списка).
"""
import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.services.admin_worker_service import AdminWorkerService

from shopcrm_bot.handlers.admin.utils import self_destruct
from shopcrm_bot.locales import Locale
from shopcrm_bot.states.admin_states import AdminWorkerState
from shopcrm_bot.ui.presenters.workers import WorkersUI

logger = logging.getLogger(__name__)

admin_workers_router = Router()


def _parse_telegram_id(data: str) -> int | None:
    """Извлекает Telegram ID из callback_data (сегмент после ':')."""
    try:
        return int(data.split(":")[1])
    except (ValueError, IndexError):
        return None


# ==================== СПИСОК ====================

@admin_workers_router.callback_query(F.data == "admin_workers")
async def route_workers_main_menu(
        callback: CallbackQuery,
        admin_worker_service: AdminWorkerService,
        main_admin_ids: list[int],
        state: FSMContext,
        locale: Locale,
):
    """Список работников (1-я страница)."""
    await state.clear()
    await callback.answer()
    await WorkersUI.show_list(
        event=callback,
        service=admin_worker_service,
        main_admin_ids=main_admin_ids,
        page=1,
        locale=locale,
    )


@admin_workers_router.callback_query(F.data.startswith("admin_workers_page:"))
async def route_workers_page(
        callback: CallbackQuery,
        admin_worker_service: AdminWorkerService,
        main_admin_ids: list[int],
        locale: Locale,
):
    """Обработка круговой пагинации.

    Callback data format: admin_workers_page:{page}
    """
    parts = callback.data.split(":")
    try:
        page = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    await callback.answer()
    await WorkersUI.show_list(
        event=callback,
        service=admin_worker_service,
        main_admin_ids=main_admin_ids,
        page=page,
        locale=locale,
    )


# ==================== ДОБАВЛЕНИЕ (FSM: ID → должность) ====================

@admin_workers_router.callback_query(F.data == "admin_worker_add")
async def route_worker_add(
        callback: CallbackQuery,
        state: FSMContext,
        locale: Locale,
):
    """Запрос Telegram ID нового работника."""
    await state.set_state(AdminWorkerState.add_id)
    await callback.answer()
    prompt_message = await callback.message.answer(
        locale.get_text("admin.workers.add_id_prompt")
    )
    await state.update_data(
        menu_message_id=callback.message.message_id,
        prompt_message_id=prompt_message.message_id,
    )


@admin_workers_router.message(AdminWorkerState.add_id, F.text)
async def handle_worker_add_id(
        message: Message,
        state: FSMContext,
        admin_ids: list[int],
        locale: Locale,
):
    """Шаг 1: введённый Telegram ID.

    Валидный ID → удаляем промпт и ввод, просим должность.
    Ошибка → временное сообщение (self-destruct) и сброс состояния.
    """
    data = await state.get_data()
    prompt_message_id = data.get("prompt_message_id")

    text = (message.text or "").strip()
    if not text.isdigit():
        await state.clear()
        err = await message.answer(locale.get_text("admin.workers.add_invalid_id"))
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    telegram_id = int(text)
    if telegram_id in admin_ids:
        await state.clear()
        err = await message.answer(
            locale.get_text("admin.workers.add_exists", id=telegram_id)
        )
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    # Удаляем сообщение-промпт (бот удаляет своё сообщение — работает и в личке)
    if prompt_message_id:
        with suppress(TelegramBadRequest):
            await message.bot.delete_message(message.chat.id, prompt_message_id)

    # Удаляем ввод пользователя (в личке — ограничение Telegram, в группах работает)
    with suppress(TelegramBadRequest):
        await message.delete()

    # Шаг 2: должность
    await state.set_state(AdminWorkerState.add_position)
    prompt_message = await message.answer(
        locale.get_text("admin.workers.add_position_prompt")
    )
    await state.update_data(
        telegram_id=telegram_id,
        menu_message_id=data.get("menu_message_id"),
        prompt_message_id=prompt_message.message_id,
    )


@admin_workers_router.message(AdminWorkerState.add_position, F.text)
async def handle_worker_add_position(
        message: Message,
        state: FSMContext,
        admin_worker_service: AdminWorkerService,
        main_admin_ids: list[int],
        locale: Locale,
):
    """Шаг 2: должность. Сохранение и in-place перерисовка списка."""
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    menu_message_id = data.get("menu_message_id")
    prompt_message_id = data.get("prompt_message_id")
    await state.clear()

    # Защита: состояние без telegram_id (не должно происходить —
    # add_position достижимо только через add_id).
    if telegram_id is None:
        return

    # Удаляем сообщение-промпт (бот удаляет своё сообщение — работает и в личке)
    if prompt_message_id:
        with suppress(TelegramBadRequest):
            await message.bot.delete_message(message.chat.id, prompt_message_id)

    # Удаляем ввод пользователя (в личке — ограничение Telegram, в группах работает)
    with suppress(TelegramBadRequest):
        await message.delete()

    worker, error = await admin_worker_service.add_worker(
        telegram_id=telegram_id,
        position=message.text or "",
        main_admin_ids=main_admin_ids,
    )

    if error:
        key = (
            "admin.workers.add_empty_position"
            if error == "invalid_position"
            else "admin.workers.add_exists"
        )
        err = await message.answer(locale.get_text(key, id=telegram_id))
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    success = await message.answer(
        locale.get_text(
            "admin.workers.add_success",
            id=worker.telegram_id,
            position=worker.position,
        )
    )
    asyncio.create_task(self_destruct(message=success, seconds=3))

    # Список с новым работником (in-place)
    await WorkersUI.show_list(
        event=message,
        service=admin_worker_service,
        main_admin_ids=main_admin_ids,
        page=1,
        locale=locale,
        message_id_to_edit=menu_message_id,
    )


# ==================== УДАЛЕНИЕ (с подтверждением) ====================

# ВАЖНО: хэндлер подтверждения зарегистрирован ДО ``admin_worker_del:`` —
# префикс ``admin_worker_del:`` также совпадает с ``admin_worker_del_confirm:``.
@admin_workers_router.callback_query(F.data.startswith("admin_worker_del_confirm:"))
async def route_worker_delete_confirm(
        callback: CallbackQuery,
        admin_worker_service: AdminWorkerService,
        main_admin_ids: list[int],
        locale: Locale,
):
    """Подтверждение удаления работника (необратимо).

    Callback data format: admin_worker_del_confirm:{telegram_id}
    """
    telegram_id = _parse_telegram_id(callback.data)
    if telegram_id is None:
        await callback.answer()
        return
    await callback.answer()

    _, error = await admin_worker_service.remove_worker(
        telegram_id=telegram_id,
        main_admin_ids=main_admin_ids,
    )

    if error == "main_admin":
        msg = await callback.message.answer(
            locale.get_text("admin.workers.delete_main_forbidden")
        )
        asyncio.create_task(self_destruct(message=msg, seconds=3))
    elif error == "not_found":
        msg = await callback.message.answer(
            locale.get_text("admin.workers.delete_not_found", id=telegram_id)
        )
        asyncio.create_task(self_destruct(message=msg, seconds=3))
    else:
        msg = await callback.message.answer(
            locale.get_text("admin.workers.delete_success", id=telegram_id)
        )
        asyncio.create_task(self_destruct(message=msg, seconds=3))

    # Возврат к списку (in-place) — в любом исходе
    await WorkersUI.show_list(
        event=callback,
        service=admin_worker_service,
        main_admin_ids=main_admin_ids,
        page=1,
        locale=locale,
        message_id_to_edit=callback.message.message_id,
    )


@admin_workers_router.callback_query(F.data.startswith("admin_worker_del:"))
async def route_worker_delete(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        locale: Locale,
):
    """Экран подтверждения удаления работника (in-place вместо списка).

    Callback data format: admin_worker_del:{telegram_id}
    """
    telegram_id = _parse_telegram_id(callback.data)
    if telegram_id is None:
        await callback.answer()
        return

    worker = await admin_repo.get_worker_by_telegram_id(telegram_id)
    if not worker:
        await callback.answer(
            locale.get_text("admin.workers.delete_not_found", id=telegram_id),
            show_alert=True,
        )
        return

    await callback.answer()
    await WorkersUI.show_delete_confirm(
        event=callback,
        telegram_id=telegram_id,
        position=worker.position,
        locale=locale,
        message_id_to_edit=callback.message.message_id,
    )
