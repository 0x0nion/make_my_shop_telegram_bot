"""Сервисы заказов: общая бизнес-логика оформления заказов."""
from typing import Any, Optional

from shopcrm_core.db.repositories.admin_repo import AdminRepository
from shopcrm_core.locales.locale import Locale


async def build_order_detail_text(
    admin_repo: AdminRepository,
    order_id: int,
    lang: str = "ru",
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
    items_text = []
    items_price = 0.0
    if order.items:
        for idx, item in enumerate(order.items, start=1):
            prod_name = item.product.name if item.product else locale.get_text("admin.orders.deleted_product", product_id=item.product_id)
            unit = locale.get_unit(getattr(item.product, "unit", None)) if item.product else locale.get_text("admin.orders.unit_default")
            price = float(item.price_at_purchase)
            qty = item.quantity
            item_sum = qty * price
            items_price += item_sum
            items_text.append(
                locale.get_text(
                    "admin.orders.item_line",
                    idx=idx, name=prod_name, qty=qty, unit=unit,
                    price=price, currency=locale.get_currency_symbol(), sum=item_sum,
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

    delivery_price = float(order.delivery_price) if order.delivery_price else 0.0
    total_price = float(order.total_price) if order.total_price else 0.0
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
        items_price=f"{items_price:.2f}",
        delivery_price=f"{delivery_price:.2f}",
        total_price=f"{total_price:.2f}",
        currency=locale.get_currency_symbol(),
        payment_proof_info=payment_proof_info,
        manager_comment=manager_comment,
    )

    return text, order
