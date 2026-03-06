# utils.py
import json
import os
import re
from datetime import datetime
import logging
from telegram.ext import ContextTypes  # Добавьте эту строку

# Настройка логирования
logger = logging.getLogger(__name__)

USER_FILE = "users.json"

def load_users():
    """Загружает всех пользователей из файла"""
    if not os.path.exists(USER_FILE):
        return {}
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    """Сохраняет пользователей в файл"""
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def normalize_phone(phone: str):
    """Нормализует номер телефона к формату +7XXXXXXXXXX"""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if not digits.startswith("7"):
        digits = "7" + digits
    return "+" + digits

def ensure_user(users, uid, tg_user=None):
    """Гарантирует наличие пользователя в базе данных"""
    if uid not in users:
        users[uid] = {}
    u = users[uid]
    u.setdefault("tg_id", int(uid))
    u.setdefault("username", tg_user.username if tg_user else None)
    u.setdefault("name", tg_user.first_name if tg_user else None)
    u.setdefault("phone", None)
    u.setdefault("balance", 0)
    u.setdefault("total_purchases", 0)
    u.setdefault("last_reset_year", datetime.now().year)
    u.setdefault("purchases_history", [])
    u.setdefault("registered", False)
    u.setdefault("invited_by", None)
    u.setdefault("invite_rewarded", False)
    u.setdefault("history", [])
    u.setdefault("last_activity", datetime.now().isoformat())  # НОВОЕ
    u.setdefault("created_at", datetime.now().isoformat())

def add_history(uid, title, description):
    """Добавляет запись в историю пользователя"""
    users = load_users()
    ensure_user(users, uid)
    if "history" not in users[uid]:
        users[uid]["history"] = []
    
    history_entry = {
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "title": title,
        "description": description
    }
    
    users[uid]["history"].append(history_entry)
    save_users(users)
    logger.info(f"✅ Добавлена запись в историю для {uid}: {title} - {description}")

def reset_yearly_purchases():
    """Обнуляет сумму покупок за год и пересчитывает уровень"""
    users = load_users()
    current_year = datetime.now().year
    changed = False
    
    for uid, u in users.items():
        last_reset_year = u.get("last_reset_year", current_year)
        
        # Если год сменился
        if last_reset_year < current_year:
            # Сохраняем в историю покупок за прошлый год
            old_purchases = u.get("total_purchases", 0)
            if old_purchases > 0:
                # Сохраняем в историю покупок
                if "purchases_history" not in u:
                    u["purchases_history"] = []
                
                u["purchases_history"].append({
                    "year": last_reset_year,
                    "amount": old_purchases
                })
                
                # Добавляем запись в основную историю
                add_history(
                    uid,
                    "📊 **Годовой сброс**",
                    f"Покупки за {last_reset_year} год: {old_purchases} руб. Уровень обновлен"
                )
            
            # Обнуляем покупки и обновляем год
            u["total_purchases"] = 0
            u["last_reset_year"] = current_year
            changed = True
            logger.info(f"🔄 Годовой сброс для пользователя {uid}")
    
    if changed:
        save_users(users)
        logger.info(f"✅ Выполнен годовой сброс покупок для всех пользователей")
    
    return changed

def calc_level(total_purchases):
    """Рассчитывает уровень пользователя по сумме покупок за год"""
    if total_purchases >= 50000:
        return "VIP", 10, 50000  # ← порог для следующего уровня (число)
    elif total_purchases >= 25000:
        return "PLATINUM", 7, 50000
    elif total_purchases >= 10000:
        return "GOLD", 5, 25000
    elif total_purchases >= 5000:
        return "SILVER", 3, 10000
    elif total_purchases >= 1000:
        return "BRONZE", 2, 5000
    else:
        return "НАЧИНАЮЩИЙ", 1, 1000

def find_user(users, identifier):
    """Ищет пользователя по ID, username или номеру телефона"""
    identifier_norm = identifier.lower().lstrip("@")
    
    if re.match(r"^\+?\d+$", identifier):
        phone_norm = normalize_phone(identifier)
        for uid, u in users.items():
            if u.get("phone") and normalize_phone(u["phone"]) == phone_norm:
                return uid, u
    
    for uid, u in users.items():
        if str(u.get("tg_id")) == identifier or uid == identifier:
            return uid, u
    
    for uid, u in users.items():
        if u.get("username") and u["username"].lower().lstrip("@") == identifier_norm:
            return uid, u
    
    for uid, u in users.items():
        if u.get("name") and identifier_norm in u["name"].lower():
            return uid, u
    
    return None, None

def get_user_info(uid):
    users = load_users()
    uid_str = str(uid)
    return users.get(uid_str)

def get_all_users():
    return load_users()

def get_registered_users():
    users = load_users()
    return {uid: u for uid, u in users.items() if u.get("registered")}

def get_users_by_phone(phone):
    users = load_users()
    phone_norm = normalize_phone(phone)
    result = []
    for uid, u in users.items():
        if u.get("phone") and normalize_phone(u["phone"]) == phone_norm:
            result.append((uid, u))
    return result

def update_user_balance(uid, new_balance):
    users = load_users()
    uid_str = str(uid)
    if uid_str in users:
        users[uid_str]["balance"] = new_balance
        save_users(users)
        return True
    return False

def add_bonus(uid, amount, reason=""):
    users = load_users()
    uid_str = str(uid)
    if uid_str in users:
        users[uid_str]["balance"] = users[uid_str].get("balance", 0) + amount
        reason_text = f"+{amount} бонусов"
        if reason:
            reason_text += f" ({reason})"
        add_history(uid_str, "➕ **Начисление бонусов**", reason_text)
        save_users(users)
        return True
    return False

def remove_bonus(uid, amount, reason=""):
    users = load_users()
    uid_str = str(uid)
    if uid_str in users:
        current = users[uid_str].get("balance", 0)
        if current >= amount:
            users[uid_str]["balance"] = current - amount
            reason_text = f"-{amount} бонусов"
            if reason:
                reason_text += f" ({reason})"
            add_history(uid_str, "➖ **Списание бонусов**", reason_text)
            save_users(users)
            return True
    return False

def delete_user(user_id):
    users = load_users()
    uid = str(user_id)
    if uid in users:
        del users[uid]
        save_users(users)
        logger.info(f"✅ Пользователь {uid} удален из базы данных")
        return True
    return False

def get_user_stats():
    users = load_users()
    total = len(users)
    registered = sum(1 for u in users.values() if u.get("registered"))
    total_balance = sum(u.get("balance", 0) for u in users.values())
    total_purchases = sum(u.get("total_purchases", 0) for u in users.values())
    avg_balance = total_balance / total if total > 0 else 0
    
    # Статистика по уровням
    levels = {"НАЧИНАЮЩИЙ": 0, "BRONZE": 0, "SILVER": 0, "GOLD": 0, "PLATINUM": 0, "VIP": 0}
    for u in users.values():
        level, _, _ = calc_level(u.get("total_purchases", 0))
        levels[level] = levels.get(level, 0) + 1
    
    return {
        "total": total,
        "registered": registered,
        "unregistered": total - registered,
        "total_balance": total_balance,
        "total_purchases": total_purchases,
        "avg_balance": round(avg_balance, 2),
        "levels": levels
    }

def cleanup_users(days=30):
    users = load_users()
    now = datetime.now()
    deleted = 0
    
    for uid in list(users.keys()):
        u = users[uid]
        if not u.get("registered"):
            created = u.get("created_at")
            if created:
                try:
                    created_date = datetime.fromisoformat(created)
                    if (now - created_date).days > days:
                        del users[uid]
                        deleted += 1
                except:
                    pass
    
    if deleted > 0:
        save_users(users)
        logger.info(f"✅ Удалено {deleted} незарегистрированных пользователей")
    
    return deleted

def export_users_to_csv(filename="users_export.csv"):
    users = load_users()
    import csv
    
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Имя', 'Username', 'Телефон', 'Баланс', 'Покупки', 'Год', 'Уровень', 'Зарегистрирован', 'Дата создания'])
        
        for uid, u in users.items():
            balance = u.get('balance', 0)
            total_purchases = u.get('total_purchases', 0)
            year = u.get('last_reset_year', datetime.now().year)
            level, cashback, _ = calc_level(total_purchases)
            writer.writerow([
                uid,
                u.get('name', ''),
                u.get('username', ''),
                u.get('phone', ''),
                balance,
                total_purchases,
                year,
                level,
                'Да' if u.get('registered') else 'Нет',
                u.get('created_at', '')
            ])
    
    logger.info(f"✅ Экспортировано {len(users)} пользователей в {filename}")
    return filename
    
# Добавьте эту функцию в utils.py

def update_user_activity(uid):
    """Обновляет время последней активности пользователя"""
    users = load_users()
    uid_str = str(uid)
    if uid_str in users:
        users[uid_str]["last_activity"] = datetime.now().isoformat()
        save_users(users)
        return True
    return False

def get_last_activity(uid):
    """Возвращает время последней активности пользователя в читаемом формате"""
    users = load_users()
    uid_str = str(uid)
    if uid_str in users:
        last_activity = users[uid_str].get("last_activity")
        if last_activity:
            try:
                last_time = datetime.fromisoformat(last_activity)
                now = datetime.now()
                diff = now - last_time
                
                if diff.days > 0:
                    return f"был(а) {diff.days} дн. назад"
                elif diff.seconds > 3600:
                    hours = diff.seconds // 3600
                    return f"был(а) {hours} ч. назад"
                elif diff.seconds > 60:
                    minutes = diff.seconds // 60
                    return f"был(а) {minutes} мин. назад"
                else:
                    return "онлайн 🌐"
            except:
                return "неизвестно"
    return "никогда"
    
# ------------------- Проверка и уведомление о снижении уровня -------------------
async def check_level_decrease(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет пользователей, которые давно не заходили и могут потерять уровень"""
    users = load_users()
    today = datetime.now().date()
    notifications = []
    
    print(f"🔍 Проверка {len(users)} пользователей")
    
    for uid, u in users.items():
        if not u.get('registered'):
            continue
            
        # Получаем последнюю активность
        last_activity = u.get('last_activity')
        if not last_activity:
            print(f"   - Пользователь {uid}: нет last_activity")
            continue
            
        try:
            last_date = datetime.fromisoformat(last_activity).date()
            days_inactive = (today - last_date).days
            print(f"   - Пользователь {uid}: неактивен {days_inactive} дней")
            
            # Проверяем только если пользователь не был активен более 30 дней
            if days_inactive >= 30:
                current_purchases = u.get('total_purchases', 0)
                current_level, current_cashback, next_level = calc_level(current_purchases)
                
                # Если есть следующий уровень, значит можем понизиться
                if next_level:
                    # Получаем данные следующего уровня
                    if next_level == "VIP":
                        future_cashback = 10
                    elif next_level == "PLATINUM":
                        future_cashback = 7
                    elif next_level == "GOLD":
                        future_cashback = 5
                    elif next_level == "SILVER":
                        future_cashback = 3
                    elif next_level == "BRONZE":
                        future_cashback = 2
                    else:
                        future_cashback = 1
                    
                    print(f"      Текущий уровень: {current_level}, будущий: {next_level}")
                    
                    # Проверяем, отправляли ли уже уведомление
                    last_warning = u.get('last_level_warning')
                    if not last_warning:
                        print(f"      ✅ Будет отправлено предупреждение")
                        notifications.append({
                            'uid': uid,
                            'name': u.get('name', 'Пользователь'),
                            'current_level': current_level,
                            'future_level': next_level,
                            'days_inactive': days_inactive,
                            'current_cashback': current_cashback,
                            'future_cashback': future_cashback
                        })
                        
                        # Обновляем время последнего предупреждения
                        u['last_level_warning'] = datetime.now().isoformat()
                        save_users(users)
                    else:
                        print(f"      ⏰ Предупреждение уже отправлялось")
                else:
                    print(f"      👑 Максимальный уровень, понижение невозможно")
            else:
                print(f"      ✅ Активен, пропускаем")
                        
        except Exception as e:
            print(f"❌ Ошибка проверки уровня для {uid}: {e}")
            continue
    
    print(f"📊 Итого уведомлений: {len(notifications)}")
    return notifications

# ------------------- Проверка повышения уровня после покупки -------------------
async def check_level_increase(user_id: int, old_purchases: int, new_purchases: int):
    """Проверяет, повысился ли уровень после покупки"""
    old_level, old_cashback, _ = calc_level(old_purchases)
    new_level, new_cashback, _ = calc_level(new_purchases)
    
    if new_level != old_level:
        return {
            'increased': True,
            'old_level': old_level,
            'new_level': new_level,
            'old_cashback': old_cashback,
            'new_cashback': new_cashback
        }
    return {'increased': False}