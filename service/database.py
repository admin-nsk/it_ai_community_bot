import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("it-ai-community-bot")

@dataclass
class User:
    id: Optional[int]
    telegram_id: str
    username: Optional[str]
    name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    is_superuser: bool
    is_allow_notify: bool
    is_active: bool
    is_blocked: bool

@dataclass
class Survey:
    id: Optional[int]
    slug: str
    name: str
    scenario_file: str
    created_at: datetime
    updated_at: Optional[datetime]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    is_enabled: bool

@dataclass
class Event:
    id: Optional[int]
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    price_per_user: int
    total_price: int
    count_places: int
    is_active: bool

@dataclass
class Button:
    id: Optional[int]
    title: str
    type: str
    next_state: Optional[int]

@dataclass
class EventRegistration:
    id: Optional[int]
    user_id: int
    event_id: int
    type_of_participant: str
    created_at: datetime
    updated_at: Optional[datetime]

class Database:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Создание таблицы пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id VARCHAR(100) NOT NULL UNIQUE,
                    username VARCHAR(200),
                    name VARCHAR(200),
                    phone VARCHAR(50),
                    email VARCHAR(50),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    is_superuser BOOLEAN DEFAULT FALSE,
                    is_allow_notify BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_blocked BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Создание таблицы опросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS surveys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug VARCHAR(500) NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    scenario_file TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    is_enabled BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Создание таблицы уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(2000) NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    send_time TIMESTAMP,
                    status VARCHAR(10)
                )
            ''')
            
            # Создание таблицы мероприятий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(2000) NOT NULL,
                    description TEXT NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    total_price INTEGER NOT NULL,
                    price_per_user INTEGER NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    count_places INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Создание таблицы кнопок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS buttons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(200),
                    type VARCHAR(20) NOT NULL,
                    next_state INTEGER
                )
            ''')
            
            # Создание таблицы кнопок событий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS event_buttons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    button_id INTEGER NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(id),
                    FOREIGN KEY (button_id) REFERENCES buttons(id)
                )
            ''')
            
            # Создание таблицы регистраций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS event_registration (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    type_of_participant VARCHAR(20) DEFAULT 'участник',
                    is_paid BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (event_id) REFERENCES events(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_niche (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    niche VARCHAR(200) NOT NULL,
                    is_leader BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            
            conn.commit()
    
    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """Получение пользователя по telegram_id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, telegram_id, username, name, phone, email, description,
                       created_at, updated_at, is_superuser, is_allow_notify, is_active, is_blocked
                FROM users WHERE telegram_id = ?
            ''', (telegram_id,))
            
            row = cursor.fetchone()
            if row:
                return User(
                    id=row[0], telegram_id=row[1], username=row[2], name=row[3],
                    phone=row[4], email=row[5], description=row[6],
                    created_at=datetime.fromisoformat(row[7]),
                    updated_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    is_superuser=bool(row[9]), is_allow_notify=bool(row[10]),
                    is_active=bool(row[11]), is_blocked=bool(row[12])
                )
            return None
    
    def create_user(self, telegram_id: str, username: Optional[str] = None, 
                   name: Optional[str] = None, phone: Optional[str] = None) -> User:
        """Создание нового пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (telegram_id, username, name, phone)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, username, name, phone))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            return User(
                id=user_id, telegram_id=telegram_id, username=username,
                name=name, phone=phone, email=None, description=None,
                created_at=datetime.now(), updated_at=None,
                is_superuser=False, is_allow_notify=False,
                is_active=True, is_blocked=False
            )
    
    def update_user_notify_settings(self, telegram_id: str, is_allow_notify: bool) -> bool:
        """Обновление настроек уведомлений пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET is_allow_notify = ?, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (is_allow_notify, telegram_id))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_user(self, telegram_id: str) -> bool:
        """Удаление пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE telegram_id = ?', (telegram_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_active_events(self) -> List[Event]:
        """Получение активных событий"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, start_date, end_date, count_places, is_active, price_per_user, total_price
                FROM events 
                WHERE is_active = TRUE
                ORDER BY start_date
            ''')
            
            events = []
            for row in cursor.fetchall():
                events.append(Event(
                    id=row[0], name=row[1], description=row[2],
                    start_date=datetime.fromisoformat(row[3]),
                    end_date=datetime.fromisoformat(row[4]),
                    price_per_user=row[7], total_price=row[8],
                    count_places=row[7], is_active=bool(row[8])
                ))
            return events
    
    def get_event_by_id(self, event_id: int) -> Optional[Event]:
        """Получение события по ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, start_date, end_date, count_places, is_active, price_per_user, total_price
                FROM events WHERE id = ?
            ''', (event_id,))
            
            row = cursor.fetchone()
            if row:
                return Event(
                    id=row[0], name=row[1], description=row[2],
                    start_date=datetime.fromisoformat(row[3]),
                    end_date=datetime.fromisoformat(row[4]),
                    count_places=row[5], is_active=bool(row[6]),
                    price_per_user=row[7], total_price=row[8],
                )
            return None
    
    def get_event_buttons(self, event_id: int) -> List[Button]:
        """Получение кнопок для события"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT b.id, b.title, b.type, b.next_state
                FROM buttons b
                JOIN event_buttons eb ON b.id = eb.button_id
                WHERE eb.event_id = ?
            ''', (event_id,))
            
            buttons = []
            for row in cursor.fetchall():
                buttons.append(Button(
                    id=row[0], title=row[1], type=row[2], next_state=row[3]
                ))
            return buttons
    
    def get_user_registrations(self, user_id: int) -> List[Tuple[Event, str]]:
        """Получение регистраций пользователя на события"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.id, e.name, e.description, e.start_date, e.end_date, 
                       e.count_places, e.is_active, er.type_of_participant, e.price_per_user, e.total_price
                FROM events e
                JOIN event_registration er ON e.id = er.event_id
                WHERE er.user_id = ?
                ORDER BY e.start_date
            ''', (user_id,))
            
            registrations = []
            for row in cursor.fetchall():
                event = Event(
                    id=row[0], name=row[1], description=row[2],
                    start_date=datetime.fromisoformat(row[3]),
                    end_date=datetime.fromisoformat(row[4]),
                    count_places=row[5], is_active=bool(row[6]),
                    price_per_user=row[8], total_price=row[9],
                )
                registrations.append((event, row[7]))
            return registrations
    
    def get_event_registration_count(self, event_id: int) -> int:
        """Получение количества регистраций на событие"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM event_registration 
                WHERE event_id = ? AND type_of_participant != 'лист ожидания'
            ''', (event_id,))
            
            return cursor.fetchone()[0]
    
    def register_user_for_event(self, user_id: int, event_id: int, 
                              participant_type: str) -> bool:
        """Регистрация пользователя на событие"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Проверяем, не зарегистрирован ли уже пользователь
            cursor.execute('''
                SELECT id FROM event_registration 
                WHERE user_id = ? AND event_id = ?
            ''', (user_id, event_id))
            
            if cursor.fetchone():
                return False  # Уже зарегистрирован
            
            # Проверяем количество мест
            event = self.get_event_by_id(event_id)
            if not event:
                return False
            
            current_count = self.get_event_registration_count(event_id)
            
            # Если мест нет, добавляем в лист ожидания
            if current_count >= event.count_places:
                participant_type = 'лист ожидания'
            
            cursor.execute('''
                INSERT INTO event_registration (user_id, event_id, type_of_participant)
                VALUES (?, ?, ?)
            ''', (user_id, event_id, participant_type))
            
            conn.commit()
            return True
    
    def unregister_user_from_event(self, user_id: int, event_id: int) -> bool:
        """Отмена регистрации пользователя на событие"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Удаляем регистрацию
            cursor.execute('''
                DELETE FROM event_registration 
                WHERE user_id = ? AND event_id = ?
            ''', (user_id, event_id))
            
            if cursor.rowcount == 0:
                return False
            
            # Проверяем, есть ли люди в листе ожидания
            cursor.execute('''
                SELECT id, user_id FROM event_registration 
                WHERE event_id = ? AND type_of_participant = 'лист ожидания'
                ORDER BY created_at ASC
                LIMIT 1
            ''', (event_id,))
            
            waiting_user = cursor.fetchone()
            if waiting_user:
                # Переводим первого из листа ожидания в участники
                cursor.execute('''
                    UPDATE event_registration 
                    SET type_of_participant = 'участник', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (waiting_user[0],))
            
            conn.commit()
            return True
    
    def get_active_surveys(self) -> List[Survey]:
        """Получение активных опросов"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, slug, name, scenario_file, created_at, updated_at,
                       start_date, end_date, is_enabled
                FROM surveys 
                WHERE (start_date IS NULL OR start_date <= CURRENT_TIMESTAMP)
                AND (end_date IS NULL OR end_date >= CURRENT_TIMESTAMP)
                AND is_enabled = TRUE
                ORDER BY created_at
            ''')
            
            surveys = []
            for row in cursor.fetchall():
                surveys.append(Survey(
                    id=row[0], slug=row[1], name=row[2], scenario_file=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    start_date=datetime.fromisoformat(row[6]) if row[6] else None,
                    end_date=datetime.fromisoformat(row[7]) if row[7] else None,
                    is_enabled=bool(row[8])
                ))
            return surveys
    
    def get_survey_by_slug(self, slug: str) -> Optional[Survey]:
        """Получение опроса по slug"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, slug, name, scenario_file, created_at, updated_at,
                       start_date, end_date, is_enabled
                FROM surveys WHERE slug = ?
            ''', (slug,))
            
            row = cursor.fetchone()
            if row:
                return Survey(
                    id=row[0], slug=row[1], name=row[2], scenario_file=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]) if row[5] else None,
                    start_date=datetime.fromisoformat(row[6]) if row[6] else None,
                    end_date=datetime.fromisoformat(row[7]) if row[7] else None,
                    is_enabled=bool(row[8])
                )
            return None
    
    def get_superusers(self) -> List[User]:
        """Получение суперпользователей"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, telegram_id, username, name, phone, email, description,
                       created_at, updated_at, is_superuser, is_allow_notify, is_active, is_blocked
                FROM users WHERE is_superuser = TRUE
            ''')
            
            users = []
            for row in cursor.fetchall():
                users.append(User(
                    id=row[0], telegram_id=row[1], username=row[2], name=row[3],
                    phone=row[4], email=row[5], description=row[6],
                    created_at=datetime.fromisoformat(row[7]),
                    updated_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    is_superuser=bool(row[9]), is_allow_notify=bool(row[10]),
                    is_active=bool(row[11]), is_blocked=bool(row[12])
                ))
            return users 

    def update_user_fields(self, telegram_id: str, **fields):
        if not fields:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in fields])
            values = list(fields.values())
            values.append(telegram_id)
            cursor.execute(f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def get_all_event_registrations(self) -> List[Tuple[Event, User, str, datetime]]:
        """Получение всех регистраций на активные события для админов"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.id, e.name, e.description, e.start_date, e.end_date, 
                       e.count_places, e.is_active, e.price_per_user, e.total_price,
                       u.id, u.telegram_id, u.username, u.name, u.phone, u.email, u.description,
                       u.created_at, u.updated_at, u.is_superuser, u.is_allow_notify, u.is_active, u.is_blocked,
                       er.type_of_participant, er.created_at
                FROM events e
                JOIN event_registration er ON e.id = er.event_id
                JOIN users u ON er.user_id = u.id
                WHERE e.is_active = TRUE
                ORDER BY e.start_date, er.created_at
            ''')
            
            registrations = []
            for row in cursor.fetchall():
                event = Event(
                    id=row[0], name=row[1], description=row[2],
                    start_date=datetime.fromisoformat(row[3]),
                    end_date=datetime.fromisoformat(row[4]),
                    count_places=row[5], is_active=bool(row[6]),
                    price_per_user=row[7], total_price=row[8],
                )
                user = User(
                    id=row[9], telegram_id=row[10], username=row[11], name=row[12],
                    phone=row[13], email=row[14], description=row[15],
                    created_at=datetime.fromisoformat(row[16]),
                    updated_at=datetime.fromisoformat(row[17]) if row[17] else None,
                    is_superuser=bool(row[18]), is_allow_notify=bool(row[19]),
                    is_active=bool(row[20]), is_blocked=bool(row[21])
                )
                participant_type = row[22]
                registration_date = datetime.fromisoformat(row[23])
                
                registrations.append((event, user, participant_type, registration_date))
            return registrations 