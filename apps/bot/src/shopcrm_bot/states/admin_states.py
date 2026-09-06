# state/admin_states.py
from aiogram.fsm.state import StatesGroup, State


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