import logging
import csv
import os
from collections import defaultdict

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from service.parser import BotTemplateParser
from typing import Dict, Any

logger = logging.getLogger("it-ai-community-bot")

class BotLogicGenerator:
    def __init__(self, template_path: str, csv_path: str = 'user_results.csv'):
        self.parser = BotTemplateParser(template_path)
        self.steps = self.parser.get_steps()
        self.state_map = {step['name']: idx for idx, step in enumerate(self.steps)}
        self.csv_path = csv_path
        # Формируем fieldnames один раз
        self.fieldnames = [step.get('save_to_context') for step in self.steps if 'save_to_context' in step]
        self.fieldnames = list(dict.fromkeys(self.fieldnames))  # Уникальные, порядок сохранён
        if 'user_id' not in self.fieldnames:
            self.fieldnames.insert(0, 'user_id')

    def _build_keyboard(self, keyboard_cfg):
        if not keyboard_cfg:
            return None
        if keyboard_cfg['type'] == 'inline':
            buttons = [
                [InlineKeyboardButton(btn['text'], callback_data=btn['action'])] for btn in keyboard_cfg['buttons']
            ]
            return InlineKeyboardMarkup(buttons)
        elif keyboard_cfg['type'] == 'reply':
            buttons = [[btn['text']] for btn in keyboard_cfg['buttons']]
            return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        return None

    def _save_user_data(self, user_data: dict):
        file_exists = os.path.isfile(self.csv_path)
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            if not file_exists:
                writer.writeheader()
            row = {k: user_data.get(k, '') for k in self.fieldnames}
            writer.writerow(row)

    def _make_handler(self, step: Dict[str, Any], is_callback=False):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
            user_id = update.effective_user.id if update.effective_user else None
            if is_callback and update.callback_query:
                await update.callback_query.answer()
                callback_data = update.callback_query.data
                if 'save_to_context' in step:
                    context.user_data[step['save_to_context']] = callback_data
                context.user_data['user_id'] = user_id
                # Определяем next_state из кнопки
                next_state = None
                keyboard_cfg = step.get('keyboard', {})
                if keyboard_cfg and keyboard_cfg.get('type') == 'inline':
                    for btn in keyboard_cfg.get('buttons', []):
                        if btn.get('action') == callback_data:
                            next_state = btn.get('next_state')
                            break
                # Если не найдено, fallback к next_state шага
                if not next_state:
                    next_state = step.get('next_state')
                if next_state and next_state in self.state_map:
                    next_idx = self.state_map[next_state]
                    next_step = self.steps[next_idx]
                    await update.callback_query.message.reply_text(
                        next_step['message'],
                        reply_markup=self._build_keyboard(next_step.get('keyboard'))
                    )
                    return next_idx
                self._save_user_data(context.user_data)
                return ConversationHandler.END
            else:
                if 'save_to_context' in step and update.message:
                    context.user_data[step['save_to_context']] = update.message.text
                context.user_data['user_id'] = user_id
                keyboard = self._build_keyboard(step.get('keyboard'))
                await update.message.reply_text(step['message'], reply_markup=keyboard)
                next_state = step.get('next_state')
                if next_state and next_state in self.state_map:
                    return self.state_map[next_state]
                self._save_user_data(context.user_data)
                return ConversationHandler.END
        return handler

    def _make_inline_button_handler(self, step: Dict[str, Any], is_callback=False):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id if update.effective_user else None
            # Определяем next_state из кнопки
            next_state = None
            await update.callback_query.answer()
            callback_data = update.callback_query.data
            for btn in step.get('keyboard', {}).get('buttons', []):
                if btn.get('action') == callback_data:
                    if 'save_to_context' in step:
                        context.user_data[step['save_to_context']] = callback_data
                    context.user_data['user_id'] = user_id
                    next_state = btn.get('next_state')
                    break

            # Если не найдено, fallback к next_state шага
            if not next_state:
                next_state = step.get('next_state')

            if next_state and next_state in self.state_map:
                next_idx = self.state_map[next_state]
                next_step = self.steps[next_idx]
                await update.callback_query.message.reply_text(
                    next_step['message'],
                    reply_markup=self._build_keyboard(next_step.get('keyboard'))
                )
                return next_idx
            return ConversationHandler.END
        return handler


    def generate_conversation_handler(self):
        entry_points = [CommandHandler('start', self._make_handler(self.steps[0]))]
        states = defaultdict(list)
        for idx, step in enumerate(self.steps):
            states[idx].append(MessageHandler(filters.TEXT & ~filters.COMMAND, self._make_handler(step)))
            if step.get('keyboard', {}) and step.get('keyboard', {}).get('type') == 'inline':
                states[idx].append(CallbackQueryHandler(self._make_inline_button_handler(step, is_callback=True)))
                states[idx+1].append(CallbackQueryHandler(self._make_inline_button_handler(step, is_callback=True)))

        return ConversationHandler(
            entry_points=entry_points,
            states=states,
            fallbacks=[]
        )
