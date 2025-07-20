import os
import logging
# from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from service.bot_generator import BotLogicGenerator

# Загрузка переменных окружения
# load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("it-ai-community-bot")

# Создаем роутер для обработчиков
router = Router()

def run_bot():
    """Запуск бота."""
    # Создаем бота и диспетчер
    bot = Bot(
        token=os.getenv('TELEGRAM_TOKEN'), 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрируем роутер
    dp.include_router(router)
    
    # Создаем генератор логики бота
    handler = BotLogicGenerator('/home/petrov.aleksey140/Projects/it_ai_community_bot/service/bot_templates/survey_topic_meeting.yaml')
    handler.register_handlers(router)
    
    # Запускаем бота
    dp.run_polling(bot)