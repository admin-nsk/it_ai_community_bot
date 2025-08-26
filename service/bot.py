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
from service.states import AdminSendSurveyStates

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

class AdminSendInfoStates(StatesGroup):
    choosing_action = State()
    waiting_broadcast_text = State()
    choosing_event_for_message = State()
    waiting_event_message_text = State()
    choosing_event_for_confirmation = State()

class AdminSendSurveyStates(StatesGroup):
    choosing_action = State()
    choosing_survey = State()
    choosing_event = State()
    choosing_survey_for_event = State()

class CommunityBot:
    def __init__(self):
        self.db = Database()
        self.bot_generators = {}  # Кэш для генераторов опросов
    
    def get_survey_generator(self, scenario_file: str) -> BotLogicGenerator:
        """Получение или создание генератора опроса"""
        if scenario_file not in self.bot_generators:
            templates_path = os.getenv('TEMPLATES_PATH')
            if not templates_path:
                # Если TEMPLATES_PATH не установлен, используем относительный путь
                templates_path = os.path.join(os.getcwd(), 'service', 'bot_templates')
            template_path = os.path.join(templates_path, scenario_file)
            logger.info(f"Создаем генератор для файла: {template_path}")
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

    async def send_info_command(self, message: Message, state: FSMContext):
        """Админская команда /send_info: меню выбора рассылки/подтверждений."""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await message.answer("У вас нет прав доступа к этой команде.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Информация для всех", callback_data="admin_sendinfo_all")],
            [InlineKeyboardButton(text="Информация для участников события", callback_data="admin_sendinfo_by_event")],
            [InlineKeyboardButton(text="Подтверждение участия", callback_data="admin_sendinfo_confirm")],
            [InlineKeyboardButton(text="Отправить опрос всем", callback_data="admin_send_survey_all")],
            [InlineKeyboardButton(text="Отправить опрос по событию", callback_data="admin_send_survey_by_event")]
        ])
        await state.set_state(AdminSendInfoStates.choosing_action)
        await message.answer("Выберите действие:", reply_markup=keyboard)

    async def _split_text(self, text: str, chunk_size: int = 4096):
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]

    def _to_chat_id(self, telegram_id: str):
        try:
            return int(telegram_id)
        except Exception:
            return telegram_id

    async def handle_sendinfo_action(self, callback: CallbackQuery, state: FSMContext):
        # Проверка прав
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await callback.answer("Нет прав", show_alert=True)
            return
        data = callback.data
        if data == "admin_sendinfo_all":
            await state.set_state(AdminSendInfoStates.waiting_broadcast_text)
            await callback.message.edit_text("Введите текст сообщения для всех пользователей с включёнными уведомлениями:")
        elif data == "admin_sendinfo_by_event":
            events = self.db.get_active_events()
            if not events:
                await callback.message.edit_text("Нет активных мероприятий.")
                await state.clear()
                await callback.answer()
                return
            buttons = [[InlineKeyboardButton(text=e.name, callback_data=f"as_ev_{e.id}")] for e in events]
            await state.set_state(AdminSendInfoStates.choosing_event_for_message)
            await callback.message.edit_text("Выберите событие для рассылки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        elif data == "admin_sendinfo_confirm":
            events = self.db.get_active_events()
            if not events:
                await callback.message.edit_text("Нет активных мероприятий.")
                await state.clear()
                await callback.answer()
                return
            buttons = [[InlineKeyboardButton(text=e.name, callback_data=f"admin_confirm_selectevent_{e.id}")] for e in events]
            await state.set_state(AdminSendInfoStates.choosing_event_for_confirmation)
            await callback.message.edit_text("Выберите событие для подтверждения участия:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        elif data == "admin_send_survey_all":
            surveys = self.db.get_all_surveys()
            if not surveys:
                await callback.message.edit_text("Нет доступных опросов.")
                await state.clear()
                await callback.answer()
                return
            buttons = [[InlineKeyboardButton(text=s.name, callback_data=f"admin_survey_all_{s.slug}")] for s in surveys]
            await state.set_state(AdminSendSurveyStates.choosing_survey)
            await callback.message.edit_text("Выберите опрос для отправки всем пользователям:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        elif data == "admin_send_survey_by_event":
            events = self.db.get_active_events()
            if not events:
                await callback.message.edit_text("Нет активных мероприятий.")
                await state.clear()
                await callback.answer()
                return
            buttons = [[InlineKeyboardButton(text=e.name, callback_data=f"admin_survey_event_{e.id}")] for e in events]
            await state.set_state(AdminSendSurveyStates.choosing_event)
            await callback.message.edit_text("Выберите событие для отправки опроса:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()

    async def handle_broadcast_all_text(self, message: Message, state: FSMContext):
        """Получаем текст и рассылаем всем, у кого включены уведомления."""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await message.answer("Недостаточно прав.")
            await state.clear()
            return
        text = message.text
        recipients = self.db.get_all_notifiable_users()
        sent, failed = 0, 0
        for recipient in recipients:
            try:
                chat_id = self._to_chat_id(recipient.telegram_id)
                async for chunk in self._split_text(text):
                    await message.bot.send_message(chat_id, chunk)
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Ошибка отправки пользователю {recipient.telegram_id}: {e}")
                err_text = str(e).lower()
                if 'chat not found' in err_text or 'blocked' in err_text or 'user is deactivated' in err_text:
                    try:
                        self.db.update_user_fields(recipient.telegram_id, is_blocked=True, is_allow_notify=False)
                    except Exception as _:
                        pass
        await message.answer(f"Готово. Успешно: {sent}, ошибок: {failed}.")
        await state.clear()

    async def handle_select_event_for_message(self, callback: CallbackQuery, state: FSMContext):
        # Проверка прав
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await callback.answer("Нет прав", show_alert=True)
            return
        # Универсальный парсер id события из callback_data
        try:
            event_id_str = callback.data.rsplit('_', 1)[1]
            if not event_id_str.isdigit():
                await callback.answer("Некорректный выбор.")
                return
            event_id = int(event_id_str)
        except Exception:
            await callback.answer("Некорректный выбор.")
            return
        event = self.db.get_event_by_id(event_id)
        if not event:
            await callback.answer("Событие не найдено.")
            return
        await state.update_data(selected_event_id=event_id)
        await state.set_state(AdminSendInfoStates.waiting_event_message_text)
        await callback.message.edit_text(f"Событие: {event.name}\n\nВведите текст сообщения для участников:")
        await callback.answer()

    async def handle_event_message_text(self, message: Message, state: FSMContext):
        """Получаем текст и рассылаем участникам выбранного события."""
        telegram_id = str(message.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await message.answer("Недостаточно прав.")
            await state.clear()
            return
        data = await state.get_data()
        event_id = data.get('selected_event_id')
        if not event_id:
            await message.answer("Событие не выбрано.")
            await state.clear()
            return
        recipients = self.db.get_event_registered_users(event_id)
        text = message.text
        sent, failed = 0, 0
        for recipient in recipients:
            try:
                chat_id = self._to_chat_id(recipient.telegram_id)
                async for chunk in self._split_text(text):
                    await message.bot.send_message(chat_id, chunk)
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Ошибка отправки пользователю {recipient.telegram_id}: {e}")
                err_text = str(e).lower()
                if 'chat not found' in err_text or 'blocked' in err_text or 'user is deactivated' in err_text:
                    try:
                        self.db.update_user_fields(recipient.telegram_id, is_blocked=True)
                    except Exception as _:
                        pass
        await message.answer(f"Готово. Успешно: {sent}, ошибок: {failed}.")
        await state.clear()

    async def handle_select_event_for_confirmation(self, callback: CallbackQuery, state: FSMContext):
        # Проверка прав
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await callback.answer("Нет прав", show_alert=True)
            return
        parts = callback.data.split('_')
        if len(parts) != 4 or parts[0] != 'admin' or parts[1] != 'confirm' or parts[2] != 'selectevent' or not parts[3].isdigit():
            await callback.answer("Некорректный выбор.")
            return
        event_id = int(parts[3])
        event = self.db.get_event_by_id(event_id)
        if not event:
            await callback.answer("Событие не найдено.")
            return
        recipients = self.db.get_event_registered_users(event_id)
        if not recipients:
            await callback.message.edit_text("На выбранное событие нет зарегистрированных пользователей.")
            await state.clear()
            await callback.answer()
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data=f"admin_confirm_yes_{event_id}")],
            [InlineKeyboardButton(text="Отменить", callback_data=f"admin_confirm_no_{event_id}")]
        ])
        reminder_text = (
            f"Вы зарегистрированы на мероприятие: {event.name}\n\n"
            f"Пожалуйста, подтвердите участие."
        )
        sent, failed = 0, 0
        for recipient in recipients:
            try:
                chat_id = self._to_chat_id(recipient.telegram_id)
                await callback.bot.send_message(chat_id, reminder_text, reply_markup=keyboard)
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Ошибка отправки пользователю {recipient.telegram_id}: {e}")
                err_text = str(e).lower()
                if 'chat not found' in err_text or 'blocked' in err_text or 'user is deactivated' in err_text:
                    try:
                        self.db.update_user_fields(recipient.telegram_id, is_blocked=True)
                    except Exception as _:
                        pass
        await callback.message.edit_text(f"Рассылка напоминаний завершена. Успешно: {sent}, ошибок: {failed}.")
        await state.clear()
        await callback.answer()

    async def handle_user_confirm_participation(self, callback: CallbackQuery):
        parts = callback.data.split('_')
        if len(parts) != 4 or parts[0] != 'admin' or parts[1] != 'confirm' or parts[2] != 'yes' or not parts[3].isdigit():
            await callback.answer("Некорректный выбор.")
            return
        event_id = int(parts[3])
        event = self.db.get_event_by_id(event_id)
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if event and user:
            note = (
                f"✅ Подтверждение участия\n\n"
                f"Пользователь: {user.name or ''} (@{user.username}) [id: {telegram_id}]\n"
                f"Событие: {event.name}"
            )
            for su in self.db.get_superusers():
                try:
                    await callback.bot.send_message(su.telegram_id, note)
                except Exception as e:
                    logger.error(f"Ошибка отправки суперпользователю {su.telegram_id}: {e}")
        try:
            await callback.message.edit_text("Участие подтверждено. Спасибо!")
        except Exception:
            pass
        await callback.answer("Подтверждено")

    async def handle_user_cancel_participation(self, callback: CallbackQuery):
        parts = callback.data.split('_')
        if len(parts) != 4 or parts[0] != 'admin' or parts[1] != 'confirm' or parts[2] != 'no' or not parts[3].isdigit():
            await callback.answer("Некорректный выбор.")
            return
        event_id = int(parts[3])
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        event = self.db.get_event_by_id(event_id)
        if user and event:
            # Отменяем регистрацию через существующий метод (обрабатывает лист ожидания)
            self.db.unregister_user_from_event(user.id, event_id)
            note = (
                f"❌ Отмена участия\n\n"
                f"Пользователь: {user.name or ''} (@{user.username}) [id: {telegram_id}]\n"
                f"Событие: {event.name}"
            )
            for su in self.db.get_superusers():
                try:
                    await callback.bot.send_message(su.telegram_id, note)
                except Exception as e:
                    logger.error(f"Ошибка отправки суперпользователю {su.telegram_id}: {e}")
        try:
            await callback.message.edit_text("Регистрация отменена.")
        except Exception:
            pass
        await callback.answer("Отменено")
    
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
        
        # Оставляем только активные события
        active_registrations = [(event, ptype) for event, ptype in registrations if getattr(event, 'is_active', False)]
        
        if not active_registrations:
            await message.answer("Нет активных мероприятий, на которые вы зарегистрированы.")
            return
        
        # Каждое мероприятие отдельным сообщением с кнопкой отмены
        for event, participant_type in active_registrations:
            event_text = (
                f"📍 {event.name}\n"
                f"📅 {event.start_date.strftime('%d.%m.%Y %H:%M')} - {event.end_date.strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 Тип участия: {participant_type}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Отмена регистрации", callback_data=f"event_action_{event.id}_unregister")]
            ])
            await message.answer(event_text, reply_markup=keyboard)
    
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
        logger.info(f"handle_survey_callback вызван с data: {callback.data}")
        
        try:
            survey_slug = callback.data.split('_')[1]
            logger.info(f"Извлечен survey_slug: {survey_slug}")
        except IndexError:
            logger.error(f"Не удалось извлечь survey_slug из callback.data: {callback.data}")
            await callback.answer("Ошибка: некорректные данные.")
            return
        
        survey = self.db.get_survey_by_slug(survey_slug)
        logger.info(f"Найден опрос: {survey}")
        
        if not survey:
            logger.error(f"Опрос с slug '{survey_slug}' не найден в базе данных")
            await callback.answer("Опрос не найден.")
            return
        
        # Очищаем предыдущее состояние FSM (важно для изоляции welcome FSM)
        await state.clear()
        logger.info(f"Состояние FSM очищено")
        
        # Запускаем опрос
        try:
            logger.info(f"Пытаемся создать генератор для файла: {survey.scenario_file}")
            generator = self.get_survey_generator(survey.scenario_file)
            logger.info(f"Генератор создан успешно")
            
            # Запускаем первый шаг опроса
            first_step = generator.steps[0]
            logger.info(f"Первый шаг опроса: {first_step}")
            
            keyboard = generator._build_keyboard(first_step.get('keyboard'))
            logger.info(f"Клавиатура создана: {keyboard}")
            
            await callback.message.edit_text(first_step['message'], reply_markup=keyboard)
            logger.info(f"Сообщение отправлено")
            
            await state.set_state(getattr(generator.states_group, 'step_0'))
            logger.info(f"Состояние установлено: step_0")
            
            # Сохраняем информацию об опросе в контексте
            await state.update_data(survey_slug=survey_slug, survey_name=survey.name)
            logger.info(f"Данные опроса сохранены в контексте")
            
        except Exception as e:
            logger.error(f"Ошибка запуска опроса: {e}", exc_info=True)
            await callback.message.edit_text("Ошибка при запуске опроса.")
        
        await callback.answer()



    async def handle_survey_all_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработчик выбора опроса для отправки всем пользователям"""
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await callback.answer("Нет прав", show_alert=True)
            return
        
        try:
            survey_slug = callback.data.split('_', 3)[3]
        except IndexError:
            await callback.answer("Некорректный выбор опроса.")
            return
        
        survey = self.db.get_survey_by_slug(survey_slug)
        if not survey:
            await callback.answer("Опрос не найден.")
            return
        
        # Получаем всех пользователей с включенными уведомлениями
        recipients = self.db.get_all_notifiable_users()
        if not recipients:
            await callback.message.edit_text("Нет пользователей с включенными уведомлениями.")
            await state.clear()
            await callback.answer()
            return
        
        # Отправляем опрос всем пользователям
        message_text = f"📊 Новый опрос: {survey.name}\n\nПожалуйста, пройдите опрос для улучшения нашего сообщества."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пройти опрос", callback_data=f"survey_{survey_slug}")]
        ])
        
        sent, failed = 0, 0
        for recipient in recipients:
            try:
                chat_id = self._to_chat_id(recipient.telegram_id)
                await callback.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Ошибка отправки опроса пользователю {recipient.telegram_id}: {e}")
                err_text = str(e).lower()
                if 'chat not found' in err_text or 'blocked' in err_text or 'user is deactivated' in err_text:
                    try:
                        self.db.update_user_fields(recipient.telegram_id, is_blocked=True, is_allow_notify=False)
                    except Exception as _:
                        pass
        
        await callback.message.edit_text(f"Опрос '{survey.name}' отправлен всем пользователям.\nУспешно: {sent}, ошибок: {failed}.")
        await state.clear()
        await callback.answer()

    async def handle_survey_event_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработчик выбора события для отправки опроса"""
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await callback.answer("Нет прав", show_alert=True)
            return
        
        try:
            event_id = int(callback.data.split('_', 3)[3])
        except (IndexError, ValueError):
            await callback.answer("Некорректный выбор события.")
            return
        
        event = self.db.get_event_by_id(event_id)
        if not event:
            await callback.answer("Событие не найдено.")
            return
        
        # Сохраняем выбранное событие и показываем список опросов
        await state.update_data(selected_event_id=event_id, selected_event_name=event.name)
        
        surveys = self.db.get_all_surveys()
        if not surveys:
            await callback.message.edit_text("Нет доступных опросов.")
            await state.clear()
            await callback.answer()
            return
        
        buttons = [[InlineKeyboardButton(text=s.name, callback_data=f"admin_survey_event_survey_{s.slug}")] for s in surveys]
        await state.set_state(AdminSendSurveyStates.choosing_survey_for_event)
        await callback.message.edit_text(f"Событие: {event.name}\n\nВыберите опрос для отправки участникам:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()

    async def handle_survey_event_survey_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработчик выбора опроса для конкретного события"""
        telegram_id = str(callback.from_user.id)
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user.is_superuser:
            await callback.answer("Нет прав", show_alert=True)
            return
        
        try:
            survey_slug = callback.data.split('_', 4)[4]
        except IndexError:
            await callback.answer("Некорректный выбор опроса.")
            return
        
        survey = self.db.get_survey_by_slug(survey_slug)
        if not survey:
            await callback.answer("Опрос не найден.")
            return
        
        data = await state.get_data()
        event_id = data.get('selected_event_id')
        event_name = data.get('selected_event_name')
        
        if not event_id:
            await callback.answer("Событие не выбрано.")
            return
        
        # Получаем пользователей, зарегистрированных на событие с включенными уведомлениями
        recipients = self.db.get_event_notifiable_users(event_id)
        if not recipients:
            await callback.message.edit_text("Нет участников события с включенными уведомлениями.")
            await state.clear()
            await callback.answer()
            return
        
        # Отправляем опрос участникам события
        message_text = f"📊 Опрос для участников события '{event_name}': {survey.name}\n\nПожалуйста, пройдите опрос для улучшения нашего сообщества."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пройти опрос", callback_data=f"survey_{survey_slug}")]
        ])
        
        sent, failed = 0, 0
        for recipient in recipients:
            try:
                chat_id = self._to_chat_id(recipient.telegram_id)
                await callback.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Ошибка отправки опроса пользователю {recipient.telegram_id}: {e}")
                err_text = str(e).lower()
                if 'chat not found' in err_text or 'blocked' in err_text or 'user is deactivated' in err_text:
                    try:
                        self.db.update_user_fields(recipient.telegram_id, is_blocked=True, is_allow_notify=False)
                    except Exception as _:
                        pass
        
        await callback.message.edit_text(f"Опрос '{survey.name}' отправлен участникам события '{event_name}'.\nУспешно: {sent}, ошибок: {failed}.")
        await state.clear()
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
        # Получаем список активных опросов из базы данных
        surveys = self.db.get_all_surveys()
        
        for survey in surveys:
            if survey.is_enabled:
                try:
                    generator = self.get_survey_generator(survey.scenario_file)
                    generator.register_handlers(router)
                    logger.info(f"Зарегистрированы обработчики для опроса: {survey.name} ({survey.scenario_file})")
                except Exception as e:
                    logger.error(f"Ошибка регистрации обработчиков для {survey.scenario_file}: {e}")
    
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
        router.message.register(bot_instance.send_info_command, Command("send_info"))
        router.message.register(bot_instance.event_registrations_command, Command("event_registrations"))
        
        # Обработка предложений
        router.message.register(bot_instance.handle_suggestion, StateFilter(UserStates.waiting_for_suggestion))
        # Админские FSM обработчики
        router.message.register(bot_instance.handle_broadcast_all_text, StateFilter(AdminSendInfoStates.waiting_broadcast_text))
        router.message.register(bot_instance.handle_event_message_text, StateFilter(AdminSendInfoStates.waiting_event_message_text))
        

        
        # Callback обработчики (порядок важен!)
        # Админские callback'и (строгие совпадения для корневых действий)
        router.callback_query.register(
            bot_instance.handle_select_event_for_message,
            StateFilter(AdminSendInfoStates.choosing_event_for_message),
            F.data.startswith("as_ev_")
        )
        # Совместимость со старым префиксом, если остались сообщения в истории
        router.callback_query.register(
            bot_instance.handle_select_event_for_message,
            StateFilter(AdminSendInfoStates.choosing_event_for_message),
            F.data.startswith("admin_sendinfo_selectevent_")
        )
        router.callback_query.register(bot_instance.handle_sendinfo_action, F.data == "admin_sendinfo_all")
        router.callback_query.register(bot_instance.handle_sendinfo_action, F.data == "admin_sendinfo_by_event")
        router.callback_query.register(bot_instance.handle_sendinfo_action, F.data == "admin_sendinfo_confirm")
        router.callback_query.register(bot_instance.handle_sendinfo_action, F.data == "admin_send_survey_all")
        router.callback_query.register(bot_instance.handle_sendinfo_action, F.data == "admin_send_survey_by_event")
        router.callback_query.register(bot_instance.handle_select_event_for_confirmation, F.data.startswith("admin_confirm_selectevent_"))
        router.callback_query.register(bot_instance.handle_user_confirm_participation, F.data.startswith("admin_confirm_yes_"))
        router.callback_query.register(bot_instance.handle_user_cancel_participation, F.data.startswith("admin_confirm_no_"))
        
        # Обработчики для отправки опросов
        router.callback_query.register(bot_instance.handle_survey_all_selection, StateFilter(AdminSendSurveyStates.choosing_survey), F.data.startswith("admin_survey_all_"))
        router.callback_query.register(bot_instance.handle_survey_event_selection, StateFilter(AdminSendSurveyStates.choosing_event), F.data.startswith("admin_survey_event_") & ~F.data.startswith("admin_survey_event_survey_"))
        router.callback_query.register(bot_instance.handle_survey_event_survey_selection, StateFilter(AdminSendSurveyStates.choosing_survey_for_event), F.data.startswith("admin_survey_event_survey_"))

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
            BotCommand(command='send_info', description='📣 Рассылки и подтверждения'),
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