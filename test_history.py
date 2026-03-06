# test_history.py
from utils import load_users, save_users, add_history
from datetime import datetime

print("🔍 ТЕСТ ИСТОРИИ")
print("=" * 50)

# Загружаем пользователей
users = load_users()
print(f"📁 Загружено {len(users)} пользователей")

# Добавляем тестовую запись
test_uid = "721775329"
test_title = "🧪 **Тестовая запись**"
test_desc = "Проверка работы истории"

print(f"\n📝 Добавляем тестовую запись для {test_uid}...")
add_history(test_uid, test_title, test_desc)

# Проверяем результат
users_after = load_users()
if test_uid in users_after:
    history = users_after[test_uid].get("history", [])
    print(f"\n📊 В истории теперь {len(history)} записей:")
    for i, entry in enumerate(history):
        print(f"{i+1}. {entry.get('time')} - {entry.get('title')}")
else:
    print(f"❌ Пользователь {test_uid} не найден!")

print("=" * 50)