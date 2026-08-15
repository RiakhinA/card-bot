"""
Telegram-бот для сбора данных на онлайн-визитку.
Автор: для Антона Ряхина

Собирает: фото, имя+сфера, о себе, соцсети, мессенджеры, доп.опции
Отправляет владельцу готовый пакет для генерации визитки.
"""

import logging
import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8908748343:AAEe54YM4vXz-K4ekFLEWljmHNDy06yqVMY")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "8530071")
OWNER_USERNAME = "riakhin_anton"
PRICE = "2500 грн"
PREPAY = "1250 грн"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ СОСТОЯНИЯ ============
(PHOTO, NAME, ABOUT, SOCIALS, SOCIAL_LINKS,
 MESSENGERS, MESSENGER_CONTACTS, EXTRAS, CONFIRM) = range(9)

# ============ СПРАВОЧНИКИ ============
SOCIAL_OPTIONS = [
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("tiktok", "TikTok"),
    ("youtube", "YouTube"),
    ("linkedin", "LinkedIn"),
    ("site", "Сайт"),
]

MESSENGER_OPTIONS = [
    ("telegram", "Telegram"),
    ("whatsapp", "WhatsApp"),
    ("viber", "Viber"),
    ("phone", "Позвонить"),
    ("email", "Email"),
]

EXTRA_OPTIONS = [
    ("share", "Кнопка «Поделиться»"),
    ("vcard", "Сохранить контакт (.vcf)"),
    ("lang2", "Второй язык"),
    ("qr", "QR-код"),
]


# ============ ХЕЛПЕРЫ ============
def build_multi_keyboard(options, selected, done_label="Готово ✓"):
    """Клавиатура множественного выбора с галочками."""
    keyboard = []
    row = []
    for key, label in options:
        mark = "✅ " if key in selected else "▫️ "
        row.append(InlineKeyboardButton(f"{mark}{label}", callback_data=f"tgl:{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(done_label, callback_data="done")])
    return InlineKeyboardMarkup(keyboard)


def label_for(options, key):
    for k, lbl in options:
        if k == key:
            return lbl
    return key


# ============ ШАГИ ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = (
        "Привет! 👋\n\n"
        "Я помогу собрать данные для твоей онлайн-визитки.\n\n"
        "Это небольшая страница с самым важным о тебе: фото, имя, "
        "чем занимаешься, ссылки и контакты.\n\n"
        "Её можно поставить в шапку Instagram, отправлять клиентам "
        "отдельной ссылкой или зашить в QR-код.\n\n"
        f"Базовая стоимость — от {PRICE}.\n\n"
        "Займёт 2 минуты. Начнём?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Хочу такую визитку →", callback_data="begin")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)
    return PHOTO


async def begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Шаг 1 из 6 — Фото 📷\n\n"
        "Пришли своё фото. Лучше портрет, где хорошо видно лицо.\n\n"
        "Если фото пока нет — напиши «пропустить»."
    )
    return PHOTO


async def got_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["photo_id"] = update.message.photo[-1].file_id
        context.user_data["has_photo"] = True
    elif update.message.document and update.message.document.mime_type.startswith("image"):
        context.user_data["photo_id"] = update.message.document.file_id
        context.user_data["has_photo"] = True
    else:
        txt = (update.message.text or "").strip().lower()
        if txt in ("пропустить", "скип", "нет", "later", "потом"):
            context.user_data["has_photo"] = False
        else:
            await update.message.reply_text(
                "Пришли фото картинкой или напиши «пропустить»."
            )
            return PHOTO

    await update.message.reply_text(
        "Шаг 2 из 6 — Имя и сфера ✍️\n\n"
        "Напиши, как тебя зовут и чем занимаешься.\n\n"
        "Например: «Мария Левченко, стилист по волосам» "
        "или «Алексей Миронов, фотограф»."
    )
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "Шаг 3 из 6 — Коротко о себе 💬\n\n"
        "Одно-два предложения о том, что ты делаешь и для кого.\n\n"
        "Например: «Создаю стрижки и цвет, которые подходят именно вам» "
        "или «Снимаю живые истории, портреты и события».\n\n"
        "Если не знаешь что писать — напиши «пропустить», я предложу вариант."
    )
    return ABOUT


async def got_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    context.user_data["about"] = "" if txt.lower() in ("пропустить", "скип") else txt
    context.user_data["socials"] = set()
    await update.message.reply_text(
        "Шаг 4 из 6 — Соцсети и сайт 🔗\n\n"
        "Выбери, что показывать на визитке. Можно несколько.",
        reply_markup=build_multi_keyboard(SOCIAL_OPTIONS, set())
    )
    return SOCIALS


async def toggle_social(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    sel = context.user_data.setdefault("socials", set())
    sel.symmetric_difference_update({key})
    await query.edit_message_reply_markup(
        reply_markup=build_multi_keyboard(SOCIAL_OPTIONS, sel)
    )
    return SOCIALS


async def socials_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sel = context.user_data.get("socials", set())
    if not sel:
        context.user_data["social_links"] = ""
        context.user_data["messengers"] = set()
        await query.edit_message_text("Соцсети пропущены.")
        await query.message.reply_text(
            "Шаг 5 из 6 — Мессенджеры 📱\n\n"
            "Как с тобой связываться? Можно несколько.",
            reply_markup=build_multi_keyboard(MESSENGER_OPTIONS, set())
        )
        return MESSENGERS

    names = ", ".join(label_for(SOCIAL_OPTIONS, k) for k in sel)
    await query.edit_message_text(f"Выбрано: {names}")
    await query.message.reply_text(
        "Теперь пришли ссылки одним сообщением — каждую с новой строки.\n\n"
        "Например:\n"
        "Instagram: @my_profile\n"
        "Сайт: mysite.com"
    )
    return SOCIAL_LINKS


async def got_social_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["social_links"] = update.message.text.strip()
    context.user_data["messengers"] = set()
    await update.message.reply_text(
        "Шаг 5 из 6 — Мессенджеры 📱\n\n"
        "Как с тобой связываться? Можно несколько.",
        reply_markup=build_multi_keyboard(MESSENGER_OPTIONS, set())
    )
    return MESSENGERS


async def toggle_messenger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    sel = context.user_data.setdefault("messengers", set())
    sel.symmetric_difference_update({key})
    await query.edit_message_reply_markup(
        reply_markup=build_multi_keyboard(MESSENGER_OPTIONS, sel)
    )
    return MESSENGERS


async def messengers_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sel = context.user_data.get("messengers", set())
    if not sel:
        context.user_data["messenger_contacts"] = ""
        context.user_data["extras"] = set()
        await query.edit_message_text("Мессенджеры пропущены.")
        await query.message.reply_text(
            "Шаг 6 из 6 — Дополнительно ⚙️\n\n"
            "Что ещё добавить на визитку?",
            reply_markup=build_multi_keyboard(EXTRA_OPTIONS, set())
        )
        return EXTRAS

    names = ", ".join(label_for(MESSENGER_OPTIONS, k) for k in sel)
    await query.edit_message_text(f"Выбрано: {names}")
    await query.message.reply_text(
        "Пришли контакты одним сообщением — каждый с новой строки.\n\n"
        "Например:\n"
        "Telegram: @username\n"
        "WhatsApp: +380931234567\n"
        "Email: mail@mail.com"
    )
    return MESSENGER_CONTACTS


async def got_messenger_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["messenger_contacts"] = update.message.text.strip()
    context.user_data["extras"] = set()
    await update.message.reply_text(
        "Шаг 6 из 6 — Дополнительно ⚙️\n\n"
        "Что ещё добавить на визитку?",
        reply_markup=build_multi_keyboard(EXTRA_OPTIONS, set())
    )
    return EXTRAS


async def toggle_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    sel = context.user_data.setdefault("extras", set())
    sel.symmetric_difference_update({key})
    await query.edit_message_reply_markup(
        reply_markup=build_multi_keyboard(EXTRA_OPTIONS, sel)
    )
    return EXTRAS


async def extras_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Готово, собираю всё вместе...")
    return await finish(update, context)


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    user = update.effective_user

    socials = ", ".join(label_for(SOCIAL_OPTIONS, k) for k in d.get("socials", set())) or "—"
    messengers = ", ".join(label_for(MESSENGER_OPTIONS, k) for k in d.get("messengers", set())) or "—"
    extras = ", ".join(label_for(EXTRA_OPTIONS, k) for k in d.get("extras", set())) or "—"

    # Пакет для владельца — готов к вставке в ChatGPT
    owner_msg = (
        "🆕 <b>НОВАЯ ЗАЯВКА НА ВИЗИТКУ</b>\n"
        f"От: {user.full_name}"
        f"{' (@' + user.username + ')' if user.username else ''}\n"
        f"ID: <code>{user.id}</code>\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"<b>ИМЯ И СФЕРА:</b>\n{d.get('name', '—')}\n\n"
        f"<b>О СЕБЕ:</b>\n{d.get('about') or '— (нужно предложить)'}\n\n"
        f"<b>СОЦСЕТИ:</b> {socials}\n"
        f"{d.get('social_links', '') or '—'}\n\n"
        f"<b>МЕССЕНДЖЕРЫ:</b> {messengers}\n"
        f"{d.get('messenger_contacts', '') or '—'}\n\n"
        f"<b>ДОПОЛНИТЕЛЬНО:</b> {extras}\n\n"
        f"<b>ФОТО:</b> {'прикреплено ниже ⬇️' if d.get('has_photo') else 'нет'}"
    )

    # Отправляем владельцу
    try:
        await context.bot.send_message(
            chat_id=OWNER_CHAT_ID, text=owner_msg, parse_mode="HTML"
        )
        if d.get("has_photo"):
            await context.bot.send_photo(
                chat_id=OWNER_CHAT_ID,
                photo=d["photo_id"],
                caption=f"Фото для визитки: {d.get('name', '')}"
            )
    except Exception as e:
        logger.error(f"Ошибка отправки владельцу: {e}")

    # Ответ клиенту
    client_msg = (
        "Спасибо! Всё собрал ✅\n\n"
        f"Базовая визитка — {PRICE}. В неё входит:\n"
        "• сборка страницы\n"
        "• адаптация под телефон\n"
        "• размещение по ссылке\n"
        "• помощь с добавлением в Instagram\n\n"
        f"Для старта — предоплата {PREPAY}. "
        "Дальше собираю первый вариант и присылаю ссылку на проверку. "
        "Остаток — после согласования, перед публикацией.\n\n"
        "Антон свяжется с тобой в ближайшее время. "
        "Или напиши сам, если есть вопросы 👇"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Написать Антону", url=f"https://t.me/{OWNER_USERNAME}")]
    ])

    if update.callback_query:
        await update.callback_query.message.reply_text(client_msg, reply_markup=keyboard)
    else:
        await update.message.reply_text(client_msg, reply_markup=keyboard)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отменено. Напиши /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ============ ЗАПУСК ============
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHOTO: [
                CallbackQueryHandler(begin, pattern="^begin$"),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, got_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_photo),
            ],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            ABOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_about)],
            SOCIALS: [
                CallbackQueryHandler(toggle_social, pattern="^tgl:"),
                CallbackQueryHandler(socials_done, pattern="^done$"),
            ],
            SOCIAL_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_social_links)],
            MESSENGERS: [
                CallbackQueryHandler(toggle_messenger, pattern="^tgl:"),
                CallbackQueryHandler(messengers_done, pattern="^done$"),
            ],
            MESSENGER_CONTACTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_messenger_contacts)
            ],
            EXTRAS: [
                CallbackQueryHandler(toggle_extra, pattern="^tgl:"),
                CallbackQueryHandler(extras_done, pattern="^done$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    app.add_handler(conv)
    logger.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
