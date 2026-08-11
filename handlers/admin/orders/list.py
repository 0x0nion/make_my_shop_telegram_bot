import logging
import math
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from src.core.constants import OrderStatus
from src.core.ui import UIManager

logger = logging.getLogger(__name__)

orders_list_router = Router()

PAGE_SIZE = 10

CALLBACK_TO_STATUS = {
    "admin_order_all": "all",
    "admin_order_pending": OrderStatus.PENDING.value,
    "admin_order_awaiting": OrderStatus.AWAITING_CONFIRMATION.value,
    "admin_order_processing": OrderStatus.PROCESSING.value,
    "admin_order_delivering": OrderStatus.DELIVERING.value,
}


@orders_list_router.callback_query(F.data == "admin_orders")
async def route_orders_main_menu(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        state: FSMContext,
        user: User,
):
    """
    Основное меню управления заказами со счетчиками.
    """
    await state.clear()

    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    status_counts = await admin_repo.get_orders_count_by_statuses()

    text = kb.get_text(
        "orders_menu_title",
        "📋 <b>Управление заказами</b>\n\nВыберите категорию для просмотра:"
    )

    reply_markup = kb.get_orders_menu_kb(status_counts=status_counts)

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )
    await callback.answer()


@orders_list_router.callback_query(F.data.in_(CALLBACK_TO_STATUS.keys()))
async def route_orders_by_status(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Переход в выбранный статус/фильтр (1-я страница).
    """
    db_status = CALLBACK_TO_STATUS[callback.data]
    await render_orders_list(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        status=db_status,
        page=1,
    )


@orders_list_router.callback_query(F.data.startswith("admin_orders_page:"))
async def route_orders_page(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
):
    """
    Обработка круговой пагинации.
    Callback data format: admin_orders_page:{status}:{page}
    """
    parts = callback.data.split(":")
    status = parts[1]
    page = int(parts[2])

    await render_orders_list(
        callback=callback,
        admin_repo=admin_repo,
        user=user,
        status=status,
        page=page,
    )


async def render_orders_list(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        status: str,
        page: int = 1,
):
    """
    Универсальная функция отрисовки списка заказов с круговой пагинацией по 10 элементов.
    """
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    # 1. Считаем количество заказов в текущей категории
    status_counts = await admin_repo.get_orders_count_by_statuses()

    if status == "all":
        total_count = sum(status_counts.values())
    else:
        total_count = status_counts.get(status, 0)

    total_pages = math.ceil(total_count / PAGE_SIZE)

    # Корректируем номер страницы с учётом зацикливания/границ
    if total_pages > 0:
        if page < 1:
            page = total_pages
        elif page > total_pages:
            page = 1
    else:
        page = 1

    offset = (page - 1) * PAGE_SIZE if total_count > 0 else 0

    # 2. Получаем заказы из БД
    orders = await admin_repo.get_orders_by_status(
        status=status,
        limit=PAGE_SIZE,
        offset=offset,
    )

    # 3. Формируем текст
    if not orders:
        text = f"📋 <b>Список заказов ({status})</b>\n\n<i>Заказы не найдены.</i>"
    else:
        lines = [f"📋 <b>Список заказов ({status})</b>\n"]
        for order in orders:
            lines.append(f"ID: <code>{order.id}</code> | {order.total_price} $ - <b>{order.status}</b>")

        text = "\n".join(lines)

    # 4. Собираем клавиатуру
    reply_markup = kb.get_orders_list_kb(
        orders=orders,
        current_page=page,
        total_pages=total_pages,
        status=status,
    )

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )
    await callback.answer()


@orders_list_router.callback_query(F.data == "noop")
async def process_list_noop(callback: CallbackQuery):
    """Индикатор текущей страницы."""
    await callback.answer()