# payment_handler.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from cashier_payment import payment_data, handle_customer_confirmation
import logging

logger = logging.getLogger(__name__)

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отдельный обработчик для кнопок оплаты"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    logger.info(f"💰 Payment callback: user={user_id}, text={text}")
    
    # Проверяем, есть ли активный платеж для этого пользователя
    for cashier_id, data in payment_data.items():
        if data.get("customer_uid") == user_id and data.get("awaiting_customer"):
            logger.info(f"✅ Найден активный платеж для пользователя {user_id}")
            return await handle_customer_confirmation(update, context)
    
    logger.info(f"❌ Нет активного платежа для пользователя {user_id}")
    return ConversationHandler.END