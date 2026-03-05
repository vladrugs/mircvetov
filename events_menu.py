# events_menu.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ConversationHandler, MessageHandler, filters, ContextTypes
from utils_reminders import save_event, load_user_events, delete_event, update_event
from datetime import datetime

# Состояния
ADD_NAME, ADD_DATE, REMOVE_NAME, EDIT_SELECT, EDIT_NEW_NAME, EDIT_NEW_DATE = range(6)

# ------------------- Меню событий -------------------
async def events_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню событий"""
    kb = [
        ["➕ Добавить событие", "➖ Удалить событие"],
        ["✏️ Редактировать событие", "📅 Список событий"],
        ["⬅ Назад в главное меню"]
    ]
    await update.message.reply_text(
        "📅 Меню событий:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return ConversationHandler.END

# ------------------- Добавление события -------------------
async def add_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["⬅ Назад в меню событий"]]
    await update.message.reply_text(
        "Введите название события:", 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return ADD_NAME

async def add_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    context.user_data["event_name"] = update.message.text
    kb = [["⬅ Назад в меню событий"]]
    await update.message.reply_text(
        "Введите дату события (ДД.ММ):", 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return ADD_DATE

async def add_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    try:
        day, month = map(int, update.message.text.split("."))
        # Проверка корректности даты
        if day < 1 or day > 31 or month < 1 or month > 12:
            raise ValueError
        event_date = datetime(datetime.now().year, month, day)
        if event_date < datetime.now():
            event_date = datetime(datetime.now().year + 1, month, day)
    except:
        kb = [["⬅ Назад в меню событий"]]
        await update.message.reply_text(
            "❌ Неверный формат. Используйте ДД.ММ", 
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return ADD_DATE
    
    save_event(update.message.from_user.id, context.user_data["event_name"], event_date)
    await update.message.reply_text(f"✅ Событие '{context.user_data['event_name']}' сохранено на {day:02d}.{month:02d}")
    
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
    return REMOVE_NAME

async def remove_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    # Создаем клавиатуру с событиями
    kb = [[name] for name in events.keys()]
    kb.append(["⬅ Назад в меню событий"])
    
    await update.message.reply_text(
        "Выберите событие для редактирования:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return EDIT_SELECT

async def edit_select_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    context.user_data["old_event_name"] = update.message.text
    kb = [["⬅ Назад в меню событий"]]
    await update.message.reply_text(
        "Введите новое название события (или отправьте '-' чтобы оставить прежнее):",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return EDIT_NEW_NAME

async def edit_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    new_name = update.message.text
    if new_name == "-":
        context.user_data["new_event_name"] = context.user_data["old_event_name"]
    else:
        context.user_data["new_event_name"] = new_name
    
    kb = [["⬅ Назад в меню событий"]]
    await update.message.reply_text(
        "Введите новую дату (ДД.ММ) или '-' чтобы оставить прежнюю:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return EDIT_NEW_DATE

async def edit_new_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    user_id = update.message.from_user.id
    old_name = context.user_data["old_event_name"]
    new_name = context.user_data["new_event_name"]
    date_text = update.message.text
    
    # Получаем старую дату
    events = load_user_events(user_id)
    old_date = events.get(old_name)
    
    if date_text == "-":
        new_date = old_date
    else:
        try:
            day, month = map(int, date_text.split("."))
            if day < 1 or day > 31 or month < 1 or month > 12:
                raise ValueError
            new_date = datetime(datetime.now().year, month, day)
            if new_date < datetime.now():
                new_date = datetime(datetime.now().year + 1, month, day)
        except:
            kb = [["⬅ Назад в меню событий"]]
            await update.message.reply_text(
                "❌ Неверный формат. Используйте ДД.ММ", 
                reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
            )
            return EDIT_NEW_DATE
    
    # Обновляем событие
    if update_event(user_id, old_name, new_name, new_date):
        await update.message.reply_text(f"✅ Событие обновлено!")
    else:
        await update.message.reply_text(f"❌ Ошибка при обновлении!")
    
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