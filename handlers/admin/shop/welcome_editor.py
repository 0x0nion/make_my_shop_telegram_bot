# handlers/admin/shop/welcome_editor.py
import asyncio
import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.utils import self_destruct
from locales.locale import Locale
from src.core.ui import UIManager
from state.admin_states import EditWelcome

welcome_editor_router = Router()
logger = logging.getLogger(__name__)


async def show_welcome_card(
        event: Message | CallbackQuery,
        admin_repo: AdminRepository,
        lang: str = "ru",
        message_id_to_edit: int | None = None,
):
    """Отображение актуального приветственного сообщения и фото напрямую из постоянной базы."""
    text_val = await admin_repo.get_locale_text(
        entity_id=0,
        entity_type="welcome_message",
        language_code=lang,
        use_temp=False,
    )

    locale = Locale(lang=lang)

    if not text_val:
        text_val = locale.get_text("admin.welcome_editor.default_welcome")

    photo_id = await admin_repo.get_locale_text(
        entity_id=0,
        entity_type="welcome_photo",
        language_code=lang,
        use_temp=False,
    )
    if not photo_id or (photo_id.startswith("http") == False and len(photo_id) < 10):
        photo_id = None

    reply_markup = locale.keyboards.get_welcome_editor_kb(has_photo=bool(photo_id))

    await UIManager.show(
        event=event,
        text=text_val,
        reply_markup=reply_markup,
        photo=photo_id,
        message_id_to_edit=message_id_to_edit,
    )


@welcome_editor_router.callback_query(F.data == "admin_greeting")
async def route_welcome_card(
        callback: CallbackQuery, admin_repo: AdminRepository, user: User
):
    """Открытие меню редактора приветствия по кнопке из настроек магазина."""
    lang = user.language
    await show_welcome_card(event=callback, admin_repo=admin_repo, lang=lang)
    await callback.answer()


@welcome_editor_router.callback_query(F.data == "admin_edit_wel_text")
async def start_edit_welcome_text(
        callback: CallbackQuery, state: FSMContext, user: User
):
    """Запрос нового текста приветствия."""
    await callback.answer()
    lang = user.language
    locale = Locale(lang=lang)

    await state.set_state(EditWelcome.text)
    await state.update_data(menu_message_id=callback.message.message_id)

    prompt_text = locale.get_text("admin.welcome_editor.text")

    await UIManager.show(
        event=callback,
        text=prompt_text,
        reply_markup=None,
    )


@welcome_editor_router.callback_query(F.data == "admin_edit_wel_photo")
async def start_edit_welcome_photo(
        callback: CallbackQuery, state: FSMContext, user: User
):
    """Запрос нового фото для приветствия."""
    await callback.answer()
    lang = user.language
    locale = Locale(lang=lang)

    await state.set_state(EditWelcome.photo)
    await state.update_data(menu_message_id=callback.message.message_id)

    prompt_text = locale.get_text("admin.welcome_editor.photo")

    await UIManager.show(
        event=callback,
        text=prompt_text,
        reply_markup=None,
    )


@welcome_editor_router.callback_query(F.data == "admin_edit_wel_del_photo")
async def delete_welcome_photo(
        callback: CallbackQuery, admin_repo: AdminRepository, user: User
):
    """Удаление фото приветствия напрямую из базы."""
    lang = user.language

    for lang_code in admin_repo.SUPPORTED_LANGUAGES:
        await admin_repo.update_temp_locale(
            entity_id=0,
            entity_type="welcome_photo",
            language_code=lang_code,
            text="",
            admin_id=callback.from_user.id
        )

    await admin_repo.delete_temp_locale_for_all_languages(
        entity_id=0,
        entity_type="welcome_photo",
        admin_id=callback.from_user.id,
    )

    from sqlalchemy import delete
    from database.models import LocaleText
    await admin_repo.session.execute(
        delete(LocaleText).where(
            LocaleText.entity_id == 0,
            LocaleText.entity_type == "welcome_photo"
        )
    )
    await admin_repo.session.commit()

    await show_welcome_card(event=callback, admin_repo=admin_repo, lang=lang)
    await callback.answer()


@welcome_editor_router.message(EditWelcome.text, F.text)
async def process_welcome_text_input(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
):
    """Сохранение нового текста приветствия напрямую в постоянную БД для всех языков."""
    new_text = message.text.strip()
    user_data = await state.get_data()
    menu_message_id = user_data.get("menu_message_id")
    lang = user.language

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    for lang_code in admin_repo.SUPPORTED_LANGUAGES:
        existing = await admin_repo.get_locale_text(
            entity_id=0,
            entity_type="welcome_message",
            language_code=lang_code,
            use_temp=False,
        )
        if existing is not None:
            from sqlalchemy import update
            from database.models import LocaleText
            await admin_repo.session.execute(
                update(LocaleText)
                .where(
                    LocaleText.entity_id == 0,
                    LocaleText.entity_type == "welcome_message",
                    LocaleText.language_code == lang_code
                )
                .values(text=new_text)
            )
        else:
            from database.models import LocaleText
            admin_repo.session.add(LocaleText(
                entity_id=0,
                entity_type="welcome_message",
                language_code=lang_code,
                text=new_text
            ))
    await admin_repo.session.commit()

    await state.clear()

    if menu_message_id:
        await show_welcome_card(
            event=message,
            admin_repo=admin_repo,
            lang=lang,
            message_id_to_edit=menu_message_id,
        )


@welcome_editor_router.message(EditWelcome.photo, F.photo)
async def process_welcome_photo_input(
        message: Message,
        state: FSMContext,
        admin_repo: AdminRepository,
        user: User,
):
    """Сохранение нового фото приветствия напрямую в постоянную БД для всех языков."""
    photo_id = message.photo[-1].file_id
    user_data = await state.get_data()
    menu_message_id = user_data.get("menu_message_id")
    lang = user.language

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    for lang_code in admin_repo.SUPPORTED_LANGUAGES:
        existing = await admin_repo.get_locale_text(
            entity_id=0,
            entity_type="welcome_photo",
            language_code=lang_code,
            use_temp=False,
        )
        if existing is not None:
            from sqlalchemy import update
            from database.models import LocaleText
            await admin_repo.session.execute(
                update(LocaleText)
                .where(
                    LocaleText.entity_id == 0,
                    LocaleText.entity_type == "welcome_photo",
                    LocaleText.language_code == lang_code
                )
                .values(text=photo_id)
            )
        else:
            from database.models import LocaleText
            admin_repo.session.add(LocaleText(
                entity_id=0,
                entity_type="welcome_photo",
                language_code=lang_code,
                text=photo_id
            ))
    await admin_repo.session.commit()

    await state.clear()

    if menu_message_id:
        await show_welcome_card(
            event=message,
            admin_repo=admin_repo,
            lang=lang,
            message_id_to_edit=menu_message_id,
        )


@welcome_editor_router.message(EditWelcome.photo)
async def process_welcome_photo_invalid(message: Message, user: User):
    """Обработка неверного ввода (если прислали не фото)."""
    lang = user.language
    locale = Locale(lang=lang)
    err_msg = locale.get_text("admin.welcome_editor.not_photo")
    err = await message.answer(err_msg)
    asyncio.create_task(self_destruct(err))