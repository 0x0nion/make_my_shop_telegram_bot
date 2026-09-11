# handlers/client/main.py
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from shopcrm_core.db.models import User
from shopcrm_core.db.repositories.user_repo import UserRepository
from shopcrm_bot.handlers.admin.utils import SUPPORTED_LANGUAGES
from shopcrm_bot.locales import Locale
from shopcrm_bot.ui import UIManager

logger = logging.getLogger(__name__)

client_main_router = Router()


async def show_client_main_menu(
    event: Message | CallbackQuery,
    user_repo: UserRepository,
    user: User,
    message_id_to_edit: int | None = None,
) -> None:
    """Единая точка отображения главного меню пользователя.

    Текст и медиа подгружаются из БД. Если приветствие в БД пустое, используется
    дефолтный текст из локали.
    """
    lang = user.language if user and user.language else "ru"
    locale = Locale(lang)

    text, photo_id = await user_repo.get_welcome_card(lang_code=lang)

    if not text:
        text = locale.get_text("client.user_main")

    orders_count = user.active_orders_count if user else 0
    cart_count = len(user.cart) if user and user.cart else 0

    kb = locale.keyboards
    reply_markup = kb.get_main_kb(orders=orders_count, cart=cart_count)

    await UIManager.show(
        event=event,
        text=text,
        reply_markup=reply_markup,
        photo=photo_id,
        message_id_to_edit=message_id_to_edit,
    )


@client_main_router.message(CommandStart())
async def cmd_start(
    message: Message,
    user_repo: UserRepository,
    state: FSMContext,
    user: User,
) -> None:
    # Сбрасываем только состояние FSM, сохраняя данные корзины
    # (адрес доставки, комментарий, cart_message_id)
    await state.set_state(None)

    if user and user.language:
        await show_client_main_menu(
            event=message,
            user_repo=user_repo,
            user=user
        )
    else:
        locale = Locale("en")
        kb = locale.keyboards

        await UIManager.show(
            event=message,
            text=locale.get_text("client.select_language_title"),
            # На первом запуске языка ещё нет — кнопка «Назад» не нужна.
            reply_markup=kb.get_language_keyboard(exclude=["back"]),
        )


@client_main_router.callback_query(F.data.startswith("client_main"))
async def open_main_menu(
    callback: CallbackQuery,
    user_repo: UserRepository,
    user: User,
) -> None:
    await callback.answer()
    await show_client_main_menu(
        event=callback,
        user_repo=user_repo,
        user=user,
        message_id_to_edit=callback.message.message_id,
    )


@client_main_router.callback_query(F.data.startswith("client_settings"))
async def open_settings(
    callback: CallbackQuery,
    user: User,
) -> None:
    await callback.answer()
    locale = Locale(user.language)
    kb = locale.keyboards

    await UIManager.show(
        event=callback,
        text=locale.get_text("client.select_language_title"),
        reply_markup=kb.get_language_keyboard(),
        message_id_to_edit=callback.message.message_id,
    )


@client_main_router.callback_query(F.data.startswith("lang_"))
async def select_language(
    callback: CallbackQuery,
    user_repo: UserRepository,
) -> None:
    lang_code = callback.data.split("_")[-1]

    # Валидация: разрешены только поддерживаемые языки
    if lang_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"[MAIN HANDLER] Invalid language code: {lang_code}")
        await callback.answer()
        return

    await callback.answer()

    user = await user_repo.update_language(
        user_id=callback.from_user.id,
        language=lang_code
    )

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass

    await show_client_main_menu(
        event=callback,
        user_repo=user_repo,
        user=user,
        message_id_to_edit=None,
    )