# handlers.py
from roles import is_admin, is_cashier, get_all_admins
import admin
import json, os, re
from datetime import datetime
from io import BytesIO
import logging

import qrcode
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, ConversationHandler, filters, CallbackQueryHandler

from utils import load_users, save_users, ensure_user, normalize_phone, add_history, calc_level, update_user_activity
from utils_reminders import load_user_events

# Настройка логирования
logger = logging.getLogger(__name__)

# -------------------- STATES для регистрации покупателя --------------------
REGISTER_PHONE, REGISTER_NAME = range(2)

# -------------------- Вспомогательная функция для обновления активности --------------------
async def update_activity(update: Update):
    """Обновляет активность пользователя"""
    if update.effective_user:
        update_user_activity(update.effective_user.id)

# -------------------- Уведомление админов о новой регистрации --------------------
async def notify_admins_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE, new_user, phone, registered_by=None):
    """Отправляет уведомление всем администраторам о новом пользователе"""
    admins_list = get_all_admins()
    if not admins_list:
        return
    
    # Информация о новом пользователе
    user_id = new_user.id
    user_name = getattr(new_user, 'first_name', 'Неизвестно')
    username = getattr(new_user, 'username', None)
    
    # Кто зарегистрировал
    if registered_by:
        registrar_name = getattr(registered_by, 'first_name', 'Неизвестно')
        registrar_id = registered_by.id
        registrar_text = f"👤 Зарегистрировал: {registrar_name} (ID: {registrar_id})"
    else:
        registrar_text = "👤 Зарегистрировался самостоятельно"
    
    # Текст уведомления
    notification = (
        f"🆕 **НОВЫЙ ПОЛЬЗОВАТЕЛЬ!**\n\n"
        f"👤 Имя: {user_name}\n"
        f"📱 Телефон: {phone}\n"
        f"🆔 ID: `{user_id}`\n"
        f"💬 Username: @{username if username else 'нет'}\n"
        f"💰 Начислено: 300 бонусов\n"
        f"{registrar_text}\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    # Отправляем каждому админу
    for admin_id in admins_list:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=notification,
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

# -------------------- /start --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    user = update.effective_user
    users = load_users()
    uid = str(user.id)
    ensure_user(users, uid, user)

    if context.args:
        ref = context.args[0]
        if ref != uid and ref in users:
            users[uid]["invited_by"] = ref
            save_users(users)

    # Путь к картинке
    image_path = "welcome.jpg"
    
    kb = [[KeyboardButton("📞 Поделиться контактом", request_contact=True)]]
    
    # Проверяем, есть ли файл
    if os.path.exists(image_path):
        try:
            with open(image_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=InputFile(photo, filename="welcome.jpg"),
                    caption="🌸 Добро пожаловать в Мир Цветов!\n"
                            "Чтобы участвовать в бонусной программе, нажмите кнопку ниже 👇",
                    reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
                )
        except Exception as e:
            logger.error(f"Ошибка отправки картинки: {e}")
            await update.message.reply_text(
                "🌸 Добро пожаловать в Мир Цветов!\n"
                "Чтобы участвовать в бонусной программе, нажмите кнопку ниже 👇",
                reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "🌸 Добро пожаловать в Мир Цветов!\n"
            "Чтобы участвовать в бонусной программе, нажмите кнопку ниже 👇",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

# -------------------- Контакт --------------------
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    user = update.effective_user
    users = load_users()
    uid = str(user.id)
    ensure_user(users, uid, user)

    phone = normalize_phone(update.message.contact.phone_number)
    users[uid]["phone"] = phone
    users[uid]["registered"] = True

    if users[uid]["balance"] == 0:
        users[uid]["balance"] = 300
        add_history(uid, "➕ **Начисление бонусов**", f"+300 бонусов (регистрация)")
        logger.info(f"Пользователь {uid} получил 300 бонусов за регистрацию")

        inviter = users[uid].get("invited_by")
        if inviter and inviter in users and not users[uid]["invite_rewarded"]:
            ensure_user(users, inviter)
            users[inviter]["balance"] += 300
            users[uid]["invite_rewarded"] = True
            add_history(inviter, "➕ **Начисление бонусов**", f"+300 бонусов (приглашение друга @{user.username})")
            logger.info(f"Пользователь {inviter} получил 300 бонусов за приглашение {uid}")

    save_users(users)
    
    # Уведомляем админов о новой регистрации
    await notify_admins_new_user(update, context, user, phone)
    
    await show_menu(update, context)

# -------------------- Главное меню --------------------
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню"""
    await update_activity(update)
    try:
        # Определяем пользователя
        if update.message:
            user = update.message.from_user
        elif update.callback_query:
            user = update.callback_query.from_user
        else:
            user = update.effective_user

        uid = str(user.id)
        users = load_users()
        ensure_user(users, uid, user)

        # Проверяем, не пора ли обновить год
        current_year = datetime.now().year
        last_reset_year = users[uid].get("last_reset_year", current_year)
        
        if last_reset_year < current_year:
            # Сохраняем историю прошлого года
            old_purchases = users[uid].get("total_purchases", 0)
            if old_purchases > 0:
                if "purchases_history" not in users[uid]:
                    users[uid]["purchases_history"] = []
                users[uid]["purchases_history"].append({
                    "year": last_reset_year,
                    "amount": old_purchases
                })
                add_history(
                    uid,
                    "📊 **Годовой сброс**",
                    f"Покупки за {last_reset_year} год: {old_purchases} руб. Уровень обновлен"
                )
            
            # Обнуляем для нового года
            users[uid]["total_purchases"] = 0
            users[uid]["last_reset_year"] = current_year
            save_users(users)

        balance_amount = users[uid]["balance"]
        total_purchases = users[uid].get("total_purchases", 0)
        level, cashback, next_level_threshold = calc_level(total_purchases)

        # Базовая клавиатура для всех
        kb = [
            ["💰 Баланс", "📄 История"],
            ["📷 QR-код", "👥 Пригласить друга"],
            ["📞 Контакты"],
            ["📅 События"]
        ]

        # Если пользователь админ ИЛИ кассир - показываем служебные кнопки
        if is_admin(user.id) or is_cashier(user.id):
            kb.append(["💳 Оплата бонусами"])
            kb.append(["📝 Регистрация по номеру"])
        
        # Дополнительно для админов показываем админку
        if is_admin(user.id):
            kb.append(["⚙ Админ"])

        # Формируем текст о следующем уровне с обработкой ошибок
        next_level_text = ""
        try:
            # Преобразуем в числа, чтобы избежать ошибок
            next_level_threshold_num = int(next_level_threshold) if next_level_threshold else 0
            total_purchases_num = int(total_purchases)
            
            if level == "НАЧИНАЮЩИЙ":
                next_level_text = f"\n⬆ До BRONZE: {next_level_threshold_num - total_purchases_num} руб."
            elif level == "BRONZE":
                next_level_text = f"\n⬆ До SILVER: {next_level_threshold_num - total_purchases_num} руб."
            elif level == "SILVER":
                next_level_text = f"\n⬆ До GOLD: {next_level_threshold_num - total_purchases_num} руб."
            elif level == "GOLD":
                next_level_text = f"\n⬆ До PLATINUM: {next_level_threshold_num - total_purchases_num} руб."
            elif level == "PLATINUM":
                next_level_text = f"\n⬆ До VIP: {next_level_threshold_num - total_purchases_num} руб."
        except Exception as e:
            print(f"Ошибка расчета следующего уровня: {e}")
            next_level_text = ""

        # Отправляем сообщение
        if update.message:
            await update.message.reply_text(
                f"💰 **Баланс:** {balance_amount} бонусов\n"
                f"📅 **Сезон {current_year}:** {total_purchases} руб.\n"
                f"🏆 **Уровень:** {level}\n"
                f"💸 **Кэшбэк:** {cashback}%"
                f"{next_level_text}",
                reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
                parse_mode='Markdown'
            )
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                f"💰 **Баланс:** {balance_amount} бонусов\n"
                f"📅 **Сезон {current_year}:** {total_purchases} руб.\n"
                f"🏆 **Уровень:** {level}\n"
                f"💸 **Кэшбэк:** {cashback}%"
                f"{next_level_text}",
                reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
                parse_mode='Markdown'
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка в show_menu: {e}")
        if update.message:
            await update.message.reply_text(
                "⚠️ Произошла ошибка. Попробуйте еще раз.",
                reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
            )
        return ConversationHandler.END

# -------------------- Обработчик кнопки "⬅ В главное меню" --------------------
async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    """Обработчик для кнопки возврата в главное меню"""
    logger.info(f"Пользователь {update.effective_user.id} нажал кнопку возврата в меню")
    return await show_menu(update, context)

# -------------------- Баланс --------------------
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    await show_menu(update, context)

# -------------------- Обработка кнопки "Назад в меню" из контактов --------------------
async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_menu(update, context)

# -------------------- Пригласить --------------------
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)
    uid = str(update.effective_user.id)
    link = f"https://t.me/mircvetovtosno_bot?start={uid}"
    
    # Простой текст без Markdown
    text = (
        f"🎁 Подарите 300 бонусов вашим друзьям!\n\n"
        f"Просто перешлите сообщение ниже другу:\n"
        f"{link}\n\n"
        f"Когда друг зарегистрируется, вы получите 300 бонусов, "
        f"а также 10% от его будущих покупок будут начисляться на ваш счет!"
    )
    
    await update.message.reply_text(text)

# -------------------- Контакты --------------------
async def contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)
    
    # Простой текст без Markdown
    text = (
        "Наш магазин:\n"
        "📍 Тосно, Боярова 6, стр. 1\n\n"
        "Телефон:\n"
        "+7 906 229-42-80\n\n"
        "Telegram:\n"
        "@Knyazhna_Olya\n\n"
        "Мы в соцсетях:"
    )
    
    # Создаем инлайн-кнопки (без tel: ссылки)
    keyboard = [
        [
            InlineKeyboardButton("🌐 ВКонтакте", url="https://vk.com/mircvetovtosno"),
            InlineKeyboardButton("✈️ Telegram канал", url="https://t.me/mircvetovtosno")
        ],
        [
            InlineKeyboardButton("📍 На карте", url="https://yandex.ru/profile/130403110314?lang=ru"),
            InlineKeyboardButton("⭐ Оставить отзыв", url="https://yandex.ru/profile/130403110314?lang=ru")
        ],
        [InlineKeyboardButton("⬅ Назад в меню", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text, 
        reply_markup=reply_markup
    )

# -------------------- Функция для форматирования истории --------------------
def format_history_entry(entry):
    """Форматирует запись истории для красивого отображения"""
    time = entry.get('time', '')
    title = entry.get('title', 'Операция')
    description = entry.get('description', '')
    
    # Определяем эмодзи по типу операции
    if "➕" in title or "Начисление" in title:
        emoji = '➕'
    elif "➖" in title or "Списание" in title:
        emoji = '➖'
    elif "Годовой" in title:
        emoji = '📅'
    else:
        emoji = '📝'
    
    return f"{emoji} **{title}**\n   └ {time} — {description}"

# -------------------- История --------------------
async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    user = update.effective_user
    uid = str(user.id)
    users = load_users()
    ensure_user(users, uid, user)

    history = users[uid].get("history", [])
    
    if not history:
        await update.message.reply_text(
            "📄 **История операций пуста**\n\n"
            "Здесь будут отображаться все начисления и списания бонусов.",
            parse_mode='Markdown'
        )
        return

    # Сортируем историю по времени (сначала новые)
    sorted_history = sorted(history, key=lambda x: x.get('time', ''), reverse=True)
    
    # Разбиваем на страницы по 5 записей
    page = 0
    context.user_data['history_page'] = page
    context.user_data['history_data'] = sorted_history
    
    await show_history_page(update, context, page)

async def show_history_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    await update_activity(update)  # Обновляем активность
    """Показывает страницу истории"""
    user = update.effective_user
    uid = str(user.id)
    users = load_users()
    history = context.user_data.get('history_data', [])
    
    if not history:
        return
    
    items_per_page = 5
    total_pages = (len(history) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(history))
    
    # Заголовок
    text = f"📄 **История операций** (страница {page + 1}/{total_pages})\n\n"
    
    # Записи
    for i in range(start_idx, end_idx):
        entry = history[i]
        text += format_history_entry(entry) + "\n\n"
    
    # Статистика
    total_plus = 0
    total_minus = 0
    for e in history:
        desc = e.get('description', '')
        if '+' in desc:
            try:
                total_plus += int(desc.split()[0].replace('+', ''))
            except:
                pass
        elif '-' in desc:
            try:
                total_minus += int(desc.split()[0].replace('-', ''))
            except:
                pass
    
    text += f"📊 **Итого:** +{total_plus} / -{total_minus}"
    
    # Кнопки навигации
    keyboard = []
    nav_row = []
    
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀ Предыдущая", callback_data=f"history_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Следующая ▶", callback_data=f"history_page_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu_from_history")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def history_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    """Обработка навигации по истории"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_to_menu_from_history":
        await show_menu(update, context)
        return
    
    if data.startswith("history_page_"):
        page = int(data.split("_")[2])
        await show_history_page(update, context, page)

# -------------------- QR --------------------
async def show_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    user = update.effective_user
    uid = str(user.id)
    users = load_users()
    ensure_user(users, uid, user)

    qr_data = f"TG_ID:{uid}"
    img = qrcode.make(qr_data)

    bio = BytesIO()
    bio.name = "bonus_qr.png"
    img.save(bio, "PNG")
    bio.seek(0)

    await update.message.reply_photo(
        photo=InputFile(bio, filename="bonus_qr.png"),
        caption=f"💳 **Ваш бонусный QR-код**\n\n"
                f"Покажите этот код кассиру для списания бонусов.\n"
                f"💰 Текущий баланс: {users[uid]['balance']} бонусов",
        parse_mode='Markdown'
    )

# -------------------- Обработчик любого текстового сообщения --------------------
async def any_message_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    """Любое сообщение открывает главное меню с подсказкой"""
    user = update.effective_user
    logger.info(f"📨 Пользователь {user.id} отправил: '{update.message.text}' - открываем меню")
    
    # Отправляем подсказку
    await update.message.reply_text(
        "❓ Я не понимаю команд, но могу показать меню!\n"
        "🔽 Нажмите на кнопки ниже для навигации:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Показываем главное меню
    return await show_menu(update, context)

# -------------------- Возврат в главное меню --------------------
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    """Возврат в главное меню"""
    return await show_menu(update, context)

# -------------------- Админ --------------------
async def open_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    await admin.admin_menu(update, context)

# -------------------- Регистрация покупателя --------------------
async def register_customer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    user = update.effective_user
    if not (is_admin(user.id) or is_cashier(user.id)):
        await update.message.reply_text("❌ У вас нет доступа к этой функции.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 **Регистрация нового покупателя**\n\n"
        "Введите номер телефона покупателя:\n"
        "(например: +79991234567 или 89991234567)",
        reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True),
        parse_mode='Markdown'
    )
    return REGISTER_PHONE

async def register_customer_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    if update.message.text == "⬅ Отмена":
        await update.message.reply_text("❌ Регистрация отменена", reply_markup=ReplyKeyboardRemove())
        return await show_menu(update, context)
    
    users = load_users()
    phone = re.sub(r"\D", "", update.message.text.strip())
    
    # Нормализация номера
    if phone.startswith("8"):
        phone = "+7" + phone[1:]
    elif phone.startswith("7"):
        phone = "+7" + phone[1:]
    elif phone.startswith("+7"):
        # Уже нормализован
        pass
    else:
        # Если номер без кода, пробуем добавить +7
        if len(phone) == 10:  # 10 цифр - московский номер
            phone = "+7" + phone
        else:
            await update.message.reply_text(
                "❌ Неверный формат номера. Используйте +7XXXXXXXXXX или 8XXXXXXXXXX",
                reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
            )
            return REGISTER_PHONE
    
    # Проверяем корректность длины номера
    if len(phone) != 12 or not phone.startswith("+7"):
        await update.message.reply_text(
            "❌ Неверный формат номера. Номер должен содержать 10 цифр после кода страны",
            reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
        )
        return REGISTER_PHONE

    # Проверка на существующий номер
    for u in users.values():
        if u.get("phone") == phone:
            await update.message.reply_text(
                f"❌ Этот номер уже зарегистрирован: {phone}",
                reply_markup=ReplyKeyboardRemove()
            )
            return await show_menu(update, context)

    context.user_data["reg_phone"] = phone
    await update.message.reply_text(
        "📝 Введите имя покупателя (можно оставить пустым):",
        reply_markup=ReplyKeyboardMarkup([["⬅ Отмена"]], resize_keyboard=True)
    )
    return REGISTER_NAME

async def register_customer_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update_activity(update)  # Обновляем активность
    if update.message.text == "⬅ Отмена":
        await update.message.reply_text("❌ Регистрация отменена", reply_markup=ReplyKeyboardRemove())
        return await show_menu(update, context)
    
    users = load_users()
    name = update.message.text.strip()
    phone = context.user_data.get("reg_phone")
    
    if not phone:
        await update.message.reply_text("❌ Ошибка: номер телефона не найден", reply_markup=ReplyKeyboardRemove())
        return await show_menu(update, context)
    
    # Генерируем новый ID
    max_id = 1000
    for k in users.keys():
        try:
            max_id = max(max_id, int(k))
        except:
            pass
    uid = str(max_id + 1)
    
    current_year = datetime.now().year
    
    users[uid] = {
        "id": uid,
        "tg_id": None,
        "name": name if name else "Покупатель",
        "username": None,
        "phone": phone,
        "balance": 300,
        "total_purchases": 0,
        "last_reset_year": current_year,
        "purchases_history": [],
        "registered": True,
        "invited_by": None,
        "invite_rewarded": False,
        "history": [{
            "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "title": "➕ **Начисление бонусов**",
            "description": f"+300 бонусов (регистрация через {update.effective_user.first_name})"
        }],
        "created_at": datetime.now().isoformat()
    }
    
    save_users(users)
    
    # Уведомляем админов о новой регистрации
    fake_user = type('User', (), {'id': uid, 'first_name': name if name else "Покупатель", 'username': None})
    await notify_admins_new_user(update, context, fake_user, phone, registered_by=update.effective_user)
    
    await update.message.reply_text(
        f"✅ **Покупатель успешно зарегистрирован!**\n\n"
        f"👤 Имя: {name if name else 'Покупатель'}\n"
        f"📱 Телефон: {phone}\n"
        f"💰 Начислено: 300 бонусов\n"
        f"🆔 ID: {uid}",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    
    return await show_menu(update, context)

def get_register_customer_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📝 Регистрация по номеру"), register_customer_start)],
        states={
            REGISTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_customer_phone)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_customer_name)],
        },
        fallbacks=[MessageHandler(filters.Regex("⬅ Отмена"), back_to_menu)],
        per_user=True,
        name="register_customer_conv"
    )
    
    # Добавьте в конец файла
async def check_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки проверки баланса"""
    query = update.callback_query
    await query.answer()
    await show_menu(update, context)

async def history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки истории"""
    query = update.callback_query
    await query.answer()
    await show_history(update, context)