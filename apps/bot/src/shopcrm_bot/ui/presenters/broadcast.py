# ui/presenters/broadcast.py
"""Презентер раздела «Рассылка»: сборка текста и клавиатуры экранов.

Экраны:
  - start    — вход в раздел (кнопка «Новая рассылка»);
  - progress — идущая рассылка (счётчики, только «Назад»);
  - result   — результат последней рассылки.

Весь текст — через ``UIManager.show`` (правило «1 сообщения»).
"""
from aiogram.types import CallbackQuery, Message
from shopcrm_core.db.models.broadcast import Broadcast, BroadcastStatus
from shopcrm_core.db.models.user import User
from shopcrm_core.db.repositories.admin_repo import AdminRepository

from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager


class BroadcastUI:
    """Сборка текста и клавиатуры экранов рассылки."""

    @staticmethod
    async def show_screen(
        event: Message | CallbackQuery,
        admin_repo: AdminRepository,
        user: User,
        locale: Locale,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Главный экран раздела: активная рассылка -> прогресс,
        иначе результат последней, иначе стартовый экран."""
        active = await admin_repo.get_active_broadcast()
        if active:
            await BroadcastUI.show_progress(event, locale, active, message_id_to_edit)
            return
        last = await admin_repo.get_latest_broadcast(user.id)
        if last:
            await BroadcastUI.show_result(event, locale, last, message_id_to_edit)
            return
        await BroadcastUI.show_start(event, locale, message_id_to_edit)

    @staticmethod
    async def show_start(
        event: Message | CallbackQuery,
        locale: Locale,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Стартовый экран: описание + «Новая рассылка»."""
        title = locale.get_text("admin.broadcast.title")
        description = locale.get_text("admin.broadcast.description")
        kb = locale.keyboards.build("admin.broadcast")
        await UIManager.show(
            event=event,
            text=f"{title}\n\n{description}",
            reply_markup=kb,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def show_progress(
        event: Message | CallbackQuery,
        locale: Locale,
        broadcast: Broadcast,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Экран идущей рассылки: счётчики + «Назад»."""
        title = locale.get_text("admin.broadcast.progress_title")
        remaining = max(0, broadcast.total - broadcast.sent - broadcast.failed - broadcast.blocked)
        body = locale.get_text(
            "admin.broadcast.progress_text",
            sent=broadcast.sent,
            failed=broadcast.failed,
            blocked=broadcast.blocked,
            remaining=remaining,
        )
        kb = locale.keyboards.build("admin.broadcast", exclude=["admin_broadcast_start"])
        await UIManager.show(
            event=event,
            text=f"{title}\n\n{body}",
            reply_markup=kb,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def show_result(
        event: Message | CallbackQuery,
        locale: Locale,
        broadcast: Broadcast,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Экран результата последней рассылки."""
        if broadcast.status == BroadcastStatus.COMPLETED.value:
            title = locale.get_text("admin.broadcast.result_completed")
        elif broadcast.status == BroadcastStatus.CANCELLED.value:
            title = locale.get_text("admin.broadcast.result_cancelled")
        elif broadcast.status == BroadcastStatus.INTERRUPTED.value:
            title = locale.get_text("admin.broadcast.result_interrupted")
        else:
            title = locale.get_text("admin.broadcast.progress_title")

        body = locale.get_text(
            "admin.broadcast.result_text",
            sent=broadcast.sent,
            failed=broadcast.failed,
            blocked=broadcast.blocked,
            skipped=broadcast.skipped,
        )
        kb = locale.keyboards.build("admin.broadcast")
        await UIManager.show(
            event=event,
            text=f"{title}\n\n{body}",
            reply_markup=kb,
            message_id_to_edit=message_id_to_edit,
        )

