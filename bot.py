import asyncio
import logging
import os
from html import escape
from pathlib import Path
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "riakhin_anton").lstrip("@")
ASSETS = Path(__file__).parent / "assets"

BASE_PRICE = 900
BASE_PREPAY = 600
LANGUAGE_PRICES = {"ready": 500, "our": 800}
LANGUAGES = {"uk": "Українська", "ru": "Русский", "en": "English"}
SOCIALS = {"instagram": "Instagram", "facebook": "Facebook", "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok", "site": "Сайт"}
MESSENGERS = {"telegram": "Telegram", "whatsapp": "WhatsApp", "viber": "Viber", "phone": "Позвонить", "other": "Моего мессенджера нет"}
EXTRAS = {"share": "Поделиться визиткой", "vcf": "Сохранить контакт (.vcf)"}


class Form(StatesGroup):
    name = State()
    language = State()
    custom_language = State()
    language_pair = State()
    pair_custom_language = State()
    translation = State()
    photo = State()
    color = State()
    about = State()
    translation_text = State()
    socials = State()
    social_link = State()
    messengers = State()
    messenger_value = State()
    extras = State()


router = Router()


def menu(items, chosen, prefix, done):
    rows = [[InlineKeyboardButton(text=("✓ " if key in chosen else "") + label, callback_data=f"{prefix}:{key}")] for key, label in items.items()]
    rows.append([InlineKeyboardButton(text=done, callback_data=f"{prefix}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Українська", callback_data="lang:uk")],
        [InlineKeyboardButton(text="Русский", callback_data="lang:ru")],
        [InlineKeyboardButton(text="English", callback_data="lang:en")],
        [InlineKeyboardButton(text="Два языка", callback_data="lang:two")],
        [InlineKeyboardButton(text="Написать свой язык", callback_data="lang:custom")],
        [InlineKeyboardButton(text="Отменить выбор", callback_data="lang:cancel")],
    ])


def pair_menu(chosen):
    rows = [[InlineKeyboardButton(text=("✓ " if code in chosen else "") + label, callback_data=f"lp:{code}")] for code, label in LANGUAGES.items()]
    rows += [
        [InlineKeyboardButton(text="Написать свой язык", callback_data="lp:custom")],
        [InlineKeyboardButton(text="Продолжить с 2 языками ✓", callback_data="lp:done")],
        [InlineKeyboardButton(text="← Вернуться к одному языку", callback_data="lp:one")],
        [InlineKeyboardButton(text="Отменить выбор", callback_data="lp:cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def translation_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пришлю готовый перевод: +500 грн", callback_data="tr:ready")],
        [InlineKeyboardButton(text="Переведите вы: +800 грн", callback_data="tr:our")],
        [InlineKeyboardButton(text="← Изменить языки", callback_data="tr:languages")],
        [InlineKeyboardButton(text="Оставить один язык", callback_data="tr:one")],
    ])


def support_button():
    draft = quote("Привет, у меня вопрос по визитке: ")
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Есть вопрос? Написать в поддержку", url=f"tg://resolve?domain={OWNER_USERNAME}&text={draft}")
    ]])


def price_info(data):
    mode = data.get("translation_mode")
    addon = LANGUAGE_PRICES.get(mode, 0)
    total = BASE_PRICE + addon
    prepay = BASE_PREPAY if not addon else total // 2
    return {"addon": addon, "total": total, "prepay": prepay, "balance": total - prepay}


def money(value):
    return f"{value} грн"


def language_names(data):
    values = data.get("language_values", [])
    return ", ".join(values) or "не указан"


def contact_prompt(key):
    if key == "other":
        return "Напиши название мессенджера и ссылку или контакт. Например: Signal: https://… или Discord: https://…"
    return f"Пришли контакт для <b>{MESSENGERS[key]}</b>."


async def examples(message):
    paths = [ASSETS / x for x in ("01-anton.png", "02-male.png", "03-female.png", "04-builder.png")]
    if all(p.exists() for p in paths):
        await message.answer_media_group([InputMediaPhoto(media=FSInputFile(p)) for p in paths])
    else:
        await message.answer("Примеры визиток пока загружаются. Мы пришлём их отдельно.")


async def ask_photo(message, state):
    await state.set_state(Form.photo)
    await message.answer("Теперь пришли фото для визитки.")


async def ask_about(message, state):
    await state.set_state(Form.about)
    await message.answer(
        "Расскажи подробнее, чем ты полезен людям, что делаешь или с какими запросами к тебе приходят.\n\n"
        "Здесь не нужно ужимать всё до шапки Instagram. На визитке есть место для нормального описания, до 600 символов.\n\n"
        "Например:\n\n"
        "Коуч: помогаю не потеряться между работой, отношениями и своими желаниями. Вместе находим опору, ясность и следующий шаг, когда привычный путь больше не работает.\n\n"
        "Массажист: работаю с напряжением в теле, восстановлением и бережной заботой о себе. Подбираю формат массажа под самочувствие, запрос и ритм жизни.\n\n"
        "Блогер и инфлюенсер: создаю контент о путешествиях, стиле жизни и красивых местах Киева. Сотрудничаю с брендами, которым важно живое и эстетичное присутствие в соцсетях."
    )


async def ask_messengers(message):
    await message.answer("Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь каждый контакт по очереди.", reply_markup=menu(MESSENGERS, [], "m", "Готово ✓"))


async def ask_extras(message):
    await message.answer(
        "Выбери нужные пункты, затем нажми «Завершить заявку ✓».\n\n"
        "Эти функции можно оставить или убрать по желанию. Так человек сам выберет: поделиться визиткой с другом или сохранить контакт в телефон.\n\n"
        "Ничего дополнительно заполнять не нужно.",
        reply_markup=menu(EXTRAS, [], "e", "Завершить заявку ✓"),
    )


async def start_socials(message, state):
    await state.update_data(social_keys=[])
    await state.set_state(Form.socials)
    await message.answer("Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь ссылки по очереди.", reply_markup=menu(SOCIALS, [], "s", "Готово ✓"))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await examples(message)
    await message.answer(
        "<b>Привет!</b> Я помогу собрать данные для минималистичной онлайн-визитки.\n\n"
        "Это небольшая страница с самым важным о тебе: её можно поставить в Instagram и отправлять клиентам ссылкой.\n\n"
        "Посмотреть пример готовой визитки: <a href=\"https://riakhin-card.my-webcard.workers.dev\">https://riakhin-card.my-webcard.workers.dev</a>\n\n"
        "<b>Базовая визитка: 900 грн.</b>\n\n"
        "Как тебя зовут и чем занимаешься?\n\n"
        "Например: Александр, помогаю выйти из кризиса.\n"
        "Антон, делаю онлайн-визитки.\n"
        "Марина, массажист.\n"
        "Олег, дизайн кухонь.\n"
        "Катя, коуч.\n\n"
        "Подробное описание будет следующим шагом."
    )
    await state.set_state(Form.name)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Сбор данных отменён. Когда будешь готов, отправь /start.")


@router.message(Form.name, F.text)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.language)
    await message.answer(
        "На каком языке нужна визитка?\n\n"
        "Визитка на двух языках подойдёт, если к тебе обращаются люди из другой страны, ты живёшь или работаешь за границей, развиваешь международную аудиторию или хочешь отправлять одну понятную ссылку клиентам на разных языках.\n\n"
        "На странице появится переключатель языков возле имени и фото. Содержание визитки будет одинаковым, меняется только язык.\n\n"
        "Базовая визитка на одном языке стоит 900 грн.\n\n"
        "Второй язык: +500 грн, если ты пришлёшь готовый перевод. +800 грн, если переводим мы. Перед публикацией отправим текст на подтверждение. Входит одна правка.",
        reply_markup=language_menu(),
    )


@router.callback_query(Form.language, F.data.startswith("lang:"))
async def choose_language(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбор языка отменён. Когда будешь готов, отправь /start.")
    elif key == "two":
        await state.update_data(language_values=[], translation_mode=None)
        await state.set_state(Form.language_pair)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери два языка для визитки. На странице появится переключатель возле имени и фото.", reply_markup=pair_menu([]))
    elif key == "custom":
        await state.set_state(Form.custom_language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Напиши нужный язык. Например: Polski, Deutsch или Español.")
    else:
        await state.update_data(language_values=[LANGUAGES[key]], translation_mode=None)
        await callback.message.edit_reply_markup(reply_markup=None)
        await ask_photo(callback.message, state)
    await callback.answer()


@router.message(Form.custom_language, F.text)
async def custom_language(message: Message, state: FSMContext):
    value = message.text.strip()
    await state.update_data(language_values=[value], translation_mode=None)
    await ask_photo(message, state)


@router.callback_query(Form.language_pair, F.data.startswith("lp:"))
async def choose_language_pair(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("language_values", [])
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбор языка отменён. Когда будешь готов, отправь /start.")
    elif key == "one":
        await state.update_data(language_values=[], translation_mode=None)
        await state.set_state(Form.language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери один язык для визитки.", reply_markup=language_menu())
    elif key == "custom":
        if len(selected) >= 2:
            await callback.answer("Уже выбрано два языка.", show_alert=True)
            return
        await state.set_state(Form.pair_custom_language)
        await callback.message.answer("Напиши второй язык. Например: Polski, Deutsch или Español.")
    elif key == "done":
        if len(selected) != 2:
            await callback.answer("Выбери, пожалуйста, ровно два языка.", show_alert=True)
            return
        await state.set_state(Form.translation)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Как будет подготовлен перевод?", reply_markup=translation_menu())
    else:
        label = LANGUAGES[key]
        selected = selected.copy()
        if label in selected:
            selected.remove(label)
        elif len(selected) < 2:
            selected.append(label)
        else:
            await callback.answer("Можно выбрать только два языка.", show_alert=True)
            return
        await state.update_data(language_values=selected)
        chosen_codes = [code for code, name in LANGUAGES.items() if name in selected]
        await callback.message.edit_reply_markup(reply_markup=pair_menu(chosen_codes))
    await callback.answer()


@router.message(Form.pair_custom_language, F.text)
async def pair_custom_language(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("language_values", []).copy()
    value = message.text.strip()
    if value and value not in selected and len(selected) < 2:
        selected.append(value)
    await state.update_data(language_values=selected)
    chosen_codes = [code for code, name in LANGUAGES.items() if name in selected]
    await state.set_state(Form.language_pair)
    await message.answer("Язык добавлен. Теперь выбери второй пункт или продолжи.", reply_markup=pair_menu(chosen_codes))


@router.callback_query(Form.translation, F.data.startswith("tr:"))
async def choose_translation(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "languages":
        await state.update_data(language_values=[], translation_mode=None)
        await state.set_state(Form.language_pair)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери два языка для визитки.", reply_markup=pair_menu([]))
    elif key == "one":
        await state.update_data(language_values=[], translation_mode=None)
        await state.set_state(Form.language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери один язык для визитки.", reply_markup=language_menu())
    else:
        await state.update_data(translation_mode=key)
        await callback.message.edit_reply_markup(reply_markup=None)
        await ask_photo(callback.message, state)
    await callback.answer()


@router.message(Form.photo, F.photo)
async def photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(Form.color)
    await message.answer(
        "Теперь выберем цвет визитки.\n\n"
        "Пришли скрин шапки Instagram, и мы подберём визитку в той же тональности.\n\n"
        "Или напиши цвет словами: тёмно-зелёный, бежевый, синий.\n\n"
        "Если не знаешь, напиши «не знаю»."
    )


@router.message(Form.photo)
async def need_photo(message: Message):
    await message.answer("Прикрепи, пожалуйста, именно фотографию.")


@router.message(Form.color, F.photo)
async def color_photo(message: Message, state: FSMContext):
    await state.update_data(color_photo_id=message.photo[-1].file_id, color_note="Скрин шапки Instagram приложен")
    await ask_about(message, state)


@router.message(Form.color, F.text)
async def color_text(message: Message, state: FSMContext):
    await state.update_data(color_note=message.text.strip())
    await ask_about(message, state)


@router.message(Form.color)
async def need_color(message: Message):
    await message.answer("Пришли скрин шапки Instagram или напиши цвет словами. Можно также написать «не знаю».")


@router.message(Form.about, F.text)
async def about(message: Message, state: FSMContext):
    about_text = message.text.strip()
    await state.update_data(about=about_text, social_keys=[])
    if len(about_text) > 600:
        await message.answer(f"Текст получился длинный: {len(about_text)} символов. Визитка лучше смотрится до 600. Сохраним всё в заявке и при сборке поможем выделить главное.")
    data = await state.get_data()
    if data.get("translation_mode") == "ready":
        await state.set_state(Form.translation_text)
        await message.answer("Пришли готовый перевод имени, сферы и описания одним сообщением. Ссылки и контакты повторно заполнять не нужно.")
    else:
        await start_socials(message, state)


@router.message(Form.translation_text, F.text)
async def translation_text(message: Message, state: FSMContext):
    await state.update_data(translation_text=message.text.strip())
    await start_socials(message, state)


@router.callback_query(Form.socials, F.data.startswith("s:"))
async def socials(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("social_keys", [])
    if key == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        if selected:
            await state.update_data(social_values={}, social_index=0)
            await state.set_state(Form.social_link)
            await callback.message.answer(f"Пришли ссылку на <b>{SOCIALS[selected[0]]}</b>.")
        else:
            await state.update_data(messenger_keys=[])
            await state.set_state(Form.messengers)
            await ask_messengers(callback.message)
        await callback.answer()
        return
    selected = selected.copy()
    selected.remove(key) if key in selected else selected.append(key)
    await state.update_data(social_keys=selected)
    await callback.message.edit_reply_markup(reply_markup=menu(SOCIALS, selected, "s", "Готово ✓"))
    await callback.answer()


@router.message(Form.social_link, F.text)
async def social_link(message: Message, state: FSMContext):
    data = await state.get_data()
    keys, index = data["social_keys"], data["social_index"]
    values = data["social_values"]
    values[keys[index]] = message.text.strip()
    index += 1
    if index < len(keys):
        await state.update_data(social_values=values, social_index=index)
        await message.answer(f"Теперь ссылку на <b>{SOCIALS[keys[index]]}</b>.")
    else:
        await state.update_data(social_values=values, messenger_keys=[])
        await state.set_state(Form.messengers)
        await ask_messengers(message)


@router.callback_query(Form.messengers, F.data.startswith("m:"))
async def messengers(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("messenger_keys", [])
    if key == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        if selected:
            await state.update_data(messenger_values={}, messenger_index=0)
            await state.set_state(Form.messenger_value)
            await callback.message.answer(contact_prompt(selected[0]))
        else:
            await state.update_data(extra_keys=[])
            await state.set_state(Form.extras)
            await ask_extras(callback.message)
        await callback.answer()
        return
    selected = selected.copy()
    selected.remove(key) if key in selected else selected.append(key)
    await state.update_data(messenger_keys=selected)
    await callback.message.edit_reply_markup(reply_markup=menu(MESSENGERS, selected, "m", "Готово ✓"))
    await callback.answer()


@router.message(Form.messenger_value, F.text)
async def messenger_value(message: Message, state: FSMContext):
    data = await state.get_data()
    keys, index = data["messenger_keys"], data["messenger_index"]
    values = data["messenger_values"]
    values[keys[index]] = message.text.strip()
    index += 1
    if index < len(keys):
        await state.update_data(messenger_values=values, messenger_index=index)
        await message.answer(contact_prompt(keys[index]))
    else:
        await state.update_data(messenger_values=values, extra_keys=[])
        await state.set_state(Form.extras)
        await ask_extras(message)


def application(data, user):
    socials = "\n".join(f"• {SOCIALS[k]}: {escape(v)}" for k, v in data.get("social_values", {}).items()) or "не выбрано"
    contacts = "\n".join(f"• {MESSENGERS[k]}: {escape(v)}" for k, v in data.get("messenger_values", {}).items()) or "не выбрано"
    extras = ", ".join(EXTRAS[k] for k in data.get("extra_keys", [])) or "не выбрано"
    username = f" (@{user.username})" if user.username else ""
    price = price_info(data)
    translation = {"ready": "готовый перевод от клиента", "our": "переводим мы"}.get(data.get("translation_mode"), "не требуется")
    client_draft = f"Привет, {user.full_name}! Мы посмотрели материалы, всё хорошо. Для начала работы нужна предоплата {money(price['prepay'])}. Вот реквизиты: [впиши сам]. Как удобно оплатить?"
    translation_text = escape(data.get("translation_text", "не прислан")) if data.get("translation_mode") == "ready" else "не требуется"
    return (
        "<b>НОВАЯ ЗАЯВКА НА ВИЗИТКУ</b>\n\n"
        f"<b>Клиент:</b> {escape(user.full_name)}{username}\n\n"
        f"<b>Имя и сфера:</b> {escape(data['name'])}\n"
        f"<b>Язык:</b> {escape(language_names(data))}\n"
        f"<b>Перевод:</b> {translation}\n"
        f"<b>Стоимость:</b> {money(price['total'])}, предоплата {money(price['prepay'])}\n"
        f"<b>Текст перевода:</b> {translation_text}\n\n"
        f"<b>О себе:</b> {escape(data['about'])}\n\n"
        f"<b>Цвет:</b> {escape(data.get('color_note', 'не указан'))}\n\n"
        f"<b>Соцсети / сайт:</b>\n{socials}\n\n"
        f"<b>Связь:</b>\n{contacts}\n\n"
        f"<b>Дополнительно:</b> {extras}\n\n"
        f"<b>Скопируй и отправь клиенту:</b>\n<code>{escape(client_draft)}</code>"
    )


def owner_keyboard(user, data):
    rows = []
    if user.username:
        payment = price_info(data)
        draft = quote(f"Привет, {user.full_name}! Мы посмотрели материалы, всё хорошо. Для начала работы нужна предоплата {money(payment['prepay'])}. Вот реквизиты: [впиши сам]. Как удобно оплатить?")
        rows.append([InlineKeyboardButton(text="Написать клиенту", url=f"tg://resolve?domain={user.username}&text={draft}")])
    rows.append([InlineKeyboardButton(text="Визитка отправлена", callback_data=f"delivery:{user.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(Form.extras, F.data.startswith("e:"))
async def extras(callback: CallbackQuery, state: FSMContext, bot: Bot):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("extra_keys", [])
    if key != "done":
        selected = selected.copy()
        selected.remove(key) if key in selected else selected.append(key)
        await state.update_data(extra_keys=selected)
        await callback.message.edit_reply_markup(reply_markup=menu(EXTRAS, selected, "e", "Завершить заявку ✓"))
        await callback.answer()
        return
    price = price_info(data)
    try:
        await bot.send_photo(int(OWNER_CHAT_ID), data["photo_id"], caption="<b>Фото к заявке</b>")
        if data.get("color_photo_id"):
            await bot.send_photo(int(OWNER_CHAT_ID), data["color_photo_id"], caption="<b>Скрин стиля для визитки</b>")
        await bot.send_message(int(OWNER_CHAT_ID), application(data, callback.from_user), reply_markup=owner_keyboard(callback.from_user, data))
        language_line = ""
        if price["addon"]:
            language_line = f"\n\nВторой язык: <b>+{money(price['addon'])}</b>. Общая стоимость: <b>{money(price['total'])}</b>."
        text = (
            "<b>Готово, заявку получили.</b>\n\n"
            f"Стоимость: <b>{money(price['total'])}</b>. Чтобы начать работу, нужна предоплата <b>{money(price['prepay'])}</b>. "
            "Мы посмотрим материалы и пришлём реквизиты для оплаты. Готовую визитку получишь в течение 24 часов после предоплаты."
            f"{language_line}\n\n"
            "В течение недели можно внести правки: текст, соцсети, мессенджер, цвет - всё за один раз бесплатно. Если что-то работает некорректно по нашей вине, исправим бесплатно.\n\n"
            f"После согласования готовой визитки, перед публикацией, оплачивается остаток <b>{money(price['balance'])}</b>."
        )
    except Exception:
        logging.exception("Could not send application")
        text = "Не получилось передать заявку автоматически. Напиши нам напрямую."
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text, reply_markup=support_button())
    await state.clear()
    await callback.answer("Заявка отправлена")


@router.callback_query(F.data.startswith("delivery:"))
async def delivery(callback: CallbackQuery, bot: Bot):
    if not OWNER_CHAT_ID or callback.message.chat.id != int(OWNER_CHAT_ID):
        await callback.answer("Эта кнопка доступна только владельцу бота.", show_alert=True)
        return
    client_id = int(callback.data.split(":", 1)[1])
    try:
        await bot.send_message(client_id, "Если захочешь что-то изменить позже: цвет, текст, добавить соцсеть или мессенджер - одна правка 200 грн. Пиши в любое время.", reply_markup=support_button())
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Сообщение клиенту отправлено")
    except Exception:
        logging.exception("Could not send delivery message")
        await callback.answer("Не получилось отправить сообщение клиенту.", show_alert=True)


async def main():
    if not BOT_TOKEN or not OWNER_CHAT_ID:
        raise RuntimeError("Set BOT_TOKEN and OWNER_CHAT_ID in Railway Variables. Never save a token in GitHub.")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
