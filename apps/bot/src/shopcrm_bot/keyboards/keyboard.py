# keyboards/keyboard.py
import logging
from typing import Any, Dict, List, Optional, Union

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shopcrm_core.locales.utils import SafeDict
from shopcrm_core.constants import OrderStatus

logger = logging.getLogger(__name__)


class KeyboardFactory:
    """Единый генератор Inline-клавиатур для single-message системы.

    Все статические шаблоны читаются из locales/locale.json,
    динамические клавиатуры собираются из них + данных приложения.
    """

    def __init__(self, locale):
        self.locale = locale

    def get_button_text(
            self,
            path_or_value: Any,
            btn_key: Optional[Union[str, List[str]]] = None,
            default: str = "XXX",
            **kwargs
    ) -> Union[str, Dict[str, str]]:
        """Универсальный извлекатель локализованных текстов.

        Варианты использования:
        1. Один ключ:  get_button_text("admin.orders_menu", "back") -> "⬅️ Назад"
        2. Список:     get_button_text("admin.catalog_navigation", ["back", "save_changes"]) -> dict
        3. Напрямую:   get_button_text({"ru": "Кнопка", "en": "Button"}) -> "Кнопка"
        """
        lang = getattr(self.locale, "lang", "ru")

        # 1. Если передали готовое значение кнопки (dict или str-ключ напрямую)
        if btn_key is None:
            if not path_or_value:
                return default

            if isinstance(path_or_value, dict):
                translations = {
                    k: v for k, v in path_or_value.items()
                    if k not in ("callback_data", "url", "symbol") and isinstance(v, str)
                }
                raw_text = (
                        translations.get(lang)
                        or translations.get("en")
                        or next(iter(translations.values()), default)
                )
            else:
                path_str = str(path_or_value)
                if self.locale.has_text(path_str):
                    translated = self.locale.get_text(path_str, **kwargs)
                    raw_text = translated if translated != "XXX" else path_str
                else:
                    raw_text = path_str

            if kwargs and isinstance(raw_text, str):
                try:
                    return raw_text.format_map(SafeDict(kwargs))
                except Exception as e:
                    logger.error(f"[KEYBOARDS] Error formatting text '{raw_text}': {e}")
                    return raw_text

            return str(raw_text)

        # 2. Если передали path в locale.json и ключ(и) кнопок
        kb_data = self.locale.get_keyboard_data(str(path_or_value))
        buttons_dict = kb_data.get("buttons", {}) if isinstance(kb_data, dict) else {}

        # Если btn_key — список ключей -> возвращаем dict {key: text}
        if isinstance(btn_key, list):
            return {
                key: self.get_button_text(buttons_dict.get(key), default=default, **kwargs)
                for key in btn_key
            }

        # Если btn_key — одиночная строка
        btn_val = buttons_dict.get(btn_key)
        if btn_val is not None:
            return self.get_button_text(btn_val, default=default, **kwargs)

        return default

    def get_inline(
            self,
            path: str,
            callbacks: Optional[Dict[str, str]] = None,
            exclude: Optional[List[str]] = None,
            **kwargs
    ) -> InlineKeyboardMarkup:
        """Собирает Inline-клавиатуру по пути в locale.json."""
        kb_data = self.locale.get_keyboard_data(path)
        builder = InlineKeyboardBuilder()

        if not isinstance(kb_data, dict):
            logger.error(f"[KEYBOARDS] Structure at path '{path}' must be a dict.")
            return builder.as_markup()

        buttons_dict: Dict[str, Any] = kb_data.get("buttons", {})
        sizes: List[int] = kb_data.get("sizes", [])
        callbacks_map = callbacks or {}

        exclude_set = set(exclude or [])
        buttons: List[InlineKeyboardButton] = []
        for btn_key, btn_value in buttons_dict.items():
            if btn_key in exclude_set:
                continue
            if isinstance(btn_value, dict):
                callback_data = btn_value.get("callback_data", btn_key)
                url = btn_value.get("url")
            else:
                callback_data = btn_key
                url = None

            # Вызываем единый get_button_text напрямую
            btn_text = self.get_button_text(btn_value, **kwargs)

            if btn_key in callbacks_map:
                callback_data = callbacks_map[btn_key]

            if kwargs and callback_data:
                try:
                    callback_data = callback_data.format_map(SafeDict(kwargs))
                except Exception as e:
                    logger.error(f"[KEYBOARDS] Error formatting callback '{callback_data}': {e}")

            buttons.append(
                InlineKeyboardButton(text=btn_text, callback_data=callback_data, url=url)
            )

        if buttons:
            if sizes:
                builder.add(*buttons)
                builder.adjust(*sizes)
            else:
                for btn in buttons:
                    builder.row(btn)

        return builder.as_markup()

    def build(
            self,
            path: str,
            callbacks: Optional[Dict[str, str]] = None,
            exclude: Optional[List[str]] = None,
            **kwargs
    ) -> InlineKeyboardMarkup:
        """Универсальный alias-метод для быстрой сборки клавиатуры."""
        return self.get_inline(path=path, callbacks=callbacks, exclude=exclude, **kwargs)

    def get_kb(self, key: str, callbacks: Optional[Dict[str, str]] = None, **kwargs):
        """Прямая сборка статической клиентской клавиатуры по ключу (legacy-совместимый API).

        Ключи соответствуют разделу keyboards.client в locale.json
        (перенесено из kb.json): get_kb("cancel") -> keyboards.client.cancel.
        """
        return self.build(f"client.{key}", callbacks=callbacks, **kwargs)

    def get_cancel_kb(
            self,
            back_callback: str,
            path: str = "base.action",
            btn_key: str = "cancel"
    ) -> InlineKeyboardMarkup:
        """Универсальная клавиатура отмены/возврата с кастомным callback_data."""
        cancel_text = self.get_button_text(path, btn_key, default="📥 Cancel")

        builder = InlineKeyboardBuilder()
        builder.button(text=cancel_text, callback_data=back_callback)
        return builder.as_markup()

    def get_back_kb(self, back_callback: str) -> InlineKeyboardMarkup:
        """Универсальная клавиатура «⬅️ Назад» с кастомным callback_data."""
        back_text = self.get_button_text("base.back", default="⬅️ Back")

        builder = InlineKeyboardBuilder()
        builder.button(text=back_text, callback_data=back_callback)
        return builder.as_markup()

    # ==================================================================
    # Клиентские динамические клавиатуры
    # ==================================================================

    def get_main_kb(self, orders: int = 0, cart: int = 0) -> InlineKeyboardMarkup:
        """Главное меню клиента со счетчиками заказов и корзины."""
        cart_str = f" ({cart})" if cart > 0 else ""
        orders_str = f" ({orders})" if orders > 0 else ""

        return self.build(
            "client.user_main_menu",
            callbacks={"client_orders": "client_orders", "client_cart": "client_cart"},
            orders=orders_str,
            cart=cart_str,
        )

    def get_orders_kb(
        self,
        orders: list,
        page: int = 1,
        total_pages: int = 1,
    ) -> InlineKeyboardMarkup:
        """Список всех заказов пользователя с круговой пагинацией."""
        builder = InlineKeyboardBuilder()

        order_template = self.get_button_text(
            "client.orders_list", "order_template", default="Order #{id}"
        )
        back_text = self.get_button_text(
            "client.orders_list", "client_main", default="🔙 Back"
        )

        for order in orders:
            date_str = (
                order.created_at.strftime("%d.%m")
                if getattr(order, "created_at", None) is not None
                else ""
            )
            button_text = self.get_button_text(
                order_template,
                id=order.id,
                date=date_str,
                price=float(getattr(order, "total_price", 0.0)),
                currency=self.locale.get_currency_symbol(),
            )
            builder.row(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"view_details_order_{order.id}",
                )
            )

        # Блок круговой пагинации (как в админ-списке заказов)
        if orders and total_pages > 1:
            prev_page = total_pages if page == 1 else page - 1
            next_page = 1 if page == total_pages else page + 1

            builder.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"client_orders_page:{prev_page}",
                ),
                InlineKeyboardButton(
                    text=f"{page}/{total_pages}",
                    callback_data="noop",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"client_orders_page:{next_page}",
                ),
            )

        builder.row(
            InlineKeyboardButton(text=back_text, callback_data="client_main")
        )
        return builder.as_markup()

    def get_client_order_detail_kb(self, order_id: int, cancellable: bool) -> InlineKeyboardMarkup:
        """Клавиатура карточки заказа клиента: условная отмена + возврат к списку."""
        builder = InlineKeyboardBuilder()

        if cancellable:
            cancel_text = self.get_button_text(
                "client.order_detail", "cancel_order", default="❌ Cancel Order"
            )
            builder.row(
                InlineKeyboardButton(
                    text=cancel_text,
                    callback_data=f"client_order_cancel:{order_id}",
                )
            )

        back_text = self.get_button_text(
            "client.back_to_orders", "client_orders", default="🔙 Back to list"
        )
        builder.row(
            InlineKeyboardButton(text=back_text, callback_data="client_orders")
        )
        return builder.as_markup()

    def get_shop_keyboard(
            self,
            categories: list,
            products: list,
            current_cat_id: Optional[int],
            parent_id: Optional[int],
            category_names: Optional[Dict[int, str]] = None,
    ) -> InlineKeyboardMarkup:
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
            price = float(getattr(product, "price", 0.0) or 0.0)
            currency = self.locale.get_currency_symbol(getattr(product, "currency", None))
            btn_text = self.get_button_text(
                "client.shop_navigation",
                "product_button",
                default="{name} — {price:.2f} {currency}",
                name=product.name,
                price=price,
                currency=currency,
            )
            builder.row(
                InlineKeyboardButton(text=btn_text, callback_data=f"client_item_{product.id}")
            )

        # Навигация
        nav = self.get_button_text(
            "client.shop_navigation", ["back", "to_main_menu"], default="⬅️ Back"
        )
        if current_cat_id:
            parent_to_go = parent_id if parent_id else "root"
            builder.row(
                InlineKeyboardButton(text=nav["back"], callback_data=f"client_shop_{parent_to_go}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text=nav["to_main_menu"], callback_data="client_main")
            )

        return builder.as_markup()

    def get_product_card_kb(
            self,
            product_id: int,
            category_id: Optional[int],
            prev_id: Optional[int],
            next_id: Optional[int],
            cart_item: int = 0,
            manager_url: str = "https://t.me/@el_mex",
    ) -> InlineKeyboardMarkup:
        """Карточка конкретного товара с пагинацией (⬅️ ➡️), кнопкой корзины и менеджером."""
        texts = self.get_button_text(
            "client.product_card",
            ["add_to_cart", "cart_label", "manager", "back"],
            default="XXX",
        )

        count_str = f" ({cart_item})" if cart_item > 0 else ""
        cart_text = self.get_button_text(
            texts["cart_label"], count=count_str
        )

        back_cat = category_id if category_id else "root"

        builder = InlineKeyboardBuilder()

        # Ряд: Пагинация и добавление
        nav_row = []
        if prev_id:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"prev_{prev_id}"))

        nav_row.append(
            InlineKeyboardButton(
                text=texts["add_to_cart"],
                callback_data=f"order_{product_id}",
                style="success",
            )
        )

        if next_id:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"next_{next_id}"))

        builder.row(*nav_row)

        # Ряд: Перейти в корзину
        builder.row(
            InlineKeyboardButton(text=cart_text, callback_data="client_cart", style="primary")
        )

        # Ряд: Связь с менеджером
        builder.row(InlineKeyboardButton(text=texts["manager"], url=manager_url))

        # Ряд: Назад к категории
        builder.row(
            InlineKeyboardButton(text=texts["back"], callback_data=f"client_shop_{back_cat}")
        )

        return builder.as_markup()

    def get_cart_kb(self, cart_items: list) -> InlineKeyboardMarkup:
        """Меню корзины с изменением количества (➖ / ➕) и оформлением."""
        texts = self.get_button_text(
            "client.cart_actions",
            ["set_address", "set_comment", "checkout", "back"],
            default="XXX",
        )

        builder = InlineKeyboardBuilder()

        # Позиции корзины
        for item in cart_items:
            product_name = item.product.name if getattr(item, "product", None) else "Product"
            builder.row(
                InlineKeyboardButton(text=product_name, callback_data=f"client_item_{item.product_id}"),
                InlineKeyboardButton(text="➖", callback_data=f"dec_{item.product_id}", style="danger"),
                InlineKeyboardButton(text="➕", callback_data=f"inc_{item.product_id}", style="success")
            )

        # Кнопки ввода данных
        builder.row(
            InlineKeyboardButton(text=texts["set_address"], callback_data="set_address"),
            InlineKeyboardButton(text=texts["set_comment"], callback_data="set_comment")
        )

        # Оформление доступно всегда (адрес доставки опционален)
        builder.row(
            InlineKeyboardButton(
                text=texts["checkout"], callback_data="checkout_confirm", style="success"
            )
        )

        builder.row(InlineKeyboardButton(text=texts["back"], callback_data="client_main"))

        return builder.as_markup()

    def get_order_payment_request_kb(self, order_id: int) -> InlineKeyboardMarkup:
        """Выбор способа оплаты конкретного заказа (клиенту)."""
        return self.build("client.order_payment_request", order_id=order_id)

    def get_language_keyboard(
            self, exclude: Optional[List[str]] = None
    ) -> InlineKeyboardMarkup:
        """Клавиатура выбора языка.

        exclude — ключи кнопок для скрытия (например, ["back"] на первом
        запуске, когда возвращаться в меню некуда).
        """
        return self.build("client.language_selection", exclude=exclude)

    # ==================================================================
    # Админские динамические клавиатуры
    # ==================================================================

    def build_catalog_edit_kb(
            self,
            categories: list,
            products: list,
            current_cat_id: Optional[int],
            parent_id: Optional[int],
            category_names: Optional[Dict[int, str]] = None,
            has_description: bool = False,
    ) -> InlineKeyboardMarkup:
        """Динамический конструктор управления категориями и товарами магазина."""
        from shopcrm_bot.keyboards.admin import build_catalog_edit_kb

        return build_catalog_edit_kb(
            keyboard_factory=self,
            categories=categories,
            products=products,
            current_cat_id=current_cat_id,
            parent_id=parent_id,
            category_names=category_names,
            has_description=has_description,
        )

    def get_unit_selection_kb(self, product_id: int | None = None) -> InlineKeyboardMarkup:
        """Клавиатура выбора единицы измерения (единицы из locale.json)."""
        builder = InlineKeyboardBuilder()

        units_data = self.locale.locales.get("units", {})
        lang = self.locale.lang

        for unit_code, labels in units_data.items():
            if unit_code == "default" or not isinstance(labels, dict):
                continue
            label_text = labels.get(lang) or labels.get("en") or labels.get("ru") or unit_code

            if product_id is not None:
                callback_data = f"admin_set_unit_{product_id}_{unit_code}"
            else:
                callback_data = f"admin_select_unit_{unit_code}"

            builder.button(text=f"📦 {label_text}", callback_data=callback_data)

        builder.adjust(3)

        back_text = self.get_button_text("base.back", default="⬅️ Back")
        back_callback = (
            f"admin_item_{product_id}" if product_id is not None else "admin_cancel_action"
        )
        builder.row(InlineKeyboardButton(text=back_text, callback_data=back_callback))

        return builder.as_markup()

    def get_orders_menu_kb(
            self,
            status_counts: dict[str, int] | None = None,
    ) -> InlineKeyboardMarkup:
        """Меню управления заказами с динамическими счетчиками.

        locale.json использует плейсхолдер {count} в тексте кнопок, поэтому
        значение подставляется индивидуально для каждой кнопки: build() передаёт
        все kwargs каждой кнопке и не может различить счётчики по именам кнопок.
        """
        from shopcrm_core.constants import ADMIN_ORDER_STATUS_FILTERS

        status_map = ADMIN_ORDER_STATUS_FILTERS
        counts = status_counts or {}

        buttons = self.locale.get_keyboard_data("admin.orders_menu")
        btns = buttons.get("buttons", {}) if isinstance(buttons, dict) else {}
        sizes = buttons.get("sizes") if isinstance(buttons, dict) else None

        out_buttons: List[InlineKeyboardButton] = []
        for btn_key, btn_val in btns.items():
            count: int | None = None
            if btn_key == "admin_order_all" and counts:
                count = sum(counts.values())
            elif btn_key in status_map and counts:
                count = counts.get(status_map[btn_key], 0)

            formatted_count = f" ({count})" if count is not None else ""
            text = self.get_button_text(btn_val, default="XXX", count=formatted_count)
            actual_callback = "admin_main_menu" if btn_key == "back" else btn_key
            out_buttons.append(
                InlineKeyboardButton(text=text, callback_data=actual_callback)
            )

        builder = InlineKeyboardBuilder()
        if out_buttons:
            if sizes:
                builder.add(*out_buttons)
                builder.adjust(*sizes)
            else:
                for btn in out_buttons:
                    builder.row(btn)
        return builder.as_markup()

    @staticmethod
    def _format_count(counts: dict, status: Optional[str]) -> str:
        """Символ в скобках только при ненулевом счетчике."""
        count = counts.get(status, 0) if status else counts.get("__all__", 0)
        return f" ({count})" if count > 0 else ""

    def get_orders_list_kb(
            self,
            orders: list,
            current_page: int,
            total_pages: int,
            status: str,
    ) -> InlineKeyboardMarkup:
        """Список заказов админа с круговой пагинацией."""
        builder = InlineKeyboardBuilder()

        button_template = self.get_button_text(
            "text.admin.orders.list_button", default="#{id}"
        )
        back_text = self.get_button_text("base.back", default="⬅️ Back")
        export_text = self.get_button_text(
            "text.admin.orders.export_csv_button", default="📤 Export CSV"
        )

        for order in orders:
            button_text = self.get_button_text(
                button_template,
                id=order.id,
                price=getattr(order, "total_price", 0),
                status=order.status,
                currency=self.locale.get_currency_symbol(),
            )
            builder.row(
                InlineKeyboardButton(
                    text=button_text,
                    # Передаём status и current_page, чтобы «Назад» из карточки
                    # возвращал в тот же список с тем же фильтром и страницей
                    callback_data=f"admin_order_view:{order.id}:{status}:{current_page}",
                )
            )

        # Блок круговой пагинации
        if orders and total_pages > 0:
            prev_page = total_pages if current_page == 1 else current_page - 1
            next_page = 1 if current_page == total_pages else current_page + 1

            builder.row(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"admin_orders_page:{status}:{prev_page}",
                ),
                InlineKeyboardButton(
                    text=f"{current_page}/{total_pages}",
                    callback_data="noop",
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"admin_orders_page:{status}:{next_page}",
                ),
            )

        # Экспорт текущего отфильтрованного списка в CSV
        builder.row(
            InlineKeyboardButton(
                text=export_text,
                callback_data=f"admin_orders_export:{status}",
            )
        )

        builder.row(
            InlineKeyboardButton(text=back_text, callback_data="admin_orders")
        )

        return builder.as_markup()

    def get_order_detail_kb(
            self,
            order: Any,
            status: str = "all",
            page: int = 1,
    ) -> InlineKeyboardMarkup:
        """Клавиатура карточки заказа (динамическая, зависит от статуса).

        - ``pending``: редактор (принять + правки) + постоянные кнопки, БЕЗ «Запросить оплату».
        - ``processing`` / ``payment_requested`` (не оплачен и клиент ещё не дал ответ —
          нет чека на проверке и способ оплаты не выбран): «Запросить оплату» +
          постоянные кнопки, БЕЗ редактора. Кнопка позволяет админу повторно
          запрашивать оплату, пока клиент не ответил (чек/хэш или наличные).
        - ``delivering`` (не оплачен): «Оплачено» — админ подтверждает получение
          оплаты (например, наличных от клиента курьеру) перед закрытием заказа.
        - остальные статусы: только постоянные кнопки.

        Постоянные кнопки («Написать покупателю», «Изменить статус») — во всех статусах.
        """
        builder = InlineKeyboardBuilder()

        order_status = getattr(order, "status", None)
        is_paid = bool(getattr(order, "is_paid", False))
        proof_type = getattr(order, "payment_proof_type", None)

        texts = self.get_button_text(
            "admin.order_detail",
            [
                "admin_order_accept",
                "admin_order_contact_client",
                "admin_order_edit_items",
                "admin_order_edit_addr",
                "admin_order_edit_shipping",
                "admin_order_edit_comment",
                "admin_order_request_payment",
                "admin_order_mark_paid",
                "admin_order_change_status",
                "back",
            ],
            default="XXX",
        )

        def _row(btn_key: str, callback_key: str) -> None:
            builder.row(
                InlineKeyboardButton(
                    text=texts[btn_key],
                    callback_data=f"{callback_key}:{order.id}:{status}:{page}",
                )
            )

        if order_status == OrderStatus.PENDING.value:
            # Редактор заказа: принять + правки параметров (без «Запросить оплату»)
            _row("admin_order_accept", "admin_order_accept")
            _row("admin_order_edit_items", "admin_order_edit_items")
            _row("admin_order_edit_addr", "admin_order_edit_addr")
            _row("admin_order_edit_shipping", "admin_order_edit_shipping")
            _row("admin_order_edit_comment", "admin_order_edit_comment")
        elif (
                order_status in (
                    OrderStatus.PROCESSING.value,
                    OrderStatus.PAYMENT_REQUESTED.value,
                )
                and not is_paid
                and not proof_type
        ):
            # Заказ ожидает оплаты и клиент ещё не ответил (нет чека на проверке,
            # не выбран наличный расчёт): админ может запросить/повторно запросить оплату
            _row("admin_order_request_payment", "admin_order_request_payment")
        elif order_status == OrderStatus.DELIVERING.value and not is_paid:
            # Заказ в пути и оплата ещё не подтверждена (типично для наличных):
            # админ отмечает получение оплаты перед закрытием заказа
            _row("admin_order_mark_paid", "admin_order_mark_paid")

        # Постоянные кнопки — во всех статусах
        _row("admin_order_contact_client", "admin_order_contact_client")
        _row("admin_order_change_status", "admin_order_change_status")

        builder.row(
            InlineKeyboardButton(
                text=texts["back"],
                callback_data=f"admin_orders_page:{status}:{page}",
            )
        )

        return builder.as_markup()

    def get_order_items_editor_kb(
            self,
            order,
            status: str = "all",
            page: int = 1,
    ) -> InlineKeyboardMarkup:
        """Редактор состава заказа (➖/➕ по позициям, добавление, назад)."""
        builder = InlineKeyboardBuilder()

        unit_default = self.locale.get_unit(None)

        if order.items:
            for item in order.items:
                prod_name = (
                    item.product.name
                    if item.product
                    else self.locale.get_text(
                        "admin.orders.deleted_product", product_id=item.product_id
                    )
                )
                unit = (
                    self.locale.get_unit(getattr(item.product, "unit", None))
                    if item.product
                    else unit_default
                )
                builder.row(
                    InlineKeyboardButton(
                        text=f"{prod_name} ({item.quantity} {unit})",
                        callback_data=f"admin_order_noop:{order.id}",
                    ),
                    InlineKeyboardButton(
                        text="➖",
                        callback_data=f"admin_order_dec_item:{order.id}:{item.id}:{status}:{page}",
                    ),
                    InlineKeyboardButton(
                        text="➕",
                        callback_data=f"admin_order_inc_item:{order.id}:{item.id}:{status}:{page}",
                    ),
                )

        add_product_text = self.get_button_text(
            "text.admin.orders.btn_add_product", default="➕ Add product"
        )
        builder.row(
            InlineKeyboardButton(
                text=add_product_text,
                callback_data=f"admin_order_add_item_start:{order.id}:{status}:{page}",
            )
        )

        back_text = self.get_button_text("base.back", default="⬅️ Back")
        builder.row(
            InlineKeyboardButton(
                text=back_text,
                callback_data=f"admin_order_view:{order.id}:{status}:{page}",
            )
        )

        return builder.as_markup()

    def get_payment_details_editor_kb(self, has_text: bool) -> InlineKeyboardMarkup:
        """Редактор платежных данных: Изменить / Добавить + Назад."""
        edit_btn_key = "edit" if has_text else "add"
        texts = self.get_button_text(
            "admin.payment_editor", [edit_btn_key, "back"], default="XXX"
        )

        builder = InlineKeyboardBuilder()
        builder.button(
            text=texts[edit_btn_key],
            callback_data="admin_edit_payment_text",
        )
        builder.button(
            text=texts["back"],
            callback_data="admin_shop_settings",
        )
        builder.adjust(1)
        return builder.as_markup()

    def get_welcome_editor_kb(self, has_photo: bool = False) -> InlineKeyboardMarkup:
        """Редактор приветственного сообщения и фото."""
        buttons = self.locale.get_keyboard_data("admin.welcome_editor")
        btns = buttons.get("buttons", {}) if isinstance(buttons, dict) else {}

        texts = {
            key: self.get_button_text(btns.get(key), default="XXX")
            for key in ("admin_edit_wel_text", "admin_edit_wel_photo", "admin_edit_wel_del_photo", "admin_shop_settings")
        }

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=texts["admin_edit_wel_text"], callback_data="admin_edit_wel_text")
        )
        builder.row(
            InlineKeyboardButton(text=texts["admin_edit_wel_photo"], callback_data="admin_edit_wel_photo")
        )
        if has_photo:
            builder.row(
                InlineKeyboardButton(text=texts["admin_edit_wel_del_photo"], callback_data="admin_edit_wel_del_photo")
            )
        builder.row(
            InlineKeyboardButton(text=texts["admin_shop_settings"], callback_data="admin_shop_settings")
        )
        return builder.as_markup()

    def get_product_editor_kb(
            self,
            product_id: int,
            category_id: int | str,
            has_photo: bool = False,
    ) -> InlineKeyboardMarkup:
        """Управление характеристиками конкретного товара.

        Кнопки фото зависят от наличия фото у товара:
        - без фото: «📸 Добавить фото»;
        - с фото: «📸 Изменить фото» + «🗑 Удалить фото».
        """
        exclude = ["edit_photo"] if has_photo else ["edit_photo_change", "delete_photo"]
        return self.build(
            "admin.product_editor",
            callbacks={
                "back": f"admin_catalog_{category_id}",
            },
            id=product_id,
            exclude=exclude,
        )

    def get_order_status_kb(
            self,
            order_id: int,
            status: str = "all",
            page: int = 1,
    ) -> InlineKeyboardMarkup:
        """Выбор нового статуса заказа (все статусы из enum OrderStatus)."""
        from shopcrm_core.constants import ORDER_STATUS_CODES, ORDER_STATUS_VALUES

        buttons = self.locale.get_keyboard_data("admin.order_status_menu")
        btns = buttons.get("buttons", {}) if isinstance(buttons, dict) else {}
        sizes = buttons.get("sizes") if isinstance(buttons, dict) else None

        # Короткий код фильтра (лимит callback_data — 64 байта); "all" остаётся как есть.
        filter_code = ORDER_STATUS_CODES.get(status, status)

        out_buttons: List[InlineKeyboardButton] = []
        for btn_key, btn_val in btns.items():
            text = self.get_button_text(btn_val, default="XXX")

            if btn_key == "back":
                actual_callback = f"admin_order_view:{order_id}:{status}:{page}"
            elif btn_key in ORDER_STATUS_VALUES:
                actual_callback = (
                    f"admin_order_set_status:{order_id}:{ORDER_STATUS_CODES[btn_key]}:{filter_code}:{page}"
                )
            else:
                continue

            out_buttons.append(
                InlineKeyboardButton(text=text, callback_data=actual_callback)
            )

        builder = InlineKeyboardBuilder()
        if out_buttons:
            if sizes:
                builder.add(*out_buttons)
                builder.adjust(*sizes)
            else:
                for btn in out_buttons:
                    builder.row(btn)
        return builder.as_markup()

    def get_payment_verify_kb(self, order_id: int) -> InlineKeyboardMarkup:
        """Быстрое подтверждение/отклонение оплаты (уведомления админа)."""
        return self.build("admin.payment_verify", order_id=order_id)