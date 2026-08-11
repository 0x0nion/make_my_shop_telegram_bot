# state/user_states.py
from aiogram.fsm.state import StatesGroup, State


class UserState(StatesGroup):
    get_product_amount = State()
    waiting_for_address = State()
    waiting_for_comment = State()


class UserPaymentState(StatesGroup):
    waiting_for_proof = State()

