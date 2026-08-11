# handlers/admin/orders/view.py
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.orders.common import render_order_detail
from src.core.constants import OrderStatus

logger = logging.getLogger(__name__)

order_view_router = Router()


@order_view_router.callback_query(F.data.startswith("admin_order_view:"))
async def route_order_view(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    state: FSMContext,
    user: User,
):
    await state.clear()
    parts = callback.data.split(":")
    order_id = int(parts[1])
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1

    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_view_router.callback_query(F.data.startswith("admin_order_accept:"))
async def process_accept_order(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
    user: User,
):
    """
    Подтверждение заказа администратором.
    Заказ переводится в статус PROCESSING (передан в сборку / ожидает курьера).
    """
    parts = callback.data.split(":")
    order_id, status, page = int(parts[1]), parts[2], int(parts[3])

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # Заказ отработан администратором и переходит на стадию подготовки/сборки перед доставкой
    order.status = OrderStatus.PROCESSING.value
    order.is_paid = True

    await admin_repo.update_order(order)
    await callback.answer("✅ Заказ подтвержден и переведен в обработку!", show_alert=True)

    await render_order_detail(
        event=callback,
        admin_repo=admin_repo,
        user=user,
        order_id=order_id,
        status=status,
        page=page,
    )


@order_view_router.callback_query(F.data.startswith("admin_order_contact_client:"))
async def process_contact_client(
    callback: CallbackQuery,
    admin_repo: AdminRepository,
):
    parts = callback.data.split(":")
    order_id = int(parts[1])

    order = await admin_repo.get_order_by_id(order_id)
    if not order or not order.user:
        await callback.answer("❌ Данные пользователя недоступны", show_alert=True)
        return

    await callback.answer(
        f"💬 Чат с пользователем ID {order.user.id} в разработке...",
        show_alert=True,
    )


