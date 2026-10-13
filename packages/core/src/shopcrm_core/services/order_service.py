"""Сервисы заказов: общая бизнес-логика оформления заказов."""
import asyncio
from typing import Any, Optional

from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_core.locales.locale import Locale
from shopcrm_core.utils import format_price

# Длина разделителя блоков в карточке заказа: длинный — для обычного сообщения,
# короткий — для caption под фото (колонка caption уже, длинная линия переносится).
_SEPARATOR_LONG = "━" * 20
_SEPARATOR_SHORT = "━" * 12


def _order_product_ids(order) -> list[int]:
    """Уникальные ID товаров из позиций заказа (без дублей и None)."""
    seen: list[int] = []
    for item in getattr(order, "items", []) or []:
        pid = getattr(item, "product_id", None)
        if pid is not None and pid not in seen:
            seen.append(pid)
    return seen


async def get_user_order_product_names(
    user_repo: UserRepository,
    order,
    lang: str,
) -> dict[int, str]:
    """Локализованные названия товаров заказа (entity_type='product_name').

    Возвращает словарь product_id -> название только для тех товаров,
    для которых есть запись в локальном хранилище. Для остальных
    вызывающий код использует fallback на product.name.
    """
    product_ids = _order_product_ids(order)
    if not product_ids:
        return {}
    results = await asyncio.gather(
        *[
            user_repo.get_locale_text(
                entity_type="product_name",
                entity_id=pid,
                lang_code=lang,
            )
            for pid in product_ids
        ]
    )
    return {pid: loc for pid, loc in zip(product_ids, results) if loc}


async def get_admin_order_product_names(
    admin_repo: AdminRepository,
    order,
    lang: str,
) -> dict[int, str]:
    """Локализованные названия товаров заказа для админ-экранов (production-таблицы)."""
    product_ids = _order_product_ids(order)
    if not product_ids:
        return {}
    results = await asyncio.gather(
        *[
            admin_repo.get_locale_text(
                entity_id=pid,
                entity_type="product_name",
                language_code=lang,
                use_temp=False,
            )
            for pid in product_ids
        ]
    )
    return {pid: loc for pid, loc in zip(product_ids, results) if loc}


async def build_order_detail_text(
    admin_repo: AdminRepository,
    order_id: int,
    lang: str = "en",
) -> tuple[str, Optional[Any]]:
    """Формирует текстовое описание заказа для администратора."""
    locale = Locale(lang)
    order = await admin_repo.get_order_by_id(order_id)
    if not order:
        return "", None

    # 1. Покупатель
    buyer_info = locale.get_text("admin.orders.buyer_unknown")
    if order.user:
        u_id = order.user.id
        u_name = getattr(order.user, "username", None)
        if u_name:
            buyer_info = locale.get_text("admin.orders.buyer_name", username=u_name, user_id=u_id)
        else:
            buyer_info = locale.get_text("admin.orders.buyer_id", user_id=u_id)

    # 2. Состав заказа
    product_names = await get_admin_order_product_names(admin_repo, order, lang)
    items_text = []
    items_price = 0
    if order.items:
        for idx, item in enumerate(order.items, start=1):
            if item.product:
                prod_name = product_names.get(item.product_id) or item.product.name
            else:
                prod_name = locale.get_text("admin.orders.deleted_product", product_id=item.product_id)
            unit = locale.get_unit(getattr(item.product, "unit", None)) if item.product else locale.get_text("admin.orders.unit_default")
            price = item.price_at_purchase
            qty = item.quantity
            item_sum = qty * price
            items_price += item_sum
            items_text.append(
                locale.get_text(
                    "admin.orders.item_line",
                    idx=idx, name=prod_name, qty=qty, unit=unit,
                    price=format_price(price), currency=locale.get_currency_symbol(), sum=format_price(item_sum),
                )
            )
    else:
        no_items_str = locale.get_text("admin.orders.no_items")
        items_text.append(no_items_str)

    items_block = "\n".join(items_text)

    # 3. Поля заказа
    no_addr_str = locale.get_text("admin.orders.no_address")
    no_comment_str = locale.get_text("admin.orders.no_comment")
    no_proof_str = locale.get_text("admin.orders.no_payment_proof")

    delivery_price = order.delivery_price if order.delivery_price else 0
    total_price = order.total_price if order.total_price else 0
    delivery_address = locale.format_address(order.delivery_address, order.delivery_address_type) or no_addr_str
    user_comment = order.user_comment or no_comment_str
    manager_comment = order.manager_comment or no_comment_str
    created_at_str = order.created_at.strftime("%d.%m.%Y %H:%M") if order.created_at else "—"
    paid_status_str = locale.get_text("admin.orders.paid_yes") if getattr(order, "is_paid", False) else locale.get_text("admin.orders.paid_no")

    if order.payment_proof_type == "photo":
        payment_proof_info = locale.get_text("admin.orders.proof_photo")
    elif order.payment_proof_type == "cash":
        payment_proof_info = locale.get_text("admin.orders.proof_cash")
    elif order.payment_proof_type == "document":
        payment_proof_info = locale.get_text("admin.orders.proof_document")
    elif order.payment_proof_type == "tx_hash":
        payment_proof_info = locale.get_text("admin.orders.proof_tx", proof=order.payment_proof)
    elif order.payment_proof:
        payment_proof_info = locale.get_text("admin.orders.proof_code", proof=order.payment_proof)
    else:
        payment_proof_info = no_proof_str

    # caption под фото уже обычного сообщения → короче разделитель, чтобы линия не переносилась
    separator = _SEPARATOR_SHORT if order.payment_proof_type == "photo" else _SEPARATOR_LONG

    card_template = locale.get_text("admin.orders.detail_card")

    text = card_template.format(
        order_id=order.id,
        created_at=created_at_str,
        status=order.status,
        is_paid_status=paid_status_str,
        buyer_info=buyer_info,
        delivery_address=delivery_address,
        items_block=items_block,
        user_comment=user_comment,
        items_price=format_price(items_price),
        delivery_price=format_price(delivery_price),
        total_price=format_price(total_price),
        currency=locale.get_currency_symbol(),
        payment_proof_info=payment_proof_info,
        manager_comment=manager_comment,
        separator=separator,
    )

    return text, order
