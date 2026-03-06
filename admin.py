# admin.py
from roles import admins, cashiers, add_admin, remove_admin, add_cashier, remove_cashier, is_admin, is_cashier
from roles import get_admins_list, get_admin_details, get_cashiers_list, get_cashier_details
from utils import load_users, save_users, add_history, find_user, delete_user, calc_level, get_last_activity, update_user_activity
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, ConversationHandler, filters
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
import re
import logging

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- Состояния ConversationHandler --------------------
ADMIN_USER, ADMIN_AMOUNT, WAIT_QR, WAIT_AMOUNT, ADMIN_SELECT_USER, ADMIN_MESSAGE = range(6)
admin_actions = {}

# -------------------- Очистка данных пользователя --------------------
def clear_user_data(user_id):
    """Полностью очищает все данные пользователя"""
    if user_id in admin_actions:
        del admin_actions[user_id]
        logger.info(f"🧹 Очищены данные пользователя {user_id}")

# -------------------- Меню админа --------------------
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Очищаем старые данные пользователя
    clear_user_data(user.id)
    logger.info(f"🔥 АДМИН МЕНЮ вызвано пользователем {user.id}")
    
    if not is_admin(user.id):
        logger.info(f"❌ Пользователь {user.id} не админ")
        await update.message.reply_text("❌ Вы не админ!")
        return ConversationHandler.END

    logger.info(f"✅ Пользователь {user.id} админ, показываем меню")
    
    kb = [
        [InlineKeyboardButton("💰 Начислить бонус", callback_data="admin_add")],
        [InlineKeyboardButton("💸 Снять бонус", callback_data="admin_remove")],
        [InlineKeyboardButton("📷 Списание по QR", callback_data="admin_qr")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📈 Клиенты по уровням", callback_data="show_level_stats")],
        [InlineKeyboardButton("⭐ Оценки покупателей", callback_data="show_ratings_stats")],  # Новая кнопка
        [InlineKeyboardButton("👥 Список админов", callback_data="admin_list_admins")],
        [InlineKeyboardButton("🔰 Список кассиров", callback_data="admin_list_cashiers")],
        [InlineKeyboardButton("👑 Назначить админа", callback_data="role_admin")],
        [InlineKeyboardButton("👑 Удалить админа", callback_data="role_remove_admin")],
        [InlineKeyboardButton("🔰 Назначить кассира", callback_data="role_cashier")],
        [InlineKeyboardButton("🔰 Удалить кассира", callback_data="role_remove_cashier")],
        [InlineKeyboardButton("🗑 Удалить пользователя", callback_data="admin_delete_user")],
        [InlineKeyboardButton("❌ Выйти из админки", callback_data="exit_admin")]
    ]
    
    await update.message.reply_text(
        "⚙ Меню администратора:",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    
    return ConversationHandler.END

# -------------------- Показать статистику уровней --------------------
async def show_level_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику клиентов по уровням"""
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    
    # Статистика по уровням
    levels = {
        "НАЧИНАЮЩИЙ": 0,
        "BRONZE": 0,
        "SILVER": 0,
        "GOLD": 0,
        "PLATINUM": 0,
        "VIP": 0
    }
    
    for uid, u in users.items():
        if u.get('registered'):
            total_purchases = u.get('total_purchases', 0)
            level, cashback, _ = calc_level(total_purchases)
            if level in levels:
                levels[level] += 1
    
    # Формируем текст
    text = "📊 **СТАТИСТИКА КЛИЕНТОВ ПО УРОВНЯМ**\n\n"
    
    level_emojis = {
        "НАЧИНАЮЩИЙ": "🌱",
        "BRONZE": "🥉",
        "SILVER": "🥈",
        "GOLD": "🥇",
        "PLATINUM": "💎",
        "VIP": "👑"
    }
    
    total_clients = sum(levels.values())
    text += f"👥 **Всего клиентов:** {total_clients}\n\n"
    
    for level, count in levels.items():
        emoji = level_emojis.get(level, "📌")
        text += f"{emoji} **{level}**: {count} чел.\n"
    
    # Создаем кнопки
    keyboard = []
    
    # Кнопки по уровням
    for level, count in levels.items():
        if count > 0:
            keyboard.append([
                InlineKeyboardButton(
                    f"{level_emojis.get(level, '📌')} {level} ({count})", 
                    callback_data=f"show_level_{level}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 В админку", callback_data="back_to_admin")])
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Показать клиентов уровня --------------------
async def show_level_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список клиентов выбранного уровня с информацией об активности"""
    query = update.callback_query
    await query.answer()
    
    level = query.data.replace("show_level_", "")
    
    users = load_users()
    
    # Собираем клиентов этого уровня
    clients = []
    for uid, u in users.items():
        if u.get('registered'):
            total_purchases = u.get('total_purchases', 0)
            user_level, _, _ = calc_level(total_purchases)
            if user_level == level:
                last_activity = get_last_activity(uid)
                clients.append({
                    "uid": uid,
                    "name": u.get('name', 'Неизвестно'),
                    "phone": u.get('phone', 'Нет'),
                    "balance": u.get('balance', 0),
                    "purchases": total_purchases,
                    "last_activity": last_activity
                })
    
    if not clients:
        await query.message.edit_text(f"📭 Нет клиентов уровня {level}")
        return await show_level_stats(update, context)
    
    # Сортируем по последней активности (онлайн первыми)
    clients.sort(key=lambda x: 0 if "онлайн" in x["last_activity"] else 1)
    
    level_emojis = {
        "НАЧИНАЮЩИЙ": "🌱",
        "BRONZE": "🥉",
        "SILVER": "🥈",
        "GOLD": "🥇",
        "PLATINUM": "💎",
        "VIP": "👑"
    }
    emoji = level_emojis.get(level, "📌")
    
    text = f"{emoji} **КЛИЕНТЫ УРОВНЯ {level}**\n\n"
    text += f"Всего: {len(clients)} клиентов\n\n"
    
    # Создаем кнопки для каждого клиента (макс 8)
    keyboard = []
    for i, client in enumerate(clients[:8], 1):
        name = client['name']
        if len(name) > 15:
            name = name[:15] + "..."
        
        # Добавляем индикатор активности
        activity_icon = "🟢" if "онлайн" in client["last_activity"] else "⚪"
        
        btn_text = f"{activity_icon} {name} ({client['purchases']} руб.)"
        keyboard.append([InlineKeyboardButton(
            btn_text, 
            callback_data=f"client_details_{client['uid']}"
        )])
    
    if len(clients) > 8:
        text += f"\n... и еще {len(clients) - 8} клиентов"
    
    keyboard.append([InlineKeyboardButton("🔙 К уровням", callback_data="back_to_levels")])
    keyboard.append([InlineKeyboardButton("🔙 В админку", callback_data="back_to_admin")])
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Показать подробную информацию о клиенте --------------------
async def show_client_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обновляем активность админа
    if update.effective_user:
        update_user_activity(update.effective_user.id)
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    target_uid = data.replace("client_details_", "")
    
    users = load_users()
    if target_uid not in users:
        await query.message.edit_text("❌ Клиент не найден")
        return await admin_menu(update, context)
    
    user = users[target_uid]
    name = user.get('name', 'Неизвестно')
    phone = user.get('phone', 'Нет')
    balance = user.get('balance', 0)
    total_purchases = user.get('total_purchases', 0)
    last_activity = get_last_activity(target_uid)
    
    # Получаем уровень
    level, cashback, _ = calc_level(total_purchases)
    
    # Получаем историю покупок
    history = user.get('history', [])
    last_purchases = []
    for h in reversed(history[-5:]):  # Последние 5 записей
        if 'покупка' in h.get('description', '').lower():
            last_purchases.append(h)
    
    # Получаем последние оценки
    ratings = user.get('ratings', [])
    last_rating = ratings[-1] if ratings else None
    
    text = f"👤 **ДЕТАЛЬНАЯ ИНФОРМАЦИЯ**\n\n"
    text += f"**Имя:** {name}\n"
    text += f"**Телефон:** {phone}\n"
    text += f"**ID:** `{target_uid}`\n"
    text += f"**Баланс:** {balance} бонусов\n"
    text += f"**Покупки за год:** {total_purchases} руб.\n"
    text += f"**Уровень:** {level} ({cashback}% кэшбэк)\n"
    text += f"**Последняя активность:** {last_activity}\n"
    
    if last_rating:
        text += f"**Последняя оценка:** {last_rating.get('rating')}/5\n"
    
    if last_purchases:
        text += "\n**Последние покупки:**\n"
        for p in last_purchases:
            text += f"  • {p.get('description', '')}\n"
    
    # Кнопки действий
    keyboard = [
        [
            InlineKeyboardButton("✉️ Написать", callback_data=f"message_client_{target_uid}"),
            InlineKeyboardButton("💰 Начислить", callback_data=f"bonus_add_{target_uid}")
        ],
        [
            InlineKeyboardButton("💸 Списать", callback_data=f"bonus_remove_{target_uid}"),
            InlineKeyboardButton("📊 История", callback_data=f"client_history_{target_uid}")
        ],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_clients")]
    ]
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Показать историю клиента --------------------
async def show_client_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает полную историю операций клиента"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    target_uid = data.replace("client_history_", "")
    
    users = load_users()
    if target_uid not in users:
        await query.message.edit_text("❌ Клиент не найден")
        return await admin_menu(update, context)
    
    user = users[target_uid]
    name = user.get('name', 'Неизвестно')
    history = user.get('history', [])
    
    if not history:
        await query.message.edit_text(f"📭 У клиента {name} нет истории операций")
        return await show_client_details(update, context)
    
    # Показываем последние 20 записей
    text = f"📊 **ИСТОРИЯ ОПЕРАЦИЙ**\n\n"
    text += f"👤 Клиент: {name}\n"
    text += f"🆔 ID: {target_uid}\n\n"
    
    for h in reversed(history[-20:]):
        time = h.get('time', '')
        desc = h.get('description', '')
        text += f"• {time} — {desc}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад к клиенту", callback_data=f"client_details_{target_uid}")],
        [InlineKeyboardButton("🔙 В админку", callback_data="back_to_admin")]
    ]
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Быстрое начисление бонусов --------------------
async def quick_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрое начисление/снятие бонусов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    # Обновляем активность админа
    if update.effective_user:
        update_user_activity(update.effective_user.id)
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("bonus_add_"):
        target_uid = data.replace("bonus_add_", "")
        action = "admin_add"
    elif data.startswith("bonus_remove_"):
        target_uid = data.replace("bonus_remove_", "")
        action = "admin_remove"
    else:
        return await admin_menu(update, context)
    
    users = load_users()
    if target_uid not in users:
        await query.message.edit_text("❌ Клиент не найден")
        return await admin_menu(update, context)
    
    target_user = users[target_uid]
    name = target_user.get('name', 'Неизвестно')
    
    # Сохраняем данные
    user_id = query.from_user.id
    if user_id not in admin_actions:
        admin_actions[user_id] = {}
    
    admin_actions[user_id] = {
        "target": target_uid,
        "target_name": name,
        "action": action
    }
    
    action_text = "начисления" if action == "admin_add" else "снятия"
    await query.message.edit_text(
        f"💰 **{action_text.title()} бонусов**\n\n"
        f"Клиент: {name}\n"
        f"ID: {target_uid}\n\n"
        f"Введите сумму:"
    )
    
    await query.message.reply_text(
        "📝 Введите сумму:",
        reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
    )
    
    return ADMIN_AMOUNT

# -------------------- Начать отправку сообщения клиенту --------------------
async def start_message_to_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отправки сообщения клиенту"""
    # Обновляем активность админа
    if update.effective_user:
        update_user_activity(update.effective_user.id)
    
    print("🔥 start_message_to_client вызвана")
    query = update.callback_query
    await query.answer()
    
    print(f"📊 Данные callback: {query.data}")
    uid = query.data.replace("message_client_", "")
    print(f"👤 ID клиента: {uid}")
    
    users = load_users()
    if uid not in users:
        print("❌ Клиент не найден")
        await query.message.edit_text("❌ Клиент не найден")
        from handlers import show_menu
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await show_menu(fake_update, context)
    
    target_user = users[uid]
    name = target_user.get('name', 'Неизвестно')
    phone = target_user.get('phone', 'Нет')
    
    # Сохраняем ID клиента в user_data
    context.user_data['message_target'] = uid
    context.user_data['message_target_name'] = name
    print(f"✅ Сохранено в user_data: target={uid}, name={name}")
    
    await query.message.edit_text(
        f"✉️ **Отправка сообщения**\n\n"
        f"👤 **Имя:** {name}\n"
        f"📱 **Телефон:** {phone}\n"
        f"🆔 **ID:** {uid}\n\n"
        f"Введите текст сообщения:"
    )
    
    await query.message.reply_text(
        "📝 Введите текст сообщения (или нажмите кнопку ниже):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
    )
    
    return ADMIN_MESSAGE  # Возвращаем состояние для сообщений
    
# ------------------- Показать статистику оценок -------------------
async def show_ratings_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику оценок покупателей"""
    print("📊 show_ratings_stats вызвана")
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    
    total_ratings = 0
    ratings_sum = 0
    ratings_distribution = {1:0, 2:0, 3:0, 4:0, 5:0}
    feedbacks = []
    
    for uid, u in users.items():
        # Собираем оценки
        user_ratings = u.get('ratings', [])
        for r in user_ratings:
            rating = r.get('rating', 0)
            ratings_distribution[rating] = ratings_distribution.get(rating, 0) + 1
            total_ratings += 1
            ratings_sum += rating
        
        # Собираем отзывы для оценок 1-3
        user_feedbacks = u.get('feedback', [])
        for f in user_feedbacks:
            feedbacks.append({
                'user': u.get('name', 'Неизвестно'),
                'phone': u.get('phone', 'Нет'),
                'rating': f.get('rating', 0),
                'text': f.get('feedback', ''),
                'purchase': f.get('purchase', 0),
                'date': f.get('date', '')
            })
    
    avg_rating = ratings_sum / total_ratings if total_ratings > 0 else 0
    
    text = "📊 **СТАТИСТИКА ОЦЕНОК ПОКУПАТЕЛЕЙ**\n\n"
    
    if total_ratings == 0:
        text += "❌ Пока нет ни одной оценки"
    else:
        text += f"📝 **Всего оценок:** {total_ratings}\n"
        text += f"⭐ **Средняя оценка:** {avg_rating:.1f}/5\n\n"
        
        text += "**📊 Распределение:**\n"
        for i in range(1, 6):
            count = ratings_distribution.get(i, 0)
            percent = (count / total_ratings * 100) if total_ratings > 0 else 0
            bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
            text += f"{i} ⭐: {count} ({percent:.1f}%)\n"
            text += f"   {bar}\n"
    
    # Кнопки для навигации
    keyboard = []
    
    if feedbacks:
        print(f"📝 Найдено {len(feedbacks)} отзывов, добавляем кнопку")
        keyboard.append([InlineKeyboardButton("📝 Последние отзывы", callback_data="show_feedbacks")])
    else:
        print("📭 Отзывов нет")
    
    keyboard.append([InlineKeyboardButton("🔙 В админку", callback_data="back_to_admin")])
    
    # ОТЛАДКА: выводим информацию о кнопках
    print(f"🔍 Создана клавиатура с {len(keyboard)} рядами:")
    for i, row in enumerate(keyboard):
        for j, btn in enumerate(row):
            print(f"   Кнопка [{i}][{j}]: {btn.text}, callback: {btn.callback_data}")
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# ------------------- Показать последние отзывы -------------------
async def show_feedbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает последние отзывы (оценки 1-3)"""
    print("📝 show_feedbacks вызвана")
    query = update.callback_query
    await query.answer()
    
    users = load_users()
    all_feedbacks = []
    
    for uid, u in users.items():
        user_feedbacks = u.get('feedback', [])
        for f in user_feedbacks:
            all_feedbacks.append({
                'user': u.get('name', 'Неизвестно'),
                'phone': u.get('phone', 'Нет'),
                'rating': f.get('rating', 0),
                'text': f.get('feedback', ''),
                'purchase': f.get('purchase', 0),
                'date': f.get('date', '')
            })
    
    print(f"📊 Всего отзывов: {len(all_feedbacks)}")
    
    # Сортируем по дате (сначала новые)
    all_feedbacks.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    if not all_feedbacks:
        print("📭 Отзывов нет")
        await query.message.edit_text("📭 Нет отзывов")
        return await show_ratings_stats(update, context)
    
    # Показываем по 5 отзывов на странице
    page = int(context.user_data.get('feedbacks_page', 0))
    items_per_page = 5
    total_pages = (len(all_feedbacks) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(all_feedbacks))
    
    print(f"📄 Страница {page + 1} из {total_pages}, показаны {start_idx+1}-{end_idx}")
    
    text = f"📝 **ПОСЛЕДНИЕ ОТЗЫВЫ**\n\n"
    text += f"Страница {page + 1} из {total_pages}\n\n"
    
    for i in range(start_idx, end_idx):
        f = all_feedbacks[i]
        date_str = f['date'][:16] if f['date'] else 'Неизвестно'
        text += f"**{i+1}. {f['user']}** ({f['phone']})\n"
        text += f"   ⭐ Оценка: {f['rating']}/5\n"
        text += f"   💰 Покупка: {f['purchase']} руб.\n"
        text += f"   📝 Отзыв: {f['text']}\n"
        text += f"   🕐 {date_str}\n\n"
    
    # Кнопки навигации
    keyboard = []
    nav_row = []
    
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀ Предыдущая", callback_data="feedbacks_page_prev"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Следующая ▶", callback_data="feedbacks_page_next"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("🔙 К статистике", callback_data="back_to_ratings_stats")])
    keyboard.append([InlineKeyboardButton("🔙 В админку", callback_data="back_to_admin")])
    
    context.user_data['feedbacks_page'] = page
    context.user_data['feedbacks_data'] = all_feedbacks
    
    print(f"📋 Отправляем клавиатуру с {len(keyboard)} рядами")
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Навигация по отзывам --------------------
async def feedbacks_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка навигации по страницам отзывов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    page = context.user_data.get('feedbacks_page', 0)
    
    if data == "feedbacks_page_next":
        page += 1
    elif data == "feedbacks_page_prev":
        page -= 1
    elif data == "back_to_ratings_stats":
        return await show_ratings_stats(update, context)
    
    context.user_data['feedbacks_page'] = page
    return await show_feedbacks(update, context)

# -------------------- Обработка отправки сообщения --------------------
async def process_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает отправку сообщения клиенту"""
    # Обновляем активность админа
    if update.effective_user:
        update_user_activity(update.effective_user.id)
    
    user = update.message.from_user
    text = update.message.text.strip()
    
    print(f"📨 process_client_message: пользователь {user.id} отправил текст: '{text}'")
    print(f"📨 Данные из context: target={context.user_data.get('message_target')}, name={context.user_data.get('message_target_name')}")
    
    if text == "⬅ Отмена":
        print("❌ Отправка отменена пользователем")
        await update.message.reply_text("❌ Отправка отменена", reply_markup=ReplyKeyboardRemove())
        context.user_data.pop('message_target', None)
        context.user_data.pop('message_target_name', None)
        from handlers import show_menu
        return await show_menu(update, context)
    
    target_uid = context.user_data.get('message_target')
    target_name = context.user_data.get('message_target_name', 'Клиент')
    
    if not target_uid:
        print("❌ Ошибка: target_uid не найден в context.user_data")
        await update.message.reply_text("❌ Ошибка: клиент не найден", reply_markup=ReplyKeyboardRemove())
        from handlers import show_menu
        return await show_menu(update, context)
    
    print(f"📨 Отправляем сообщение пользователю {target_uid} ({target_name}): '{text}'")
    
    try:
        # Отправляем сообщение клиенту
        await context.bot.send_message(
            chat_id=int(target_uid),
            text=f"✉️ **Сообщение от администратора**\n\n{text}",
            parse_mode='Markdown'
        )
        
        print(f"✅ Сообщение успешно отправлено пользователю {target_uid}")
        
        # Подтверждение админу
        await update.message.reply_text(
            f"✅ **Сообщение отправлено!**\n\n"
            f"Получатель: {target_name}\n"
            f"Текст: {text}",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        
        logger.info(f"Админ {user.id} отправил сообщение пользователю {target_uid}")
        
    except Exception as e:
        error_text = str(e)
        print(f"❌ ОШИБКА при отправке: {error_text}")
        await update.message.reply_text(
            f"❌ **Ошибка при отправке**\n\n"
            f"Не удалось отправить сообщение клиенту.\n"
            f"Причина: {error_text}",
            reply_markup=ReplyKeyboardRemove()
        )
        logger.error(f"Ошибка отправки сообщения: {e}")
    
    # Очищаем данные
    context.user_data.pop('message_target', None)
    context.user_data.pop('message_target_name', None)
    print("🧹 Данные очищены, возвращаемся в главное меню")
    
    from handlers import show_menu
    return await show_menu(update, context)

# -------------------- Вернуться к уровням --------------------
async def back_to_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к статистике уровней"""
    query = update.callback_query
    await query.answer()
    return await show_level_stats(update, context)

# -------------------- Показать список кассиров для удаления --------------------
async def show_cashier_list_for_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список кассиров для удаления"""
    query = update.callback_query
    cashiers_list = get_cashiers_list()
    users = load_users()
    
    if not cashiers_list:
        await query.message.edit_text("📭 Нет кассиров для удаления")
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    # Создаем inline-кнопки
    keyboard = []
    row = []
    
    for i, cashier_id in enumerate(cashiers_list, 1):
        cashier_info = users.get(str(cashier_id), {})
        name = cashier_info.get('name', 'Неизвестно')
        if len(name) > 15:
            name = name[:15] + "..."
        
        btn_text = f"{i}. {name}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"select_remove_cashier_{cashier_id}"))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="back_to_admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        "🔰 **Выберите кассира для удаления:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Показать список админов для удаления --------------------
async def show_admin_list_for_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список админов для удаления"""
    query = update.callback_query
    admins_list = get_admins_list()
    users = load_users()
    
    if len(admins_list) <= 1:  # Только главный админ
        await query.message.edit_text("📭 Нет администраторов для удаления (кроме основного)")
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    # Создаем inline-кнопки
    keyboard = []
    row = []
    
    for i, admin_id in enumerate(admins_list, 1):
        if admin_id == 721775329:  # Пропускаем главного админа
            continue
            
        admin_info = users.get(str(admin_id), {})
        name = admin_info.get('name', 'Неизвестно')
        if len(name) > 15:
            name = name[:15] + "..."
        
        btn_text = f"{i}. {name}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"select_remove_admin_{admin_id}"))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="back_to_admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        "👑 **Выберите администратора для удаления:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Обработка кнопок админа --------------------
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обновляем активность админа
    if update.effective_user:
        update_user_activity(update.effective_user.id)
    
    query = update.callback_query
    await query.answer()
    user = query.from_user
    # Очищаем старые данные пользователя
    clear_user_data(user.id)
    logger.info(f"🔥 НАЖАТА КНОПКА: {query.data} от пользователя {user.id}")
    print(f"🔥 НАЖАТА КНОПКА: {query.data} от пользователя {user.id}")
    
    if not is_admin(user.id):
        logger.info(f"❌ Пользователь {user.id} не админ")
        await query.message.reply_text("❌ Вы не админ!")
        return ConversationHandler.END

    action = query.data
    print(f"🔍 ДЕЙСТВИЕ: {action}")

    if action == "back_to_admin":
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': user,
                'chat': query.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END

    # Выход из админки
    elif action == "exit_admin":
        await query.message.reply_text(
            "👋 Выход из админ-меню", 
            reply_markup=ReplyKeyboardRemove()
        )
        from handlers import show_menu
        return await show_menu(update, context)
        
    elif action == "show_feedbacks":
        return await show_feedbacks(update, context)

    elif action == "show_feedbacks":
        print("📝 Вызван show_feedbacks из admin_buttons")
        return await show_feedbacks(update, context)

# Добавьте этот блок после обработки show_ratings_stats
    elif action == "show_feedbacks":
        print("📝 Вызван show_feedbacks из admin_buttons")
        return await show_feedbacks(update, context)

    elif action.startswith("client_details_"):
        return await show_client_details(update, context)

    elif action.startswith("client_history_"):
        return await show_client_history(update, context)

    elif action.startswith("bonus_add_") or action.startswith("bonus_remove_"):
        return await quick_bonus_start(update, context)
        
    elif action.startswith("message_client_"):
        print(f"📨 Обработка message_client_ в admin_buttons: {action}")
        return await start_message_to_client(update, context)

    elif action == "back_to_clients":
        # Возвращаемся к списку клиентов (нужно сохранять последний уровень)
        level = context.user_data.get('current_level', 'BRONZE')
        return await show_level_clients(update, context)

    # Действия с выбором пользователя
    if action in ["admin_add", "admin_remove"]:
        admin_actions[user.id] = {"action": action}
        print(f"💾 Сохраняем действие: {action} для пользователя {user.id}")
        return await show_user_list(update, context, "select_for_bonus")
    
    elif action == "role_admin":
        admin_actions[user.id] = {"action": "add_admin"}
        return await show_user_list(update, context, "add_admin")
        
    elif action == "show_ratings_stats":
        return await show_ratings_stats(update, context)

    elif action in ["feedbacks_page_next", "feedbacks_page_prev", "back_to_ratings_stats"]:
        return await feedbacks_navigation(update, context)
    
    elif action == "role_remove_admin":
        admin_actions[user.id] = {"action": "remove_admin"}
        return await show_admin_list_for_remove(update, context)
    
    elif action == "role_cashier":
        admin_actions[user.id] = {"action": "add_cashier"}
        return await show_user_list(update, context, "add_cashier")
    
    elif action == "role_remove_cashier":
        admin_actions[user.id] = {"action": "remove_cashier"}
        return await show_cashier_list_for_remove(update, context)
    
    elif action == "admin_delete_user":
        admin_actions[user.id] = {"action": "delete_user"}
        return await show_user_list(update, context, "delete")

    elif action == "admin_qr":
        await query.message.reply_text(
            "Отправьте фото QR-кода:",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return WAIT_QR

    elif action == "admin_stats":
        users = load_users()
        text = "📊 Статистика пользователей:\n\n"
        for uid, u in users.items():
            name = u.get('name', '?')
            username = u.get('username', '?')
            balance = u.get('balance', 0)
            registered = "✅" if u.get('registered') else "❌"
            text += f"{registered} {name} | @{username} | Баланс: {balance}\n"
        
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await query.message.reply_text(part)
        else:
            await query.message.reply_text(text)
        
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': user,
                'chat': query.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END
    
    elif action == "admin_list_admins":
        admins_list = get_admins_list()
        
        if not admins_list:
            await query.message.reply_text("📭 Список администраторов пуст")
        else:
            text = "👑 СПИСОК АДМИНИСТРАТОРОВ:\n\n"
            for i, admin_id in enumerate(admins_list, 1):
                details = get_admin_details(admin_id)
                text += f"{i}. ID: {admin_id}\n"
                text += f"   👤 Имя: {details['name']}\n"
                text += f"   📱 Телефон: {details['phone']}\n"
                text += f"   🆔 Username: @{details['username']}\n\n"
            
            if len(text) > 4000:
                parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for part in parts:
                    await query.message.reply_text(part)
            else:
                await query.message.reply_text(text)
        
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': user,
                'chat': query.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END
    
    elif action == "admin_list_cashiers":
        cashiers_list = get_cashiers_list()
        
        if not cashiers_list:
            await query.message.reply_text("📭 Список кассиров пуст")
        else:
            text = "🔰 СПИСОК КАССИРОВ:\n\n"
            for i, cashier_id in enumerate(cashiers_list, 1):
                details = get_cashier_details(cashier_id)
                text += f"{i}. ID: {cashier_id}\n"
                text += f"   👤 Имя: {details['name']}\n"
                text += f"   📱 Телефон: {details['phone']}\n"
                text += f"   🆔 Username: @{details['username']}\n\n"
            
            if len(text) > 4000:
                parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for part in parts:
                    await query.message.reply_text(part)
            else:
                await query.message.reply_text(text)
        
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': user,
                'chat': query.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END
    
    elif action == "show_level_stats":
        return await show_level_stats(update, context)
    
    elif action.startswith("show_level_"):
        return await show_level_clients(update, context)
    
    elif action.startswith("msg_client_"):
        print(f"📨 Обработка msg_client_ в admin_buttons: {action}")
        return await start_message_to_client(update, context)
    
    elif action == "back_to_levels":
        return await back_to_levels(update, context)

# -------------------- Показать список пользователей для выбора --------------------
async def show_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE, action):
    """Показывает список пользователей для выбора"""
    query = update.callback_query
    users = load_users()
    
    # Фильтруем пользователей в зависимости от действия
    available_users = []
    for uid, u in users.items():
        if action == "delete" and is_admin(int(uid)):
            continue
        if action == "add_admin" and is_admin(int(uid)):
            continue
        if action == "remove_admin" and not is_admin(int(uid)):
            continue
        if action == "add_cashier" and is_cashier(int(uid)):
            continue
        if action == "remove_cashier" and not is_cashier(int(uid)):
            continue
        if action == "select_for_bonus":
            pass  # Показываем всех пользователей
        
        if u.get('registered'):
            available_users.append((uid, u))
    
    if not available_users:
        action_texts = {
            "delete": "нет пользователей для удаления",
            "add_admin": "нет пользователей для назначения админом",
            "remove_admin": "нет админов для удаления",
            "add_cashier": "нет пользователей для назначения кассиром",
            "remove_cashier": "нет кассиров для удаления",
            "select_for_bonus": "нет пользователей для начисления бонусов"
        }
        await query.message.edit_text(f"📭 {action_texts.get(action, 'Нет пользователей')}")
        return ADMIN_SELECT_USER
    
    # Сортируем по имени
    available_users.sort(key=lambda x: x[1].get('name', '') or '')
    
    # Создаем inline-кнопки
    keyboard = []
    row = []
    
    for i, (uid, u) in enumerate(available_users, 1):
        name = u.get('name', 'Без имени')
        if len(name) > 20:
            name = name[:20] + "..."
        
        balance = u.get('balance', 0)
        
        if action == "select_for_bonus":
            btn_text = f"{i}. {name} ({balance} бон.)"
            callback_data = f"select_for_bonus_{uid}"
        elif action == "delete":
            btn_text = f"{i}. {name} ({balance} бон.)"
            callback_data = f"select_delete_{uid}"
        elif action == "add_admin":
            btn_text = f"{i}. {name}"
            callback_data = f"select_add_admin_{uid}"
        elif action == "remove_admin":
            btn_text = f"{i}. {name}"
            callback_data = f"select_remove_admin_{uid}"
        elif action == "add_cashier":
            btn_text = f"{i}. {name}"
            callback_data = f"select_add_cashier_{uid}"
        elif action == "remove_cashier":
            btn_text = f"{i}. {name}"
            callback_data = f"select_remove_cashier_{uid}"
        else:
            btn_text = f"{i}. {name}"
            callback_data = f"select_{action}_{uid}"
        
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))
        
        if len(row) == 1:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="back_to_admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    title_texts = {
        "delete": "🗑 Выберите пользователя для удаления:",
        "add_admin": "👑 Выберите пользователя для назначения админом:",
        "remove_admin": "👑 Выберите админа для удаления:",
        "add_cashier": "🔰 Выберите пользователя для назначения кассиром:",
        "remove_cashier": "🔰 Выберите кассира для удаления:",
        "select_for_bonus": "💰 Выберите пользователя для начисления/снятия бонусов:"
    }
    
    await query.message.edit_text(
        title_texts.get(action, "Выберите пользователя:"),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ADMIN_SELECT_USER

# -------------------- Обработка выбора пользователя --------------------
async def handle_user_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обновляем активность админа
    if update.effective_user:
        update_user_activity(update.effective_user.id)
    
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    # ОТЛАДКА
    print(f"🎯 handle_user_selection вызвана с data: {data}")
    print(f"👤 Пользователь: {user_id}")
    
    if data == "back_to_admin":
        print("🔙 Возврат в админку")
        clear_user_data(user_id)
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END
    
    # Обработка выбора для бонусов
    if data.startswith("select_for_bonus_"):
        print("💰 Выбрано для бонусов")
        target_uid = data.replace("select_for_bonus_", "")
        print(f"🎯 target_uid: {target_uid}")
        
        if not target_uid.isdigit():
            await query.message.reply_text("❌ Неверный формат ID пользователя")
            from handlers import show_menu
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await show_menu(fake_update, context)
        
        users = load_users()
        if target_uid not in users:
            await query.message.reply_text("❌ Пользователь не найден")
            from handlers import show_menu
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await show_menu(fake_update, context)
        
        target_user = users[target_uid]
        name = target_user.get('name', 'Неизвестно')
        
        if user_id not in admin_actions:
            admin_actions[user_id] = {}
        
        admin_actions[user_id]["target"] = target_uid
        admin_actions[user_id]["target_name"] = name
        
        action_text = "начисления" if admin_actions[user_id]["action"] == "admin_add" else "снятия"
        await query.message.edit_text(
            f"💰 **{action_text.title()} бонусов**\n\n"
            f"Пользователь: {name}\n"
            f"ID: {target_uid}\n\n"
            f"Введите сумму:"
        )
        
        await query.message.reply_text(
            "📝 Введите сумму:",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return ADMIN_AMOUNT
    
    # Обработка выбора для удаления пользователя
    elif data.startswith("select_delete_"):
        print("🗑 Выбрано для удаления пользователя")
        target_uid = data.replace("select_delete_", "")
        print(f"🎯 target_uid: {target_uid}")
        
        if not target_uid.isdigit():
            await query.message.reply_text("❌ Неверный формат ID пользователя")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        users = load_users()
        if target_uid not in users:
            await query.message.reply_text("❌ Пользователь не найден")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        target_user = users[target_uid]
        name = target_user.get('name', 'Неизвестно')
        phone = target_user.get('phone', 'Нет')
        balance = target_user.get('balance', 0)
        
        if user_id not in admin_actions:
            admin_actions[user_id] = {}
        
        admin_actions[user_id]["target"] = target_uid
        admin_actions[user_id]["target_info"] = target_user
        
        confirm_kb = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_delete_yes")],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data="back_to_admin")]
        ]
        
        await query.message.edit_text(
            f"⚠️ **Подтверждение удаления**\n\n"
            f"Вы собираетесь удалить пользователя:\n"
            f"👤 **Имя:** {name}\n"
            f"📱 **Телефон:** {phone}\n"
            f"💰 **Баланс:** {balance}\n"
            f"🆔 **ID:** `{target_uid}`\n\n"
            f"Это действие нельзя отменить!",
            reply_markup=InlineKeyboardMarkup(confirm_kb),
            parse_mode='Markdown'
        )
        return ADMIN_SELECT_USER
    
    # Обработка подтверждения удаления
    elif data == "confirm_delete_yes":
        print("✅ Подтверждение удаления")
        if user_id not in admin_actions or "target" not in admin_actions[user_id]:
            await query.message.reply_text("❌ Ошибка данных. Начните заново.")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        target_uid = admin_actions[user_id]["target"]
        target_info = admin_actions[user_id].get("target_info", {})
        
        if is_admin(int(target_uid)):
            await query.message.reply_text("❌ Нельзя удалить администратора!")
            clear_user_data(user_id)
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        if delete_user(target_uid):
            name = target_info.get('name', 'Неизвестно')
            await query.message.edit_text(f"✅ **Пользователь успешно удален!**")
        else:
            await query.message.edit_text("❌ Ошибка при удалении пользователя")
        
        clear_user_data(user_id)
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    elif data.startswith("msg_client_"):
        print(f"📨 Выбрано для отправки сообщения: {data}")
        return await start_message_to_client(update, context)
    
    # Обработка выбора для назначения кассира
    elif data.startswith("select_add_cashier_"):
        print("👤 Выбрано для назначения кассира")
        target_uid = data.replace("select_add_cashier_", "")
        print(f"🎯 target_uid: {target_uid}")
        
        if not target_uid.isdigit():
            await query.message.reply_text("❌ Неверный формат ID пользователя")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        users = load_users()
        if target_uid not in users:
            await query.message.reply_text("❌ Пользователь не найден")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        target_user = users[target_uid]
        name = target_user.get('name', 'Неизвестно')
        
        if is_cashier(int(target_uid)):
            await query.message.edit_text(f"❌ Пользователь {name} уже является кассиром")
        else:
            add_cashier(int(target_uid))
            await query.message.edit_text(
                f"✅ **Кассир назначен!**\n\n"
                f"👤 Пользователь: {name}\n"
                f"🆔 ID: {target_uid}",
                parse_mode='Markdown'
            )
        
        clear_user_data(user_id)
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    # Обработка выбора для удаления кассира
    elif data.startswith("select_remove_cashier_"):
        print("🗑 Выбрано для удаления кассира")
        target_uid = data.replace("select_remove_cashier_", "")
        print(f"🎯 target_uid: {target_uid}")
        
        if not target_uid.isdigit():
            await query.message.reply_text("❌ Неверный формат ID пользователя")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        users = load_users()
        target_user = users.get(target_uid, {})
        name = target_user.get('name', 'Неизвестно')
        
        remove_cashier(int(target_uid))
        await query.message.edit_text(
            f"✅ **Кассир удален!**\n\n"
            f"👤 Пользователь: {name}\n"
            f"🆔 ID: {target_uid}",
            parse_mode='Markdown'
        )
        
        clear_user_data(user_id)
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    # Обработка выбора для назначения админа
    elif data.startswith("select_add_admin_"):
        print("👑 Выбрано для назначения админа")
        target_uid = data.replace("select_add_admin_", "")
        
        if not target_uid.isdigit():
            await query.message.reply_text("❌ Неверный формат ID пользователя")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        users = load_users()
        if target_uid not in users:
            await query.message.reply_text("❌ Пользователь не найден")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        target_user = users[target_uid]
        name = target_user.get('name', 'Неизвестно')
        
        if is_admin(int(target_uid)):
            await query.message.edit_text(f"❌ Пользователь {name} уже является администратором")
        else:
            add_admin(int(target_uid))
            await query.message.edit_text(
                f"✅ **Администратор назначен!**\n\n"
                f"👤 Пользователь: {name}\n"
                f"🆔 ID: {target_uid}",
                parse_mode='Markdown'
            )
        
        clear_user_data(user_id)
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    # Обработка выбора для удаления админа
    elif data.startswith("select_remove_admin_"):
        print("👑 Выбрано для удаления админа")
        target_uid = data.replace("select_remove_admin_", "")
        
        if not target_uid.isdigit():
            await query.message.reply_text("❌ Неверный формат ID пользователя")
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
        
        users = load_users()
        target_user = users.get(target_uid, {})
        name = target_user.get('name', 'Неизвестно')
        
        if int(target_uid) == 721775329:
            await query.message.edit_text("❌ Нельзя удалить основного администратора")
        elif remove_admin(int(target_uid)):
            await query.message.edit_text(
                f"✅ **Администратор удален!**\n\n"
                f"👤 Пользователь: {name}\n"
                f"🆔 ID: {target_uid}",
                parse_mode='Markdown'
            )
        else:
            await query.message.edit_text("❌ Ошибка при удалении администратора")
        
        clear_user_data(user_id)
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': type('obj', (object,), {
                'reply_text': query.message.reply_text,
                'from_user': query.from_user,
                'chat': query.message.chat
            })
        })
        return await admin_menu(fake_update, context)
    
    # Обработка других select_ действий (на всякий случай)
    elif data.startswith("select_"):
        print("📋 Другое select_ действие")
        parts = data.split('_')
        print(f"🔍 parts: {parts}")
        
        if len(parts) >= 4:
            if parts[1] == "add" and parts[2] == "admin":
                action = "add_admin"
                target_uid = parts[3]
            elif parts[1] == "remove" and parts[2] == "admin":
                action = "remove_admin"
                target_uid = parts[3]
            elif parts[1] == "add" and parts[2] == "cashier":
                action = "add_cashier"
                target_uid = parts[3]
            elif parts[1] == "remove" and parts[2] == "cashier":
                action = "remove_cashier"
                target_uid = parts[3]
            else:
                await query.message.reply_text("❌ Неизвестный формат действия")
                fake_update = type('obj', (object,), {
                    'effective_user': query.from_user,
                    'message': type('obj', (object,), {
                        'reply_text': query.message.reply_text,
                        'from_user': query.from_user,
                        'chat': query.message.chat
                    })
                })
                return await admin_menu(fake_update, context)
            
            if not target_uid.isdigit():
                await query.message.reply_text(f"❌ Неверный формат ID пользователя")
                fake_update = type('obj', (object,), {
                    'effective_user': query.from_user,
                    'message': type('obj', (object,), {
                        'reply_text': query.message.reply_text,
                        'from_user': query.from_user,
                        'chat': query.message.chat
                    })
                })
                return await admin_menu(fake_update, context)
            
            users = load_users()
            if target_uid not in users:
                await query.message.reply_text("❌ Пользователь не найден")
                fake_update = type('obj', (object,), {
                    'effective_user': query.from_user,
                    'message': type('obj', (object,), {
                        'reply_text': query.message.reply_text,
                        'from_user': query.from_user,
                        'chat': query.message.chat
                    })
                })
                return await admin_menu(fake_update, context)
            
            target_user = users[target_uid]
            name = target_user.get('name', 'Неизвестно')
            
            if action == "add_admin":
                add_admin(int(target_uid))
                await query.message.edit_text(f"✅ **Администратор назначен!**")
            
            elif action == "remove_admin":
                if remove_admin(int(target_uid)):
                    await query.message.edit_text(f"✅ **Администратор удален!**")
                else:
                    await query.message.edit_text("❌ Нельзя удалить основного администратора")
            
            elif action == "add_cashier":
                add_cashier(int(target_uid))
                await query.message.edit_text(f"✅ **Кассир назначен!**")
            
            elif action == "remove_cashier":
                remove_cashier(int(target_uid))
                await query.message.edit_text(f"✅ **Кассир удален!**")
            
            clear_user_data(user_id)
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': type('obj', (object,), {
                    'reply_text': query.message.reply_text,
                    'from_user': query.from_user,
                    'chat': query.message.chat
                })
            })
            return await admin_menu(fake_update, context)
    
    print("❌ Ни одно условие не сработало")
    clear_user_data(user_id)
    fake_update = type('obj', (object,), {
        'effective_user': query.from_user,
        'message': type('obj', (object,), {
            'reply_text': query.message.reply_text,
            'from_user': query.from_user,
            'chat': query.message.chat
        })
    })
    return await admin_menu(fake_update, context)

# -------------------- Ввод суммы для начисления/снятия --------------------
async def admin_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод суммы для начисления или снятия бонусов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    user = update.message.from_user
    text = update.message.text.strip()
    
    if text == "⬅ Отмена":
        await update.message.reply_text("❌ Действие отменено", reply_markup=ReplyKeyboardRemove())
        if user.id in admin_actions:
            del admin_actions[user.id]
        from handlers import show_menu
        return await show_menu(update, context)

    if user.id not in admin_actions or "target" not in admin_actions[user.id]:
        await update.message.reply_text("❌ Ошибка данных. Начните заново.", reply_markup=ReplyKeyboardRemove())
        from handlers import show_menu
        return await show_menu(update, context)

    try:
        amount = int(text)
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text(
            "❌ Введите положительное число!",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return ADMIN_AMOUNT

    # Загружаем свежие данные
    users = load_users()
    target_uid = admin_actions[user.id]["target"]
    target_name = admin_actions[user.id].get("target_name", "Пользователь")
    action = admin_actions[user.id]["action"]

    if action == "admin_add":
        users[target_uid]["balance"] = users[target_uid].get("balance", 0) + amount
        
        # ✅ add_history УЖЕ СОХРАНЯЕТ, НЕ НУЖНО ДОПОЛНИТЕЛЬНОЕ save_users!
        add_history(
            target_uid, 
            "➕ **Начисление бонусов**", 
            f"+{amount} бонусов (начислено администратором {user.first_name})"
        )
        
        await update.message.reply_text(
            f"✅ **Бонусы начислены!**\n\n"
            f"👤 Пользователь: {target_name}\n"
            f"💰 Сумма: +{amount}\n"
            f"🆔 ID: {target_uid}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

    elif action == "admin_remove":
        current_balance = users[target_uid].get("balance", 0)
        if current_balance < amount:
            await update.message.reply_text(
                f"❌ Недостаточно бонусов! Баланс: {current_balance}",
                reply_markup=ReplyKeyboardRemove()
            )
            del admin_actions[user.id]
            from handlers import show_menu
            return await show_menu(update, context)
        
        users[target_uid]["balance"] = current_balance - amount
        
        # ✅ add_history УЖЕ СОХРАНЯЕТ, НЕ НУЖНО ДОПОЛНИТЕЛЬНОЕ save_users!
        add_history(
            target_uid, 
            "➖ **Списание бонусов**", 
            f"-{amount} бонусов (снято администратором {user.first_name})"
        )
        
        await update.message.reply_text(
            f"✅ **Бонусы сняты!**\n\n"
            f"👤 Пользователь: {target_name}\n"
            f"💰 Сумма: -{amount}\n"
            f"🆔 ID: {target_uid}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

    # ✅ УБИРАЕМ save_users(users) - ОН ПЕРЕЗАПИСЫВАЕТ СТАРЫЕ ДАННЫЕ!
    # add_history уже сохранил
    
    # Удаляем временные данные
    del admin_actions[user.id]
    
    from handlers import show_menu
    return await show_menu(update, context)

# -------------------- Списание по QR --------------------
async def redeem_qr_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Отправьте фото QR-кода",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return WAIT_QR

    photo = update.message.photo[-1]
    file = await photo.get_file()
    bio = BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)
    
    try:
        img = Image.open(bio)
        decoded = decode(img)
        
        if not decoded:
            await update.message.reply_text(
                "❌ QR-код не распознан",
                reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
            )
            return WAIT_QR

        qr_data = decoded[0].data.decode()
        match = re.search(r"TG_ID:(\d+)", qr_data)
        
        if not match:
            await update.message.reply_text(
                "❌ Неверный формат QR-кода",
                reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
            )
            return WAIT_QR

        target_id = match.group(1)
        users = load_users()
        
        if target_id not in users:
            await update.message.reply_text(
                "❌ Пользователь не найден",
                reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
            )
            return WAIT_QR

        context.user_data["target_id"] = target_id
        await update.message.reply_text(
            "✅ QR распознан! Введите сумму бонусов для списания:",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return WAIT_AMOUNT
        
    except Exception as e:
        logger.error(f"Ошибка при обработке QR: {e}")
        await update.message.reply_text(
            "❌ Ошибка при обработке изображения",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return WAIT_QR

async def redeem_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()
    
    if text == "⬅ Отмена":
        await update.message.reply_text("❌ Действие отменено", reply_markup=ReplyKeyboardRemove())
        context.user_data.pop("target_id", None)
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': type('obj', (object,), {
                'reply_text': update.message.reply_text,
                'from_user': user,
                'chat': update.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END

    users = load_users()
    target_id = context.user_data.get("target_id")
    
    if not target_id:
        await update.message.reply_text("❌ Ошибка. Попробуйте заново.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    try:
        amount = int(text)
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text(
            "❌ Введите положительное число!",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return WAIT_AMOUNT

    current_balance = users[target_id].get("balance", 0)
    if current_balance < amount:
        await update.message.reply_text(f"❌ Недостаточно бонусов! Баланс: {current_balance}", reply_markup=ReplyKeyboardRemove())
        context.user_data.pop("target_id", None)
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': type('obj', (object,), {
                'reply_text': update.message.reply_text,
                'from_user': user,
                'chat': update.message.chat
            })
        })
        await admin_menu(fake_update, context)
        return ConversationHandler.END

    users[target_id]["balance"] = current_balance - amount

    add_history(
        target_id,
        "➖ **Списание бонусов по QR**",
        f"-{amount} бонусов (списано по QR-коду администратором {user.first_name})"
    )
    
    users = load_users()
    print(f"🔍 После добавления: в истории пользователя {target_uid} {len(users[target_uid].get('history', []))} записей")
    
    save_users(users)
    
    await update.message.reply_text(
        f"✅ **Бонусы списаны по QR!**\n\n"
        f"👤 Пользователь: {name}\n"
        f"💰 Сумма: -{amount}\n"
        f"🆔 ID: {target_id}",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.pop("target_id", None)
    fake_update = type('obj', (object,), {
        'effective_user': user,
        'message': type('obj', (object,), {
            'reply_text': update.message.reply_text,
            'from_user': user,
            'chat': update.message.chat
        })
    })
    await admin_menu(fake_update, context)
    return ConversationHandler.END

# -------------------- ConversationHandler --------------------
def get_admin_conv():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_buttons, pattern="^(admin_|role_|show_level_|show_ratings_stats|show_feedbacks|client_details_|client_history_|bonus_add_|bonus_remove_|back_to_clients|feedbacks_page_|back_to_ratings_stats|message_client_|back_to_levels|exit_|back_to_admin)")],
        states={
            ADMIN_SELECT_USER: [
                CallbackQueryHandler(handle_user_selection, pattern="^(select_for_bonus_|select_delete_|select_add_admin_|select_remove_admin_|select_add_cashier_|select_remove_cashier_|confirm_delete_yes|back_to_admin)"),
                CallbackQueryHandler(show_level_clients, pattern="^show_level_"),
                CallbackQueryHandler(show_ratings_stats, pattern="^show_ratings_stats$"),
                CallbackQueryHandler(show_feedbacks, pattern="^show_feedbacks$"),
                CallbackQueryHandler(show_client_details, pattern="^client_details_"),
                CallbackQueryHandler(show_client_history, pattern="^client_history_"),
                CallbackQueryHandler(quick_bonus_start, pattern="^(bonus_add_|bonus_remove_)"),
                CallbackQueryHandler(feedbacks_navigation, pattern="^(feedbacks_page_|back_to_ratings_stats)$"),
                CallbackQueryHandler(start_message_to_client, pattern="^message_client_"),
                CallbackQueryHandler(back_to_levels, pattern="^back_to_levels$"),
                CallbackQueryHandler(show_level_stats, pattern="^show_level_stats$")
            ],
            ADMIN_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_amount_input)
            ],
            ADMIN_MESSAGE: [  # Это состояние должно быть
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_client_message)
            ],
            WAIT_QR: [
                MessageHandler(filters.PHOTO, redeem_qr_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text("Отправьте фото QR-кода"))
            ],
            WAIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_amount)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("⬅ Отмена"), lambda u, c: admin_menu(u, c) or ConversationHandler.END),
            CallbackQueryHandler(lambda u, c: admin_menu(u, c) or ConversationHandler.END, pattern="^back_to_admin$")
        ],
        per_user=True,
        per_message=False,
        name="admin_conversation"
    )