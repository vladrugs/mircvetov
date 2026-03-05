# simple_events.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils_reminders import save_event, load_user_events, delete_event, update_event
from datetime import datetime

# Состояния
MAIN_MENU, ADD_NAME, ADD_DATE, DELETE_NAME, EDIT_OLD_NAME, EDIT_NEW_NAME, EDIT_NEW_DATE = range(7)

# ------------------- Главное меню событий -------------------
async def events_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню событий"""
    kb = [
        ["1️⃣ Добавить событие"],
        ["2️⃣ Удалить событие"],
        ["3️⃣ Редактировать событие"],
        ["4️⃣ Список событий"],
        ["⬅ Назад в главное меню"]
    ]
    await update.message.reply_text(
        "📅 Меню событий:\n\n"
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return MAIN_MENU

# ------------------- Добавление события -------------------
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите название события:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
    )
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад":
        return await events_main(update, context)
    
    context.user_data["event_name"] = update.message.text
    await update.message.reply_text(
        "Введите дату события (ДД.ММ):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
    )
    return ADD_DATE

async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад":
        return await events_main(update, context)
    
    try:
        day, month = map(int, update.message.text.split("."))
        event_date = datetime(datetime.now().year, month, day)
        if event_date < datetime.now():
            event_date = datetime(datetime.now().year + 1, month, day)
        
        save_event(update.message.from_user.id, context.user_data["event_name"], event_date)
        await update.message.reply_text(f"✅ Событие '{context.user_data['event_name']}' сохранено!")
        
    except:
        await update.message.reply_text(
            "❌ Неверный формат! Используйте ДД.ММ",
            reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
        )
        return ADD_DATE
    
    return await events_main(update, context)

# ------------------- Удаление события -------------------
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет событий для удаления.")
        return await events_main(update, context)
    
    # Показываем список событий
    text = "📅 Ваши события:\n\n"
    for name in events.keys():
        text += f"• {name}\n"
    text += "\nВведите название события для удаления:"
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
    )
    return DELETE_NAME

async def delete_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад":
        return await events_main(update, context)
    
    event_name = update.message.text
    user_id = update.message.from_user.id
    
    if delete_event(user_id, event_name):
        await update.message.reply_text(f"✅ Событие '{event_name}' удалено!")
    else:
        await update.message.reply_text(f"❌ Событие '{event_name}' не найдено!")
    
    return await events_main(update, context)

# ------------------- Редактирование события -------------------
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет событий для редактирования.")
        return await events_main(update, context)
    
    # Показываем список событий
    text = "📅 Ваши события:\n\n"
    for name in events.keys():
        text += f"• {name}\n"
    text += "\nВведите название события для редактирования:"
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
    )
    return EDIT_OLD_NAME

async def edit_old_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад":
        return await events_main(update, context)
    
    context.user_data["old_event_name"] = update.message.text
    await update.message.reply_text(
        "Введите новое название события:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
    )
    return EDIT_NEW_NAME

async def edit_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад":
        return await events_main(update, context)
    
    context.user_data["new_event_name"] = update.message.text
    await update.message.reply_text(
        "Введите новую дату (ДД.ММ):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
    )
    return EDIT_NEW_DATE

async def edit_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад":
        return await events_main(update, context)
    
    user_id = update.message.from_user.id
    old_name = context.user_data["old_event_name"]
    new_name = context.user_data["new_event_name"]
    
    try:
        day, month = map(int, update.message.text.split("."))
        new_date = datetime(datetime.now().year, month, day)
        if new_date < datetime.now():
            new_date = datetime(datetime.now().year + 1, month, day)
        
        if update_event(user_id, old_name, new_name, new_date):
            await update.message.reply_text(f"✅ Событие обновлено!")
        else:
            await update.message.reply_text(f"❌ Ошибка при обновлении!")
            
    except:
        await update.message.reply_text(
            "❌ Неверный формат! Используйте ДД.ММ",
            reply_markup=ReplyKeyboardMarkup([["⬅ Назад"]], resize_keyboard=True)
        )
        return EDIT_NEW_DATE
    
    return await events_main(update, context)

# ------------------- Список событий -------------------
async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет сохраненных событий.")
    else:
        text = "📅 Ваши события:\n\n"
        for name, date in events.items():
            if isinstance(date, str):
                try:
                    date = datetime.strptime(date, "%Y-%m-%d")
                    text += f"• {name} — {date.strftime('%d.%m')}\n"
                except:
                    text += f"• {name} — {date}\n"
            else:
                text += f"• {name} — {date.strftime('%d.%m')}\n"
        await update.message.reply_text(text)
    
    return await events_main(update, context)