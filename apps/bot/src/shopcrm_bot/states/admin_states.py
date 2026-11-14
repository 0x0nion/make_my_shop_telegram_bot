# state/admin_states.py
from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    add_category = State()
    edit_category_description = State()


class EditProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    unit = State()
    photo = State()


class EditWelcome(StatesGroup):
    text = State()
    photo = State()


class AdminOrderState(StatesGroup):
    edit_address = State()
    edit_shipping_cost = State()
    edit_admin_comment = State()


class EditPaymentDetails(StatesGroup):
    text = State()


class WarehouseState(StatesGroup):
    """Ввод количества для операций склада (пополнение / списание)."""
    add_stock = State()
    write_off_stock = State()


class AdminUserState(StatesGroup):
    """Ввод в разделе «Юзеры»: поиск по ID и скидка в карточке."""
    find_by_id = State()
    set_discount = State()