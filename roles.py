# roles.py
import json
import os

ADMIN_FILE = "admins.json"
CASHIERS_FILE = "cashiers.json"
ADMIN_ID = 721775329  # основной админ, нельзя удалить

# -------------------- Загрузка/сохранение --------------------
def load_json(file_path, default=set()):
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError):
        return default

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(list(data), f, ensure_ascii=False, indent=2)

# -------------------- Роли --------------------
admins = load_json(ADMIN_FILE, {ADMIN_ID})
cashiers = load_json(CASHIERS_FILE, set())

# -------------------- Админы --------------------
def add_admin(user_id: int):
    admins.add(user_id)
    save_json(ADMIN_FILE, admins)
    print(f"✅ Админ добавлен: {user_id}")

def remove_admin(user_id: int):
    if user_id == ADMIN_ID:
        return False  # нельзя удалить основного админа
    admins.discard(user_id)
    save_json(ADMIN_FILE, admins)
    print(f"✅ Админ удален: {user_id}")
    return True

def is_admin(user_id: int) -> bool:
    return user_id in admins

# -------------------- Кассиры --------------------
def add_cashier(user_id: int):
    cashiers.add(user_id)
    save_json(CASHIERS_FILE, cashiers)
    print(f"✅ Кассир добавлен: {user_id}")

def remove_cashier(user_id: int):
    cashiers.discard(user_id)
    save_json(CASHIERS_FILE, cashiers)
    print(f"✅ Кассир удален: {user_id}")

def is_cashier(user_id: int) -> bool:
    return user_id in cashiers

# -------------------- Функции для списков --------------------
def get_admins_list():
    """Возвращает список админов"""
    return list(admins)

def get_cashiers_list():
    """Возвращает список кассиров"""
    return list(cashiers)

def get_all_admins():
    """Возвращает список всех администраторов"""
    return list(admins)

def get_admin_details(admin_id):
    """Возвращает информацию об админе"""
    from utils import load_users
    users = load_users()
    admin_id_str = str(admin_id)
    if admin_id_str in users:
        user = users[admin_id_str]
        return {
            "id": admin_id,
            "name": user.get("name", "Неизвестно"),
            "username": user.get("username", "Нет"),
            "phone": user.get("phone", "Нет")
        }
    return {"id": admin_id, "name": "Неизвестно", "username": "Нет", "phone": "Нет"}

def get_cashier_details(cashier_id):
    """Возвращает информацию о кассире"""
    from utils import load_users
    users = load_users()
    cashier_id_str = str(cashier_id)
    if cashier_id_str in users:
        user = users[cashier_id_str]
        return {
            "id": cashier_id,
            "name": user.get("name", "Неизвестно"),
            "username": user.get("username", "Нет"),
            "phone": user.get("phone", "Нет")
        }
    return {"id": cashier_id, "name": "Неизвестно", "username": "Нет", "phone": "Нет"}