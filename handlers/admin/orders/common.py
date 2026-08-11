import logging
from typing import Optional, Any

from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from src.core.ui import UIManager

logger = logging.getLogger(__name__)


async def render_order_detail(
        event: CallbackQuery | Message,
        admin_repo: AdminRepository,
        user: User,
        order_id: int,
        status: str = "all",
        page: int = 1,
        message_id_to_edit: int | None = None,
):
    """
    Универсальная функция рендера карточки заказа с подгрузкой локализованного
    шаблона из admin_kb.json и сборкой клавиатуры.
    """
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        text_not_found = kb.get_text("admin_order_messages.not_found", "❌ <b>Заказ не найден.</b>")
        await UIManager.show(
            event=event,
            text=text_not_found,
            reply_markup=kb.get_cancel_add_category_kb(f"admin_orders_page:{status}:{page}"),
            message_id_to_edit=message_id_to_edit,
        )
        return

    # 1. Информация о покупателе
    buyer_info = "Неизвестен"
    if order.user:
        u_id = order.user.id
        u_name = getattr(order.user, "username", None)

        if u_name:
            buyer_info = f'<a href="https://t.me/{u_name}">@{u_name}</a> (ID: <code>{u_id}</code>)'
        else:
            buyer_info = f'<a href="tg://user?id={u_id}">Пользователь {u_id}</a> (ID: <code>{u_id}</code>)'

    # 2. Состав заказа (из модели OrderItem)
    items_text = []
    if order.items:
        for idx, item in enumerate(order.items, start=1):
            prod_name = item.product.name if item.product else f"Товар #{item.product_id}"
            unit = getattr(item.product, "unit", "шт.") if item.product else "шт."
            price = float(item.price_at_purchase)
            qty = item.quantity
            item_sum = qty * price

            items_text.append(
                f"{idx}. <b>{prod_name}</b>\n"
                f"   └ {qty} {unit} x {price:.2f} $ = <b>{item_sum:.2f} $</b>"
            )
    else:
        no_items_str = kb.get_text("admin_order_messages.no_items", "<i>Список товаров пуст.</i>")
        items_text.append(no_items_str)

    items_block = "\n".join(items_text)

    # 3. Подготовка текста полей (из модели Order)
    no_addr_str = kb.get_text("admin_order_messages.no_address", "<i>Не указан</i>")
    no_comment_str = kb.get_text("admin_order_messages.no_comment", "<i>Отсутствует</i>")
    no_proof_str = kb.get_text("admin_order_messages.no_payment_proof", "<i>Не предоставлено</i>")

    delivery_price = float(order.delivery_price) if order.delivery_price else 0.0
    total_price = float(order.total_price) if order.total_price else 0.0
    delivery_address = order.delivery_address or no_addr_str
    user_comment = order.user_comment or no_comment_str
    manager_comment = order.manager_comment or no_comment_str
    created_at_str = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "—"
    paid_status_str = "✅ Оплачен" if getattr(order, "is_paid", False) else "❌ Не оплачен"

    # Формирование информации о подтверждении оплаты
    if order.payment_proof_type == "photo":
        payment_proof_info = f"📸 Чек (фото ID: <code>{order.payment_proof}</code>)"
    elif order.payment_proof_type == "tx_hash":
        payment_proof_info = f"🔗 Хэш транзакции: <code>{order.payment_proof}</code>"
    elif order.payment_proof:
        payment_proof_info = f"<code>{order.payment_proof}</code>"
    else:
        payment_proof_info = no_proof_str

    # 4. Формирование основного текста карточки
    card_template = kb.get_text(
        "admin_order_messages.detail_card",
        "📦 <b>Заказ #{order_id}</b>\n"
        "📅 <b>Дата:</b> {created_at}\n"
        "Статус: <b>{status}</b> ({is_paid_status})\n\n"
        "👤 <b>Покупатель:</b> {buyer_info}\n"
        "📍 <b>Адрес доставки:</b> {delivery_address}\n"
        "🚚 <b>Стоимость доставки:</b> {delivery_price} $\n\n"
        "🛒 <b>Состав заказа:</b>\n{items_block}\n\n"
        "💬 <b>Комментарий пользователя:</b>\n{user_comment}\n\n"
        "💰 <b>Итого к оплате:</b> <b>{total_price} $</b>\n"
        "💳 <b>Подтверждение оплаты:</b> {payment_proof_info}\n\n"
        "💬 <b>Комментарий менеджера:</b>\n{manager_comment}"
    )

    text = card_template.format(
        order_id=order.id,
        created_at=created_at_str,
        status=order.status,
        is_paid_status=paid_status_str,
        buyer_info=buyer_info,
        delivery_address=delivery_address,
        delivery_price=f"{delivery_price:.2f}",
        items_block=items_block,
        user_comment=user_comment,
        total_price=f"{total_price:.2f}",
        payment_proof_info=payment_proof_info,
        manager_comment=manager_comment,
    )

    # 5. Генерация клавиатуры
    reply_markup = kb.get_order_detail_kb(
        order=order,
        status=status,
        page=page,
    )

    await UIManager.show(
        event=event,
        text=text,
        reply_markup=reply_markup,
        message_id_to_edit=message_id_to_edit,
    )


async def build_order_detail_text(
    admin_repo: AdminRepository,
    order_id: int,
    lang: str = "ru",
) -> tuple[str, Optional[Any]]:
    """Формирует текстовое описание заказа для администратора."""
    kb = AdminInlineKb(lang=lang)
    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        return "", None

    # 1. Покупатель
    buyer_info = "Неизвестен"
    if order.user:
        u_id = order.user.id
        u_name = getattr(order.user, "username", None)
        if u_name:
            buyer_info = f'<a href="https://t.me/{u_name}">@{u_name}</a> (ID: <code>{u_id}</code>)'
        else:
            buyer_info = f'<a href="tg://user?id={u_id}">Пользователь {u_id}</a> (ID: <code>{u_id}</code>)'

    # 2. Состав заказа
    items_text = []
    if order.items:
        for idx, item in enumerate(order.items, start=1):
            prod_name = item.product.name if item.product else f"Товар #{item.product_id}"
            unit = getattr(item.product, "unit", "шт.") if item.product else "шт."
            price = float(item.price_at_purchase)
            qty = item.quantity
            item_sum = qty * price
            items_text.append(
                f"{idx}. <b>{prod_name}</b>\n"
                f"   └ {qty} {unit} x {price:.2f} $ = <b>{item_sum:.2f} $</b>"
            )
    else:
        no_items_str = kb.get_text("admin_order_messages.no_items", "<i>Список товаров пуст.</i>")
        items_text.append(no_items_str)

    items_block = "\n".join(items_text)

    # 3. Поля заказа
    no_addr_str = kb.get_text("admin_order_messages.no_address", "<i>Не указан</i>")
    no_comment_str = kb.get_text("admin_order_messages.no_comment", "<i>Отсутствует</i>")
    no_proof_str = kb.get_text("admin_order_messages.no_payment_proof", "<i>Не предоставлено</i>")

    delivery_price = float(order.delivery_price) if order.delivery_price else 0.0
    total_price = float(order.total_price) if order.total_price else 0.0
    delivery_address = order.delivery_address or no_addr_str
    user_comment = order.user_comment or no_comment_str
    manager_comment = order.manager_comment or no_comment_str
    created_at_str = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "—"
    paid_status_str = "✅ Оплачен" if getattr(order, "is_paid", False) else "❌ Не оплачен"

    if order.payment_proof_type == "photo":
        payment_proof_info = f"📸 Чек (фото)"
    elif order.payment_proof_type == "document":
        payment_proof_info = f"📄 Чек (документ)"
    elif order.payment_proof_type == "tx_hash":
        payment_proof_info = f"🔗 Хэш: <code>{order.payment_proof}</code>"
    elif order.payment_proof:
        payment_proof_info = f"<code>{order.payment_proof}</code>"
    else:
        payment_proof_info = no_proof_str

    card_template = kb.get_text(
        "admin_order_messages.detail_card",
        "📦 <b>Заказ #{order_id}</b>\n"
        "📅 <b>Дата:</b> {created_at}\n"
        "Статус: <b>{status}</b> ({is_paid_status})\n\n"
        "👤 <b>Покупатель:</b> {buyer_info}\n"
        "📍 <b>Адрес доставки:</b> {delivery_address}\n"
        "🚚 <b>Стоимость доставки:</b> {delivery_price} $\n\n"
        "🛒 <b>Состав заказа:</b>\n{items_block}\n\n"
        "💬 <b>Комментарий пользователя:</b>\n{user_comment}\n\n"
        "💰 <b>Итого к оплате:</b> <b>{total_price} $</b>\n"
        "💳 <b>Подтверждение оплаты:</b> {payment_proof_info}\n\n"
        "💬 <b>Комментарий менеджера:</b>\n{manager_comment}"
    )

    text = card_template.format(
        order_id=order.id,
        created_at=created_at_str,
        status=order.status,
        is_paid_status=paid_status_str,
        buyer_info=buyer_info,
        delivery_address=delivery_address,
        delivery_price=f"{delivery_price:.2f}",
        items_block=items_block,
        user_comment=user_comment,
        total_price=f"{total_price:.2f}",
        payment_proof_info=payment_proof_info,
        manager_comment=manager_comment,
    )

    return text, order