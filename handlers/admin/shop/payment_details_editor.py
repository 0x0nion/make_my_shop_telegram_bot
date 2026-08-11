import logging
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import update

from database.models import LocaleText
from database.models.user import User
from database.repositories.admin_repo import AdminRepository
from handlers.admin.utils import get_user_lang
from keyboards.admin_inline import AdminInlineKb
from src.core.ui import UIManager
from state.admin_states import EditPaymentDetails

payment_details_editor_router = Router()
logger = logging.getLogger(__name__)

# Выделяем тип сущности для хранения платежных реквизитов
ENTITY_TYPE_PAYMENT_DETAILS = "payment_details"


async def show_payment_details_card(
    event: Message | CallbackQuery,
    admin_repo: AdminRepository,
    lang: str = "ru",
    message_id_to_edit: int | None = None,
):
    """Отображение карточки с текущими платежными данными."""
    text_val = await admin_repo.get_locale_text(
        entity_id=0,
        entity_type="payment_details",
        language_code=lang,
        use_temp=False,
    )

    has_text = bool(text_val and text_val.strip())

    if not has_text:
        display_text = "💳 Платежные данные еще не указаны."
    else:
        display_text = text_val

    kb = AdminInlineKb(lang=lang)
    reply_markup = kb.get_payment_details_editor_kb(has_text=has_text)

    await UIManager.show(
        event=event,
        text=display_text,
        reply_markup=reply_markup,
        message_id_to_edit=message_id_to_edit,
    )


@payment_details_editor_router.callback_query(F.data == "admin_payment_details")
async def route_payment_details_card(
    callback: CallbackQuery, admin_repo: AdminRepository, user: User
):
    """Открытие меню карточки платежных данных."""
    lang = get_user_lang(user)
    await show_payment_details_card(event=callback, admin_repo=admin_repo, lang=lang)
    await callback.answer()


@payment_details_editor_router.callback_query(F.data == "admin_edit_payment_text")
async def start_edit_payment_text(
    callback: CallbackQuery, state: FSMContext, user: User
):
    """Запрос нового текста платежных реквизитов."""
    lang = get_user_lang(user)
    kb = AdminInlineKb(lang=lang)

    await state.set_state(EditPaymentDetails.text)
    await state.update_data(menu_message_id=callback.message.message_id)

    prompt_text = kb.get_text(
        "prompts.payment_details_text",
        "✍️ Введите новые платежные реквизиты (они будут сохранены для всех языков):"
    )

    await UIManager.show(
        event=callback,
        text=prompt_text,
        reply_markup=None,
    )


@payment_details_editor_router.message(EditPaymentDetails.text, F.text)
async def process_payment_text_input(
    message: Message,
    state: FSMContext,
    admin_repo: AdminRepository,
    user: User,
):
    """Сохранение текста платежных данных в БД для всех поддерживаемых языков."""
    new_text = message.text.strip()
    user_data = await state.get_data()
    menu_message_id = user_data.get("menu_message_id")
    lang = get_user_lang(user)

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    for lang_code in admin_repo.SUPPORTED_LANGUAGES:
        existing = await admin_repo.get_locale_text(
            entity_id=0,
            entity_type=ENTITY_TYPE_PAYMENT_DETAILS,
            language_code=lang_code,
            use_temp=False,
        )
        if existing is not None:
            await admin_repo.session.execute(
                update(LocaleText)
                .where(
                    LocaleText.entity_id == 0,
                    LocaleText.entity_type == ENTITY_TYPE_PAYMENT_DETAILS,
                    LocaleText.language_code == lang_code,
                )
                .values(text=new_text)
            )
        else:
            admin_repo.session.add(
                LocaleText(
                    entity_id=0,
                    entity_type=ENTITY_TYPE_PAYMENT_DETAILS,
                    language_code=lang_code,
                    text=new_text,
                )
            )

    await admin_repo.session.commit()
    await state.clear()

    if menu_message_id:
        await show_payment_details_card(
            event=message,
            admin_repo=admin_repo,
            lang=lang,
            message_id_to_edit=menu_message_id,
        )