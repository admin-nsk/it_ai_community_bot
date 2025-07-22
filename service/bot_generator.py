import logging
import csv
import os
import pathlib
from collections import defaultdict
from typing import Dict, Any

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton
from service.parser import BotTemplateParser
import yadisk

logger = logging.getLogger("it-ai-community-bot")

class BotLogicGenerator:
    def __init__(self, template_path: str):
        self.parser = BotTemplateParser(template_path)
        self.steps = self.parser.get_steps()
        self.state_map = {step['name']: idx for idx, step in enumerate(self.steps)}
        self.csv_path = None
        self.fieldnames = [step.get('save_to_context') for step in self.steps if 'save_to_context' in step]
        self.fieldnames = list(dict.fromkeys(self.fieldnames))
        if 'user_id' not in self.fieldnames:
            self.fieldnames.insert(0, 'user_id')
        self._set_csv_path()
        
        # Создаем состояния FSM
        self.states_group = self._create_states_group()

    def _set_csv_path(self):
        self.csv_path = f'{self.parser.get_name()}.csv'

    def _create_states_group(self):
        """Создает класс состояний для FSM"""
        states_dict = {}
        for idx, step in enumerate(self.steps):
            states_dict[f'step_{idx}'] = State()
        
        return type('BotStates', (StatesGroup,), states_dict)

    def _build_keyboard(self, keyboard_cfg):
        if not keyboard_cfg:
            return None
        if keyboard_cfg['type'] == 'inline':
            buttons = [
                [InlineKeyboardButton(text=btn['text'], callback_data=btn['action'])] for btn in keyboard_cfg['buttons']
            ]
            return InlineKeyboardMarkup(inline_keyboard=buttons)
        elif keyboard_cfg['type'] == 'reply':
            buttons = [[KeyboardButton(text=btn['text'])] for btn in keyboard_cfg['buttons']]
            return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        return None

    def _save_user_data(self, user_data: dict):
        file_exists = os.path.isfile(self.csv_path)
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            if not file_exists:
                writer.writeheader()
            row = {k: user_data.get(k, '') for k in self.fieldnames}
            writer.writerow(row)

        # Загружаем на Яндекс.Диск
        try:
            y = yadisk.Client(token=os.getenv('YANDEX_DISK_TOKEN'))
            filename = pathlib.Path(self.csv_path).name
            y.upload(self.csv_path, f'/bot_feedbacks/{filename}', overwrite=True)
        except Exception as e:
            logger.error(f"Ошибка при загрузке на Яндекс.Диск: {e}")

    def _get_next_state(self, step: Dict[str, Any], callback_data: str = None) -> tuple:
        """Определяет следующее состояние и шаг"""
        next_state = None
        
        if callback_data:
            # Ищем next_state в кнопках
            keyboard_cfg = step.get('keyboard', {})
            if keyboard_cfg and keyboard_cfg.get('type') == 'inline':
                for btn in keyboard_cfg.get('buttons', []):
                    if btn.get('action') == callback_data:
                        next_state = btn.get('next_state')
                        break
        
        # Если не найдено в кнопках, берем next_state шага
        if not next_state:
            next_state = step.get('next_state')
        
        if next_state and next_state in self.state_map:
            next_idx = self.state_map[next_state]
            return f'step_{next_idx}', self.steps[next_idx]
        
        return None, None

    async def _handle_message(self, message: Message, state: FSMContext, step: Dict[str, Any], step_idx: int):
        """Обработчик текстовых сообщений"""
        user_id = message.from_user.id
        
        # Сохраняем данные в контекст
        if 'save_to_context' in step:
            await state.update_data(**{step['save_to_context']: message.text})
        await state.update_data(user_id=user_id)
        
        # Определяем следующее состояние
        next_state_name, next_step = self._get_next_state(step)
        
        if next_step is not None:
            keyboard = self._build_keyboard(next_step.get('keyboard'))
            await message.answer(next_step['message'], reply_markup=keyboard)
            await state.set_state(getattr(self.states_group, next_state_name))
        else:
            # Конец разговора
            user_data = await state.get_data()
            self._save_user_data(user_data)
            await message.answer("Спасибо за ваши ответы!")
            await state.clear()
            # --- Обновление пользователя в БД после welcome-опроса ---
            if self.parser.get_name() == "welcome":
                from service.database import Database
                db = Database()
                telegram_id = str(user_data.get("user_id"))
                name = user_data.get("name")
                contact_choice = user_data.get("contact_choice")
                phone_or_email = user_data.get("phone_or_email")
                is_allow_notify = user_data.get("is_allow_notify")
                allow_notify = True if is_allow_notify in ("Да", "yes_notify", "True", True) else False
                user = db.get_user_by_telegram_id(telegram_id)
                if user:
                    kwargs = {}
                    if name:
                        kwargs["name"] = name
                    if contact_choice == "phone" and phone_or_email:
                        kwargs["phone"] = phone_or_email
                    if contact_choice == "email" and phone_or_email:
                        kwargs["email"] = phone_or_email
                    kwargs["is_allow_notify"] = allow_notify
                    db.update_user_fields(telegram_id, **kwargs)

    async def _handle_callback(self, callback: CallbackQuery, state: FSMContext, step: Dict[str, Any], step_idx: int):
        """Обработчик callback кнопок"""
        user_id = callback.from_user.id
        callback_data = callback.data
        
        await callback.answer()
        
        # Сохраняем данные в контекст
        if 'save_to_context' in step:
            await state.update_data(**{step['save_to_context']: callback_data})
        await state.update_data(user_id=user_id)
        
        # Определяем следующее состояние
        next_state_name, next_step = self._get_next_state(step, callback_data)
        
        if next_step is not None:
            keyboard = self._build_keyboard(next_step.get('keyboard'))
            await callback.message.answer(next_step['message'], reply_markup=keyboard)
            await state.set_state(getattr(self.states_group, next_state_name))
        else:
            # Конец разговора
            user_data = await state.get_data()
            self._save_user_data(user_data)
            await callback.message.answer("Спасибо за ваши ответы!")
            await state.clear()
            # --- Обновление пользователя в БД после welcome-опроса ---
            if self.parser.get_name() == "welcome":
                from service.database import Database
                db = Database()
                telegram_id = str(user_data.get("user_id"))
                name = user_data.get("name")
                contact_choice = user_data.get("contact_choice")
                phone_or_email = user_data.get("phone_or_email")
                is_allow_notify = user_data.get("is_allow_notify")
                allow_notify = True if is_allow_notify in ("Да", "yes_notify", "True", True) else False
                user = db.get_user_by_telegram_id(telegram_id)
                if user:
                    kwargs = {}
                    if name:
                        kwargs["name"] = name
                    if contact_choice == "phone" and phone_or_email:
                        kwargs["phone"] = phone_or_email
                    if contact_choice == "email" and phone_or_email:
                        kwargs["email"] = phone_or_email
                    kwargs["is_allow_notify"] = allow_notify
                    db.update_user_fields(telegram_id, **kwargs)

    def _create_step_handler(self, step: Dict[str, Any], step_idx: int):
        """Создает обработчик для конкретного шага"""
        async def message_handler(message: Message, state: FSMContext):
            await self._handle_message(message, state, step, step_idx)
        
        async def callback_handler(callback: CallbackQuery, state: FSMContext):
            await self._handle_callback(callback, state, step, step_idx)
        
        return message_handler, callback_handler

    def register_handlers(self, router: Router):
        """Регистрирует все обработчики в роутере"""
        
        # Обработчик команды /start
        async def start_handler(message: Message, state: FSMContext):
            await state.clear()
            first_step = self.steps[0]
            keyboard = self._build_keyboard(first_step.get('keyboard'))
            await message.answer(first_step['message'], reply_markup=keyboard)
            await state.set_state(getattr(self.states_group, 'step_0'))
        
        router.message.register(start_handler, Command("start"))
        
        # Регистрируем обработчики для каждого шага
        for idx, step in enumerate(self.steps):
            state = getattr(self.states_group, f'step_{idx}')
            message_handler, callback_handler = self._create_step_handler(step, idx)
            
            # Регистрируем обработчик сообщений
            router.message.register(message_handler, StateFilter(state))
            
            # Регистрируем обработчик callback если есть inline клавиатура
            if step.get('keyboard', {}) and step.get('keyboard', {}).get('type') == 'inline':
                router.callback_query.register(callback_handler, StateFilter(state))
