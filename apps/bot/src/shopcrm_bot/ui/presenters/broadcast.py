# ui/presenters/broadcast.py
"""Презентер раздела «Рассылка»: сборка текста и клавиатуры экранов.

Экраны:
  - start    — вход в раздел (кнопка «Новая рассылка»);
  - confirm  — подтверждение с превью текста и числом получателей;
  - progress — идущая рассылка (счётчики, остановка);
  - result   — результат последней рассылки (возобновление прерванной).

Весь текст — через ``UIManager.show`` (правило «1 сообщения»).
Превью текста рассылки экранируется: экран рисуется в HTML-режиме,
а текст рассылки — произвольный.
"""
import html

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
        cooldown_hours: float = 24.0,
    ) -> None:
        """Главный экран раздела: активная рассылка -> прогресс,
        иначе результат последней, иначе стартовый экран."""
        active = await admin_repo.get_active_broadcast(user.id)
        if active:
            await BroadcastUI.show_progress(event, locale, active, message_id_to_edit)
            return
        last = await admin_repo.get_latest_broadcast(user.id)
        if last:
            await BroadcastUI.show_result(event, locale, last, message_id_to_edit)
            return
        await BroadcastUI.show_start(event, locale, message_id_to_edit, cooldown_hours)

    @staticmethod
    async def show_start(
        event: Message | CallbackQuery,
        locale: Locale,
        message_id_to_edit: int | None = None,
        cooldown_hours: float = 24.0,
    ) -> None:
        """Стартовый экран: описание + «Новая рассылка»."""
        title = locale.get_text("admin.broadcast.title")
        description = locale.get_text(
            "admin.broadcast.description",
            cooldown=int(cooldown_hours) if cooldown_hours and cooldown_hours > 0 else 0,
        )
        kb = locale.keyboards.build(
            "admin.broadcast",
            exclude=["confirm", "cancel", "refresh", "stop", "resume"],
        )
        await UIManager.show(
            event=event,
            text=f"{title}\n\n{description}",
            reply_markup=kb,
            message_id_to_edit=message_id_to_edit,
        )

    @staticmethod
    async def show_confirm(
        event: Message | CallbackQuery,
        locale: Locale,
        text: str,
        recipients: int,
        skipped: int,
        message_id_to_edit: int | None = None,
    ) -> None:
        """Экран подтверждения: превью текста + число получателей."""
        title = locale.get_text("admin.broadcast.confirm_title")
        preview = html.escape(text)[:1000]
        body = locale.get_text(
            "admin.broadcast.confirm_text", recipients=recipients, skipped=skipped
        )
        kb = locale.keyboards.build(
            "admin.broadcast",
            exclude=["start", "refresh", "stop", "resume"],
        )
        await UIManager.show(
            event=event,
            text=f"{title}\n\n{body}\n\n{preview}",
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
        """Экран идущей рассылки: счётчики + «Остановить»."""
        title = locale.get_text("admin.broadcast.progress_title")
        remaining = max(0, broadcast.total - broadcast.sent - broadcast.failed - broadcast.blocked)
        body = locale.get_text(
            "admin.broadcast.progress_text",
            sent=broadcast.sent,
            failed=broadcast.failed,
            blocked=broadcast.blocked,
            remaining=remaining,
        )
        if broadcast.status == BroadcastStatus.CANCELLING.value:
            body = locale.get_text("admin.broadcast.cancelling_text")
        kb = locale.keyboards.build(
            "admin.broadcast",
            exclude=["start", "confirm", "cancel", "resume"],
        )
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
        """Экран результата последней рассылки.

        Для прерванной (``interrupted``) показывает «Продолжить».
        """
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
        exclude = ["confirm", "cancel", "refresh", "stop"]
        if broadcast.status != BroadcastStatus.INTERRUPTED.value:
            exclude.append("resume")
        kb = locale.keyboards.build("admin.broadcast", exclude=exclude)
        await UIManager.show(
            event=event,
            text=f"{title}\n\n{body}",
            reply_markup=kb,
            message_id_to_edit=message_id_to_edit,
        )

