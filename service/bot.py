import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, \
    BotCommandScopeDefault
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from service.database import Database
from service.bot_generator import BotLogicGenerator
from service.welcome_survey import register_welcome_survey

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("it-ai-community-bot")

# Создаем роутер для обработчиков
router = Router()

# Состояния FSM
class UserStates(StatesGroup):
    waiting_for_suggestion = State()
    waiting_for_participant_type = State()

class CommunityBot:
    def __init__(self):
        self.db = Database()
        self.bot_generators = {}  # Кэш для генераторов опросов
    
    def get_survey_generator(self, scenario_file: str) -> BotLogicGenerator:
        """Получение или создание генератора опроса"""
        if scenario_file not in self.bot_generators:
            templates_path = os.getenv('TEMPLATES_PATH')
            template_path = os.path.join(templates_path, scenario_file)
            self.bot_generators[scenario_file] = BotLogicGenerator(template_path)
        return self.bot_generators[scenario_file]
    
    async def start_command(self, message: Message):
        """Обработчик команды /start"""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user:
            # Создаем нового пользователя
            user = self.db.create_user(
                telegram_id=telegram_id,
                username=message.from_user.username,
                name=message.from_user.full_name
            )
        
        # Устанавливаем админские команды для суперпользователей
        if user.is_superuser:
            try:
                await self.set_admin_commands(message.bot, telegram_id)
            except Exception as e:
                logger.error(f"Ошибка установки админских команд для {telegram_id}: {e}")
        
        # Приветственное сообщение
        welcome_text = f"Приветствую, {message.from_user.first_name or 'пользователь'}!"
        if user.is_superuser:
            welcome_text += "\n\n🔧 <b>Режим администратора активен</b>"
        
        # Создаем inline кнопки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Пройти вводный опрос", callback_data="intro_survey")],
            [InlineKeyboardButton(text="ℹ️ Справка", callback_data="show_capabilities")]
        ])
        
        await message.answer(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
    async def events_command(self, message: Message):
        """Обработчик команды /events"""
        events = self.db.get_active_events()
        
        if not events:
            await message.answer("В данный момент нет доступных мероприятий.")
            return
        
        # Создаем кнопки для каждого события
        keyboard_buttons = []
        for event in events:
            keyboard_buttons.append([InlineKeyboardButton(
                text=event.name, 
                callback_data=f"event_{event.id}"
            )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer("Доступные мероприятия:", reply_markup=keyboard)
    
    async def surveys_command(self, message: Message):
        """Обработчик команды /surveys"""
        surveys = self.db.get_active_surveys()
        
        if not surveys:
            await message.answer("В данный момент нет доступных опросов.")
            return
        
        # Создаем кнопки для каждого опроса
        keyboard_buttons = []
        for survey in surveys:
            keyboard_buttons.append([InlineKeyboardButton(
                text=survey.name, 
                callback_data=f"survey_{survey.slug}"
            )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer("Доступные опросы:", reply_markup=keyboard)
    
    async def myevents_command(self, message: Message):
        """Обработчик команды /myevents"""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user:
            await message.answer("Пользователь не найден.")
            return
        
        registrations = self.db.get_user_registrations(user.id)
        
        if not registrations:
            await message.answer("Вы не зарегистрированы ни на одно мероприятие.")
            return
        
        # Формируем список регистраций
        events_text = "Ваши мероприятия:\n\n"
        for event, participant_type in registrations:
            events_text += f"📍 {event.name}\n"
            events_text += f"📅 {event.start_date.strftime('%d.%m.%Y %H:%M')} - {event.end_date.strftime('%d.%m.%Y %H:%M')}\n"
            events_text += f"👤 Тип участия: {participant_type}\n\n"
        
        await message.answer(events_text)
    
    async def suggest_command(self, message: Message, state: FSMContext):
        """Обработчик команды /suggest"""
        await message.answer("Пожалуйста, введите ваш вопрос или предложение:")
        await state.set_state(UserStates.waiting_for_suggestion)
    
    async def onoff_notify_command(self, message: Message):
        """Обработчик команды /onoff_notify"""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user:
            await message.answer("Пользователь не найден.")
            return
        
        # Инвертируем настройку уведомлений
        new_setting = not user.is_allow_notify
        self.db.update_user_notify_settings(telegram_id, new_setting)
        
        status = "включены" if new_setting else "отключены"
        await message.answer(f"Уведомления {status}.")
    
    async def offbot_command(self, message: Message):
        """Обработчик команды /offbot"""
        telegram_id = str(message.from_user.id)
        
        # Удаляем пользователя
        if self.db.delete_user(telegram_id):
            await message.answer("Ваши данные удалены. Бот отключен.")
        else:
            await message.answer("Ошибка при удалении данных.")
    
    async def event_registrations_command(self, message: Message):
        """Обработчик команды /event_registrations (только для суперпользователей)"""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user or not user.is_superuser:
            await message.answer("У вас нет прав доступа к этой команде.")
            return
        
        registrations = self.db.get_all_event_registrations()
        
        if not registrations:
            await message.answer("Нет регистраций на активные мероприятия.")
            return
        
        # Группируем регистрации по событиям
        events_dict = {}
        for event, user_reg, participant_type, registration_date in registrations:
            if event.id not in events_dict:
                events_dict[event.id] = {
                    'event': event,
                    'registrations': []
                }
            events_dict[event.id]['registrations'].append((user_reg, participant_type, registration_date))
        
        # Отправляем отчет по частям
        current_part = "📊 <b>Регистрации на активные мероприятия:</b>\n\n"
        
        for event_data in events_dict.values():
            event = event_data['event']
            registrations_list = event_data['registrations']
            
            event_text = f"📅 <b>{event.name}</b>\n"
            event_text += f"🗓 {event.start_date.strftime('%d.%m.%Y %H:%M')} - {event.end_date.strftime('%d.%m.%Y %H:%M')}\n"
            event_text += f"👥 Всего регистраций: {len(registrations_list)}\n\n"
            
            # Группируем по типам участников
            participants_by_type = {}
            for user_reg, participant_type, reg_date in registrations_list:
                if participant_type not in participants_by_type:
                    participants_by_type[participant_type] = []
                participants_by_type[participant_type].append((user_reg, reg_date))
            
            for participant_type, users_list in participants_by_type.items():
                event_text += f"<b>{participant_type.title()}:</b>\n"
                for user_reg, reg_date in users_list:
                    name = user_reg.name or "Не указано"
                    username = f"@{user_reg.username}" if user_reg.username else "нет username"
                    event_text += f"• {name} ({username}) - {reg_date.strftime('%d.%m.%Y %H:%M')}\n"
                event_text += "\n"
            
            event_text += "─" * 30 + "\n\n"
            
            # Если добавление этого события превысит лимит, отправляем текущую часть
            if len(current_part + event_text) > 4096:
                await message.answer(current_part, parse_mode=ParseMode.HTML)
                current_part = "📊 <b>Регистрации на активные мероприятия (продолжение):</b>\n\n" + event_text
            else:
                current_part += event_text
        
        # Отправляем оставшуюся часть
        if current_part.strip():
            await message.answer(current_part, parse_mode=ParseMode.HTML)
    
    async def handle_suggestion(self, message: Message, state: FSMContext):
        """Обработчик предложений пользователей"""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user:
            await message.answer("Пользователь не найден.")
            await state.clear()
            return
        
        suggestion_text = f"💡 Новое предложение/вопрос\n\n"
        suggestion_text += f"От: {message.from_user.full_name} (@{message.from_user.username})\n"
        suggestion_text += f"ID: {telegram_id}\n\n"
        suggestion_text += f"Сообщение:\n{message.text}"
        
        # Отправляем суперпользователям
        superusers = self.db.get_superusers()
        for superuser in superusers:
            try:
                await message.bot.send_message(superuser.telegram_id, suggestion_text)
            except Exception as e:
                logger.error(f"Ошибка отправки предложения суперпользователю {superuser.telegram_id}: {e}")
        
        await message.answer("Спасибо за ваше предложение! Мы рассмотрим его.")
        await state.clear()
    
    async def handle_event_callback(self, callback: CallbackQuery):
        parts = callback.data.split('_')
        if len(parts) != 2 or not parts[1].isdigit():
            await callback.answer("Некорректный callback.")
            return
        event_id = int(parts[1])
        event = self.db.get_event_by_id(event_id)
        
        if not event:
            await callback.answer("Событие не найдено.")
            return
        
        # Формируем информацию о событии
        event_text = f"📍📢 {event.name}\n\n"
        event_text += f"📅 Начало: {event.start_date.strftime('%d.%m.%Y %H:%M')}\n"
        event_text += f"📅 Окончание: {event.end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
        if event.count_places:
            event_text += f"👥 Количество мест: {event.count_places}\n"
        if event.price_per_user:
            event_text += f"💰 Стоимость участия: {event.price_per_user}₽\n"
        event_text += f"📝 Описание:\n{event.description}"
        
        # Получаем кнопки для события
        buttons = self.db.get_event_buttons(event_id)
        
        if buttons:
            keyboard_buttons = []
            for button in buttons:
                keyboard_buttons.append([InlineKeyboardButton(
                    text=button.title, 
                    callback_data=f"event_action_{event_id}_{button.type}"
                )])
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        else:
            keyboard = None
        
        await callback.message.edit_text(event_text, reply_markup=keyboard)
        await callback.answer()
    
    async def handle_event_action(self, callback: CallbackQuery):
        print(f"handle_event_action: {callback.data}")
        parts = callback.data.split('_')
        if len(parts) < 4 or parts[0] != 'event' or parts[1] != 'action' or not parts[2].isdigit():
            await callback.answer("Некорректный callback.")
            return
        event_id = int(parts[2])
        action_type = parts[3]
        
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user:
            await callback.answer("Пользователь не найден.")
            return
        
        if action_type == "registration":
            # Показываем выбор типа участия
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Участник", callback_data=f"register_{event_id}_участник")],
                [InlineKeyboardButton(text="Спикер", callback_data=f"register_{event_id}_спикер")],
                [InlineKeyboardButton(text="Организатор", callback_data=f"register_{event_id}_организатор")]
            ])
            await callback.message.edit_text("В качестве кого вы хотите зарегистрироваться?", reply_markup=keyboard)
        
        elif action_type == "unregister":
            # Отменяем регистрацию
            if self.db.unregister_user_from_event(user.id, event_id):
                await callback.message.edit_text("Регистрация отменена.")
            else:
                await callback.message.edit_text("Ошибка при отмене регистрации.")
        
        await callback.answer()
    
    async def handle_registration(self, callback: CallbackQuery):
        print(f"handle_registration: {callback.data}")
        parts = callback.data.split('_')
        if len(parts) != 3 or parts[0] != 'register' or not parts[1].isdigit():
            await callback.answer("Некорректный callback.")
            return
        event_id = int(parts[1])
        participant_type = parts[2]
        
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        
        if not user:
            await callback.answer("Пользователь не найден.")
            return
        
        # Регистрируем пользователя
        if self.db.register_user_for_event(user.id, event_id, participant_type):
            if participant_type == "лист ожидания":
                await callback.message.edit_text("Вы добавлены в лист ожидания.")
            else:
                await callback.message.edit_text(f"Вы успешно зарегистрированы как {participant_type}!")
        else:
            await callback.message.edit_text("Ошибка при регистрации или вы уже зарегистрированы.")
        
        await callback.answer()
    
    async def handle_survey_callback(self, callback: CallbackQuery, state: FSMContext):
        """Обработчик выбора опроса"""
        survey_slug = callback.data.split('_')[1]
        survey = self.db.get_survey_by_slug(survey_slug)
        
        if not survey:
            await callback.answer("Опрос не найден.")
            return
        
        # Очищаем предыдущее состояние FSM (важно для изоляции welcome FSM)
        await state.clear()
        
        # Запускаем опрос
        try:
            generator = self.get_survey_generator(survey.scenario_file)
            
            # Запускаем первый шаг опроса
            first_step = generator.steps[0]
            keyboard = generator._build_keyboard(first_step.get('keyboard'))
            await callback.message.edit_text(first_step['message'], reply_markup=keyboard)
            await state.set_state(getattr(generator.states_group, 'step_0'))
            
            # Сохраняем информацию об опросе в контексте
            await state.update_data(survey_slug=survey_slug, survey_name=survey.name)
            
        except Exception as e:
            logger.error(f"Ошибка запуска опроса: {e}")
            await callback.message.edit_text("Ошибка при запуске опроса.")
        
        await callback.answer()
    
    async def handle_show_capabilities(self, callback: CallbackQuery):
        """Обработчик показа возможностей"""
        capabilities_text = """
🤖 <b>Возможности бота:</b>

📅 <b>/events</b> - Просмотр доступных мероприятий и регистрация на них

📊 <b>/surveys</b> - Участие в опросах сообщества

📋 <b>/myevents</b> - Ваши зарегистрированные мероприятия

💡 <b>/suggest</b> - Отправить вопрос или предложение администрации

🔔 <b>/onoff_notify</b> - Включить/отключить уведомления

❌ <b>/offbot</b> - Отключить бота и удалить данные
        """
        
        await callback.message.edit_text(capabilities_text, parse_mode=ParseMode.HTML)
        await callback.answer()
    
    def _register_survey_handlers(self, router: Router):
        """Регистрация обработчиков для опросов"""
        # Регистрируем обработчики для всех известных опросов
        known_surveys = ['survey_topic_meeting.yaml']
        
        for survey_file in known_surveys:
            try:
                generator = self.get_survey_generator(survey_file)
                generator.register_handlers(router)
            except Exception as e:
                logger.error(f"Ошибка регистрации обработчиков для {survey_file}: {e}")
    
    def register_handlers(self, router: Router):
        """Регистрация всех обработчиков"""
        bot_instance = self
        
        # Команды
        router.message.register(bot_instance.start_command, Command("start"))
        router.message.register(bot_instance.events_command, Command("events"))
        router.message.register(bot_instance.surveys_command, Command("surveys"))
        router.message.register(bot_instance.myevents_command, Command("myevents"))
        router.message.register(bot_instance.suggest_command, Command("suggest"))
        router.message.register(bot_instance.onoff_notify_command, Command("onoff_notify"))
        router.message.register(bot_instance.offbot_command, Command("offbot"))
        router.message.register(bot_instance.event_registrations_command, Command("event_registrations"))
        
        # Обработка предложений
        router.message.register(bot_instance.handle_suggestion, StateFilter(UserStates.waiting_for_suggestion))
        
        # Callback обработчики (порядок важен!)
        router.callback_query.register(bot_instance.handle_registration, F.data.startswith("register_"))
        router.callback_query.register(bot_instance.handle_event_action, F.data.startswith("event_action_"))
        router.callback_query.register(bot_instance.handle_event_callback, F.data.startswith("event_"))
        router.callback_query.register(bot_instance.handle_survey_callback, F.data.startswith("survey_"))
        router.callback_query.register(bot_instance.handle_show_capabilities, F.data == "show_capabilities")
        
        # Регистрируем обработчики опросов динамически
        self._register_survey_handlers(router)
        # Подключаем кастомный welcome-опрос
        register_welcome_survey(router)

    async def set_commands(self, bot):
        """Set bot commands."""
        # Команды для обычных пользователей
        user_commands = [
            BotCommand(command='start', description='Старт и приветствие'),
            BotCommand(command='events', description='Доступные мероприятия'),
            BotCommand(command='surveys', description='Опросы сообщества'),
            BotCommand(command='myevents', description='Мои мероприятия'),
            BotCommand(command='suggest', description='Предложение/вопрос'),
            BotCommand(command='onoff_notify', description='Уведомления вкл/выкл'),
            BotCommand(command='offbot', description='Отключить бота'),
        ]
        await bot.set_my_commands(user_commands, BotCommandScopeDefault())
    
    async def set_admin_commands(self, bot, telegram_id: str):
        """Set admin commands for superuser."""
        from aiogram.types import BotCommandScopeChat
        
        admin_commands = [
            BotCommand(command='start', description='Старт и приветствие'),
            BotCommand(command='events', description='Доступные мероприятия'),
            BotCommand(command='surveys', description='Опросы сообщества'),
            BotCommand(command='myevents', description='Мои мероприятия'),
            BotCommand(command='event_registrations', description='📊 Регистрации на события'),
        ]
        await bot.set_my_commands(admin_commands, BotCommandScopeChat(chat_id=int(telegram_id)))

def run_bot():
    """Запуск бота."""
    # Создаем бота и диспетчер
    bot = Bot(
        token=os.getenv('TELEGRAM_TOKEN'), 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Создаем экземпляр бота и регистрируем обработчики
    community_bot = CommunityBot()
    community_bot.register_handlers(router)
    
    # Устанавливаем команды бота
    async def set_commands():
        await community_bot.set_commands(bot)
        
        # Устанавливаем админские команды для всех суперпользователей
        try:
            superusers = community_bot.db.get_superusers()
            for superuser in superusers:
                await community_bot.set_admin_commands(bot, superuser.telegram_id)
        except Exception as e:
            logger.error(f"Ошибка установки админских команд при старте: {e}")
    
    # Регистрируем роутер
    dp.include_router(router)
    
    # Устанавливаем команды при старте
    dp.startup.register(set_commands)
    
    # Запускаем бота
    dp.run_polling(bot)