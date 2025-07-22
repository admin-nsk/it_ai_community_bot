from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from service.database import Database

class WelcomeSurveyStates(StatesGroup):
    ask_name = State()
    contact_choice = State()
    contact_input = State()
    notify_choice = State()
    thanks = State()

welcome_router = Router()

def register_welcome_survey(main_router: Router):
    main_router.include_router(welcome_router)

@welcome_router.callback_query(F.data == "intro_survey")
async def start_welcome_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Как к вам обращаться? Пожалуйста, введите ваше имя.")
    await state.set_state(WelcomeSurveyStates.ask_name)
    await callback.answer()

@welcome_router.message(WelcomeSurveyStates.ask_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Телефон", callback_data="phone")],
        [InlineKeyboardButton(text="Email", callback_data="email")],
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_contact")],
    ])
    await message.answer("Хотите оставить свой телефон и/или email?", reply_markup=keyboard)
    await state.set_state(WelcomeSurveyStates.contact_choice)

@welcome_router.callback_query(WelcomeSurveyStates.contact_choice, F.data.in_(["phone", "email", "skip_contact"]))
async def process_contact_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    choice = callback.data
    await state.update_data(contact_choice=choice)
    if choice == "skip_contact":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="yes_notify")],
            [InlineKeyboardButton(text="Нет", callback_data="no_notify")],
        ])
        await callback.message.answer("Хотите получать уведомления о новых мероприятиях и опросах?", reply_markup=keyboard)
        await state.set_state(WelcomeSurveyStates.notify_choice)
    else:
        text = "Пожалуйста, введите ваш телефон:" if choice == "phone" else "Пожалуйста, введите ваш email:"
        await callback.message.answer(text)
        await state.set_state(WelcomeSurveyStates.contact_input)

@welcome_router.message(WelcomeSurveyStates.contact_input)
async def process_contact_input(message: Message, state: FSMContext):
    data = await state.get_data()
    contact_choice = data.get("contact_choice")
    if contact_choice == "phone":
        await state.update_data(phone=message.text)
    elif contact_choice == "email":
        await state.update_data(email=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="yes_notify")],
        [InlineKeyboardButton(text="Нет", callback_data="no_notify")],
    ])
    await message.answer("Хотите получать уведомления о новых мероприятиях и опросах?", reply_markup=keyboard)
    await state.set_state(WelcomeSurveyStates.notify_choice)

@welcome_router.callback_query(WelcomeSurveyStates.notify_choice, F.data.in_(["yes_notify", "no_notify"]))
async def process_notify_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    allow_notify = callback.data == "yes_notify"
    await state.update_data(is_allow_notify=allow_notify)
    data = await state.get_data()
    telegram_id = str(callback.from_user.id)
    db = Database()
    user = db.get_user_by_telegram_id(telegram_id)
    kwargs = {}
    if data.get("name"):
        kwargs["name"] = data["name"]
    if data.get("phone"):
        kwargs["phone"] = data["phone"]
    if data.get("email"):
        kwargs["email"] = data["email"]
    kwargs["is_allow_notify"] = allow_notify
    if user and kwargs:
        db.update_user_fields(telegram_id, **kwargs)
    await callback.message.answer("Спасибо за прохождение вводного опроса! Добро пожаловать!")
    await state.clear() 