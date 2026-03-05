# debug_events.py
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from utils_reminders import save_event, load_user_events, delete_event, update_reminder_settings
from datetime import datetime, timedelta
import logging

# Состояния
ADD_NAME, ADD_DATE, REMOVE_NAME, EDIT_SELECT, EDIT_NAME, EDIT_DATE, REMINDER_SETTINGS = range(7)

logger = logging.getLogger(__name__)

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
        if day < 1 or day > 31 or month < 1 or month > 12:
            raise ValueError
        
        event_date = datetime(datetime.now().year, month, day)
        if event_date < datetime.now():
            event_date = datetime(datetime.now().year + 1, month, day)
        
        context.user_data["event_date"] = event_date
        return await show_reminder_settings(update, context)
        
    except Exception as e:
        kb = [["⬅ Назад в меню событий"]]
        await update.message.reply_text(
            "❌ Неверный формат. Используйте ДД.ММ", 
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return ADD_DATE

async def show_reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает настройки напоминаний"""
    event_name = context.user_data["event_name"]
    event_date = context.user_data["event_date"]
    
    text = f"📅 **Событие:** {event_name}\n"
    text += f"📆 **Дата:** {event_date.strftime('%d.%m.%Y')}\n\n"
    text += "⚙️ **Настройки напоминаний:**\n\n"
    text += "Выберите, когда напоминать:"
    
    keyboard = [
        [InlineKeyboardButton("✅ За 7 дней", callback_data="remind_7days")],
        [InlineKeyboardButton("✅ За 1 день", callback_data="remind_1day")],
        [InlineKeyboardButton("⬜ За час", callback_data="remind_hour")],
        [InlineKeyboardButton("⬜ В день события", callback_data="remind_dayof")],
        [InlineKeyboardButton("✅ Готово", callback_data="remind_done")]
    ]
    
    # Сохраняем настройки по умолчанию
    context.user_data["reminder_settings"] = {
        "7_days": True,
        "1_day": True,
        "hour": False,
        "day_of": False
    }
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return REMINDER_SETTINGS

async def handle_reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает настройки напоминаний"""
    query = update.callback_query
    await query.answer()
    
    settings = context.user_data.get("reminder_settings", {})
    
    if query.data == "remind_7days":
        settings["7_days"] = not settings.get("7_days", True)
        # Обновляем клавиатуру
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('7_days', True) else '⬜'} За 7 дней", callback_data="remind_7days")],
            [InlineKeyboardButton(f"{'✅' if settings.get('1_day', True) else '⬜'} За 1 день", callback_data="remind_1day")],
            [InlineKeyboardButton(f"{'✅' if settings.get('hour', False) else '⬜'} За час", callback_data="remind_hour")],
            [InlineKeyboardButton(f"{'✅' if settings.get('day_of', False) else '⬜'} В день события", callback_data="remind_dayof")],
            [InlineKeyboardButton("✅ Готово", callback_data="remind_done")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "remind_1day":
        settings["1_day"] = not settings.get("1_day", True)
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('7_days', True) else '⬜'} За 7 дней", callback_data="remind_7days")],
            [InlineKeyboardButton(f"{'✅' if settings.get('1_day', True) else '⬜'} За 1 день", callback_data="remind_1day")],
            [InlineKeyboardButton(f"{'✅' if settings.get('hour', False) else '⬜'} За час", callback_data="remind_hour")],
            [InlineKeyboardButton(f"{'✅' if settings.get('day_of', False) else '⬜'} В день события", callback_data="remind_dayof")],
            [InlineKeyboardButton("✅ Готово", callback_data="remind_done")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "remind_hour":
        settings["hour"] = not settings.get("hour", False)
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('7_days', True) else '⬜'} За 7 дней", callback_data="remind_7days")],
            [InlineKeyboardButton(f"{'✅' if settings.get('1_day', True) else '⬜'} За 1 день", callback_data="remind_1day")],
            [InlineKeyboardButton(f"{'✅' if settings.get('hour', False) else '⬜'} За час", callback_data="remind_hour")],
            [InlineKeyboardButton(f"{'✅' if settings.get('day_of', False) else '⬜'} В день события", callback_data="remind_dayof")],
            [InlineKeyboardButton("✅ Готово", callback_data="remind_done")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "remind_dayof":
        settings["day_of"] = not settings.get("day_of", False)
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('7_days', True) else '⬜'} За 7 дней", callback_data="remind_7days")],
            [InlineKeyboardButton(f"{'✅' if settings.get('1_day', True) else '⬜'} За 1 день", callback_data="remind_1day")],
            [InlineKeyboardButton(f"{'✅' if settings.get('hour', False) else '⬜'} За час", callback_data="remind_hour")],
            [InlineKeyboardButton(f"{'✅' if settings.get('day_of', False) else '⬜'} В день события", callback_data="remind_dayof")],
            [InlineKeyboardButton("✅ Готово", callback_data="remind_done")]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "remind_done":
        # Сохраняем событие с настройками
        event_name = context.user_data["event_name"]
        event_date = context.user_data["event_date"]
        
        save_event(
            update.effective_user.id, 
            event_name, 
            event_date, 
            settings
        )
        
        # Формируем текст ответа
        text = f"✅ **Событие сохранено!**\n\n"
        text += f"📅 {event_name} — {event_date.strftime('%d.%m.%Y')}\n\n"
        text += f"⚙️ Напоминания:\n"
        if settings.get('7_days'):
            text += "✅ За 7 дней\n"
        if settings.get('1_day'):
            text += "✅ За 1 день\n"
        if settings.get('hour'):
            text += "✅ За час\n"
        if settings.get('day_of'):
            text += "✅ В день события\n"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown'
        )
        
        # Очищаем данные
        context.user_data.pop("event_name", None)
        context.user_data.pop("event_date", None)
        context.user_data.pop("reminder_settings", None)
        
        # Создаем фейковый update для вызова меню событий
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            }),
            'callback_query': None
        })
        
        return await events_menu(fake_update, context)
    
    # Сохраняем обновленные настройки
    context.user_data["reminder_settings"] = settings
    return REMINDER_SETTINGS

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

# ------------------- Список событий -------------------
async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    events = load_user_events(user_id)
    
    if not events:
        await update.message.reply_text("📅 У вас нет сохраненных событий.")
    else:
        text = "📅 **Ваши события:**\n\n"
        for name, data in events.items():
            if isinstance(data, dict):
                date = data.get("date")
                reminders = data.get("reminders", {})
            else:
                date = data
                reminders = {}
            
            if isinstance(date, datetime):
                date_str = date.strftime('%d.%m.%Y')
            else:
                date_str = str(date)
            
            text += f"• **{name}** — {date_str}\n"
            if reminders:
                text += f"  ⏰ Напоминания:\n"
                if reminders.get("7_days"): text += "    • За 7 дней\n"
                if reminders.get("1_day"): text += "    • За 1 день\n"
                if reminders.get("hour"): text += "    • За час\n"
                if reminders.get("day_of"): text += "    • В день события\n"
            text += "\n"
        await update.message.reply_text(text, parse_mode='Markdown')
    
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
    kb = [["⬅ Назад в меню событий"]]
    await update.message.reply_text(
        "Введите новое название события (или '-' чтобы оставить прежнее):",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return EDIT_NAME

async def edit_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    return EDIT_DATE

async def edit_event_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅ Назад в меню событий":
        return await events_menu(update, context)
    
    user_id = update.message.from_user.id
    old_name = context.user_data["old_event_name"]
    new_name = context.user_data["new_event_name"]
    date_text = update.message.text
    
    # Получаем старое событие
    events = load_user_events(user_id)
    old_event = events.get(old_name, {})
    
    if isinstance(old_event, dict):
        old_date = old_event.get("date")
        old_reminders = old_event.get("reminders", {})
    else:
        old_date = old_event
        old_reminders = {}
    
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
            return EDIT_DATE
    
    # Сохраняем с настройками
    if delete_event(user_id, old_name):
        save_event(user_id, new_name, new_date, old_reminders)
        await update.message.reply_text(f"✅ Событие обновлено!")
    else:
        await update.message.reply_text(f"❌ Ошибка при обновлении!")
    
    return await events_menu(update, context)

# ------------------- ConversationHandler -------------------
conv_events = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("📅 События"), events_menu),  # Добавьте эту строку
        MessageHandler(filters.Regex("➕ Добавить событие"), add_event_start),
        MessageHandler(filters.Regex("➖ Удалить событие"), remove_event_start),
        MessageHandler(filters.Regex("✏️ Редактировать событие"), edit_event_start),
        MessageHandler(filters.Regex("📅 Список событий"), list_events),
    ],
    states={
        ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_name)],
        ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_date)],
        REMINDER_SETTINGS: [CallbackQueryHandler(handle_reminder_settings)],
        REMOVE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_event_name)],
        EDIT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_select)],
        EDIT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_name)],
        EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_event_date)],
    },
    fallbacks=[
        MessageHandler(filters.Regex("⬅ Назад в меню событий"), events_menu),
        MessageHandler(filters.Regex("⬅ Назад в главное меню"), lambda u, c: ConversationHandler.END)
    ],
    per_user=True,
    name="events_conversation"
)