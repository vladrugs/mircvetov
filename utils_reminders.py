# utils_reminders.py
import json
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

FILE_PATH = "user_events.json"

# ------------------- Загрузка всех событий -------------------
def load_all_events():
    if not os.path.exists(FILE_PATH):
        return {}
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ------------------- Сохранение всех событий -------------------
def save_all_events(events):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2, default=str)

# ------------------- Добавление события -------------------
def save_event(user_id, name, date, reminder_settings=None):
    """Сохраняет событие с настройками напоминаний"""
    events = load_all_events()
    uid = str(user_id)
    if uid not in events:
        events[uid] = {}
    
    # Настройки напоминаний по умолчанию
    if reminder_settings is None:
        reminder_settings = {
            "7_days": True,
            "1_day": True,
            "hour": False,
            "day_of": False
        }
    
    # Сохраняем событие с полем для отслеживания отправленных напоминаний
    if isinstance(date, datetime):
        events[uid][name] = {
            "date": date.strftime("%Y-%m-%d"),
            "reminders": reminder_settings,
            "sent_reminders": {},  # Новое поле для отслеживания отправленных
            "created_at": datetime.now().isoformat()
        }
    else:
        events[uid][name] = {
            "date": str(date),
            "reminders": reminder_settings,
            "sent_reminders": {},
            "created_at": datetime.now().isoformat()
        }
    
    save_all_events(events)
    logger.info(f"✅ Событие '{name}' сохранено для пользователя {uid}")

# ------------------- Обновление настроек напоминаний -------------------
def update_reminder_settings(user_id, event_name, settings):
    """Обновляет настройки напоминаний для события"""
    events = load_all_events()
    uid = str(user_id)
    
    if uid in events and event_name in events[uid]:
        if isinstance(events[uid][event_name], dict):
            events[uid][event_name]["reminders"] = settings
        else:
            # Если старое событие (только дата), преобразуем
            old_date = events[uid][event_name]
            events[uid][event_name] = {
                "date": old_date if isinstance(old_date, str) else old_date.strftime("%Y-%m-%d"),
                "reminders": settings,
                "created_at": datetime.now().isoformat()
            }
        save_all_events(events)
        return True
    return False

# ------------------- Удаление события -------------------
def delete_event(user_id, name):
    events = load_all_events()
    uid = str(user_id)
    if uid in events and name in events[uid]:
        del events[uid][name]
        save_all_events(events)
        logger.info(f"✅ Событие '{name}' удалено для пользователя {uid}")
        return True
    return False

# ------------------- Загрузка событий пользователя -------------------
def load_user_events(user_id):
    events = load_all_events()
    uid = str(user_id)
    user_events = {}
    
    if uid in events:
        for name, event_data in events[uid].items():
            try:
                # Проверяем, является ли событие словарем (новый формат) или строкой (старый формат)
                if isinstance(event_data, dict):
                    date_str = event_data.get("date", "")
                    reminders = event_data.get("reminders", {})
                else:
                    date_str = event_data
                    reminders = {
                        "7_days": True,
                        "1_day": True,
                        "hour": False,
                        "day_of": False,
                        "custom_times": []
                    }
                
                # Парсим дату
                if ' ' in date_str:
                    date_part = date_str.split(' ')[0]
                else:
                    date_part = date_str
                
                dt = datetime.strptime(date_part, "%Y-%m-%d")
                user_events[name] = {
                    "date": dt,
                    "reminders": reminders
                }
                    
            except Exception as e:
                logger.error(f"Ошибка парсинга события '{name}': {e}")
                user_events[name] = {
                    "date": event_data,
                    "reminders": {}
                }
    
    return user_events

# ------------------- Сбор уведомлений за 3, 2, 1 день -------------------
def get_upcoming_events():
    """Собирает все события, которые нужно напомнить"""
    events = load_all_events()
    notifications = []
    today = datetime.now()
    
    for uid, user_events in events.items():
        for name, event_data in user_events.items():
            try:
                # Получаем дату и настройки
                if isinstance(event_data, dict):
                    date_str = event_data.get("date", "")
                    reminders = event_data.get("reminders", {})
                    # Получаем информацию о том, какие напоминания уже отправлены
                    sent_reminders = event_data.get("sent_reminders", {})
                else:
                    date_str = event_data
                    reminders = {
                        "7_days": True,
                        "1_day": True,
                        "hour": False,
                        "day_of": False
                    }
                    sent_reminders = {}
                
                # Парсим дату
                if ' ' in date_str:
                    date_part = date_str.split(' ')[0]
                else:
                    date_part = date_str
                
                event_date = datetime.strptime(date_part, "%Y-%m-%d")
                
                # Если событие прошло, переносим на следующий год
                if event_date < today:
                    event_date = event_date.replace(year=today.year + 1)
                
                days_left = (event_date - today).days
                hours_left = (event_date - today).seconds // 3600
                
                # Проверяем различные интервалы напоминаний
                # и убеждаемся, что они еще не были отправлены
                
                # За 7 дней
                if reminders.get("7_days", False) and days_left == 7:
                    if not sent_reminders.get("7_days"):
                        notifications.append((uid, name, days_left, "7_days", "За 7 дней"))
                        # Помечаем как отправленное
                        if isinstance(event_data, dict):
                            if "sent_reminders" not in event_data:
                                event_data["sent_reminders"] = {}
                            event_data["sent_reminders"]["7_days"] = True
                
                # За 1 день
                if reminders.get("1_day", False) and days_left == 1:
                    if not sent_reminders.get("1_day"):
                        notifications.append((uid, name, days_left, "1_day", "Завтра"))
                        if isinstance(event_data, dict):
                            if "sent_reminders" not in event_data:
                                event_data["sent_reminders"] = {}
                            event_data["sent_reminders"]["1_day"] = True
                
                # За час
                if reminders.get("hour", False) and days_left == 0 and hours_left == 1:
                    if not sent_reminders.get("hour"):
                        notifications.append((uid, name, 0, "hour", "Через час"))
                        if isinstance(event_data, dict):
                            if "sent_reminders" not in event_data:
                                event_data["sent_reminders"] = {}
                            event_data["sent_reminders"]["hour"] = True
                
                # В день события
                if reminders.get("day_of", False) and days_left == 0 and hours_left == 0:
                    if not sent_reminders.get("day_of"):
                        notifications.append((uid, name, 0, "day_of", "Сегодня"))
                        if isinstance(event_data, dict):
                            if "sent_reminders" not in event_data:
                                event_data["sent_reminders"] = {}
                            event_data["sent_reminders"]["day_of"] = True
                
                # Сохраняем изменения
                if notifications:
                    save_all_events(events)
                    
            except Exception as e:
                print(f"Ошибка обработки события {name}: {e}")
                continue
                
    return notifications