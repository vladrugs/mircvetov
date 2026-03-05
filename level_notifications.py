# level_notifications.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import load_users, calc_level
import logging

logger = logging.getLogger(__name__)

# ------------------- Уведомление о возможном понижении уровня -------------------
async def send_level_decrease_warning(context: ContextTypes.DEFAULT_TYPE, user_data):
    """Отправляет предупреждение о возможном понижении уровня"""
    uid = user_data['uid']
    name = user_data['name']
    current_level = user_data['current_level']
    future_level = user_data['future_level']
    days_inactive = user_data['days_inactive']
    current_cashback = user_data['current_cashback']
    future_cashback = user_data['future_cashback']
    
    text = (
        f"⚠️ **Внимание!**\n\n"
        f"Уважаемый(ая) {name}, вы не заходили в бот {days_inactive} дней.\n\n"
        f"Если в ближайшие 7 дней не будет покупок, ваш уровень понизится:\n"
        f"• Текущий уровень: {current_level} ({current_cashback}% кэшбэк)\n"
        f"• Будет через 7 дней: {future_level} ({future_cashback}% кэшбэк)\n\n"
        f"🏃‍♂️ Совершите покупку, чтобы сохранить уровень!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🛍 Перейти в магазин", url="https://t.me/mircvetovtosno")],
        [InlineKeyboardButton("📞 Связаться с нами", callback_data="contacts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Отправлено предупреждение о понижении уровня пользователю {uid}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки предупреждения пользователю {uid}: {e}")

# ------------------- Поздравление с повышением уровня -------------------
async def send_level_up_congratulations(context: ContextTypes.DEFAULT_TYPE, user_id: int, level_info):
    """Отправляет поздравление с повышением уровня"""
    old_level = level_info['old_level']
    new_level = level_info['new_level']
    old_cashback = level_info['old_cashback']
    new_cashback = level_info['new_cashback']
    
    # Эмодзи для разных уровней
    level_emojis = {
        "BRONZE": "🥉",
        "SILVER": "🥈",
        "GOLD": "🥇",
        "PLATINUM": "💎",
        "VIP": "👑"
    }
    
    old_emoji = level_emojis.get(old_level, "🎯")
    new_emoji = level_emojis.get(new_level, "🎯")
    
    text = (
        f"🎉 **Поздравляем с повышением уровня!**\n\n"
        f"{old_emoji} **Было:** {old_level} ({old_cashback}% кэшбэк)\n"
        f"{new_emoji} **Стало:** {new_level} ({new_cashback}% кэшбэк)\n\n"
        f"✨ Ваш кэшбэк увеличен! Теперь вы получаете больше бонусов за каждую покупку.\n\n"
        f"Спасибо, что выбираете нас! 🌸"
    )
    
    keyboard = [
        [InlineKeyboardButton("💰 Посмотреть баланс", callback_data="check_balance")],
        [InlineKeyboardButton("🛍 История покупок", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Отправлено поздравление о повышении уровня пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки поздравления пользователю {user_id}: {e}")

# ------------------- Уведомление о достижении нового уровня -------------------
async def send_level_milestone(context: ContextTypes.DEFAULT_TYPE, user_id: int, level: str, cashback: int):
    """Отправляет уведомление о достижении нового уровня (без повышения)"""
    level_emojis = {
        "BRONZE": "🥉",
        "SILVER": "🥈",
        "GOLD": "🥇",
        "PLATINUM": "💎",
        "VIP": "👑"
    }
    emoji = level_emojis.get(level, "🎯")
    
    text = (
        f"{emoji} **Новый уровень!**\n\n"
        f"Вы достигли уровня **{level}**!\n"
        f"Теперь ваш кэшбэк составляет **{cashback}%**.\n\n"
        f"Продолжайте в том же духе! 💪"
    )
    
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=text,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Отправлено уведомление о достижении уровня {level} пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")