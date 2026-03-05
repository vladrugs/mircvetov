# ratings.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from utils import load_users, save_users, add_history
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Состояния
WAITING_FEEDBACK = 1

# Хранилище для ожидающих оценки покупок
pending_ratings = {}

# ------------------- Функция для запуска опроса после покупки -------------------
async def ask_for_rating(context: ContextTypes.DEFAULT_TYPE, user_id: int, purchase_amount: int, purchase_date: datetime):
    """Отправляет запрос на оценку покупки через 24 часа"""
    # Для теста используем 1 минуту, для продакшена - 24 часа
    test_mode = False  # Поставьте False для продакшена
    
    if test_mode:
        delay = timedelta(minutes=1)
        delay_text = "1 минуту"
    else:
        delay = timedelta(hours=24)
        delay_text = "24 часа"
    
    job_time = datetime.now() + delay
    
    context.job_queue.run_once(
        send_rating_request,
        when=delay,
        data={
            'user_id': user_id,
            'purchase_amount': purchase_amount,
            'purchase_date': purchase_date
        },
        name=f"rating_{user_id}_{purchase_date.timestamp()}"
    )
    logger.info(f"📅 Запланирован запрос оценки для пользователя {user_id} через {delay_text} (на {job_time})")

# ------------------- Отправка запроса оценки -------------------
async def send_rating_request(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с просьбой оценить покупку"""
    job = context.job
    data = job.data
    
    user_id = data['user_id']
    purchase_amount = data['purchase_amount']
    
    # Клавиатура с оценками
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="rate_1"),
            InlineKeyboardButton("2", callback_data="rate_2"),
            InlineKeyboardButton("3", callback_data="rate_3"),
            InlineKeyboardButton("4", callback_data="rate_4"),
            InlineKeyboardButton("5", callback_data="rate_5")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🌟 **Оцените вашу покупку!**\n\n"
                 f"Вчера вы совершили покупку на сумму {purchase_amount} руб.\n"
                 f"Пожалуйста, оцените её от 1 до 5:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Сохраняем информацию об ожидающей оценке
        pending_ratings[user_id] = {
            'purchase_amount': purchase_amount,
            'job_name': job.name
        }
        logger.info(f"✅ Запрос оценки отправлен пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса оценки пользователю {user_id}: {e}")

# ------------------- Обработка оценки -------------------
async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие на кнопку с оценкой"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    rating = int(query.data.split('_')[1])
    
    if user_id not in pending_ratings:
        await query.edit_message_text(
            "❌ К сожалению, время для оценки этой покупки истекло.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    purchase_amount = pending_ratings[user_id]['purchase_amount']
    
    # Сохраняем оценку
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {}
    
    if 'ratings' not in users[uid]:
        users[uid]['ratings'] = []
    
    users[uid]['ratings'].append({
        'rating': rating,
        'amount': purchase_amount,
        'date': datetime.now().isoformat()
    })
    save_users(users)
    
    if rating <= 3:
        # Для низких оценок - просим объяснить причину
        context.user_data['temp_rating'] = rating
        context.user_data['temp_purchase'] = purchase_amount
        
        keyboard = [
            [InlineKeyboardButton("⬅ Отмена", callback_data="cancel_feedback")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        reasons = {
            1: "😞 Очень плохо",
            2: "😕 Плохо",
            3: "😐 Средне"
        }
        
        await query.edit_message_text(
            f"📝 **Расскажите подробнее**\n\n"
            f"Вы поставили оценку {rating} — {reasons[rating]}.\n"
            f"Пожалуйста, напишите, что именно вам не понравилось?\n\n"
            f"Это поможет нам стать лучше!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return WAITING_FEEDBACK
        
    else:
        # Для высоких оценок - просим оставить отзыв на Яндекс Картах
        yandex_link = "https://yandex.ru/profile/130403110314?lang=ru"
        
        keyboard = [
            [InlineKeyboardButton("⭐ Оставить отзыв на Яндекс Картах", url=yandex_link)],
            [InlineKeyboardButton("✅ Уже оставил(а)", callback_data="review_done")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎉 **Спасибо за высокую оценку!**\n\n"
            f"Мы очень рады, что вам понравилось! 🌸\n\n"
            f"Будем благодарны, если вы оставите отзыв о нашем магазине на Яндекс Картах.\n"
            f"Это поможет другим людям найти нас и тоже порадовать себя цветами!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Удаляем из ожидающих оценок
        del pending_ratings[user_id]
        return ConversationHandler.END

# ------------------- Обработка текстового отзыва для низких оценок -------------------
async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовый отзыв для оценок 1-3"""
    user_id = update.message.from_user.id
    feedback = update.message.text
    
    rating = context.user_data.get('temp_rating')
    purchase = context.user_data.get('temp_purchase')
    
    if not rating or not purchase:
        await update.message.reply_text(
            "❌ Ошибка. Пожалуйста, начните заново.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Сохраняем отзыв
    users = load_users()
    uid = str(user_id)
    
    if 'feedback' not in users[uid]:
        users[uid]['feedback'] = []
    
    users[uid]['feedback'].append({
        'rating': rating,
        'feedback': feedback,
        'purchase': purchase,
        'date': datetime.now().isoformat()
    })
    save_users(users)
    
    # Отправляем уведомление админам
    await notify_admins_about_feedback(context, user_id, rating, feedback, purchase)
    
    await update.message.reply_text(
        f"🙏 **Спасибо за ваш отзыв!**\n\n"
        f"Мы обязательно учтём ваши замечания и постараемся стать лучше.\n"
        f"Приносим извинения за доставленные неудобства.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Очищаем временные данные
    context.user_data.pop('temp_rating', None)
    context.user_data.pop('temp_purchase', None)
    if user_id in pending_ratings:
        del pending_ratings[user_id]
    
    return ConversationHandler.END

# ------------------- Уведомление админов о негативном отзыве -------------------
async def notify_admins_about_feedback(context, user_id, rating, feedback, purchase):
    """Отправляет уведомление админам о негативном отзыве"""
    from roles import get_all_admins
    
    admins_list = get_all_admins()
    if not admins_list:
        return
    
    users = load_users()
    user_name = users.get(str(user_id), {}).get('name', 'Неизвестно')
    
    notification = (
        f"⚠️ **Новый негативный отзыв!**\n\n"
        f"👤 Пользователь: {user_name} (ID: {user_id})\n"
        f"⭐ Оценка: {rating}/5\n"
        f"💰 Сумма покупки: {purchase} руб.\n"
        f"📝 Отзыв: {feedback}\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    for admin_id in admins_list:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=notification,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

# ------------------- Обработка кнопки "Уже оставил(а)" -------------------
async def review_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие на кнопку 'Уже оставил(а)'"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Удаляем из ожидающих оценок
    if user_id in pending_ratings:
        del pending_ratings[user_id]
    
    await query.edit_message_text(
        "🎉 **Спасибо за ваш отзыв!**\n\n"
        "Мы очень ценим ваше мнение и будем рады видеть вас снова! 🌸",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

# ------------------- Отмена -------------------
async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена оставления отзыва"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    await query.edit_message_text(
        "❌ Оставление отзыва отменено.",
        parse_mode='Markdown'
    )
    
    if user_id in pending_ratings:
        del pending_ratings[user_id]
    
    context.user_data.pop('temp_rating', None)
    context.user_data.pop('temp_purchase', None)
    
    return ConversationHandler.END

# ------------------- ConversationHandler для опроса -------------------
ratings_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(handle_rating, pattern="^rate_[1-5]$")],
    states={
        WAITING_FEEDBACK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback),
            CallbackQueryHandler(cancel_feedback, pattern="^cancel_feedback$")
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_feedback, pattern="^cancel_feedback$"),
        CallbackQueryHandler(review_done, pattern="^review_done$")
    ],
    name="ratings_conversation",
    per_user=True
)