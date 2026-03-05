# reminders_handlers.py
from telegram import Update
from telegram.ext import ContextTypes
from utils_reminders import save_event, delete_event, load_user_events
from datetime import datetime

# -------------------- Добавить событие --------------------
async def add_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название события:")
    return "WAIT_EVENT_NAME"

async def add_reminder_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["event_name"] = update.message.text
    await update.message.reply_text("Введите дату события в формате ДД.ММ:")
    return "WAIT_EVENT_DATE"

async def add_reminder_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("event_name")
    try:
        date = datetime.strptime(update.message.text, "%d.%m")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Попробуйте снова.")
        return "WAIT_EVENT_DATE"

    save_event(update.message.from_user.id, name, date)
    await update.message.reply_text(f"✅ Событие '{name}' добавлено на {date.strftime('%d.%m')}")
    return -1

# -------------------- Удалить событие --------------------
async def remove_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    if not events:
        await update.message.reply_text("У вас нет событий для удаления.")
        return -1
    text = "📅 Ваши события:\n"
    for name, dt in events.items():
        text += f"- {name} ({dt.strftime('%d.%m')})\n"
    await update.message.reply_text(text + "\nВведите точное название события для удаления:" )
    return "WAIT_REMOVE_NAME"

async def remove_reminder_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    user_id = update.message.from_user.id
    deleted = delete_event(user_id, name)
    if deleted:
        await update.message.reply_text(f"✅ Событие '{name}' удалено.")
    else:
        await update.message.reply_text("❌ Событие не найдено.")
    return -1

# -------------------- Список событий --------------------
async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    if not events:
        await update.message.reply_text("У вас нет событий.")
    else:
        text = "📅 Ваши события:\n"
        for name, dt in events.items():
            text += f"{name} — {dt.strftime('%d.%m')}\n"
        await update.message.reply_text(text)