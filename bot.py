import os
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import yadisk

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния разговора
RATING, COMMENT = range(2)

# Клавиатура для оценки
rating_keyboard = [['1', '2', '3', '4', '5']]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога и запрос оценки встречи."""
    await update.message.reply_text(
        'Привет! Пожалуйста, оцените прошедшую встречу по шкале от 1 до 5, '
        'где 1 - совсем не понравилось, 5 - очень понравилось.',
        reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return RATING


async def rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняем оценку и запрашиваем комментарий."""
    user_rating = update.message.text
    if user_rating not in ['1', '2', '3', '4', '5']:
        await update.message.reply_text(
            'Пожалуйста, выберите оценку от 1 до 5.',
            reply_markup=ReplyKeyboardMarkup(rating_keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return RATING

    context.user_data['rating'] = user_rating
    await update.message.reply_text(
        'Спасибо! Теперь, пожалуйста, напишите ваш комментарий о встрече '
        '(или отправьте /skip, если не хотите оставлять комментарий).'
    )
    return COMMENT


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


def main() -> None:
    """Запуск бота."""
    # Создаем приложение
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # Добавляем обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, rating)],
            COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, comment),
                CommandHandler('skip', skip_comment)
            ],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()