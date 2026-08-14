# keyboards/client_inline.py
import logging
from pathlib import Path
from typing import Optional, List, Dict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.base import BaseKeyboardFactory

logger = logging.getLogger(__name__)


class ClientInlineKb(BaseKeyboardFactory):
    """
    Единая фабрика клиентских inline-клавиатур.
    Объединяет функционал вывода каталога, корзины, заказов и оплаты.
    """
    # Определяем приоритетный путь к JSON, проверяя старые имена на случай плавного перехода
    _base_dir = Path(__file__).resolve().parent
    JSON_PATH = _base_dir / "client_kb.json"

    def __init__(self, lang: str = "ru"):
        actual_path = self.JSON_PATH
        if not actual_path.exists():
            for fallback_name in ("kb.json", "user_kb.json"):
                fallback = self._base_dir / fallback_name
                if fallback.exists():
                    actual_path = fallback
                    break

        super().__init__(json_path=actual_path, lang=lang, default_lang="en")

    def get_kb(self, key: str) -> Optional[InlineKeyboardMarkup]:
        """Прямая сборка статической клавиатуры по ключу из JSON."""
        return self.build_from_config(key)

    def get_main_kb(self, orders: int = 0, cart: int = 0) -> Optional[InlineKeyboardMarkup]:
        """Главное меню клиента со счетчиками заказов и корзины."""
        cart_str = f" ({cart})" if cart > 0 else ""
        orders_str = f" ({orders})" if orders > 0 else ""

        format_kwargs = {
            "client_orders": {"orders": orders_str},
            "client_cart": {"cart": cart_str},
        }

        return self.build_from_config("user_main_menu", format_kwargs=format_kwargs)

    def get_orders_kb(self, orders: list) -> Optional[InlineKeyboardMarkup]:
        """Список активных/прошедших заказов пользователя."""
        builder = InlineKeyboardBuilder()

        order_template = self.get_text_by_path(
            "orders_list.buttons.order_template",
            default="Order #{id}"
        )
        back_text = self.get_text_by_path(
            "orders_list.buttons.client_main",
            default="🔙 Back"
        )

        for order in orders:
            date_str = order.created_at.strftime("%d.%m") if hasattr(order, "created_at") else ""
            button_text = order_template.format(
                id=order.id,
                date=date_str,
                price=float(getattr(order, "total_price", 0.0))
            )
            builder.row(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"view_details_order_{order.id}"
                )
            )

        builder.row(
            InlineKeyboardButton(
                text=back_text,
                callback_data="client_main"
            )
        )
        return builder.as_markup()

    def get_shop_keyboard(
        self,
        categories: list,
        products: list,
        current_cat_id: Optional[int],
        parent_id: Optional[int],
        category_names: Optional[Dict[int, str]] = None,
    ) -> Optional[InlineKeyboardMarkup]:
        """Иерархическое меню каталога (Категории + Товары + Навигация назад)."""
        category_names = category_names or {}
        builder = InlineKeyboardBuilder()

        # Категории
        for category in categories:
            cat_text = category_names.get(category.id, getattr(category, "name", ""))
            builder.row(
                InlineKeyboardButton(text=f"{cat_text}", callback_data=f"client_shop_{category.id}")
            )

        # Товары в текущей категории
        for product in products:
            builder.row(
                InlineKeyboardButton(text=f"{product.name}", callback_data=f"client_item_{product.id}")
            )

        # Навигация
        if current_cat_id:
            back_text = self.get_text_by_path("shop_navigation.buttons.back", default="⬅️ Back")
            parent_to_go = parent_id if parent_id else "root"
            builder.row(InlineKeyboardButton(text=back_text, callback_data=f"client_shop_{parent_to_go}"))
        else:
            to_main_text = self.get_text_by_path("shop_navigation.buttons.to_main_menu", default="⬅️ Main Menu")
            builder.row(InlineKeyboardButton(text=to_main_text, callback_data="client_main"))

        return builder.as_markup()

    def get_product_card_kb(
        self,
        product_id: int,
        category_id: Optional[int],
        prev_id: Optional[int],
        next_id: Optional[int],
        cart_item: int = 0,
        manager_url: str = "https://t.me/@el_mex"
    ) -> Optional[InlineKeyboardMarkup]:
        """Карточка конкретного товара с пагинацией (⬅️ ➡️), кнопкой корзины и менеджером."""
        add_to_cart_text = self.get_text_by_path("product_card.buttons.add_to_cart", default="🛒 Add to Cart")
        cart_template = self.get_text_by_path("product_card.buttons.cart_label", default="🧺 Cart{count}")
        manager_text = self.get_text_by_path("product_card.buttons.manager", default="💬 Manager")
        back_text = self.get_text_by_path("product_card.buttons.back", default="⬅️ Back")

        count_str = f" ({cart_item})" if cart_item > 0 else ""
        cart_text = cart_template.format(count=count_str)

        builder = InlineKeyboardBuilder()

        # Ряд: Пагинация и добавление
        nav_row = []
        if prev_id:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"prev_{prev_id}"))

        nav_row.append(InlineKeyboardButton(text=add_to_cart_text, callback_data=f"order_{product_id}", style='success'))

        if next_id:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"next_{next_id}"))

        builder.row(*nav_row)

        # Ряд: Перейти в корзину
        builder.row(InlineKeyboardButton(text=cart_text, callback_data="client_cart", style='primary'))

        # Ряд: Связь с менеджером
        builder.row(InlineKeyboardButton(text=manager_text, url=manager_url))

        # Ряд: Назад к категории
        back_cat = category_id if category_id else "root"
        builder.row(InlineKeyboardButton(text=back_text, callback_data=f"client_shop_{back_cat}"))

        return builder.as_markup()

    def get_cart_kb(self, cart_items: list, has_address: bool) -> Optional[InlineKeyboardMarkup]:
        """Меню корзины с возможностью изменения количества (➕ / ➖) и оформления."""
        set_address_text = self.get_text_by_path("cart_actions.buttons.set_address", default="📍 Set Address")
        set_comment_text = self.get_text_by_path("cart_actions.buttons.set_comment", default="📝 Comment")
        checkout_text = self.get_text_by_path("cart_actions.buttons.checkout", default="✅ Checkout")
        back_text = self.get_text_by_path("cart_actions.buttons.back", default="⬅️ Back")

        builder = InlineKeyboardBuilder()

        # Позиции корзины
        for item in cart_items:
            product_name = item.product.name if getattr(item, "product", None) else "Product"
            builder.row(
                InlineKeyboardButton(text=product_name, callback_data=f"item_{item.product_id}"),
                InlineKeyboardButton(text="➖", callback_data=f"dec_{item.product_id}", style="danger"),
                InlineKeyboardButton(text="➕", callback_data=f"inc_{item.product_id}", style="success")
            )

        # Кнопки ввода данных
        builder.row(
            InlineKeyboardButton(text=set_address_text, callback_data="set_address"),
            InlineKeyboardButton(text=set_comment_text, callback_data="set_comment")
        )

        # Оформление доступно только при указанном адресе
        if has_address:
            builder.row(InlineKeyboardButton(text=checkout_text, callback_data="checkout_confirm", style="success"))

        builder.row(InlineKeyboardButton(text=back_text, callback_data="client_main"))

        return builder.as_markup()

    def get_order_payment_request_kb(self, order_id: int) -> InlineKeyboardMarkup:
        """Выбор способа оплаты конкретного заказа (перенесено из user_inline.py)."""
        builder = InlineKeyboardBuilder()

        cash_text = self.get_text_by_path(
            "order_payment_request.buttons.cash",
            default="💵 Наличными (курьеру)"
        )
        paid_text = self.get_text_by_path(
            "order_payment_request.buttons.paid",
            default="✅ Я оплатил"
        )

        builder.button(text=cash_text, callback_data=f"user_pay_cash:{order_id}")
        builder.button(text=paid_text, callback_data=f"user_pay_confirm:{order_id}", style='success')

        builder.adjust(1)
        return builder.as_markup()

    def get_language_keyboard(self) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура выбора языка (динамически строится из JSON)."""
        return self.build_from_config("language_selection")