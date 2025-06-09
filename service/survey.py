import os
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, \
    CallbackContext, CallbackQueryHandler


from service.states import STATES, SURVEY_KEYS

logger = logging.getLogger("it-ai-community-bot")



async def meeting_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога и запрос оценки встречи."""
    await update.effective_message.reply_text(
        'Какие форматы встреч и виды активности Вам интересны\n'
        '▪️Онлайн-встречи / офлайн-митапы / гостевые визиты\n'
        '▪️Экскурсии\n'
        '▪️Мастермайнды\n'
        '▪️Выступления и обмен кейсами\n'
        '▪️Конкурс идей или запуск внутренних проектов\n'
        '▪️Предложите свой вариант',
        # reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True),
        # reply_markup=_get_rating_keyboard(),
    )
    return STATES.SURVEY_MEETING_TOPICS

async def meeting_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[SURVEY_KEYS.meeting_format] = update.message.text
    await update.message.reply_text(
        'Какие темы Вам были бы интересны\n'
        '▪️Как собрать сильную dev-команду\n'
        '▪️Автоматизация бизнес-процессов\n'
        '▪️Построение архитектуры веб-сервисов\n'
        '▪️Аудит и консалтинг IT-инфраструктуры\n'
        '▪️Внедрение AI в бизнес-процессы (примеры)\n'
        '▪️AI-ассистенты: опыт, инструменты, эффективность\n'
        '▪️Предложите свой вариант\n',
        # reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True),
        # reply_markup=_get_rating_keyboard(),
    )
    return STATES.SURVEY_MEETING_FREQUENCY

async def meeting_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[SURVEY_KEYS.meeting_topics] = update.message.text
    """Начало диалога и запрос оценки встречи."""
    await update.message.reply_text(
        'Какая периодичность встреч была бы комфортна?',
        # reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True),
        # reply_markup=_get_rating_keyboard(),
    )
    return STATES.SURVEY_MEETING_HELPS

async def meeting_helps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[SURVEY_KEYS.meeting_frequency] = update.message.text
    await update.message.reply_text(
        'Готовы ли оказать какую-либо помощь в развитии направления\n'
        '▪️Помощь с организацией встреч\n'
        '▪️Выступать спикером\n'
        '▪️Кого-то привлечь извне (спикеров, экспертов, менторов)\n'
        '▪️Предложите свой вариант\n',
        # reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True),
        # reply_markup=_get_rating_keyboard(),
    )
    return STATES.SURVEY_MEETING_END

async def meeting_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data[SURVEY_KEYS.meeting_help] = update.message.text
    await update.message.reply_text(
        'Спасибо! Теперь, пожалуйста, напишите ваш комментарий о встрече '
    )
    return STATES.COMMENT