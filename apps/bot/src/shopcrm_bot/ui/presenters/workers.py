# ui/presenters/workers.py
"""Презентер раздела «Работники»: список и подтверждение удаления.

Весь рендер — через ``UIManager.show`` (система «1 сообщения»):
in-place edit по ``message_id_to_edit``, fallback на новое сообщение.
"""
import math

from aiogram.types import CallbackQuery, Message
from shopcrm_core.services.admin_worker_service import AdminWorkerService

from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager

PAGE_SIZE = 5


class WorkersUI:
    """Экраны раздела «Работники»."""

    @staticmethod
    async def show_list(
        event: Message | CallbackQuery,
        service: AdminWorkerService,
        main_admin_ids: list[int],
        page: int = 1,
        locale: Locale | None = None,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Список работников с круговой пагинацией (по 5 на страницу).

        :param service: сервис работников (список = env-админ + БД)
        :param main_admin_ids: главный админ из env (виртуальный, без удаления)
        :param page: страница списка (круговая пагинация)
        :param locale: локаль юзера из БД (инжектится middleware'ом)
        :param message_id_to_edit: in-place перерисовка (после FSM-ввода/удаления)
        """
        if locale is None:
            locale = Locale("en")
        kb = locale.keyboards

        entries = await service.list_workers(main_admin_ids)
        total_count = len(entries)
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
        page_entries = entries[offset:offset + PAGE_SIZE]

        # Текст: ID + должность в 1 строку (как в списке юзеров)
        if not page_entries:
            text = (
                locale.get_text("admin.workers.list_header")
                + "\n\n"
                + locale.get_text("admin.workers.list_empty")
            )
        else:
            lines = [locale.get_text("admin.workers.list_header") + "\n"]
            for entry in page_entries:
                if entry.is_main:
                    position = locale.get_text("admin.workers.main_position")
                    marker = "🛡️ "
                else:
                    position = entry.position
                    marker = ""
                lines.append(
                    locale.get_text(
                        "admin.workers.list_line",
                        id=entry.telegram_id,
                        position=position,
                        marker=marker,
                    )
                )
            text = "\n".join(lines)

        reply_markup = kb.get_workers_list_kb(
            workers=page_entries,
            current_page=page,
            total_pages=total_pages,
        )

        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def show_delete_confirm(
        event: Message | CallbackQuery,
        telegram_id: int,
        position: str,
        locale: Locale | None = None,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Экран подтверждения удаления работника (in-place вместо списка)."""
        if locale is None:
            locale = Locale("en")

        text = locale.get_text(
            "admin.workers.delete_confirm_text",
            id=telegram_id,
            position=position,
        )

        reply_markup = locale.keyboards.get_worker_delete_confirm_kb(
            telegram_id=telegram_id,
        )

        await UIManager.show(
            event=event,
            text=text,
            reply_markup=reply_markup,
            message_id_to_edit=message_id_to_edit,
        )
