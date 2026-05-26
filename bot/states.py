from aiogram.fsm.state import State, StatesGroup


class FilterSetup(StatesGroup):
    name = State()
    keywords = State()
    exclude_keywords = State()
    min_budget = State()
    max_budget = State()
    exchanges = State()
    confirm = State()


class ProfileSetup(StatesGroup):
    description = State()
    skills = State()
    experience = State()
    response_style = State()


class TemplateCreate(StatesGroup):
    title = State()
    text = State()


class AIChat(StatesGroup):
    negotiation_message = State()


class BlacklistAdd(StatesGroup):
    client_name = State()
    reason = State()


class AdminStates(StatesGroup):
    broadcast_message = State()
    broadcast_confirm = State()
    user_lookup = State()
    grant_sub_user_id = State()
    grant_sub_tier = State()
    grant_sub_months = State()
    ai_prompt = State()
