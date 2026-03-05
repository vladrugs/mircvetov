# cashier_payment.py
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from utils import load_users, save_users, add_history, check_level_increase
from datetime import datetime
import logging
import re
from ratings import ask_for_rating
from level_notifications import send_level_up_congratulations, send_level_milestone

# Импортируем функцию show_menu напрямую
from handlers import show_menu

# Состояния
CASHIER_PHONE, CASHIER_PURCHASE, CASHIER_BONUS = range(3)

# Максимальный процент списания
MAX_BONUS_PERCENT = 30

# Временное хранилище
payment_data = {}

logger = logging.getLogger(__name__)

# ------------------- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ВОЗВРАТА В МЕНЮ -------------------
async def return_to_main_menu(user_id, context):
    """Возвращает пользователя в главное меню"""
    from handlers import show_menu
    
    # Создаем простое сообщение для вызова меню
    class SimpleMessage:
        def __init__(self, user_id):
            self.text = "/start"
            self.from_user = type('User', (), {'id': user_id, 'first_name': 'User', 'username': None})
            self.chat = type('Chat', (), {'id': user_id})
            self.message_id = 0
            self.date = datetime.now()
    
    class SimpleUpdate:
        def __init__(self, user_id):
            self.message = SimpleMessage(user_id)
            self.effective_user = self.message.from_user
            self.effective_chat = self.message.chat
            self.update_id = 0
    
    simple_update = SimpleUpdate(user_id)
    await show_menu(simple_update, context)

# ------------------- НАЧАЛО ОПЛАТЫ (кассир) -------------------
async def payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса оплаты"""
    cashier_id = update.effective_user.id
    
    # Показываем клавиатуру с кнопкой отмены
    kb = ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
    
    # Инициализируем данные для кассира
    payment_data[cashier_id] = {
        "cashier_id": cashier_id,
        "step": "start"
    }
    
    await update.message.reply_text(
        "💳 **Оплата бонусами**\n\n"
        "Введите номер телефона покупателя:\n"
        "(например: +79991234567 или 89991234567)",
        reply_markup=kb,
        parse_mode='Markdown'
    )
    return CASHIER_PHONE

# ------------------- ВВОД ТЕЛЕФОНА (кассир) -------------------
async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка номера телефона"""
    text = update.message.text.strip()
    cashier_id = update.effective_user.id
    
    if text == "⬅ Отмена":
        await update.message.reply_text("❌ Операция отменена", reply_markup=ReplyKeyboardRemove())
        payment_data.pop(cashier_id, None)
        from handlers import back_to_menu
        return await back_to_menu(update, context)
    
    # Нормализуем номер
    phone = re.sub(r"\D", "", text)
    if phone.startswith("8"):
        phone = "+7" + phone[1:]
    elif phone.startswith("7"):
        phone = "+7" + phone[1:]
    else:
        phone = "+7" + phone
    
    # Ищем пользователя
    users = load_users()
    customer_uid = None
    customer_data = None
    
    for uid, data in users.items():
        if data.get("phone") == phone:
            customer_uid = uid
            customer_data = data
            break
    
    if not customer_data:
        kb = ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        await update.message.reply_text(
            "❌ Пользователь с таким номером не найден!\n"
            "Проверьте номер и попробуйте снова:",
            reply_markup=kb
        )
        return CASHIER_PHONE
    
    # Сохраняем данные
    if cashier_id not in payment_data:
        payment_data[cashier_id] = {}
    
    payment_data[cashier_id].update({
        "customer_uid": customer_uid,
        "customer_name": customer_data.get("name", "Покупатель"),
        "customer_balance": customer_data.get("balance", 0),
        "step": "phone_entered"
    })
    
    kb = ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
    await update.message.reply_text(
        f"✅ **Покупатель найден!**\n\n"
        f"👤 **{customer_data.get('name', 'Покупатель')}**\n"
        f"📱 `{phone}`\n"
        f"💰 **Доступно бонусов:** {customer_data.get('balance', 0)}\n\n"
        f"Введите сумму покупки в рублях:",
        reply_markup=kb,
        parse_mode='Markdown'
    )
    return CASHIER_PURCHASE

# ------------------- ВВОД СУММЫ (кассир) -------------------
async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы покупки"""
    text = update.message.text.strip()
    cashier_id = update.effective_user.id
    
    if text == "⬅ Отмена":
        await update.message.reply_text("❌ Операция отменена", reply_markup=ReplyKeyboardRemove())
        payment_data.pop(cashier_id, None)
        from handlers import back_to_menu
        return await back_to_menu(update, context)
    
    # Проверяем, есть ли данные для кассира
    if cashier_id not in payment_data:
        await update.message.reply_text("❌ Ошибка данных. Начните заново.", reply_markup=ReplyKeyboardRemove())
        from handlers import back_to_menu
        return await back_to_menu(update, context)
    
    try:
        amount = int(re.sub(r"\D", "", text))
        if amount <= 0:
            raise ValueError
    except:
        kb = ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        await update.message.reply_text(
            "❌ Введите корректную сумму покупки (целое число):",
            reply_markup=kb
        )
        return CASHIER_PURCHASE
    
    payment_data[cashier_id]["purchase_amount"] = amount
    
    # Максимум бонусов
    max_bonus = min(
        payment_data[cashier_id]["customer_balance"],
        int(amount * MAX_BONUS_PERCENT / 100)
    )
    payment_data[cashier_id]["max_bonus"] = max_bonus
    
    kb = ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
    await update.message.reply_text(
        f"💰 **Сумма покупки:** {amount} руб.\n"
        f"🎯 **Максимально можно списать:** {max_bonus} бонусов\n"
        f"📊 Это {MAX_BONUS_PERCENT}% от суммы покупки\n\n"
        f"Введите количество бонусов для списания "
        f"(от 0 до {max_bonus}):",
        reply_markup=kb,
        parse_mode='Markdown'
    )
    return CASHIER_BONUS

# ------------------- ВВОД БОНУСОВ (кассир) -------------------
async def process_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка количества бонусов"""
    text = update.message.text.strip()
    cashier_id = update.effective_user.id
    
    if text == "⬅ Отмена":
        await update.message.reply_text("❌ Операция отменена", reply_markup=ReplyKeyboardRemove())
        payment_data.pop(cashier_id, None)
        from handlers import back_to_menu
        return await back_to_menu(update, context)
    
    # Проверяем, есть ли данные для кассира
    if cashier_id not in payment_data:
        await update.message.reply_text("❌ Ошибка данных. Начните заново.", reply_markup=ReplyKeyboardRemove())
        from handlers import back_to_menu
        return await back_to_menu(update, context)
    
    try:
        bonus = int(text)
        max_bonus = payment_data[cashier_id]["max_bonus"]
        if bonus < 0 or bonus > max_bonus:
            raise ValueError
    except:
        kb = ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        await update.message.reply_text(
            f"❌ Введите число от 0 до {payment_data[cashier_id]['max_bonus']}:",
            reply_markup=kb
        )
        return CASHIER_BONUS
    
    # Сохраняем бонусы
    payment_data[cashier_id]["bonus"] = bonus
    purchase = payment_data[cashier_id]["purchase_amount"]
    final = purchase - bonus
    
    if bonus == 0:
        # Если бонусы не списываем
        await update.message.reply_text(
            f"✅ **Оплата без списания бонусов**\n\n"
            f"Сумма к оплате: {purchase} руб.",
            reply_markup=ReplyKeyboardRemove()
        )
        payment_data.pop(cashier_id, None)
        from handlers import back_to_menu
        return await back_to_menu(update, context)
    
    # Сохраняем данные для покупателя
    customer_uid = payment_data[cashier_id]["customer_uid"]
    payment_data[f"customer_{customer_uid}"] = {
        "cashier_id": cashier_id,
        "bonus": bonus,
        "purchase": purchase,
        "final": final,
        "customer_name": payment_data[cashier_id]["customer_name"]
    }
    
    # ИНЛАЙН-КНОПКИ (под сообщением)
    keyboard = [
        [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ СПИСАНИЕ", callback_data=f"confirm_{cashier_id}")],
        [InlineKeyboardButton("❌ ОТКАЗАТЬСЯ", callback_data=f"reject_{cashier_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Отправляем сообщение покупателю с инлайн-кнопками
        await context.bot.send_message(
            chat_id=int(customer_uid),
            text=f"🛍 **Подтверждение оплаты бонусами**\n\n"
                 f"Сумма покупки: {purchase} руб.\n"
                 f"Списание бонусов: {bonus}\n"
                 f"Итого к оплате: {final} руб.\n\n"
                 f"Подтверждаете списание бонусов?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Подтверждение кассиру
        await update.message.reply_text(
            f"✅ **Запрос отправлен покупателю!**\n\n"
            f"Сумма покупки: {purchase} руб.\n"
            f"Списание бонусов: {bonus}\n"
            f"Итого к оплате: {final} руб.\n\n"
            f"Ожидайте подтверждения от покупателя...",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Возвращаем кассира в меню
        from handlers import back_to_menu
        return await back_to_menu(update, context)
        
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await update.message.reply_text(
            f"❌ **Не удалось отправить запрос покупателю**\n\n"
            f"Покупатель **{payment_data[cashier_id]['customer_name']}** еще не начал диалог с ботом.\n\n"
            f"📱 Отправьте покупателю ссылку:\n"
            f"https://t.me/mircvetovtosno_bot\n\n"
            f"Попросите написать любое сообщение (например, \"Привет\")",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        payment_data.pop(cashier_id, None)
        payment_data.pop(f"customer_{customer_uid}", None)
        from handlers import back_to_menu
        return await back_to_menu(update, context)

# ------------------- ОБРАБОТКА НАЖАТИЙ НА ИНЛАЙН-КНОПКИ (покупатель) -------------------
async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    customer_id = str(query.from_user.id)
    customer_key = f"customer_{customer_id}"
    
    # Проверяем, есть ли активный запрос
    if customer_key not in payment_data:
        await query.edit_message_text(
            "❌ **Запрос устарел**\n\nВремя подтверждения истекло.",
            parse_mode='Markdown'
        )
        return
    
    info = payment_data[customer_key]
    cashier_id = info["cashier_id"]
    bonus = info["bonus"]
    purchase = info["purchase"]
    final = info["final"]
    customer_name = info.get("customer_name", "Покупатель")
    
    if data.startswith("confirm_"):
        # Списываем бонусы
        users = load_users()
        current_balance = users[customer_id].get("balance", 0)
        
        # Проверяем, не пора ли обновить год
        current_year = datetime.now().year
        last_reset_year = users[customer_id].get("last_reset_year", current_year)
        
        if last_reset_year < current_year:
            # Сохраняем историю прошлого года
            old_purchases = users[customer_id].get("total_purchases", 0)
            if old_purchases > 0:
                if "purchases_history" not in users[customer_id]:
                    users[customer_id]["purchases_history"] = []
                users[customer_id]["purchases_history"].append({
                    "year": last_reset_year,
                    "amount": old_purchases
                })
                add_history(
                    customer_id,
                    "📊 **Годовой сброс**",
                    f"Покупки за {last_reset_year} год: {old_purchases} руб."
                )
            
            # Обнуляем для нового года
            users[customer_id]["total_purchases"] = 0
            users[customer_id]["last_reset_year"] = current_year
        
        # Получаем старую сумму покупок ДО обновления
        old_purchases = users[customer_id].get("total_purchases", 0)
        
        if current_balance < bonus:
            # Недостаточно бонусов
            await query.edit_message_text(
                f"❌ **Недостаточно бонусов!**\n\n"
                f"Текущий баланс: {current_balance}\n"
                f"Запрошено: {bonus}",
                parse_mode='Markdown'
            )
            await context.bot.send_message(
                chat_id=cashier_id,
                text=f"❌ **Недостаточно бонусов у покупателя!**\n\n"
                     f"Покупатель: {customer_name}\n"
                     f"Текущий баланс: {current_balance}\n"
                     f"Запрошено: {bonus}"
            )
        else:
            # Обновляем баланс и общую сумму покупок
            users[customer_id]["balance"] = current_balance - bonus
            users[customer_id]["total_purchases"] = old_purchases + purchase
            
            # Добавляем запись в историю
            add_history(
                customer_id,
                "➖ **Списание бонусов**",
                f"-{bonus} бонусов (оплата покупки {purchase} руб.)"
            )
            
            save_users(users)
            
            # Проверяем повышение уровня
            from level_notifications import send_level_up_congratulations, send_level_milestone
            from utils import check_level_increase
            
            level_change = await check_level_increase(int(customer_id), old_purchases, users[customer_id]["total_purchases"])
            if level_change['increased']:
                await send_level_up_congratulations(context, int(customer_id), level_change)
            else:
                # Проверяем, может быть просто достигнут новый уровень (без повышения)
                old_level, _, _ = calc_level(old_purchases)
                new_level, new_cashback, _ = calc_level(users[customer_id]["total_purchases"])
                if new_level != old_level:
                    await send_level_milestone(context, int(customer_id), new_level, new_cashback)
            
            # Сообщение покупателю
            await query.edit_message_text(
                f"✅ **Бонусы успешно списаны!**\n\n"
                f"Списано бонусов: {bonus}\n"
                f"Остаток на счете: {current_balance - bonus}\n"
                f"Сумма покупки: {purchase} руб.\n"
                f"К оплате: {final} руб.\n\n"
                f"Спасибо за покупку! 🌸",
                parse_mode='Markdown'
            )
            
            # Сообщение кассиру
            await context.bot.send_message(
                chat_id=cashier_id,
                text=f"✅ **Покупатель подтвердил списание!**\n\n"
                     f"Покупатель: {customer_name}\n"
                     f"Списано бонусов: {bonus}\n"
                     f"Сумма покупки: {purchase} руб.\n"
                     f"Итого к оплате: {final} руб.\n\n"
                     f"Остаток бонусов покупателя: {current_balance - bonus}",
                parse_mode='Markdown'
            )
    
    elif data.startswith("reject_"):
        # Покупатель отказался
        await query.edit_message_text(
            "❌ **Вы отказались от списания бонусов**",
            parse_mode='Markdown'
        )
        await context.bot.send_message(
            chat_id=cashier_id,
            text=f"❌ **Покупатель отказался от списания бонусов**\n\n"
                 f"Покупатель: {customer_name}",
            parse_mode='Markdown'
        )
    
    # Очищаем данные
    payment_data.pop(customer_key, None)
    if cashier_id in payment_data:
        payment_data.pop(cashier_id, None)

# ------------------- ОБРАБОТЧИК ДЛЯ КАССИРА -------------------
cashier_conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^💳 Оплата бонусами$"), payment_start)],
    states={
        CASHIER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_phone)],
        CASHIER_PURCHASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_purchase)],
        CASHIER_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bonus)],
    },
    fallbacks=[MessageHandler(filters.Regex("^⬅ Отмена$"), process_phone)],
    name="cashier_conv"
)

# ------------------- ОБРАБОТЧИК ДЛЯ ИНЛАЙН-КНОПОК -------------------
payment_callback_handler = CallbackQueryHandler(payment_callback, pattern="^(confirm_|reject_)")