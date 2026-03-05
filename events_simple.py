# events_simple.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from utils_reminders import save_event, load_user_events, delete_event, update_event
from datetime import datetime

# Хранилище временных данных пользователей
user_temp_data = {}

# ------------------- Главное меню событий -------------------
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

# ------------------- Добавление события -------------------
async def add_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # Если пользователь в процессе добавления
    if user_id in user_temp_data:
        step = user_temp_data[user_id].get("step")
        
        # Шаг 2 - ввод даты
        if step == "waiting_date":
            try:
                day, month = map(int, update.message.text.split("."))
                event_date = datetime(datetime.now().year, month, day)
                if event_date < datetime.now():
                    event_date = datetime(datetime.now().year + 1, month, day)
                
                event_name = user_temp_data[user_id]["name"]
                save_event(user_id, event_name, event_date)
                
                del user_temp_data[user_id]
                await update.message.reply_text(f"✅ Событие '{event_name}' сохранено!")
                return await events_menu(update, context)
                
            except:
                await update.message.reply_text(
                    "❌ Неверный формат! Введите дату в формате ДД.ММ:",
                    reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
                )
                return
    
    # Шаг 1 - запрос названия
    user_temp_data[user_id] = {"step": "waiting_name"}
    await update.message.reply_text(
        "Введите название события:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )

async def add_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if update.message.text == "⬅ Назад в меню событий":
        if user_id in user_temp_data:
            del user_temp_data[user_id]
        return await events_menu(update, context)
    
    user_temp_data[user_id] = {"step": "waiting_date", "name": update.message.text}
    await update.message.reply_text(
        "Введите дату события (ДД.ММ):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )

# ------------------- Удаление события -------------------
async def delete_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет событий для удаления.")
        return await events_menu(update, context)
    
    # Показываем список событий
    text = "📅 Выберите событие для удаления:\n\n"
    kb = []
    for name in events.keys():
        text += f"• {name}\n"
        kb.append([f"❌ {name}"])
    
    kb.append(["⬅ Назад в меню событий"])
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def delete_event_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    # Убираем "❌ " из начала строки
    event_name = update.message.text.replace("❌ ", "")
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
    
    # Показываем список событий
    text = "📅 Выберите событие для редактирования:\n\n"
    kb = []
    for name in events.keys():
        text += f"• {name}\n"
        kb.append([f"✏️ {name}"])
    
    kb.append(["⬅ Назад в меню событий"])
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def edit_event_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    event_name = update.message.text.replace("✏️ ", "")
    user_id = update.message.from_user.id
    
    context.user_data["edit_old_name"] = event_name
    await update.message.reply_text(
        f"Редактирование: {event_name}\n\nВведите новое название:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )

async def edit_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    context.user_data["edit_new_name"] = update.message.text
    await update.message.reply_text(
        "Введите новую дату (ДД.ММ):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
    )

async def edit_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    try:
        day, month = map(int, update.message.text.split("."))
        new_date = datetime(datetime.now().year, month, day)
        if new_date < datetime.now():
            new_date = datetime(datetime.now().year + 1, month, day)
        
        user_id = update.message.from_user.id
        old_name = context.user_data["edit_old_name"]
        new_name = context.user_data["edit_new_name"]
        
        if update_event(user_id, old_name, new_name, new_date):
            await update.message.reply_text(f"✅ Событие обновлено!")
        else:
            await update.message.reply_text(f"❌ Ошибка при обновлении!")
            
    except:
        await update.message.reply_text(
            "❌ Неверный формат! Введите дату ДД.ММ:",
            reply_markup=ReplyKeyboardMarkup([["⬅ Назад в меню событий"]], resize_keyboard=True)
        )
        return
    
    # Очищаем данные
    context.user_data.pop("edit_old_name", None)
    context.user_data.pop("edit_new_name", None)
    
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
                    text += f"• {name} — {date.strftime('%d.%m')}\n"
                except:
                    text += f"• {name} — {date}\n"
            else:
                text += f"• {name} — {date.strftime('%d.%m')}\n"
        await update.message.reply_text(text)
    
    return await events_menu(update, context)