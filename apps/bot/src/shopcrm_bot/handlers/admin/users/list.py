# handlers/admin/users/list.py
import logging
import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from shopcrm_core.db.repositories.admin_repo import AdminRepository

from shopcrm_bot.handlers.admin.users.card import render_user_card
from shopcrm_bot.locales import Locale
from shopcrm_bot.states.admin_states import AdminUserState
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)

users_list_router = Router()

PAGE_SIZE = 5


@users_list_router.callback_query(F.data == "admin_users")
async def route_users_main_menu(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        state: FSMContext,
        locale: Locale,
):
    """
    Список пользователей (1-я страница).
    """
    await state.clear()
    await render_users_list(
        callback=callback,
        admin_repo=admin_repo,
        page=1,
        locale=locale,
    )


@users_list_router.callback_query(F.data.startswith("admin_users_page:"))
async def route_users_page(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        locale: Locale,
):
    """
    Обработка круговой пагинации.
    Callback data format: admin_users_page:{page}
    """
    parts = callback.data.split(":")
    try:
        page = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    await render_users_list(
        callback=callback,
        admin_repo=admin_repo,
        page=page,
        locale=locale,
    )


async def render_users_list(
        callback: CallbackQuery,
        admin_repo: AdminRepository,
        page: int = 1,
        locale: Locale | None = None,
) -> None:
    """
    Универсальная функция отрисовки списка пользователей
    с круговой пагинацией по 5 элементов.

    :param locale: локаль юзера из БД (инжектится middleware'ом);
        при отсутствии — fallback на "en"
    """
    if locale is None:
        locale = Locale("en")
    kb = locale.keyboards

    # 1. Считаем общее количество пользователей
    total_count = await admin_repo.get_users_count()
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

    # 2. Получаем пользователей из БД
    users = await admin_repo.get_users_page(
        limit=PAGE_SIZE,
        offset=offset,
    )

    # 3. Формируем текст: ID + мини-данные в 1 строку
    if not users:
        text = (
            locale.get_text("admin.users.list_header")
            + "\n\n"
            + locale.get_text("admin.users.list_empty")
        )
    else:
        lines = [locale.get_text("admin.users.list_header") + "\n"]
        for user in users:
            lines.append(
                locale.get_text(
                    "admin.users.list_line",
                    id=user.id,
                    name=user.first_name or "—",
                    username=f"@{user.username}" if user.username else "—",
                    orders=len(user.orders or []),
                )
            )

        text = "\n".join(lines)

    # 4. Собираем клавиатуру
    reply_markup = kb.get_users_list_kb(
        users=users,
        current_page=page,
        total_pages=total_pages,
    )

    await UIManager.show(
        event=callback,
        text=text,
        reply_markup=reply_markup,
    )
    await callback.answer()


@users_list_router.callback_query(F.data == "admin_users_find")
async def route_users_find_by_id(
        callback: CallbackQuery,
        state: FSMContext,
        locale: Locale,
):
    """Запрос ID пользователя для поиска."""
    await state.set_state(AdminUserState.find_by_id)
    await callback.answer()
    await callback.message.answer(
        locale.get_text("admin.users.find_prompt")
    )


@users_list_router.message(AdminUserState.find_by_id, F.text)
async def handle_users_find_input(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        locale: Locale,
):
    """Обработка введённого ID: открытие карточки найденного пользователя."""
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer(locale.get_text("admin.users.find_invalid"))
        return

    user_id = int(text)
    target = await admin_repo.get_user_by_id(user_id)

    if not target:
        await state.clear()
        await message.answer(
            locale.get_text("admin.users.find_not_found", id=user_id)
        )
        return

    await state.clear()
    await render_user_card(
        event=message,
        target=target,
        page=1,
        locale=locale,
    )


@users_list_router.callback_query(F.data == "noop")
async def process_users_noop(callback: CallbackQuery):
    """Индикатор текущей страницы."""
    await callback.answer()
