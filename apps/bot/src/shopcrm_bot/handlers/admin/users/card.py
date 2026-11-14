# handlers/admin/users/card.py
import asyncio
import logging
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from shopcrm_core.constants import OrderStatus
from shopcrm_core.db.models.user import User
from shopcrm_core.services.admin_user_service import AdminUserService
from shopcrm_core.services.validation import validate_discount
from shopcrm_core.utils import format_price

from shopcrm_bot.handlers.admin.utils import self_destruct
from shopcrm_bot.locales import Locale
from shopcrm_bot.states.admin_states import AdminUserState
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)

user_card_router = Router()


def _format_discount(value: float) -> str:
    """Форматирует скидку без хвостовых нулей: 10.0 -> "10", 15.5 -> "15.5"."""
    return f"{value:g}"


def _build_card_text(target: User, locale: Locale) -> str:
    """Собирает текст карточки пользователя со всей полезной сводкой."""
    lines = [locale.get_text("admin.users.card_title", id=target.id), ""]

    lines.append(locale.get_text("admin.users.card_name", name=target.first_name or "—"))
    if target.username:
        lines.append(
            locale.get_text("admin.users.card_username", username=f"@{target.username}")
        )
    if target.created_at:
        lines.append(
            locale.get_text(
                "admin.users.card_registered",
                date=target.created_at.strftime("%d.%m.%Y"),
            )
        )
    lines.append(locale.get_text("admin.users.card_language", lang=target.language or "—"))

    role_key = (
        "admin.users.role_admin" if target.role == "admin" else "admin.users.role_client"
    )
    lines.append(locale.get_text("admin.users.card_role", role=locale.get_text(role_key)))

    # Активен = есть заказы в не-финальных статусах.
    active_count = target.active_orders_count
    if active_count > 0:
        lines.append(locale.get_text("admin.users.card_active", count=active_count))
    else:
        lines.append(locale.get_text("admin.users.card_inactive"))

    orders = target.orders or []
    lines.append(locale.get_text("admin.users.card_orders", count=len(orders)))
    # «Потрачено» — сумма по всем заказам, кроме отменённых.
    total_spent = sum(
        float(o.total_price or 0)
        for o in orders
        if o.status != OrderStatus.CANCELLED.value
    )
    lines.append(
        locale.get_text("admin.users.card_total_spent", total=format_price(total_spent))
    )
    lines.append(
        locale.get_text(
            "admin.users.card_discount", discount=_format_discount(target.discount or 0)
        )
    )

    return "\n".join(lines)


async def render_user_card(
        event: Message | CallbackQuery,
        target: User,
        page: int = 1,
        locale: Locale | None = None,
        message_id_to_edit: int | None = None,
) -> None:
    """Отрисовка карточки пользователя (полная версия).

    :param page: страница списка, на которую ведёт «Назад»
    :param locale: локаль юзера из БД (инжектится middleware'ом);
        при отсутствии — fallback на "en"
    :param message_id_to_edit: ID сообщения для in-place перерисовки
        (после ввода скидки); по умолчанию — текущее сообщение
    """
    if locale is None:
        locale = Locale("en")

    text = _build_card_text(target, locale)
    reply_markup = locale.keyboards.get_user_card_kb(user_id=target.id, page=page)

    await UIManager.show(
        event=event,
        text=text,
        reply_markup=reply_markup,
        message_id_to_edit=message_id_to_edit,
    )

    if isinstance(event, CallbackQuery):
        await event.answer()


@user_card_router.callback_query(F.data.startswith("admin_user_card:"))
async def route_user_card(
        callback: CallbackQuery,
        admin_user_service: AdminUserService,
        locale: Locale,
):
    """Открытие карточки пользователя.

    Callback data format: admin_user_card:{user_id}:{page}
    """
    parts = callback.data.split(":")
    try:
        user_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 1
    except (ValueError, IndexError):
        await callback.answer()
        return

    target = await admin_user_service.get_user_card(user_id)
    if not target:
        await callback.answer(
            locale.get_text("admin.users.find_not_found", id=user_id),
            show_alert=True,
        )
        return

    await render_user_card(
        event=callback,
        target=target,
        page=page,
        locale=locale,
    )


# ==================== ВВОД СКИДКИ ====================

@user_card_router.callback_query(F.data.startswith("admin_user_discount:"))
async def route_user_discount(
        callback: CallbackQuery,
        state: FSMContext,
        locale: Locale,
):
    """Запрос скидки для пользователя.

    Callback data format: admin_user_discount:{user_id}:{page}
    """
    parts = callback.data.split(":")
    try:
        user_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 1
    except (ValueError, IndexError):
        await callback.answer()
        return

    await state.set_state(AdminUserState.set_discount)
    await callback.answer()
    prompt_message = await callback.message.answer(
        locale.get_text("admin.users.discount_prompt")
    )
    await state.update_data(
        user_id=user_id,
        page=page,
        menu_message_id=callback.message.message_id,
        prompt_message_id=prompt_message.message_id,
    )


@user_card_router.message(AdminUserState.set_discount, F.text)
async def handle_user_discount_input(
        message: Message,
        state: FSMContext,
        admin_user_service: AdminUserService,
        user: User,
        locale: Locale,
):
    """Обработка ввода скидки: сохранение и перерисовка карточки."""
    data = await state.get_data()
    user_id = data.get("user_id")
    page = data.get("page", 1)
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

    discount, error = validate_discount(message.text, user.language or "en")
    if error:
        err = await message.answer(error)
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    target = await admin_user_service.set_user_discount(user_id, discount)
    if not target:
        err = await message.answer(
            locale.get_text("admin.users.find_not_found", id=user_id)
        )
        asyncio.create_task(self_destruct(message=err, seconds=3))
        return

    success = await message.answer(
        locale.get_text(
            "admin.users.discount_success",
            id=target.id,
            discount=_format_discount(target.discount or 0),
        )
    )
    asyncio.create_task(self_destruct(message=success, seconds=3))

    # Перерисовываем карточку с новым значением скидки (in-place).
    await render_user_card(
        event=message,
        target=target,
        page=page,
        locale=locale,
        message_id_to_edit=menu_message_id,
    )
