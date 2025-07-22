# IT AI Community Bot

Бот для управления IT сообществом с поддержкой мероприятий, опросов и уведомлений.

## Возможности

- 📅 **Управление мероприятиями** - создание, регистрация участников, лист ожидания
- 📊 **Опросы** - проведение опросов с динамическими сценариями
- 👥 **Управление пользователями** - регистрация, настройки уведомлений
- 💡 **Обратная связь** - отправка предложений администрации
- 🔔 **Уведомления** - система уведомлений для пользователей

## Архитектура

### База данных (SQLite)

Бот использует SQLite базу данных со следующими таблицами:

- `users` - пользователи бота
- `events` - мероприятия
- `surveys` - опросы
- `notifications` - уведомления
- `buttons` - кнопки для интерфейса
- `event_buttons` - связь кнопок с мероприятиями
- `event_registration` - регистрации на мероприятия

### Команды бота

- `/start` - Приветствие и первичная настройка
- `/events` - Список доступных мероприятий
- `/surveys` - Доступные опросы
- `/myevents` - Ваши зарегистрированные мероприятия
- `/suggest` - Отправить предложение администрации
- `/onoff_notify` - Включить/отключить уведомления
- `/offbot` - Отключить бота и удалить данные

## Установка и запуск

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd it_ai_community_bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` с переменными окружения:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
YANDEX_DISK_TOKEN=your_yandex_disk_token
```

4. Инициализируйте базу данных с тестовыми данными:
```bash
python init_database.py
```

5. Запустите бота:
```bash
python bot.py
```

## Структура проекта

```
it_ai_community_bot/
├── bot.py                 # Главный файл запуска
├── init_database.py       # Инициализация БД
├── requirements.txt       # Зависимости
├── service/
│   ├── bot.py            # Основная логика бота
│   ├── database.py       # Работа с БД
│   ├── bot_generator.py  # Генератор опросов
│   ├── parser.py         # Парсер YAML
│   └── bot_templates/    # Шаблоны опросов
└── README.md
```

## Настройка мероприятий

Для добавления мероприятия в базу данных используйте SQL:

```sql
INSERT INTO events (name, description, start_date, end_date, count_places, is_active)
VALUES ('Название мероприятия', 'Описание', '2024-01-01 10:00:00', '2024-01-01 12:00:00', 50, TRUE);
```

## Настройка опросов

Опросы создаются через YAML файлы в папке `bot_templates/`. Пример:

```yaml
name: "Опрос обратной связи"
steps:
  - name: "welcome"
    message: "Добро пожаловать в опрос!"
    keyboard:
      type: "inline"
      buttons:
        - text: "Начать"
          action: "start_survey"
    next_state: "question_1"
  
  - name: "question_1"
    message: "Как вам мероприятие?"
    save_to_context: "feedback"
    keyboard:
      type: "inline"
      buttons:
        - text: "Отлично"
          action: "excellent"
        - text: "Хорошо"
          action: "good"
        - text: "Плохо"
          action: "bad"
```

## Разработка

### Добавление новых функций

1. Создайте новый обработчик в `service/bot.py`
2. Зарегистрируйте его в методе `register_handlers`
3. При необходимости добавьте новые таблицы в `service/database.py`

### Тестирование

Для тестирования используйте тестовые данные из `init_database.py`:

- Тестовый суперпользователь: `123456789`
- Тестовые мероприятия: "IT Meetup 2024", "Python Workshop"
- Тестовые опросы: "welcome", "feedback"

## Лицензия

MIT License 