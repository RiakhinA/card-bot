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
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from services.application_service import build_application_service_from_environment

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
    language_select = State()
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
    review = State()
    edit_menu = State()
    edit_name = State()
    edit_photo = State()
    edit_color = State()
    edit_about = State()


router = Router()


def menu(items, chosen, prefix, done):
    rows = [[InlineKeyboardButton(text=("✓ " if key in chosen else "") + label, callback_data=f"{prefix}:{key}")] for key, label in items.items()]
    rows.append([InlineKeyboardButton(text=done, callback_data=f"{prefix}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Один язык", callback_data="lc:one")],
        [InlineKeyboardButton(text="Два языка", callback_data="lc:two")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="lc:cancel")],
    ])


def language_select_menu(mode, chosen):
    rows = [[InlineKeyboardButton(text=("✓ " if label in chosen else "") + label, callback_data=f"ls:{code}")] for code, label in LANGUAGES.items()]
    confirm = "Подтвердить язык ✓" if len(chosen) == 1 and mode == "one" else "Подтвердить 2 языка ✓" if len(chosen) == 2 and mode == "two" else "Выбери язык" if mode == "one" else "Выбери 2 языка"
    rows += [
        [InlineKeyboardButton(text="Написать свой язык", callback_data="ls:custom")],
        [InlineKeyboardButton(text=confirm, callback_data="ls:done")],
        [InlineKeyboardButton(text="← Назад", callback_data="ls:back")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="ls:cancel")],
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


def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отменить заявку")]], resize_keyboard=True)


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


async def ask_extras(message, chosen=None):
    chosen = list(EXTRAS) if chosen is None else chosen
    await message.answer(
        "Выбери нужные пункты, затем нажми «Завершить заявку ✓».\n\n"
        "Эти функции можно оставить или убрать по желанию. Так человек сам выберет: поделиться визиткой с другом или сохранить контакт в телефон.\n\n"
        "Ничего дополнительно заполнять не нужно.",
        reply_markup=menu(EXTRAS, chosen, "e", "Завершить заявку ✓"),
    )


async def start_socials(message, state):
    await state.update_data(social_keys=[])
    await state.set_state(Form.socials)
    await message.answer("Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь ссылки по очереди.", reply_markup=menu(SOCIALS, [], "s", "Готово ✓"))


def review_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отправить заявку ✓", callback_data="rv:send")],
        [InlineKeyboardButton(text="Изменить данные", callback_data="rv:edit")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="rv:cancel")],
    ])


def edit_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Имя и сфера", callback_data="ed:name")],
        [InlineKeyboardButton(text="Язык", callback_data="ed:language")],
        [InlineKeyboardButton(text="Фото", callback_data="ed:photo")],
        [InlineKeyboardButton(text="Цвет", callback_data="ed:color")],
        [InlineKeyboardButton(text="О себе", callback_data="ed:about")],
        [InlineKeyboardButton(text="Соцсети и сайт", callback_data="ed:socials")],
        [InlineKeyboardButton(text="Мессенджеры", callback_data="ed:messengers")],
        [InlineKeyboardButton(text="Дополнительные функции", callback_data="ed:extras")],
        [InlineKeyboardButton(text="← Вернуться к проверке", callback_data="ed:review")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="ed:cancel")],
    ])


async def show_review(message, state):
    data = await state.get_data()
    socials = ", ".join(SOCIALS[k] for k in data.get("social_values", {})) or "не выбрано"
    messengers = ", ".join(MESSENGERS[k] for k in data.get("messenger_values", {})) or "не выбрано"
    extras = ", ".join(EXTRAS[k] for k in data.get("extra_keys", [])) or "не выбрано"
    price = price_info(data)
    await state.update_data(return_to_review=False)
    await state.set_state(Form.review)
    await message.answer(
        "<b>Проверь заявку перед отправкой.</b>\n\n"
        f"<b>Имя и сфера:</b> {escape(data.get('name', ''))}\n"
        f"<b>Язык:</b> {escape(language_names(data))}\n"
        f"<b>Цвет:</b> {escape(data.get('color_note', 'не указан'))}\n"
        f"<b>Соцсети:</b> {socials}\n"
        f"<b>Мессенджеры:</b> {messengers}\n"
        f"<b>Дополнительно:</b> {extras}\n"
        f"<b>Стоимость:</b> {money(price['total'])}, предоплата {money(price['prepay'])}",
        reply_markup=review_keyboard(),
    )


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
        "Подробное описание будет следующим шагом.",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(Form.name)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Сбор данных отменён. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())


@router.message(F.text == "Отменить заявку")
async def cancel_by_button(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())


@router.message(Form.name, F.text)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.language)
    await message.answer(
        "Сколько языков нужно для визитки?\n\n"
        "Один язык входит в базовую стоимость 900 грн. Два языка нужны, если ты работаешь с аудиторией из разных стран или хочешь отправлять одну ссылку клиентам на разных языках.",
        reply_markup=language_menu(),
    )


@router.callback_query(Form.language, F.data.startswith("lc:"))
async def choose_language_count(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    else:
        mode = "one" if key == "one" else "two"
        await state.update_data(language_mode=mode, language_values=[], translation_mode=None)
        await state.set_state(Form.language_select)
        await callback.message.edit_reply_markup(reply_markup=None)
        intro = "Выбери язык визитки." if mode == "one" else "Выбери два языка для визитки. На странице появится переключатель возле имени и фото."
        await callback.message.answer(intro, reply_markup=language_select_menu(mode, []))
    await callback.answer()


@router.callback_query(Form.language_select, F.data.startswith("ls:"))
async def choose_language(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    mode = data.get("language_mode", "one")
    selected = data.get("language_values", [])
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    elif key == "back":
        await state.update_data(language_values=[], translation_mode=None)
        await state.set_state(Form.language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Сколько языков нужно для визитки?", reply_markup=language_menu())
    elif key == "custom":
        if len(selected) >= (1 if mode == "one" else 2):
            await callback.answer("Сначала убери выбранный язык.", show_alert=True)
            return
        await state.set_state(Form.custom_language)
        await callback.message.answer("Напиши нужный язык. Например: Polski, Deutsch или Español.")
    elif key == "done":
        need = 1 if mode == "one" else 2
        if len(selected) != need:
            await callback.answer(f"Выбери, пожалуйста, {need} язык{'а' if need == 2 else ''}.", show_alert=True)
            return
        await callback.message.edit_reply_markup(reply_markup=None)
        if mode == "two":
            await state.set_state(Form.translation)
            await callback.message.answer("Как будет подготовлен перевод?", reply_markup=translation_menu())
        elif data.get("return_to_review"):
            await show_review(callback.message, state)
        else:
            await ask_photo(callback.message, state)
    else:
        label = LANGUAGES[key]
        selected = selected.copy()
        if label in selected:
            selected.remove(label)
        elif len(selected) < (1 if mode == "one" else 2):
            selected.append(label)
        else:
            await callback.answer("Сначала убери выбранный язык.", show_alert=True)
            return
        await state.update_data(language_values=selected)
        await callback.message.edit_reply_markup(reply_markup=language_select_menu(mode, selected))
    await callback.answer()


@router.message(Form.custom_language, F.text)
async def custom_language(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("language_values", []).copy()
    value = message.text.strip()
    mode = data.get("language_mode", "one")
    limit = 1 if mode == "one" else 2
    if value and value not in selected and len(selected) < limit:
        selected.append(value)
    await state.update_data(language_values=selected)
    await state.set_state(Form.language_select)
    await message.answer("Язык добавлен. Подтверди выбор или выбери ещё один язык.", reply_markup=language_select_menu(mode, selected))


@router.callback_query(Form.translation, F.data.startswith("tr:"))
async def choose_translation(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "languages":
        await state.update_data(language_values=[], translation_mode=None, language_mode="two")
        await state.set_state(Form.language_select)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери два языка для визитки.", reply_markup=language_select_menu("two", []))
    elif key == "one":
        await state.update_data(language_values=[], translation_mode=None, language_mode="one")
        await state.set_state(Form.language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Сколько языков нужно для визитки?", reply_markup=language_menu())
    else:
        await state.update_data(translation_mode=key)
        await callback.message.edit_reply_markup(reply_markup=None)
        data = await state.get_data()
        if data.get("return_to_review"):
            if key == "ready":
                await state.set_state(Form.translation_text)
                await callback.message.answer("Пришли готовый перевод имени, сферы и описания одним сообщением.")
            else:
                await show_review(callback.message, state)
        else:
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
        if data.get("return_to_review"):
            await show_review(message, state)
        else:
            await start_socials(message, state)


@router.message(Form.translation_text, F.text)
async def translation_text(message: Message, state: FSMContext):
    await state.update_data(translation_text=message.text.strip())
    data = await state.get_data()
    if data.get("return_to_review"):
        await show_review(message, state)
    else:
        await start_socials(message, state)


@router.callback_query(Form.socials, F.data.startswith("s:"))
async def socials(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("social_keys", [])
    if key == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        if selected:
            values = {k: v for k, v in data.get("social_values", {}).items() if k in selected}
            to_fill = [k for k in selected if k not in values]
            await state.update_data(social_values=values, social_input_keys=to_fill, social_index=0)
            if to_fill:
                await state.set_state(Form.social_link)
                await callback.message.answer(f"Пришли ссылку на <b>{SOCIALS[to_fill[0]]}</b>.")
            elif data.get("return_to_review"):
                await show_review(callback.message, state)
            else:
                await state.update_data(messenger_keys=[])
                await state.set_state(Form.messengers)
                await ask_messengers(callback.message)
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
    keys, index = data["social_input_keys"], data["social_index"]
    values = data["social_values"]
    values[keys[index]] = message.text.strip()
    index += 1
    if index < len(keys):
        await state.update_data(social_values=values, social_index=index)
        await message.answer(f"Теперь ссылку на <b>{SOCIALS[keys[index]]}</b>.")
    else:
        await state.update_data(social_values=values)
        if data.get("return_to_review"):
            await show_review(message, state)
        else:
            await state.update_data(messenger_keys=[])
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
            values = {k: v for k, v in data.get("messenger_values", {}).items() if k in selected}
            to_fill = [k for k in selected if k not in values]
            await state.update_data(messenger_values=values, messenger_input_keys=to_fill, messenger_index=0)
            if to_fill:
                await state.set_state(Form.messenger_value)
                await callback.message.answer(contact_prompt(to_fill[0]))
            elif data.get("return_to_review"):
                await show_review(callback.message, state)
            else:
                await state.update_data(extra_keys=list(EXTRAS))
                await state.set_state(Form.extras)
                await ask_extras(callback.message)
        else:
            await state.update_data(extra_keys=list(EXTRAS))
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
    keys, index = data["messenger_input_keys"], data["messenger_index"]
    values = data["messenger_values"]
    values[keys[index]] = message.text.strip()
    index += 1
    if index < len(keys):
        await state.update_data(messenger_values=values, messenger_index=index)
        await message.answer(contact_prompt(keys[index]))
    else:
        await state.update_data(messenger_values=values)
        if data.get("return_to_review"):
            await show_review(message, state)
        else:
            await state.update_data(extra_keys=list(EXTRAS))
            await state.set_state(Form.extras)
            await ask_extras(message)


def application(data, user, client_id=None, application_id=None):
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
        f"<b>Client ID:</b> {escape(client_id or 'не создан')}\n"
        f"<b>Application ID:</b> {escape(application_id or 'не создан')}\n\n"
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
async def extras(callback: CallbackQuery, state: FSMContext):
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
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_review(callback.message, state)
    await callback.answer()


async def send_application(message: Message, state: FSMContext, bot: Bot, user):
    data = await state.get_data()
    price = price_info(data)
    try:
        application_service = build_application_service_from_environment()
        submission = await application_service.persist_submission(
            bot=bot,
            telegram_user=user,
            data=data,
            price_snapshot=price,
            request_key=f"telegram:{user.id}:{message.chat.id}:{message.message_id}",
        )
    except Exception:
        logging.exception("Could not persist application")
        await message.answer("Не получилось передать заявку автоматически. Напиши нам напрямую.", reply_markup=support_button())
        return False

    try:
        if submission.created:
            await bot.send_photo(int(OWNER_CHAT_ID), data["photo_id"], caption="<b>Фото к заявке</b>")
            if data.get("color_photo_id"):
                await bot.send_photo(int(OWNER_CHAT_ID), data["color_photo_id"], caption="<b>Скрин стиля для визитки</b>")
            await bot.send_message(
                int(OWNER_CHAT_ID),
                application(
                    data,
                    user,
                    client_id=submission.client.client_id,
                    application_id=submission.application.application_id,
                ),
                reply_markup=owner_keyboard(user, data),
            )
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
    await message.answer(text, reply_markup=support_button())
    await state.clear()
    return text != "Не получилось передать заявку автоматически. Напиши нам напрямую."


@router.callback_query(Form.review, F.data.startswith("rv:"))
async def review(callback: CallbackQuery, state: FSMContext, bot: Bot):
    key = callback.data.split(":", 1)[1]
    if key == "send":
        await callback.message.edit_reply_markup(reply_markup=None)
        sent = await send_application(callback.message, state, bot, callback.from_user)
        if sent:
            await callback.answer("Заявка отправлена")
        else:
            await callback.answer("Не получилось передать заявку автоматически.", show_alert=True)
    elif key == "edit":
        await state.set_state(Form.edit_menu)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Что хочешь изменить?", reply_markup=edit_keyboard())
        await callback.answer()
    else:
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
        await callback.answer()


@router.callback_query(Form.edit_menu, F.data.startswith("ed:"))
async def edit(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "review":
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_review(callback.message, state)
    elif key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    elif key == "name":
        await state.set_state(Form.edit_name)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Напиши имя и сферу заново.")
    elif key == "photo":
        await state.set_state(Form.edit_photo)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Пришли новое фото для визитки.")
    elif key == "color":
        await state.set_state(Form.edit_color)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Пришли новый скрин шапки Instagram или напиши цвет словами.")
    elif key == "about":
        await state.set_state(Form.edit_about)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Напиши новое описание о себе.")
    elif key == "language":
        await state.update_data(return_to_review=True, language_values=[], translation_mode=None)
        await state.set_state(Form.language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Сколько языков нужно для визитки?", reply_markup=language_menu())
    elif key == "socials":
        data = await state.get_data()
        selected = data.get("social_keys", [])
        await state.update_data(return_to_review=True)
        await state.set_state(Form.socials)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери актуальные соцсети и сайт. Новые пункты нужно будет заполнить ссылками.", reply_markup=menu(SOCIALS, selected, "s", "Готово ✓"))
    elif key == "messengers":
        data = await state.get_data()
        selected = data.get("messenger_keys", [])
        await state.update_data(return_to_review=True)
        await state.set_state(Form.messengers)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери актуальные мессенджеры. Новые пункты нужно будет заполнить контактами.", reply_markup=menu(MESSENGERS, selected, "m", "Готово ✓"))
    else:
        data = await state.get_data()
        await state.set_state(Form.extras)
        await callback.message.edit_reply_markup(reply_markup=None)
        await ask_extras(callback.message, data.get("extra_keys", list(EXTRAS)))
    await callback.answer()


@router.message(Form.edit_name, F.text)
async def edit_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await show_review(message, state)


@router.message(Form.edit_photo, F.photo)
async def edit_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await show_review(message, state)


@router.message(Form.edit_photo)
async def need_edit_photo(message: Message):
    await message.answer("Прикрепи, пожалуйста, именно фотографию.")


@router.message(Form.edit_color, F.photo)
async def edit_color_photo(message: Message, state: FSMContext):
    await state.update_data(color_photo_id=message.photo[-1].file_id, color_note="Скрин шапки Instagram приложен")
    await show_review(message, state)


@router.message(Form.edit_color, F.text)
async def edit_color_text(message: Message, state: FSMContext):
    await state.update_data(color_note=message.text.strip())
    await show_review(message, state)


@router.message(Form.edit_about, F.text)
async def edit_about(message: Message, state: FSMContext):
    await state.update_data(about=message.text.strip())
    await show_review(message, state)


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
