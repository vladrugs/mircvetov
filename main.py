# main.py
import os
import sys
from pathlib import Path
import warnings
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", category=PTBUserWarning)


import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Простой HTTP-сервер для Render (чтобы не было предупреждения о портах)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        # Отключаем логирование запросов
        pass

def run_health_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"💓 Health check server running on port {port}")
    server.serve_forever()

# Запускаем в отдельном потоке
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()

# Определяем путь для файлов данных
if os.environ.get('RENDER'):
    # На Render используем /tmp для временных файлов
    DATA_DIR = '/tmp/data'
else:
    # Локально используем текущую папку
    DATA_DIR = '.'

# Создаем папку для данных если её нет
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# Аналогично для других файлов...

import logging
import datetime
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, CallbackQueryHandler
)

# Импортируем из handlers.py
from handlers import (
    start, handle_contact, balance, invite, contacts,
    show_history, show_qr, back_to_menu, get_register_customer_conv,
    handle_back_to_menu, any_message_to_menu,
    check_balance_callback, history_callback, test_history,
    open_admin_menu  # 👈 ДОБАВЛЯЕМ ЭТОТ ИМПОРТ
)

# Импортируем из admin.py
from admin import get_admin_conv  # 👈 ТОЛЬКО get_admin_conv, НЕ admin_menu
from roles import admins
from utils_reminders import get_upcoming_events
from utils import reset_yearly_purchases

# Импортируем из debug_events.py
from debug_events import conv_events

# Импортируем из cashier_payment.py
from cashier_payment import cashier_conv_handler, payment_callback_handler

# Импортируем из ratings.py
from ratings import ratings_conv

# Импорты для уведомлений об уровнях
from level_notifications import send_level_decrease_warning
from utils import check_level_decrease

# ------------------- Фоновая задача уведомлений -------------------
async def reminders_job(context):
    notifications = get_upcoming_events()
    for user_id, name, days_left, reminder_type, label in notifications:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=f"⏰ **Напоминание:** '{name}'\n{label}",
            parse_mode='Markdown'
        )

# ------------------- Фоновая задача годового сброса -------------------
async def yearly_reset_job(context):
    """Ежедневная проверка для годового сброса"""
    reset_yearly_purchases()

# ------------------- Фоновая задача проверки уровней -------------------
async def level_check_job(context):
    """Ежедневная проверка уровней пользователей"""
    print(f"🔍 Запуск проверки уровней в {datetime.datetime.now()}")
    
    # Получаем список пользователей для предупреждения
    notifications = await check_level_decrease(context)
    print(f"📊 Найдено уведомлений: {len(notifications)}")
    
    # Отправляем уведомления
    for notification in notifications:
        print(f"   - Отправка уведомления пользователю {notification['uid']}")
        await send_level_decrease_warning(context, notification)

# ------------------- Main -------------------
def main():
    logging.basicConfig(
        filename="bot.log",
        level=logging.ERROR,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    TOKEN = "8277300875:AAE2S8LGrA_Y4Bov2W3ElXRooVesHrFqDDs"
    app = Application.builder().token(TOKEN).build()

    # ------------------- Основные команды -------------------
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.Regex("💰 Баланс"), balance))
    app.add_handler(MessageHandler(filters.Regex("👥 Пригласить друга"), invite))
    app.add_handler(MessageHandler(filters.Regex("📞 Контакты"), contacts))
    app.add_handler(MessageHandler(filters.Regex("📄 История"), show_history))
    app.add_handler(MessageHandler(filters.Regex("📷 QR-код"), show_qr))
    
    # ------------------- ratings_conv ДОЛЖЕН БЫТЬ ДО УНИВЕРСАЛЬНОГО -------------------
    app.add_handler(ratings_conv)
    
    # ------------------- Админка -------------------
    app.add_handler(MessageHandler(filters.Regex("⚙ Админ"), open_admin_menu))  # 👈 ИСПРАВЛЕНО
    app.add_handler(get_admin_conv())
    app.bot_data["admins"] = admins
    
    # ------------------- Регистрация по номеру -------------------
    app.add_handler(get_register_customer_conv())
    
    # ------------------- Оплата бонусами -------------------
    app.add_handler(cashier_conv_handler)
    
    # ------------------- Обработчик инлайн-кнопок -------------------
    app.add_handler(payment_callback_handler)
    app.add_handler(CallbackQueryHandler(check_balance_callback, pattern="^check_balance$"))
    app.add_handler(CallbackQueryHandler(history_callback, pattern="^history$"))
    
    # ------------------- Обработчик кнопки "⬅ В главное меню" -------------------
    app.add_handler(MessageHandler(filters.Regex("⬅ В главное меню"), handle_back_to_menu))
    
    # ------------------- Обработчики событий -------------------
    app.add_handler(conv_events)
    app.add_handler(CommandHandler("test", test_history))
    
    # ------------------- Навигация -------------------
    app.add_handler(MessageHandler(filters.Regex("⬅ Назад в главное меню"), back_to_menu))
    app.add_handler(MessageHandler(filters.Regex("⬅ Отмена"), back_to_menu))
    
    # ------------------- Универсальный обработчик (В САМОМ КОНЦЕ) -------------------
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_to_menu))

    # ------------------- Фоновые задачи -------------------
    app.job_queue.run_repeating(reminders_job, interval=3600, first=60)
    app.job_queue.run_daily(yearly_reset_job, time=datetime.time(0, 0, 0))
    app.job_queue.run_daily(level_check_job, time=datetime.time(10, 0, 0))
    app.job_queue.run_once(level_check_job, when=10)

    print("✅ Бот запущен")
    print("📱 Доступные функции:")
    print("   - Регистрация по контакту")
    print("   - Бонусная система с годовым сбросом уровней")
    print("   - События и напоминания с настройками")
    print("   - Админ-панель с выбором пользователей")
    print("   - Оплата бонусами для кассиров")
    print("   - История операций")
    print("   - Уведомления админам о новых регистрациях")
    print("   - Любое сообщение открывает главное меню")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()