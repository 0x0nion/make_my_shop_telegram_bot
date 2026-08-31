import logging
from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from locales.locale import Locale
from src.core.ui import UIManager

logger = logging.getLogger(__name__)

order_items_router = Router()


async def render_edit_order_items_ui(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        order_id: int,
        status: str = "all",
        page: int = 1,
):
    """
    Функция отрисовки интерфейса редактирования позиций.
    Динамически собирает список товаров в тексте сообщения и прикрепляет клавиатуру.
    """
    lang = user.language
    kb = Locale(lang).keyboards

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # 1. Формируем текстовый список товаров
    items_lines = []
    if order.items:
        for idx, item in enumerate(order.items, start=1):
            prod_name = item.product.name if item.product else f"Товар #{item.product_id}"
            unit = getattr(item.product, "unit", "шт.") if item.product else "шт."
            price = float(item.price_at_purchase)
            qty = item.quantity
            item_sum = qty * price

            items_lines.append(
                f"{idx}. <b>{prod_name}</b>\n"
                f"   └ {qty} {unit} × {price:.2f} $ = <b>{item_sum:.2f} $</b>"
            )
    else:
        items_lines.append("<i>Список товаров пуст.</i>")

    items_block = "\n".join(items_lines)
    delivery_price = float(order.delivery_price or 0.0)
    total_price = float(order.total_price or 0.0)

    # 2. Собираем общий текст
    text = (
        f"✏️ <b>Редактирование состава заказа #{order.id}</b>\n\n"
        f"🛒 <b>Текущие товары:</b>\n"
        f"{items_block}\n\n"
        f"🚚 <b>Доставка:</b> {delivery_price:.2f} $\n"
        f"💰 <b>Итоговая сумма:</b> <b>{total_price:.2f} $</b>\n\n"
        f"👇 <i>Используйте кнопки ниже для изменения количества (➕ / ➖) или удаления товаров:</i>"
    )

    # 3. Генерируем клавиатуру с кнопками
    reply_markup = kb.get_order_items_editor_kb(order=order, status=status, page=page)

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )


@order_items_router.callback_query(F.data.startswith("admin_order_edit_items:"))
async def route_edit_order_items(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    await render_edit_order_items_ui(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_items_router.callback_query(F.data.startswith("admin_order_dec_item:"))
async def process_dec_order_item(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    item_id = int(parts[2])
    status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    order = await admin_repo.get_order_by_id(order_id)
    if order and order.items:
        item = next((i for i in order.items if i.id == item_id), None)
        if item:
            if item.quantity > 1:
                item.quantity -= 1
            else:
                order.items.remove(item)

            items_sum = sum(i.quantity * float(i.price_at_purchase) for i in order.items)
            current_delivery = float(order.delivery_price or 0.0)
            order.total_price = items_sum + current_delivery

            await admin_repo.update_order(order)

    await render_edit_order_items_ui(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_items_router.callback_query(F.data.startswith("admin_order_inc_item:"))
async def process_inc_order_item(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    item_id = int(parts[2])
    status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    order = await admin_repo.get_order_by_id(order_id)
    if order and order.items:
        item = next((i for i in order.items if i.id == item_id), None)
        if item:
            item.quantity += 1

            items_sum = sum(i.quantity * float(i.price_at_purchase) for i in order.items)
            current_delivery = float(order.delivery_price or 0.0)
            order.total_price = items_sum + current_delivery

            await admin_repo.update_order(order)

    await render_edit_order_items_ui(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_items_router.callback_query(F.data.startswith("admin_order_delete_item:"))
async def process_delete_order_item(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    item_id = int(parts[2])
    status = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 1

    order = await admin_repo.get_order_by_id(order_id)
    if order and order.items:
        item_to_remove = next((i for i in order.items if i.id == item_id), None)
        if item_to_remove:
            order.items.remove(item_to_remove)

            items_sum = sum(i.quantity * float(i.price_at_purchase) for i in order.items)
            current_delivery = float(order.delivery_price or 0.0)

            order.total_price = items_sum + current_delivery
            await admin_repo.update_order(order)

    await render_edit_order_items_ui(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_items_router.callback_query(F.data.startswith("admin_order_noop:"))
async def process_order_noop(callback: CallbackQuery):
    await callback.answer()

