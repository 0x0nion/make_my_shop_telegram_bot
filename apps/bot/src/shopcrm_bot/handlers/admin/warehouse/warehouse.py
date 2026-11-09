# handlers/admin/warehouse/warehouse.py
"""Хэндлеры раздела «Склад»: навигация и операции с остатками.

Callback-данные:
  - ``admin_warehouse``            — корневой экран
  - ``admin_warehouse_cat_{id}``   — экран категории
  - ``admin_warehouse_prod_{id}``  — карточка товара
  - ``admin_warehouse_add_{id}``   — запрос количества для пополнения
  - ``admin_warehouse_off_{id}``   — запрос количества для списания
  - ``admin_warehouse_del_{id}``   — экран подтверждения удаления
  - ``admin_warehouse_del_confirm_{id}`` — подтверждение полного удаления
  - ``admin_warehouse_restore_{id}`` — возврат архивного товара в каталог
"""
import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.services.validation import validate_quantity
from shopcrm_core.services.warehouse_service import WarehouseService

from shopcrm_bot.handlers.admin.utils import self_destruct
from shopcrm_bot.locales import Locale
from shopcrm_bot.states.admin_states import WarehouseState
from shopcrm_bot.ui.presenters.warehouse import WarehouseUI

warehouse_router = Router()
logger = logging.getLogger(__name__)


def _parse_id(data: str) -> int | None:
    """Извлекает ID из callback_data (последний сегмент после '_')."""
    try:
        return int(data.split("_")[-1])
    except (ValueError, IndexError):
        return None


# ==================== НАВИГАЦИЯ ====================

@warehouse_router.callback_query(F.data == "admin_warehouse")
async def warehouse_root(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Корневой экран склада."""
    await callback.answer()
    await WarehouseUI.show_root(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        message_id_to_edit=callback.message.message_id,
    )


@warehouse_router.callback_query(F.data.startswith("admin_warehouse_cat_"))
async def warehouse_category(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Экран категории склада."""
    await callback.answer()
    category_id = _parse_id(callback.data)
    if category_id is None:
        logger.warning(f"[WAREHOUSE] Invalid category callback: {callback.data}")
        return
    await WarehouseUI.show_category(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        category_id=category_id,
        message_id_to_edit=callback.message.message_id,
    )


@warehouse_router.callback_query(F.data.startswith("admin_warehouse_prod_"))
async def warehouse_product(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Карточка товара склада."""
    await callback.answer()
    product_id = _parse_id(callback.data)
    if product_id is None:
        logger.warning(f"[WAREHOUSE] Invalid product callback: {callback.data}")
        return
    await WarehouseUI.show_product(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        product_id=product_id,
        message_id_to_edit=callback.message.message_id,
    )


# ==================== ЗАПРОС КОЛИЧЕСТВА ====================

@warehouse_router.callback_query(F.data.startswith("admin_warehouse_add_"))
async def warehouse_start_add_stock(
    callback: CallbackQuery,
    state: FSMContext,
    locale: Locale,
):
    """Запрос количества для пополнения."""
    product_id = _parse_id(callback.data)
    if product_id is None:
        await callback.answer()
        return
    await state.set_state(WarehouseState.add_stock)
    await callback.answer()
    prompt_message = await callback.message.answer(
        locale.get_text("admin.warehouse.add_stock_prompt")
    )
    await state.update_data(
        product_id=product_id,
        menu_message_id=callback.message.message_id,
        prompt_message_id=prompt_message.message_id,
    )


@warehouse_router.callback_query(F.data.startswith("admin_warehouse_off_"))
async def warehouse_start_write_off(
    callback: CallbackQuery,
    state: FSMContext,
    locale: Locale,
):
    """Запрос количества для списания."""
    product_id = _parse_id(callback.data)
    if product_id is None:
        await callback.answer()
        return
    await state.set_state(WarehouseState.write_off_stock)
    await callback.answer()
    prompt_message = await callback.message.answer(
        locale.get_text("admin.warehouse.write_off_prompt")
    )
    await state.update_data(
        product_id=product_id,
        menu_message_id=callback.message.message_id,
        prompt_message_id=prompt_message.message_id,
    )


# ==================== ПОЛНОЕ УДАЛЕНИЕ ТОВАРА ====================

@warehouse_router.callback_query(F.data.startswith("admin_warehouse_del_confirm_"))
async def warehouse_confirm_delete(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    warehouse_service: WarehouseService,
    user: User,
    locale: Locale,
):
    """Подтверждение полного удаления товара (необратимо)."""
    product_id = _parse_id(callback.data)
    if product_id is None:
        await callback.answer()
        return
    await callback.answer()

    # Запоминаем данные до удаления (объект будет отсоединён от сессии)
    product_before = await admin_repo.get_product_by_id(product_id)
    if not product_before:
        msg = await callback.message.answer(
            locale.get_text("admin.warehouse.product_not_found")
        )
        asyncio.create_task(self_destruct(message=msg, seconds=3))
        return
    name = product_before.name
    category_id = product_before.category_id

    _, error = await warehouse_service.delete_product(product_id, admin_id=user.id)

    if error in ("has_stock", "has_orders"):
        key = (
            "admin.warehouse.delete_blocked_stock"
            if error == "has_stock"
            else "admin.warehouse.delete_blocked_orders"
        )
        msg = await callback.message.answer(locale.get_text(key))
        asyncio.create_task(self_destruct(message=msg, seconds=5))
        # Возврат в карточку товара
        await WarehouseUI.show_product(
            event=callback,
            admin_repo=admin_repo,
            user=user,
            locale=locale,
            product_id=product_id,
            message_id_to_edit=callback.message.message_id,
        )
        return

    # Успех: товар и история удалены
    msg = await callback.message.answer(
        locale.get_text("admin.warehouse.delete_success", name=name)
    )
    asyncio.create_task(self_destruct(message=msg, seconds=3))
    if category_id:
        await WarehouseUI.show_category(
            event=callback,
            admin_repo=admin_repo,
            user=user,
            locale=locale,
            category_id=category_id,
            message_id_to_edit=callback.message.message_id,
        )
    else:
        await WarehouseUI.show_root(
            event=callback,
            admin_repo=admin_repo,
            user=user,
            locale=locale,
            message_id_to_edit=callback.message.message_id,
        )


@warehouse_router.callback_query(F.data.startswith("admin_warehouse_del_"))
async def warehouse_start_delete(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
    locale: Locale,
):
    """Экран подтверждения полного удаления товара."""
    product_id = _parse_id(callback.data)
    if product_id is None:
        await callback.answer()
        return
    product = await admin_repo.get_product_by_id(product_id)
    if not product:
        await callback.answer(
            locale.get_text("admin.warehouse.product_not_found"), show_alert=True
        )
        return
    await callback.answer()
    await WarehouseUI.show_delete_confirm(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        product_id=product_id,
        message_id_to_edit=callback.message.message_id,
    )


# ==================== ВОЗВРАТ ИЗ АРХИВА ====================

@warehouse_router.callback_query(F.data.startswith("admin_warehouse_restore_"))
async def warehouse_restore_product(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    warehouse_service: WarehouseService,
    user: User,
    locale: Locale,
):
    """Возврат архивного товара в каталог (is_active=True)."""
    product_id = _parse_id(callback.data)
    if product_id is None:
        await callback.answer()
        return
    await callback.answer()

    product, error = await warehouse_service.restore_product(product_id, admin_id=user.id)
    if error == "not_found":
        msg = await callback.message.answer(
            locale.get_text("admin.warehouse.product_not_found")
        )
        asyncio.create_task(self_destruct(message=msg, seconds=3))
        return

    if error is None:
        # Успех: товар возвращён в каталог
        msg = await callback.message.answer(
            locale.get_text("admin.warehouse.restore_success", name=product.name)
        )
        asyncio.create_task(self_destruct(message=msg, seconds=3))
    # error == "already_active" — просто показываем актуальную карточку

    await WarehouseUI.show_product(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        product_id=product_id,
        message_id_to_edit=callback.message.message_id,
    )


# ==================== ОБРАБОТКА ВВОДА ====================

@warehouse_router.message(WarehouseState.add_stock, F.text)
async def warehouse_process_add_stock(
    message: Message,
    state: FSMContext,
    admin_repo: AdminRepository,
    warehouse_service: WarehouseService,
    user: User,
    locale: Locale,
):
    """Обработка ввода количества для пополнения."""
    data = await state.get_data()
    product_id = data.get("product_id")
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

    qty, error = validate_quantity(message.text, user.language)
    if error:
        err = await message.answer(error)
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    product = await warehouse_service.add_stock(product_id, qty, admin_id=user.id)
    if not product:
        err = await message.answer(locale.get_text("admin.warehouse.product_not_found"))
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    success = locale.get_text(
        "admin.warehouse.add_stock_success", name=product.name, qty=qty, stock=product.stock
    )
    err = await message.answer(success)
    asyncio.create_task(self_destruct(message=err, seconds=3))

    await WarehouseUI.show_product(
        event=message,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        product_id=product_id,
        message_id_to_edit=menu_message_id,
    )


@warehouse_router.message(WarehouseState.write_off_stock, F.text)
async def warehouse_process_write_off(
    message: Message,
    state: FSMContext,
    admin_repo: AdminRepository,
    warehouse_service: WarehouseService,
    user: User,
    locale: Locale,
):
    """Обработка ввода количества для списания."""
    data = await state.get_data()
    product_id = data.get("product_id")
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

    qty, error = validate_quantity(message.text, user.language)
    if error:
        err = await message.answer(error)
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    product = await warehouse_service.write_off_stock(product_id, qty, admin_id=user.id)
    if not product:
        err = await message.answer(locale.get_text("admin.warehouse.product_not_found"))
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    success = locale.get_text(
        "admin.warehouse.write_off_success", name=product.name, qty=qty, stock=product.stock
    )
    err = await message.answer(success)
    asyncio.create_task(self_destruct(message=err, seconds=3))

    await WarehouseUI.show_product(
        event=message,
        admin_repo=admin_repo,
        user=user,
        locale=locale,
        product_id=product_id,
        message_id_to_edit=menu_message_id,
    )

