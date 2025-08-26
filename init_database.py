#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных с тестовыми данными
"""

import sqlite3
from datetime import datetime, timedelta
from service.database import Database

def init_test_data():
    """Инициализация тестовых данных"""
    db = Database()
    
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        
        # Создаем тестового суперпользователя
        # cursor.execute('''
        #     INSERT OR IGNORE INTO users (telegram_id, username, name, is_superuser, is_allow_notify)
        #     VALUES ('123456789', 'admin', 'Администратор', TRUE, TRUE)
        # ''')
        
        # Создаем тестовые опросы
        cursor.execute('''
            INSERT OR IGNORE INTO surveys (slug, name, scenario_file, is_enabled)
            VALUES 
            ('feedback_test', 'Опрос обратной связи', 'survey_topic_meeting.yaml', TRUE),
            ('everymonth_niche_meeting', 'Опрос по ежемесячной нишевой встрече', 'everymonth_niche_meeting.yaml', TRUE)
        ''')
        
        # Создаем тестовые кнопки
        cursor.execute('''
            INSERT OR IGNORE INTO buttons (title, type, next_state)
            VALUES 
            ('Регистрация', 'registration', NULL),
            ('Отмена регистрации', 'unregister', NULL),
            ('Внешняя ссылка', 'ext_link', NULL)
        ''')
        
        # Создаем тестовые события
        current_time = datetime.now()
        start_date = current_time + timedelta(days=10)
        end_date = start_date + timedelta(hours=2)
        
        cursor.execute('''
            INSERT OR IGNORE INTO events (name, description, start_date, end_date, count_places, is_active, total_price, price_per_user)
            VALUES 
            ('IT Meetup 2025', 'Встреча IT сообщества с обсуждением последних трендов', ?, ?, 50, TRUE, 1000, 50),
            ('IT Workshop', 'Практический воркшоп по для начинающих', ?, ?, 30, TRUE, 2000, 100)
        ''', (
            start_date.isoformat(), end_date.isoformat(),
            (start_date + timedelta(days=3)).isoformat(), (end_date + timedelta(days=3)).isoformat(),
        ))
        
        # Получаем ID событий и кнопок для связывания
        cursor.execute('SELECT id FROM events WHERE name = "IT Meetup 2025"')
        event1_id = cursor.fetchone()[0]
        
        cursor.execute('SELECT id FROM events WHERE name = "IT Workshop"')
        event2_id = cursor.fetchone()[0]
        
        cursor.execute('SELECT id FROM buttons WHERE title = "Регистрация"')
        reg_button_id = cursor.fetchone()[0]
        
        cursor.execute('SELECT id FROM buttons WHERE title = "Отмена регистрации"')
        unreg_button_id = cursor.fetchone()[0]
        
        # Связываем кнопки с событиями
        cursor.execute('''
            INSERT OR IGNORE INTO event_buttons (event_id, button_id)
            VALUES 
            (?, ?),
            (?, ?),
            (?, ?),
            (?, ?)
        ''', (
            event1_id, reg_button_id,
            event1_id, unreg_button_id,
            event2_id, reg_button_id,
            event2_id, unreg_button_id
        ))
        
        conn.commit()
        print("Тестовые данные успешно добавлены!")

if __name__ == '__main__':
    init_test_data() 