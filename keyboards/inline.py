# keyboards/inline.py
import json
import logging
from pathlib import Path
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


def get_language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Русский 🇷🇺", callback_data="lang_ru")
    builder.button(text="English 🇺🇸", callback_data="lang_en")
    builder.button(text="Español 🇪🇸", callback_data="lang_es")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Редактировать Магазин", callback_data="admin_shop")
    builder.button(text="Склад", callback_data="admin_warehouse")
    builder.button(text="👥 Юзеры", callback_data="admin_users")
    builder.button(text="Работники", callback_data="admin_workers")
    builder.button(text="Рассылка", callback_data="admin_alert")
    builder.button(text="Статистика", callback_data="admin_stat")
    builder.adjust(1)
    return builder.as_markup()


class InlineKb:
    locale_path = Path(__file__).resolve().parent / "kb.json"

    def __init__(self, lang: str = 'en'):
        self.lang = lang
        self.template = self._load_json()

    def _load_json(self):
        try:
            with open(self.locale_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return data
        except Exception as e:
            logger.critical(f"Failed to open/parse {self.locale_path}: {e}", exc_info=True)
            return None

    def get_main_kb(self, orders: int, cart: int) -> Optional[InlineKeyboardMarkup]:
        if self.template is None:
            logger.critical("[INLINE KB] Keyboards template is missing (kb.json was not loaded)!")
            return None

        data = self.template.get("user_main_menu")
        if data is None:
            logger.critical("[INLINE KB] Keyboard with key 'user_main_menu' not found in kb.json!")
            return None

        buttons = data.get("buttons")
        sizes = data.get("sizes")

        if not buttons or not sizes:
            logger.critical("[INLINE KB] Invalid structure (missing 'buttons' or 'sizes') for key 'user_main_menu'!")
            return None

        cart_str = f" ({cart})" if cart > 0 else ""
        orders_str = f" ({orders})" if orders > 0 else ""

        builder = InlineKeyboardBuilder()

        for callback_data, translations in buttons.items():
            button_text_template = translations.get(self.lang) or translations.get("en") or "XXX"

            if not translations.get(self.lang):
                logger.warning(f"[INLINE KB] Missing translation for lang '{self.lang}' in button '{callback_data}'")

            try:
                button_text = button_text_template.format(orders=orders_str, cart=cart_str)
            except (KeyError, IndexError) as e:
                logger.error(f"[INLINE KB] Failed to format button '{callback_data}': {e}")
                button_text = button_text_template

            builder.button(text=button_text, callback_data=callback_data)

        builder.adjust(*sizes)

        return builder.as_markup()

    def get_kb(self, key: str) -> Optional[InlineKeyboardMarkup]:
        if self.template is None:
            logger.critical("[INLINE KB] Keyboards template is missing (kb.json was not loaded)!")
            return None

        data = self.template.get(key)
        if data is None:
            logger.critical(f"[INLINE KB] Keyboard with key '{key}' not found in kb.json!")
            return None

        buttons = data.get("buttons")
        sizes = data.get("sizes")

        if not buttons or not sizes:
            logger.critical(f"[INLINE KB] Invalid structure (missing 'buttons' or 'sizes') for key '{key}'!")
            return None

        builder = InlineKeyboardBuilder()

        for callback_data, translations in buttons.items():
            button_text = translations.get(self.lang) or translations.get("en") or "XXX"

            if not translations.get(self.lang):
                logger.warning(f"[INLINE KB] Missing translation for lang '{self.lang}' in button '{callback_data}'")

            builder.button(text=button_text, callback_data=callback_data)

        builder.adjust(*sizes)

        return builder.as_markup()

    def get_orders_kb(self, orders: list) -> Optional[InlineKeyboardMarkup]:
        if self.template is None:
            logger.critical("[INLINE KB] Keyboards template is missing (kb.json was not loaded)!")
            return None

        data = self.template.get("orders_list")
        if data is None:
            logger.critical("[INLINE KB] Keyboard with key 'orders_list' not found in kb.json!")
            return None

        buttons = data.get("buttons")
        if not buttons:
            logger.critical("[INLINE KB] Missing 'buttons' for key 'orders_list'!")
            return None

        back_btn_translations = buttons.get("client_main", {})
        back_text = back_btn_translations.get(self.lang) or back_btn_translations.get("en") or "🔙 Back"

        order_btn_translations = buttons.get("order_template", {})
        order_template = order_btn_translations.get(self.lang) or order_btn_translations.get("en") or "Order #{id}"

        builder = InlineKeyboardBuilder()

        for order in orders:
            date_str = order.created_at.strftime("%d.%m")
            button_text = order_template.format(
                id=order.id,
                date=date_str,
                price=float(order.total_price)
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
            current_cat_id: int | None,
            parent_id: int | None,
            category_names: dict[int, str] | None = None,
    ) -> Optional[InlineKeyboardMarkup]:
        if self.template is None:
            logger.critical("[INLINE KB] Keyboards template is missing!")
            return None

        nav_data = self.template.get("shop_navigation")
        if not nav_data:
            logger.critical("[INLINE KB] 'shop_navigation' not found in kb.json!")
            return None

        nav_buttons = nav_data.get("buttons", {})

        back_data = nav_buttons.get("back", {})
        to_main_data = nav_buttons.get("to_main_menu", {})

        back_text = back_data.get(self.lang) or back_data.get("en") or "⬅️ Back"
        to_main_text = to_main_data.get(self.lang) or to_main_data.get("en") or "⬅️ Main Menu"

        category_names = category_names or {}
        builder = InlineKeyboardBuilder()

        for category in categories:
            cat_text = category_names.get(category.id, category.name)
            builder.row(
                InlineKeyboardButton(text=f"{cat_text}", callback_data=f"client_shop_{category.id}")
            )

        for product in products:
            builder.row(
                InlineKeyboardButton(text=f"{product.name}", callback_data=f"client_item_{product.id}")
            )

        if current_cat_id:
            parent_to_go = parent_id if parent_id else "root"
            builder.row(InlineKeyboardButton(text=back_text, callback_data=f"client_shop_{parent_to_go}"))
        else:
            builder.row(InlineKeyboardButton(text=to_main_text, callback_data="client_main"))

        return builder.as_markup()

    def get_product_card_kb(
            self,
            product_id: int,
            category_id: int | None,
            prev_id: int | None,
            next_id: int | None,
            cart_item: int = 0,
            manager_url: str = "https://t.me/@el_mex"
    ) -> Optional[InlineKeyboardMarkup]:
        if self.template is None:
            return None

        data = self.template.get("product_card")
        if not data:
            logger.critical("[INLINE KB] 'product_card' configuration not found in kb.json!")
            return None

        buttons_cfg = data.get("buttons", {})

        add_to_cart_text = buttons_cfg.get("add_to_cart", {}).get(self.lang) or "🛒 Add to Cart"
        cart_template = buttons_cfg.get("cart_label", {}).get(self.lang) or "🧺 Cart{count}"
        manager_text = buttons_cfg.get("manager", {}).get(self.lang) or "💬 Manager"
        back_text = buttons_cfg.get("back", {}).get(self.lang) or "⬅️ Back"

        count_str = f" ({cart_item})" if cart_item > 0 else ""
        cart_text = cart_template.format(count=count_str)

        builder = InlineKeyboardBuilder()

        nav_row = []
        if prev_id:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"prev_{prev_id}"))

        nav_row.append(InlineKeyboardButton(text=add_to_cart_text, callback_data=f"order_{product_id}", style='success'))

        if next_id:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"next_{next_id}"))

        builder.row(*nav_row)

        builder.row(InlineKeyboardButton(text=cart_text, callback_data="client_cart", style="primary"))

        builder.row(InlineKeyboardButton(text=manager_text, url=manager_url))

        back_cat = category_id if category_id else "root"
        builder.row(InlineKeyboardButton(text=back_text, callback_data=f"client_shop_{back_cat}"))

        return builder.as_markup()

    def get_cart_kb(self, cart_items: list, has_address: bool) -> Optional[InlineKeyboardMarkup]:
        if self.template is None:
            return None

        cfg = self.template.get("cart_actions")
        if not cfg:
            logger.critical("[INLINE KB] 'cart_actions' configuration not found in kb.json!")
            return None

        buttons_cfg = cfg.get("buttons", {})

        set_address_text = buttons_cfg.get("set_address", {}).get(self.lang) or "📍 Set Address"
        set_comment_text = buttons_cfg.get("set_comment", {}).get(self.lang) or "📝 Comment"
        checkout_text = buttons_cfg.get("checkout", {}).get(self.lang) or "✅ Checkout"
        back_text = buttons_cfg.get("back", {}).get(self.lang) or "⬅️ Back"

        builder = InlineKeyboardBuilder()

        for item in cart_items:
            product_name = item.product.name if item.product else "Deleted Product"
            builder.row(
                InlineKeyboardButton(text=product_name, callback_data=f"item_{item.product_id}"),
                InlineKeyboardButton(text="➖", callback_data=f"dec_{item.product_id}", style='danger'),
                InlineKeyboardButton(text="➕", callback_data=f"inc_{item.product_id}", style='success')
            )

        builder.row(
            InlineKeyboardButton(text=set_address_text, callback_data="set_address"),
            InlineKeyboardButton(text=set_comment_text, callback_data="set_comment")
        )

        if has_address:
            builder.row(InlineKeyboardButton(text=checkout_text, callback_data="checkout_confirm"))

        builder.row(InlineKeyboardButton(text=back_text, callback_data="client_main"))

        return builder.as_markup()