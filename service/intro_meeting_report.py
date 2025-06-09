import os
import logging
import pandas as pd
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, \
    CallbackContext, CallbackQueryHandler
import yadisk

from service.survey import meeting_format, meeting_frequency,meeting_topics,meeting_helps, meeting_end
from service.states import STATES, SURVEY_KEYS

logger = logging.getLogger("it-ai-community-bot")



# Клавиатура для оценки
rating_keyboard = [['1', '2', '3', '4', '5']]

RATING_DATA = (
    ('1', 'rating_1'),
    ('2', 'rating_2'),
    ('3', 'rating_3'),
    ('4', 'rating_4'),
    ('5', 'rating_5'),
)

COLUMN = (
    'rating',
    'comment'
)

def _get_rating_keyboard():
    keyboard = []
    buttons = []
    for text,name in RATING_DATA:
        buttons.append(InlineKeyboardButton(text, callback_data=name))
    keyboard.append(buttons)
    return InlineKeyboardMarkup(keyboard)

async def _button_handler(update: Update, context: CallbackContext) -> int:
    query = update.callback_query  # Получаем запрос от кнопки
    await query.answer()

    for rate, button_name in RATING_DATA:
        if query.data == button_name:
            context.user_data['rating'] = rate
            return await meeting_format(update, context)
    else:
        if context.user_data.get('rating') is None:
            await update.effective_message.reply_text(
                'Пожалуйста, выберите оценку от 1 до 5.',
                reply_markup=_get_rating_keyboard()
            )
            return STATES.RATING
    return STATES.RATING

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога и запрос оценки встречи."""
    await update.message.reply_text(
        'Привет! Пожалуйста, оцените вводную встречу по шкале от 1 до 5, '
        'где 1 - совсем не понравилось, 5 - очень понравилось.',
        # reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True),
        reply_markup=_get_rating_keyboard(),
    )
    return STATES.RATING


async def rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем оценку и запрашиваем комментарий."""
    # query = update.callback_query
    # await query.answer()

    user_rating = update.message.text
    if user_rating not in ['1', '2', '3', '4', '5']:
        await update.message.reply_text(
            'Пожалуйста, выберите оценку от 1 до 5.',
            # reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True)
            reply_markup=_get_rating_keyboard()
        )
        return STATES.RATING

    # context.user_data['rating'] = user_rating
    # await update.message.reply_text(
    #     'Спасибо! Теперь, пожалуйста, напишите ваш комментарий о встрече '
    # )
    # await query.edit_message_text("Спасибо! Теперь, пожалуйста, напишите ваш комментарий о встрече")
    return STATES.SURVEY_MEETING_FORMAT


async def comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем комментарий и завершаем диалог."""
    context.user_data['comment'] = update.message.text
    await save_feedback(update, context)
    await update.message.reply_text(
        'Спасибо за ваш отзыв! Он был успешно сохранен.'
    )
    return ConversationHandler.END


async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропускаем комментарий и завершаем диалог."""
    context.user_data['comment'] = ''
    await save_feedback(update, context)
    await update.message.reply_text(
        'Спасибо за вашу оценку!'
    )
    return ConversationHandler.END


async def save_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем отзыв в CSV и загружаем на Яндекс.Диск."""
    user = update.effective_user
    feedback_data = {
        'user_id': user.id,
        'username': user.username,
        'rating': context.user_data['rating'],
        'comment': context.user_data['comment'],
        SURVEY_KEYS.meeting_topics: context.user_data[SURVEY_KEYS.meeting_topics],
        SURVEY_KEYS.meeting_format: context.user_data[SURVEY_KEYS.meeting_format],
        SURVEY_KEYS.meeting_frequency: context.user_data[SURVEY_KEYS.meeting_frequency],
        SURVEY_KEYS.meeting_help: context.user_data[SURVEY_KEYS.meeting_help],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }


    # Создаем DataFrame и сохраняем в CSV
    df = pd.DataFrame([feedback_data])
    csv_filename = 'feedback.csv'

    # Если файл существует, добавляем новые данные
    if os.path.exists(csv_filename):
        df.to_csv(csv_filename, mode='a', header=False, index=False)
    else:
        df.to_csv(csv_filename, index=False)

    # Загружаем на Яндекс.Диск
    try:
        # y = yadisk.Client(token=os.getenv('YANDEX_DISK_TOKEN'), id=os.getenv('YANDEX_APP_ID'), secret=os.getenv('YANDEX_APP_SECRET'))
        y = yadisk.Client(token=os.getenv('YANDEX_DISK_TOKEN'))
        y.upload(csv_filename, f'/bot_feedbacks/{csv_filename}', overwrite=True)
    except Exception as e:
        logger.error(f"Ошибка при загрузке на Яндекс.Диск: {e}")


def get_conversation_handler() -> ConversationHandler:
    # Добавляем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            STATES.RATING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rating),
                CallbackQueryHandler(_button_handler),
            ],
            STATES.COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment),
                CommandHandler('skip', skip_comment)
            ],
            STATES.SURVEY_MEETING_FORMAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, meeting_format),
                CommandHandler('skip', skip_comment)
            ],
            STATES.SURVEY_MEETING_TOPICS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, meeting_topics),
                CommandHandler('skip', skip_comment)
            ],
            STATES.SURVEY_MEETING_FREQUENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, meeting_frequency),
                CommandHandler('skip', skip_comment)
            ],
            STATES.SURVEY_MEETING_HELPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, meeting_helps),
                CommandHandler('skip', skip_comment)
            ],
            STATES.SURVEY_MEETING_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, meeting_end),
                CommandHandler('skip', skip_comment)
            ],
        },
        fallbacks=[],
    )
    return conv_handler