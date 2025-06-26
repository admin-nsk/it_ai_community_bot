import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from service.bot_generator import BotLogicGenerator
from service.intro_meeting_report import get_conversation_handler

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("it-ai-community-bot")

def run_bot():
    """Запуск бота."""
    # Создаем приложение
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

    # application.add_handler(get_conversation_handler())
    handler = BotLogicGenerator('/home/petrov.aleksey140/Projects/it_ai_community_bot/service/bot_templates/survey_topic_meeting.yaml')
    application.add_handler(handler.generate_conversation_handler())

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)