# events_handler.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from utils_reminders import save_event, load_user_events, delete_event, update_event
from datetime import datetime

# Состояния
EVENT_MENU, ADD_NAME, ADD_DATE, REMOVE_SELECT, EDIT_SELECT, EDIT_NAME, EDIT_DATE = range(7)

# ------------------- Меню событий -------------------
async def events_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню событий"""
    kb = [
        ["➕ Добавить событие"],
        ["➖ Удалить событие"],
        ["✏️ Редактировать событие"],
        ["📅 Список событий"],
        ["⬅ Назад в главное меню"]
    ]
    await update.message.reply_text(
        "📅 Меню событий:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return EVENT_MENU

# ------------------- Добавление события -------------------
async def add_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите название события:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )
    return ADD_NAME

async def add_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    context.user_data["event_name"] = update.message.text
    await update.message.reply_text(
        "Введите дату события (ДД.ММ):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )
    return ADD_DATE

async def add_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    try:
        day, month = map(int, update.message.text.split("."))
        if day < 1 or day > 31 or month < 1 or month > 12:
            raise ValueError
        
        event_date = datetime(datetime.now().year, month, day)
        if event_date < datetime.now():
            event_date = datetime(datetime.now().year + 1, month, day)
        
        save_event(update.message.from_user.id, context.user_data["event_name"], event_date)
        await update.message.reply_text(f"✅ Событие '{context.user_data['event_name']}' сохранено на {day:02d}.{month:02d}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте ДД.ММ",
            reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
        )
        return ADD_DATE
    
    return await events_menu(update, context)

# ------------------- Удаление события -------------------
async def remove_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет событий для удаления.")
        return await events_menu(update, context)
    
    # Создаем клавиатуру с событиями
    kb = [[name] for name in events.keys()]
    kb.append(["⬅ Назад в меню событий"])
    
    await update.message.reply_text(
        "Выберите событие для удаления:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return REMOVE_SELECT

async def remove_event_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    event_name = update.message.text
    user_id = update.message.from_user.id
    
    if delete_event(user_id, event_name):
        await update.message.reply_text(f"✅ Событие '{event_name}' удалено!")
    else:
        await update.message.reply_text(f"❌ Событие '{event_name}' не найдено!")
    
    return await events_menu(update, context)

# ------------------- Редактирование события -------------------
async def edit_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет событий для редактирования.")
        return await events_menu(update, context)
    
    kb = [[name] for name in events.keys()]
    kb.append(["⬅ Назад в меню событий"])
    
    await update.message.reply_text(
        "Выберите событие для редактирования:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return EDIT_SELECT

async def edit_event_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    context.user_data["old_event_name"] = update.message.text
    await update.message.reply_text(
        "Введите новое название события:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )
    return EDIT_NAME

async def edit_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    context.user_data["new_event_name"] = update.message.text
    await update.message.reply_text(
        "Введите новую дату (ДД.ММ):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )
    return EDIT_DATE

async def edit_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    user_id = update.message.from_user.id
    old_name = context.user_data["old_event_name"]
    new_name = context.user_data["new_event_name"]
    
    try:
        day, month = map(int, update.message.text.split("."))
        if day < 1 or day > 31 or month < 1 or month > 12:
            raise ValueError
        
        new_date = datetime(datetime.now().year, month, day)
        if new_date < datetime.now():
            new_date = datetime(datetime.now().year + 1, month, day)
        
        if update_event(user_id, old_name, new_name, new_date):
            await update.message.reply_text(f"✅ Событие обновлено!")
        else:
            await update.message.reply_text(f"❌ Ошибка при обновлении!")
            
    except Exception as e:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте ДД.ММ",
            reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
        )
        return EDIT_DATE
    
    return await events_menu(update, context)

# ------------------- Список событий -------------------
async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                except:
                    pass
            if isinstance(date, datetime):
                text += f"• {name} — {date.strftime('%d.%m')}\n"
            else:
                text += f"• {name} — {date}\n"
        await update.message.reply_text(text)
    
    return await events_menu(update, context)