# keyboards/admin_inline.py
import json
import logging
from pathlib import Path
from typing import Optional, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from locales.units import ProductUnit, UNIT_LABELS
from src.core.constants import OrderStatus

logger = logging.getLogger(__name__)


class AdminInlineKb:
    locale_path = Path(__file__).resolve().parent / "admin_kb.json"

    def __init__(self, lang: str = 'ru'):
        self.lang = lang
        self.template = self._load_json()

    def _load_json(self):
        try:
            with open(self.locale_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            logger.critical(f"[ADMIN KB] Failed to open/parse {self.locale_path}: {e}", exc_info=True)
            return None

    def get_kb(self, key: str) -> Optional[InlineKeyboardMarkup]:
        """Универсальный метод генерации клавиатур из admin_kb.json"""
        if self.template is None:
            logger.critical("[ADMIN KB] Keyboards template is missing!")
            return None

        data = self.template.get(key)
        if data is None:
            logger.critical(f"[ADMIN KB] Keyboard with key '{key}' not found!")
            return None

        buttons = data.get("buttons")
        sizes = data.get("sizes")

        if not buttons or not sizes:
            logger.critical(f"[ADMIN KB] Invalid structure for key '{key}'!")
            return None

        builder = InlineKeyboardBuilder()

        for callback_data, translations in buttons.items():
            button_text = translations.get(self.lang) or translations.get("en") or "XXX"

            if not translations.get(self.lang):
                logger.warning(f"[ADMIN KB] Missing translation for lang '{self.lang}' in button '{callback_data}'")

            builder.button(text=button_text, callback_data=callback_data)

        builder.adjust(*sizes)
        return builder.as_markup()

    def get_shop_settings_kb(self) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура для подменю 'Настройка магазина' с корректным callback для возврата"""
        if self.template is None:
            logger.critical("[ADMIN KB] Keyboards template is missing!")
            return None

        data = self.template.get("admin_shop_settings_menu")
        if data is None:
            logger.critical("[ADMIN KB] Keyboard with key 'admin_shop_settings_menu' not found!")
            return None

        buttons = data.get("buttons")
        sizes = data.get("sizes")

        if not buttons or not sizes:
            logger.critical("[ADMIN KB] Invalid structure for 'admin_shop_settings_menu'!")
            return None

        builder = InlineKeyboardBuilder()

        for callback_data, translations in buttons.items():
            button_text = translations.get(self.lang) or translations.get("en") or "XXX"

            # Подменяем callback для кнопки "back" на тот, который ожидает роутер главного меню
            actual_callback = "admin_mainmenu" if callback_data == "back" else callback_data

            builder.button(text=button_text, callback_data=actual_callback)

        builder.adjust(*sizes)
        return builder.as_markup()

    def get_text(self, path: str, default: str = "") -> str:
        """Вспомогательный метод для получения локализованных строк/сообщений"""
        if self.template is None:
            return default

        keys = path.split(".")
        current = self.template.get("admin_messages", {})

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, {})
            else:
                return default

        if isinstance(current, dict):
            return current.get(self.lang) or current.get("en") or default
        return default

    def get_cancel_add_category_kb(self, back_callback: str) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура отмены с динамическим callback_data для возврата назад"""
        if self.template is None:
            return None

        cfg = self.template.get("admin_category_actions")
        if not cfg:
            logger.critical("[ADMIN KB] 'admin_category_actions' configuration not found!")
            return None

        buttons_cfg = cfg.get("buttons", {})
        cancel_text = buttons_cfg.get("cancel", {}).get(self.lang) or "📥 Cancel"

        builder = InlineKeyboardBuilder()
        builder.button(text=cancel_text, callback_data=back_callback, style='danger')
        return builder.as_markup()

    def get_shop_edit_kb(
            self,
            categories: list,
            products: list,
            current_cat_id: int | None,
            parent_id: int | None,
            category_names: dict[int, str] | None = None,
            has_description: bool = False  # Флаг: есть ли описание у текущей категории/главного меню
    ) -> Optional[InlineKeyboardMarkup]:
        """Динамический конструктор управления категориями и товарами магазина"""
        if self.template is None:
            return None

        nav_data = self.template.get("admin_shop_navigation")
        if not nav_data:
            logger.critical("[ADMIN KB] 'admin_shop_navigation' configuration not found!")
            return None

        nav_buttons = nav_data.get("buttons", {})

        # Локализуем статические кнопки
        back_text = nav_buttons.get("back", {}).get(self.lang) or "⬅️ Back"
        to_main_text = nav_buttons.get("to_main_menu", {}).get(self.lang) or "⬅️ To Main Menu"
        del_text = nav_buttons.get("delete", {}).get(self.lang) or "❌ Delete"
        add_sub_text = nav_buttons.get("add_subcategory", {}).get(self.lang) or "🟢 Add Subcategory"
        add_prod_text = nav_buttons.get("add_product", {}).get(self.lang) or "🔴 Add Product Here"
        add_tittle_text = nav_buttons.get("add_tittle", {}).get(self.lang) or "📝 Category details"
        del_tittle_text = nav_buttons.get("delete_tittle", {}).get(self.lang) or "🗑 Delete description"
        save_text = nav_buttons.get("save_changes", {}).get(self.lang) or "💾 Save Changes"

        builder = InlineKeyboardBuilder()

        # 1. Навигация "Назад" / "В главное меню" (теперь кнопка назад ведет в подменю настройки магазина)
        if current_cat_id:
            parent_to_go = parent_id if parent_id else "root"
            builder.row(InlineKeyboardButton(text=back_text, callback_data=f"admin_shop_{parent_to_go}"))
        else:
            builder.row(InlineKeyboardButton(text=to_main_text, callback_data="admin_shop_settings"))

        # 2. Список подкатегорий (Имя категории из словаря локалей/модели + кнопка «Удалить»)
        for category in categories:
            cat_display_name = (
                category_names.get(category.id) if category_names and category.id in category_names
                else category.name
            )
            builder.row(
                InlineKeyboardButton(text=f"📁 {cat_display_name}", callback_data=f"admin_shop_{category.id}"),
                InlineKeyboardButton(text=del_text, callback_data=f"admin_del_cat_{category.id}")
            )

        # 3. Список товаров (Имя товара + кнопка «Удалить»)
        for product in products:
            builder.row(
                InlineKeyboardButton(text=f"📦 {product.name}", callback_data=f"admin_item_{product.id}"),
                InlineKeyboardButton(text=del_text, callback_data=f"admin_del_item_{product.id}")
            )

        # 4. Управление и добавление ресурсов
        cat_suffix = f"_{current_cat_id}" if current_cat_id else "_root"
        builder.row(InlineKeyboardButton(text=add_sub_text, callback_data=f"admin_addcat{cat_suffix}"))
        builder.row(InlineKeyboardButton(text=add_prod_text, callback_data=f"admin_add_item{cat_suffix}"))

        # Кнопки описания: если описание есть, выводим «Описание» и «Удалить описание» на одной строке.
        # Если описания нет — только кнопку добавления.
        if has_description:
            builder.row(
                InlineKeyboardButton(text=add_tittle_text, callback_data=f"admin_add_tittle{cat_suffix}"),
                InlineKeyboardButton(text=del_tittle_text, callback_data=f"admin_del_tittle{cat_suffix}")
            )
        else:
            builder.row(InlineKeyboardButton(text=add_tittle_text, callback_data=f"admin_add_tittle{cat_suffix}"))

        builder.row(InlineKeyboardButton(text=save_text, callback_data="admin_save_shop"))

        return builder.as_markup()

    def get_product_editor_kb(self, product_id: int, category_id: int | str) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура управления характеристиками конкретного товара"""
        if self.template is None:
            return None

        cfg = self.template.get("admin_product_editor")
        if not cfg:
            logger.critical("[ADMIN KB] 'admin_product_editor' configuration not found!")
            return None

        buttons_cfg = cfg.get("buttons", {})

        edit_name = buttons_cfg.get("edit_name", {}).get(self.lang) or "✏️ Name"
        edit_unit = buttons_cfg.get("edit_unit", {}).get(self.lang) or "⚖️ Unit"
        edit_desc = buttons_cfg.get("edit_desc", {}).get(self.lang) or "✏️ Description"
        edit_price = buttons_cfg.get("edit_price", {}).get(self.lang) or "💰 Price"
        edit_photo = buttons_cfg.get("edit_photo", {}).get(self.lang) or "📸 Photo"
        back_text = buttons_cfg.get("back", {}).get(self.lang) or "⬅️ Back"

        builder = InlineKeyboardBuilder()

        builder.row(
            InlineKeyboardButton(text=edit_name, callback_data=f"admin_edit_p_name_{product_id}"),
            InlineKeyboardButton(text=edit_unit, callback_data=f"admin_edit_p_unit_{product_id}")
        )
        builder.row(
            InlineKeyboardButton(text=edit_desc, callback_data=f"admin_edit_p_desc_{product_id}"),
            InlineKeyboardButton(text=edit_price, callback_data=f"admin_edit_p_price_{product_id}")
        )
        builder.row(InlineKeyboardButton(text=edit_photo, callback_data=f"admin_edit_p_photo_{product_id}"))
        builder.row(InlineKeyboardButton(text=back_text, callback_data=f"admin_shop_{category_id}"))

        return builder.as_markup()

    def get_unit_selection_kb(self, product_id: int | None = None) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура выбора единицы измерения на основе ProductUnit."""
        builder = InlineKeyboardBuilder()

        # 1. Генерируем кнопки единиц измерения (итерируемся по items для точной типизации)
        for unit_enum, labels in UNIT_LABELS.items():
            label_text = labels.get(self.lang) or labels.get("en") or labels.get("ru") or unit_enum.value

            if product_id is not None:
                callback_data = f"admin_set_unit_{product_id}_{unit_enum.value}"
            else:
                callback_data = f"admin_select_unit_{unit_enum.value}"

            builder.button(text=f"📦 {label_text}", callback_data=callback_data)

        builder.adjust(3)

        # 2. Достаем перевод "Отмена" из json (admin_category_actions.buttons.cancel)
        cancel_text = "❌ Cancel"
        if self.template:
            cfg = self.template.get("admin_category_actions", {})
            cancel_btn = cfg.get("buttons", {}).get("cancel", {})
            cancel_text = cancel_btn.get(self.lang) or cancel_btn.get("en") or cancel_btn.get("ru") or cancel_text

        cancel_callback = f"admin_edit_p_cancel_{product_id}" if product_id is not None else "admin_cancel_action"
        builder.row(InlineKeyboardButton(text=cancel_text, callback_data=cancel_callback))

        return builder.as_markup()

    def get_welcome_editor_kb(self, has_photo: bool = False) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура управления приветственным сообщением и фото (без кнопки сохранения)"""
        if self.template is None:
            return None

        cfg = self.template.get("admin_welcome_editor", {}).get("buttons", {})

        # Берем локализации из JSON с надежными фолбеками (без save)
        edit_text_label = cfg.get("admin_edit_wel_text", {}).get(self.lang) or "✏️ Изменить текст"
        edit_photo_label = cfg.get("admin_edit_wel_photo", {}).get(self.lang) or "📸 Изменить фото"
        del_photo_label = cfg.get("admin_edit_wel_del_photo", {}).get(self.lang) or "❌ Удалить фото"
        back_label = cfg.get("admin_shop_settings", {}).get(self.lang) or "⬅️ Назад"

        builder = InlineKeyboardBuilder()

        builder.row(InlineKeyboardButton(text=edit_text_label, callback_data="admin_edit_wel_text"))
        builder.row(InlineKeyboardButton(text=edit_photo_label, callback_data="admin_edit_wel_photo"))

        if has_photo:
            builder.row(InlineKeyboardButton(text=del_photo_label, callback_data="admin_edit_wel_del_photo"))

        builder.row(InlineKeyboardButton(text=back_label, callback_data="admin_shop_settings"))

        return builder.as_markup()

    def get_orders_menu_kb(
            self,
            status_counts: dict[str, int] | None = None
    ) -> Optional[InlineKeyboardMarkup]:
        """Клавиатура для подменю 'Заказы' с отображением количества заказов и корректным возвратом."""
        if self.template is None:
            logger.critical("[ADMIN KB] Keyboards template is missing!")
            return None

        data = self.template.get("admin_orders_menu")
        if data is None:
            logger.critical("[ADMIN KB] Keyboard with key 'admin_orders_menu' not found!")
            return None

        buttons = data.get("buttons")
        sizes = data.get("sizes")

        if not buttons or not sizes:
            logger.critical("[ADMIN KB] Invalid structure for 'admin_orders_menu'!")
            return None

        # Актуальный маппинг callback_data на ключи статусов из БД через OrderStatus
        status_map = {
            "admin_order_pending": OrderStatus.PENDING.value,
            "admin_order_awaiting": OrderStatus.AWAITING_CONFIRMATION.value,
            "admin_order_processing": OrderStatus.PROCESSING.value,
            "admin_order_delivering": OrderStatus.DELIVERING.value,
        }

        builder = InlineKeyboardBuilder()

        for callback_data, translations in buttons.items():
            button_text = translations.get(self.lang) or translations.get("en") or "XXX"

            # 1. Если это кнопка "Все заказы", считаем сумму всех статусов
            if callback_data == "admin_order_all" and status_counts:
                total_count = sum(status_counts.values())
                button_text = f"{button_text} ({total_count})"

            # 2. Если это кнопка конкретного статуса, берем значение по ключу
            elif callback_data in status_map and status_counts:
                st_key = status_map[callback_data]
                count = status_counts.get(st_key, 0)
                button_text = f"{button_text} ({count})"

            # Подменяем callback для кнопки "back"
            actual_callback = "admin_mainmenu" if callback_data == "back" else callback_data

            builder.button(text=button_text, callback_data=actual_callback)

        builder.adjust(*sizes)
        return builder.as_markup()

    def get_orders_list_kb(
            self,
            orders: list,
            current_page: int,
            total_pages: int,
            status: str,
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура списка заказов с круговой пагинацией.
        Каждая кнопка заказа занимает отдельную строку (1 в ряд).
        """
        builder = InlineKeyboardBuilder()

        # 1. Кнопки заказов (строго по 1 в ряд через builder.row)
        for order in orders:
            btn_text = f"#{order.id}: {order.total_price} $ - {order.status}"
            builder.row(
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"admin_order_view:{order.id}"
                )
            )

        # 2. Блок круговой пагинации (3 кнопки в 1 ряд)
        if orders and total_pages > 0:
            prev_page = total_pages if current_page == 1 else current_page - 1
            next_page = 1 if current_page == total_pages else current_page + 1

            pagination_buttons = [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"admin_orders_page:{status}:{prev_page}"
                ),
                InlineKeyboardButton(
                    text=f"{current_page}/{total_pages}",
                    callback_data="noop"
                ),
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"admin_orders_page:{status}:{next_page}"
                )
            ]
            builder.row(*pagination_buttons)

        # 3. Кнопка возврата (1 кнопка в ряд)
        back_text = "⬅️ Назад"
        if self.template:
            cfg = self.template.get("admin_orders_menu", {}).get("buttons", {}).get("back", {})
            back_text = cfg.get(self.lang) or cfg.get("en") or "⬅️ Назад"

        builder.row(
            InlineKeyboardButton(text=back_text, callback_data="admin_orders")
        )

        return builder.as_markup()

    def get_order_detail_kb(
            self,
            order: Any,
            status: str = "all",
            page: int = 1,
    ) -> Optional[InlineKeyboardMarkup]:
        """
        Клавиатура карточки заказа:
        - ✅ Принять заказ (появляется вверху, если статус pending)
        - 💬 Написать покупателю (прямая связь через бота)
        - ✏️ Редактировать заказ
        - 📍 Редактировать адрес
        - 🚚 Редактировать стоимость доставки
        - 💬 Добавить комментарий от админа
        - 💳 Запросить оплату
        - 🔄 Изменить статус
        - ⬅️ Назад (с сохранением пагинации)
        """
        if self.template is None:
            logger.critical("[ADMIN KB] Keyboards template is missing!")
            return None

        data = self.template.get("admin_order_detail")
        if data is None:
            logger.critical("[ADMIN KB] Keyboard template 'admin_order_detail' not found!")
            return None

        buttons = data.get("buttons", {})
        builder = InlineKeyboardBuilder()

        def get_btn_text(key: str, default: str) -> str:
            trans = buttons.get(key, {})
            return trans.get(self.lang) or trans.get("en") or default

        # 1. Если статус заказа "pending" — добавляем главное действие "Принять заказ"
        if getattr(order, "status", None) == "pending":
            builder.row(
                InlineKeyboardButton(
                    text=get_btn_text("admin_order_accept", "✅ Принять заказ"),
                    callback_data=f"admin_order_accept:{order.id}:{status}:{page}"
                )
            )

        # 2. Кнопка прямого контакта с клиентом через бота
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_contact_client", "💬 Написать покупателю"),
                callback_data=f"admin_order_contact_client:{order.id}:{status}:{page}"
            )
        )

        # 3. Основные кнопки редактирования заказа
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_edit_items", "✏️ Редактировать заказ"),
                callback_data=f"admin_order_edit_items:{order.id}:{status}:{page}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_edit_addr", "📍 Редактировать адрес"),
                callback_data=f"admin_order_edit_addr:{order.id}:{status}:{page}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_edit_shipping", "🚚 Редактировать стоимость доставки"),
                callback_data=f"admin_order_edit_shipping:{order.id}:{status}:{page}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_edit_comment", "💬 Добавить комментарий от админа"),
                callback_data=f"admin_order_edit_comment:{order.id}:{status}:{page}"
            )
        )

        # 4. Нижний блок: Запрос оплаты и Смена статуса
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_request_payment", "💳 Запросить оплату"),
                callback_data=f"admin_order_request_payment:{order.id}:{status}:{page}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("admin_order_change_status", "🔄 Изменить статус"),
                callback_data=f"admin_order_change_status:{order.id}:{status}:{page}"
            )
        )

        # 5. Возврат на ту же страницу пагинации
        builder.row(
            InlineKeyboardButton(
                text=get_btn_text("back", "⬅️ Назад"),
                callback_data=f"admin_orders_page:{status}:{page}"
            )
        )

        return builder.as_markup()

    def get_order_items_editor_kb(
            self,
            order,
            status: str = "all",
            page: int = 1,
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура редактирования состава заказа для админа.
        Позволяет изменять количество товаров (➕/➖) и добавлять новые.
        """
        builder = InlineKeyboardBuilder()

        # 1. Позиции заказа (Список товаров с кнопками управления)
        if order.items:
            for item in order.items:
                prod_name = item.product.name if item.product else f"Товар #{item.product_id}"
                # Название товара ведет на просмотр или заглушку
                builder.row(
                    InlineKeyboardButton(
                        text=f"{prod_name} ({item.quantity} шт.)",
                        callback_data=f"admin_order_noop:{order.id}"
                    ),
                    InlineKeyboardButton(
                        text="➖",
                        callback_data=f"admin_order_dec_item:{order.id}:{item.id}:{status}:{page}"
                    ),
                    InlineKeyboardButton(
                        text="➕",
                        callback_data=f"admin_order_inc_item:{order.id}:{item.id}:{status}:{page}"
                    )
                )

        # 2. Кнопка добавления нового товара в заказ
        add_product_text = self.get_text("admin_order_buttons.add_product", "➕ Добавить товар")
        builder.row(
            InlineKeyboardButton(
                text=add_product_text,
                callback_data=f"admin_order_add_item_start:{order.id}:{status}:{page}"
            )
        )

        # 3. Кнопка "Назад" в карточку заказа
        back_text = self.get_text("common.back", "⬅️ Назад")
        builder.row(
            InlineKeyboardButton(
                text=back_text,
                callback_data=f"admin_order_view:{order.id}:{status}:{page}"
            )
        )

        return builder.as_markup()

    def get_payment_details_editor_kb(self, has_text: bool) -> InlineKeyboardMarkup:
        """
        Клавиатура редактора платежных данных.
        Если текст уже установлен -> кнопка Изменить.
        Если текста нет -> кнопка Добавить.
        """
        builder = InlineKeyboardBuilder()

        if has_text:
            edit_btn_text = self.get_text(
                "admin_payment_editor.buttons.edit",
                "✏️ Изменить платежные данные"
            )
        else:
            edit_btn_text = self.get_text(
                "admin_payment_editor.buttons.add",
                "➕ Добавить платежные данные"
            )

        back_btn_text = self.get_text(
            "admin_payment_editor.buttons.back",
            "⬅️ Назад"
        )

        builder.button(
            text=edit_btn_text,
            callback_data="admin_edit_payment_text"
        )
        builder.button(
            text=back_btn_text,
            callback_data="admin_shop_settings"  # Имя вашего callback для возврата в настройки магазина
        )

        builder.adjust(1)
        return builder.as_markup()