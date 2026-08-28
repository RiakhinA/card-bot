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
from services.adaptive_preset import profession_needs_context, recommend_preset
from services.module_configuration import build_module_configuration, normalize_phone_values
from services.module_selection import CONTACT_MODULE, LOCATION_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE, initial_selected_modules, next_module_flow, toggle_module
from services.products_collection import ProductValidationError, add_product
from services.telegram_backend_integration import (
    build_release_2_card_draft_services_from_environment,
    create_card_draft_from_confirmed_application,
)
from services.telegram_submission_contract import (
    confirmed_submission_data,
    core_profession_required,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "riakhin_anton").lstrip("@")
ASSETS = Path(__file__).parent / "assets"

ONE_LANGUAGE_PRICE = 1200
TWO_LANGUAGE_PRICE = 1700
LANGUAGES = {"uk": "Українська", "ru": "Русский", "en": "English"}
SOCIALS = {"instagram": "Instagram", "facebook": "Facebook", "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok"}
MESSENGERS = {"phone": "Телефон", "email": "Email", "telegram": "Telegram", "whatsapp": "WhatsApp", "viber": "Viber", "other": "Другой контакт"}
PHONE_LABELS = {"work": "Рабочий", "personal": "Личный", "salon": "Салон", "other": "Другой"}
EXTRAS = {"share": "Поделиться визиткой", "vcf": "Сохранить контакт (.vcf)"}


class Form(StatesGroup):
    entry_mode = State()
    card_name = State()
    profession = State()
    work_context = State()
    preset = State()
    name = State()
    core_profession = State()
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
    modules = State()
    socials = State()
    social_link = State()
    messengers = State()
    messenger_value = State()
    other_messenger_name = State()
    other_messenger_value = State()
    phone_label = State()
    phone_value = State()
    location_city = State()
    location_address = State()
    products = State()
    product_name = State()
    product_description = State()
    product_link = State()
    extras = State()
    review = State()
    final_comment = State()
    payment_method = State()
    payment_method_other = State()
    confirmation = State()
    edit_menu = State()
    edit_name = State()
    edit_photo = State()
    edit_color = State()
    edit_about = State()


router = Router()


def menu(items, chosen, prefix, done, *, back_callback=None):
    rows = [[InlineKeyboardButton(text=("✓ " if key in chosen else "") + label, callback_data=f"{prefix}:{key}")] for key, label in items.items()]
    if back_callback:
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=back_callback)])
    rows.append([InlineKeyboardButton(text=done, callback_data=f"{prefix}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Один язык", callback_data="lc:one")],
        [InlineKeyboardButton(text="Два языка", callback_data="lc:two")],
        [InlineKeyboardButton(text="← Назад", callback_data="lc:back")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="lc:cancel")],
    ])


def interface_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Українська", callback_data="ui:uk")],
        [InlineKeyboardButton(text="Русский", callback_data="ui:ru")],
        [InlineKeyboardButton(text="English", callback_data="ui:en")],
    ])


def entry_mode_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Рассказать о себе", callback_data="entry:about")],
        [InlineKeyboardButton(text="⚡ Я знаю, что мне нужно", callback_data="entry:direct")],
    ])


def work_context_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Онлайн", callback_data="context:online")],
        [InlineKeyboardButton(text="Офлайн", callback_data="context:offline")],
        [InlineKeyboardButton(text="Онлайн и офлайн", callback_data="context:hybrid")],
        [InlineKeyboardButton(text="← Назад", callback_data="context:back")],
    ])


def preset_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="preset:continue")],
        [InlineKeyboardButton(text="Изменить набор", callback_data="preset:edit")],
        [InlineKeyboardButton(text="← Назад", callback_data="preset:back")],
    ])


def language_select_menu(mode, chosen):
    rows = [[InlineKeyboardButton(text=("✓ " if label in chosen else "") + label, callback_data=f"ls:{code}")] for code, label in LANGUAGES.items()]
    confirm = "Подтвердить язык ✓" if len(chosen) == 1 and mode == "one" else "Подтвердить 2 языка ✓" if len(chosen) == 2 and mode == "two" else "Выбери язык" if mode == "one" else "Выбери 2 языка"
    rows += [
        [InlineKeyboardButton(text="Другой язык", callback_data="ls:custom")],
        [InlineKeyboardButton(text="← Назад", callback_data="ls:back")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="ls:cancel")],
        [InlineKeyboardButton(text=confirm, callback_data="ls:done")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def translation_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пришлю готовый перевод", callback_data="tr:ready")],
        [InlineKeyboardButton(text="Нужна помощь с переводом", callback_data="tr:our")],
        [InlineKeyboardButton(text="← Изменить языки", callback_data="tr:languages")],
        [InlineKeyboardButton(text="Оставить один язык", callback_data="tr:one")],
    ])


def media_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Фото", callback_data="media:photo")],
        [InlineKeyboardButton(text="Логотип", callback_data="media:logo")],
        [InlineKeyboardButton(text="Без изображения", callback_data="media:none")],
        [InlineKeyboardButton(text="← Назад", callback_data="media:back")],
    ])


PAYMENT_METHODS = {
    "privatbank": "PrivatBank",
    "paypal": "PayPal",
    "payoneer": "Payoneer",
    "skrill": "Skrill",
    "crypto": "Криптовалюта",
    "other": "Другой способ",
}


def payment_method_keyboard():
    rows = [[InlineKeyboardButton(text=label, callback_data=f"pay:{key}")] for key, label in PAYMENT_METHODS.items()]
    rows.append([InlineKeyboardButton(text="← Вернуться к проверке", callback_data="pay:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirmation_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Изменить способ оплаты", callback_data="confirm:back")],
        [InlineKeyboardButton(text="Отправить заявку", callback_data="confirm:submit")],
    ])


def support_button():
    draft = quote("Привет, у меня вопрос по визитке: ")
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Есть вопрос? Написать в поддержку", url=f"tg://resolve?domain={OWNER_USERNAME}&text={draft}")
    ]])


def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отменить заявку")]], resize_keyboard=True)


def step_back_keyboard(callback_data):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← Назад", callback_data=callback_data)
    ]])


def progress_text(data, section):
    """Small data-driven progress for the current intake flow."""
    labels = {
        "core": "Основная информация",
        SOCIAL_MODULE: "Социальные сети",
        CONTACT_MODULE: "Контакты",
        PRODUCTS_MODULE: "Проекты и ссылки",
        LOCATION_MODULE: "Локация",
        "review": "Проверка и отправка",
    }
    selected = initial_selected_modules(data.get("selected_modules", ()))
    sequence = ["core", *(module for module in selected if module != "core"), "review"]
    current = sequence.index(section) + 1 if section in sequence else len(sequence)
    return f"<b>Шаг {current} из {len(sequence)}</b>\nТекущий раздел: <b>{labels[section]}</b>\n\n"


def price_info(data):
    language_count = len(data.get("language_values", []))
    total = TWO_LANGUAGE_PRICE if language_count >= 2 or data.get("language_mode") == "two" else ONE_LANGUAGE_PRICE
    usd = 39 if total == TWO_LANGUAGE_PRICE else 29
    return {"total": total, "currency": "UAH", "usd_total": usd, "payment_policy": "оплата после проверки заявки"}


def money(value):
    return f"{value} грн"


def tariff_text(data):
    price = price_info(data)
    return f"{money(price['total'])} / ${price['usd_total']}"


def language_names(data):
    values = data.get("language_values", [])
    return ", ".join(values) or "не указан"


def contact_prompt(key):
    return f"Пришли контакт для <b>{MESSENGERS[key]}</b>."


def phone_values(data):
    return normalize_phone_values(data)


def phones_text(data):
    phones = phone_values(data)
    return ", ".join(f"{phone['label']}: {phone['number']}" for phone in phones) or "не указано"


def contact_value_text(key, value):
    if key == "other" and isinstance(value, dict):
        name = str(value.get("name") or "Другой контакт").strip()
        contact = str(value.get("value") or "").strip()
        return f"{name}: {contact}" if contact else name
    return f"{MESSENGERS.get(key, key)}: {value}"


def contacts_review_text(data):
    values = data.get("messenger_values", {})
    rendered = [
        contact_value_text(key, value)
        for key, value in values.items()
        if key != "phone" and value not in (None, "")
    ]
    return ", ".join(rendered) or "не выбрано"


def projects_review_text(data):
    projects = data.get("product_values", [])
    if not projects:
        return "не добавлены"
    return "\n".join(
        f"• {escape(str(project.get('name') or 'Без названия'))}: {escape(str(project.get('link') or ''))}"
        for project in projects
    )


async def examples(message):
    paths = [ASSETS / x for x in ("01-anton.png", "02-male.png", "03-female.png", "04-builder.png")]
    if all(p.exists() for p in paths):
        await message.answer_media_group([InputMediaPhoto(media=FSInputFile(p)) for p in paths])
    else:
        await message.answer("Примеры визиток пока загружаются. Мы пришлём их отдельно.")


async def ask_photo(message, state):
    await state.set_state(Form.photo)
    await message.answer(
        progress_text(await state.get_data(), "core") + "Пришли файл для визитки.",
        reply_markup=step_back_keyboard("core:photo:back"),
    )


async def ask_media_choice(message, state):
    await state.set_state(Form.photo)
    await message.answer(
        progress_text(await state.get_data(), "core")
        + "Что использовать на визитке? Можно выбрать фото, логотип или вариант без изображения.",
        reply_markup=media_keyboard(),
    )


async def ask_about(message, state):
    await state.set_state(Form.about)
    await message.answer(
        progress_text(await state.get_data(), "core")
        + "Расскажи, что человеку важно узнать о тебе в первую очередь. Можно написать, чем ты занимаешься, как помогаешь, работаешь ли онлайн или офлайн, в каких городах принимаешь и другую рабочую информацию, если она важна.\n\n"
        "Здесь не нужно ужимать всё до шапки Instagram. На визитке есть место для нормального описания, до 600 символов.\n\n"
        "Например:\n\n"
        "Коуч: помогаю не потеряться между работой, отношениями и своими желаниями. Вместе находим опору, ясность и следующий шаг, когда привычный путь больше не работает.\n\n"
        "Массажист: работаю с напряжением в теле, восстановлением и бережной заботой о себе. Подбираю формат массажа под самочувствие, запрос и ритм жизни.\n\n"
        "Блогер и инфлюенсер: создаю контент о путешествиях, стиле жизни и красивых местах Киева. Сотрудничаю с брендами, которым важно живое и эстетичное присутствие в соцсетях.",
        reply_markup=step_back_keyboard("core:about:back"),
    )


async def ask_messengers(message, state, chosen=()):
    data = await state.get_data()
    await message.answer(
        progress_text(data, CONTACT_MODULE) + "Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь каждый контакт по очереди.",
        reply_markup=menu(MESSENGERS, chosen, "m", "Готово ✓", back_callback="m:back"),
    )


async def ask_extras(message, chosen=None):
    chosen = list(EXTRAS) if chosen is None else chosen
    data = await state.get_data()
    await message.answer(
        progress_text(data, "review") + "Выбери нужные пункты, затем нажми «Завершить заявку ✓».\n\n"
        "Эти функции можно оставить или убрать по желанию. Так человек сам выберет: поделиться визиткой с другом или сохранить контакт в телефон.\n\n"
        "Ничего дополнительно заполнять не нужно.",
        reply_markup=menu(EXTRAS, chosen, "e", "Завершить заявку ✓"),
    )


def module_selection_keyboard(selected_modules):
    selected = set(selected_modules)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("☑ " if SOCIAL_MODULE in selected else "☐ ") + "Социальные сети", callback_data=f"ms:{SOCIAL_MODULE}")],
        [InlineKeyboardButton(text=("☑ " if CONTACT_MODULE in selected else "☐ ") + "Контакты", callback_data=f"ms:{CONTACT_MODULE}")],
        [InlineKeyboardButton(text=("☑ " if PRODUCTS_MODULE in selected else "☐ ") + "Проекты и ссылки", callback_data=f"ms:{PRODUCTS_MODULE}")],
        [InlineKeyboardButton(text="← Назад", callback_data="ms:back")],
        [InlineKeyboardButton(text="Продолжить", callback_data="ms:continue")],
    ])


async def start_module_selection(message, state, *, preserve_completed=False):
    data = await state.get_data()
    selected_modules = initial_selected_modules(data.get("selected_modules", ()))
    completed_modules = list(data.get("completed_modules", ())) if preserve_completed else []
    await state.update_data(selected_modules=list(selected_modules), completed_modules=completed_modules)
    await state.set_state(Form.modules)
    await message.answer("<b>Что добавить в визитку?</b>\n\nВыбери нужные разделы. Их можно не выбирать, если они не нужны.", reply_markup=module_selection_keyboard(selected_modules))


async def start_core_collection(message, state):
    await state.update_data(modules_selected_before_core=True)
    await state.set_state(Form.card_name)
    await message.answer(
        progress_text(await state.get_data(), "core")
        + "Отлично. Теперь начнём основную информацию. Сначала укажи желаемое имя ссылки, например: <code>anna-koval.my-webcard.workers.dev</code>.\n\n"
        + "Это только пожелание к адресу. Мы не проверяем и не обещаем его доступность на этом шаге.",
        reply_markup=step_back_keyboard("core:card-name:back"),
    )


async def continue_after_core(message, state):
    await state.update_data(core_complete=True)
    data = await state.get_data()
    if data.get("modules_selected_before_core"):
        await start_next_selected_module(message, state)
    else:
        await start_module_selection(message, state)


async def start_next_selected_module(message, state):
    data = await state.get_data()
    next_flow = next_module_flow(data.get("selected_modules", ()), data.get("completed_modules", ()))
    if next_flow == SOCIAL_MODULE:
        await start_socials(message, state)
    elif next_flow == CONTACT_MODULE:
        await start_contacts(message, state)
    elif next_flow == PRODUCTS_MODULE:
        await start_products(message, state)
    else:
        await show_review(message, state)


async def complete_selected_module(message, state, module):
    data = await state.get_data()
    if data.get("return_to_review"):
        await show_review(message, state)
        return
    completed = list(data.get("completed_modules", ()))
    if module not in completed:
        completed.append(module)
    await state.update_data(completed_modules=completed)
    await start_next_selected_module(message, state)


async def complete_social_module(message, state):
    await complete_selected_module(message, state, SOCIAL_MODULE)


async def complete_contact_module(message, state):
    await complete_selected_module(message, state, CONTACT_MODULE)


async def complete_location_module(message, state):
    await complete_selected_module(message, state, LOCATION_MODULE)


async def complete_products_module(message, state):
    await complete_selected_module(message, state, PRODUCTS_MODULE)


async def start_socials(message, state):
    data = await state.get_data()
    selected = list(data.get("social_keys", ()))
    await state.update_data(social_keys=selected)
    await state.set_state(Form.socials)
    await message.answer(
        progress_text(data, SOCIAL_MODULE) + "Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь ссылки по очереди.",
        reply_markup=menu(SOCIALS, selected, "s", "Готово ✓", back_callback="s:back"),
    )


async def start_contacts(message, state):
    data = await state.get_data()
    selected = list(data.get("messenger_keys", ()))
    if phone_values(data) and "phone" not in selected:
        selected.append("phone")
    await state.update_data(messenger_keys=selected)
    await state.set_state(Form.messengers)
    await ask_messengers(message, state, selected)


def location_city_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить локацию", callback_data="loc:skip")],
        [InlineKeyboardButton(text="← Назад", callback_data="loc:back")],
    ])


def location_address_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить адрес", callback_data="loc:address:skip")],
        [InlineKeyboardButton(text="← Назад", callback_data="loc:address:back")],
    ])


async def start_location(message, state):
    data = await state.get_data()
    await state.set_state(Form.location_city)
    current = data.get("city")
    suffix = f" Сейчас: {escape(current)}." if current else ""
    await message.answer(
        progress_text(data, LOCATION_MODULE) + f"В каком городе вы принимаете клиентов?{suffix}",
        reply_markup=location_city_keyboard(),
    )


def products_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="＋ Добавить проект или ссылку", callback_data="p:add")],
        [InlineKeyboardButton(text="← Назад", callback_data="p:back")],
        [InlineKeyboardButton(text="Готово ✓", callback_data="p:done")],
    ])


async def start_products(message, state):
    await state.set_state(Form.products)
    await message.answer(progress_text(await state.get_data(), PRODUCTS_MODULE) + "Добавь проекты и ссылки: сайты, боты, портфолио, курсы, акции или другие внешние ресурсы.", reply_markup=products_keyboard())


@router.callback_query(Form.products, F.data.startswith("p:"))
async def products(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "add":
        await state.update_data(current_product={})
        await state.set_state(Form.product_name)
        await callback.message.answer("Название проекта или ссылки:", reply_markup=step_back_keyboard("pstep:name:back"))
    elif key == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        await complete_products_module(callback.message, state)
    elif key == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        if (await state.get_data()).get("return_to_review"):
            await show_review(callback.message, state)
        else:
            await start_module_selection(callback.message, state, preserve_completed=True)
    await callback.answer()


@router.message(Form.product_name, F.text)
async def product_name(message: Message, state: FSMContext):
    value = message.text.strip()
    if not value:
        await message.answer("Название проекта или ссылки обязательно. Напиши его, пожалуйста.")
        return
    await state.update_data(current_product={"name": value})
    await state.set_state(Form.product_description)
    await message.answer(
        "Описание (необязательно). Отправь «-», чтобы пропустить.",
        reply_markup=step_back_keyboard("pstep:description:back"),
    )


@router.message(Form.product_description, F.text)
async def product_description(message: Message, state: FSMContext):
    current = dict((await state.get_data()).get("current_product", {}))
    current["description"] = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(current_product=current)
    await state.set_state(Form.product_link)
    await message.answer(
        "Ссылка на проект обязательна. Укажи полный адрес с http:// или https://.",
        reply_markup=step_back_keyboard("pstep:link:back"),
    )


@router.message(Form.product_link, F.text)
async def product_link(message: Message, state: FSMContext):
    data = await state.get_data()
    current = dict(data.get("current_product", {}))
    link = message.text.strip()
    try:
        products = add_product(data.get("product_values", []), current.get("name", ""), current.get("description", ""), link)
    except ProductValidationError as error:
        await message.answer(str(error))
        return
    await state.update_data(product_values=products, current_product=None)
    await state.set_state(Form.products)
    await message.answer("Проект или ссылка добавлены.", reply_markup=products_keyboard())


@router.callback_query(Form.product_name, F.data == "pstep:name:back")
async def product_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.products)
    await callback.message.answer("Вернулись к списку проектов и ссылок.", reply_markup=products_keyboard())
    await callback.answer()


@router.callback_query(Form.product_description, F.data == "pstep:description:back")
async def product_description_back(callback: CallbackQuery, state: FSMContext):
    current = (await state.get_data()).get("current_product", {})
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.product_name)
    await callback.message.answer(
        f"Название проекта или ссылки (сейчас: {escape(current.get('name', ''))}). Отправь новое значение или оставь прежнее.",
        reply_markup=step_back_keyboard("pstep:name:back"),
    )
    await callback.answer()


@router.callback_query(Form.product_link, F.data == "pstep:link:back")
async def product_link_back(callback: CallbackQuery, state: FSMContext):
    current = (await state.get_data()).get("current_product", {})
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.product_description)
    await callback.message.answer(
        f"Описание (сейчас: {escape(current.get('description', '')) or 'не указано'}). Отправь новое значение или «-».",
        reply_markup=step_back_keyboard("pstep:description:back"),
    )
    await callback.answer()


def review_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Изменить модули", callback_data="rv:modules")],
        [InlineKeyboardButton(text="Изменить данные", callback_data="rv:edit")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="rv:cancel")],
        [InlineKeyboardButton(text="Продолжить к отправке", callback_data="rv:send")],
    ])


def edit_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Имя ссылки", callback_data="ed:card-name")],
        [InlineKeyboardButton(text="Имя и сфера", callback_data="ed:name")],
        [InlineKeyboardButton(text="Язык", callback_data="ed:language")],
        [InlineKeyboardButton(text="Фото / логотип", callback_data="ed:photo")],
        [InlineKeyboardButton(text="О себе", callback_data="ed:about")],
        [InlineKeyboardButton(text="Соцсети", callback_data="ed:socials")],
        [InlineKeyboardButton(text="Контакты", callback_data="ed:messengers")],
        [InlineKeyboardButton(text="Проекты и ссылки", callback_data="ed:products")],
        [InlineKeyboardButton(text="← Вернуться к проверке", callback_data="ed:review")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="ed:cancel")],
    ])


async def show_review(message, state):
    data = await state.get_data()
    selected_modules, module_configuration = build_module_configuration(data, selected_modules=tuple(data.get("selected_modules", ())))
    await state.update_data(selected_modules=list(selected_modules), module_configuration=module_configuration)
    socials = ", ".join(SOCIALS.get(k, k) for k in data.get("social_values", {})) or "не выбрано"
    messengers = contacts_review_text(data)
    products = data.get("product_values", [])
    selected_labels = {"core": "Основная информация", SOCIAL_MODULE: "Социальные сети", CONTACT_MODULE: "Контакты", PRODUCTS_MODULE: "Проекты и ссылки"}
    selected_text = ", ".join(selected_labels[module] for module in selected_modules)
    await state.update_data(return_to_review=False)
    await state.set_state(Form.review)
    await message.answer(
        progress_text(data, "review") + "<b>Проверь заявку перед отправкой.</b>\n\n"
        f"<b>Разделы:</b> {selected_text}\n"
        f"<b>Желаемое имя ссылки:</b> {escape(data.get('preferred_card_name', 'не указано'))}\n"
        f"<b>Имя:</b> {escape(data.get('name', ''))}\n"
        f"<b>Профессия:</b> {escape(data.get('profession', ''))}\n"
        f"<b>Язык:</b> {escape(language_names(data))}\n"
        f"<b>Изображение:</b> {escape(data.get('image_kind', 'не указано'))}\n"
        f"<b>Соцсети:</b> {socials}\n"
        f"<b>Мессенджеры:</b> {messengers}\n"
        f"<b>Телефоны:</b> {phones_text(data)}\n"
        f"<b>Проекты и ссылки:</b>\n{projects_review_text(data)}\n"
        f"<b>Стоимость:</b> {tariff_text(data)}\n\n"
        "После отправки мы проверим данные и пришлём реквизиты для выбранного способа оплаты.",
        reply_markup=review_keyboard(),
    )


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
    data = await state.get_data()
    if core_profession_required(data):
        await state.set_state(Form.core_profession)
        await message.answer(
            progress_text(data, "core") + "Чем вы занимаетесь? Это будет указано на визитке.",
            reply_markup=step_back_keyboard("core:profession:back"),
        )
        return
    await ask_media_choice(message, state)


@router.message(Form.card_name, F.text)
async def card_name(message: Message, state: FSMContext):
    value = message.text.strip()
    if not value:
        await message.answer("Напиши желаемое имя ссылки.")
        return
    await state.update_data(preferred_card_name=value)
    if (await state.get_data()).get("return_to_review"):
        await show_review(message, state)
        return
    await state.set_state(Form.name)
    await message.answer(
        progress_text(await state.get_data(), "core") + "Какое имя или название будет показано на визитке?",
        reply_markup=step_back_keyboard("core:name:back"),
    )


@router.callback_query(Form.card_name, F.data == "core:card-name:back")
async def card_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_module_selection(callback.message, state)
    await callback.answer()


async def ask_language(message, state):
    await state.set_state(Form.language)
    data = await state.get_data()
    await message.answer(
        progress_text(data, "core") + "Сколько языков нужно для визитки?\n\n"
        "Один язык: 1200 грн / $29. Два языка: 1700 грн / $39. Два языка нужны, если ты работаешь с аудиторией из разных стран или хочешь отправлять одну ссылку клиентам на разных языках.",
        reply_markup=language_menu(),
    )


@router.message(Form.core_profession, F.text)
async def collect_core_profession(message: Message, state: FSMContext):
    profession = message.text.strip()
    if not profession:
        await message.answer("Напиши, пожалуйста, чем ты занимаешься.")
        return
    await state.update_data(profession=profession)
    await ask_media_choice(message, state)


@router.callback_query(Form.core_profession, F.data == "core:profession:back")
async def core_profession_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.name)
    data = await state.get_data()
    await callback.message.answer(
        progress_text(data, "core") + f"Какое имя или название будет показано на визитке? Сейчас: {escape(data.get('name', 'не указано'))}",
        reply_markup=step_back_keyboard("core:name:back"),
    )
    await callback.answer()


@router.callback_query(Form.language, F.data.startswith("lc:"))
async def choose_language_count(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    elif key == "back":
        if data.get("language_before_core"):
            await state.set_state(Form.entry_mode)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer("Выберите язык интерфейса.", reply_markup=interface_language_keyboard())
            await callback.answer()
            return
        await state.set_state(Form.core_profession)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            progress_text(data, "core") + f"Чем вы занимаетесь? Сейчас: {escape(data.get('profession', 'не указано'))}",
            reply_markup=step_back_keyboard("core:profession:back"),
        )
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
        if data.get("return_to_review"):
            await show_review(callback.message, state)
        elif data.get("language_before_core"):
            await state.update_data(language_before_core=False)
            await start_module_selection(callback.message, state)
        else:
            await ask_media_choice(callback.message, state)
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
            await ask_media_choice(callback.message, state)
    await callback.answer()


@router.message(Form.photo, F.photo)
async def photo(message: Message, state: FSMContext):
    kind = (await state.get_data()).get("image_kind", "Фото")
    await state.update_data(photo_id=message.photo[-1].file_id, image_kind=kind)
    await ask_about(message, state)


@router.callback_query(Form.photo, F.data.startswith("media:"))
async def media_choice(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "back":
        await state.set_state(Form.core_profession)
        data = await state.get_data()
        await callback.message.answer(
            progress_text(data, "core") + f"Чем вы занимаетесь? Сейчас: {escape(data.get('profession', 'не указано'))}",
            reply_markup=step_back_keyboard("core:profession:back"),
        )
    elif action == "none":
        await state.update_data(image_kind="Без изображения", photo_id=None)
        await ask_about(callback.message, state)
    else:
        kind = "Фото" if action == "photo" else "Логотип"
        await state.update_data(image_kind=kind)
        await callback.message.answer(
            progress_text(await state.get_data(), "core") + f"Пришли {kind.lower()} для визитки.",
            reply_markup=step_back_keyboard("core:photo:back"),
        )
    await callback.answer()


@router.message(Form.photo)
async def need_photo(message: Message):
    await message.answer("Выбери вариант кнопкой или прикрепи изображение после выбора фото/логотипа.")


@router.message(Form.color, F.photo)
async def color_photo(message: Message, state: FSMContext):
    await state.update_data(color_photo_id=message.photo[-1].file_id, color_note="Скрин шапки Instagram приложен")
    await ask_about(message, state)


@router.message(Form.color, F.text)
async def color_text(message: Message, state: FSMContext):
    await state.update_data(color_note=message.text.strip())
    await ask_about(message, state)


@router.callback_query(Form.photo, F.data == "core:photo:back")
async def photo_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_media_choice(callback.message, state)
    await callback.answer()


@router.callback_query(Form.color, F.data == "core:color:back")
async def color_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_photo(callback.message, state)
    await callback.answer()


@router.callback_query(Form.about, F.data == "core:about:back")
async def about_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_media_choice(callback.message, state)
    await callback.answer()


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
    if data.get("return_to_review"):
        await show_review(message, state)
    else:
        await continue_after_core(message, state)


@router.message(Form.translation_text, F.text)
async def translation_text(message: Message, state: FSMContext):
    await state.update_data(translation_text=message.text.strip())
    data = await state.get_data()
    if data.get("return_to_review"):
        await show_review(message, state)
    else:
        await continue_after_core(message, state)


@router.callback_query(Form.modules, F.data.startswith("ms:"))
async def select_modules(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected_modules = initial_selected_modules(data.get("selected_modules", ()))
    if key in {SOCIAL_MODULE, CONTACT_MODULE, PRODUCTS_MODULE}:
        selected_modules = toggle_module(selected_modules, key)
        await state.update_data(selected_modules=list(selected_modules))
        await callback.message.edit_reply_markup(reply_markup=module_selection_keyboard(selected_modules))
    elif key == "continue":
        await callback.message.edit_reply_markup(reply_markup=None)
        if data.get("core_complete"):
            await start_next_selected_module(callback.message, state)
        else:
            await start_core_collection(callback.message, state)
    elif key == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        if data.get("module_selection_return_to_review"):
            await state.update_data(module_selection_return_to_review=False)
            await show_review(callback.message, state)
        elif data.get("core_complete"):
            await ask_about(callback.message, state)
        else:
            await state.set_state(Form.entry_mode)
            await callback.message.answer("Выберите удобный способ начать:", reply_markup=entry_mode_keyboard())
    await callback.answer()


@router.callback_query(Form.socials, F.data.startswith("s:"))
async def socials(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("social_keys", [])
    if key == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        if data.get("return_to_review"):
            await show_review(callback.message, state)
        else:
            await start_module_selection(callback.message, state, preserve_completed=True)
        await callback.answer()
        return
    if key == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        if selected:
            values = {k: v for k, v in data.get("social_values", {}).items() if k in selected}
            to_fill = [k for k in selected if k not in values]
            await state.update_data(social_values=values, social_input_keys=to_fill, social_index=0)
            if to_fill:
                await state.set_state(Form.social_link)
                await callback.message.answer(
                    f"Пришли ссылку на <b>{SOCIALS[to_fill[0]]}</b>.",
                    reply_markup=step_back_keyboard("s:back"),
                )
            else:
                await complete_social_module(callback.message, state)
        else:
            await complete_social_module(callback.message, state)
        await callback.answer()
        return
    selected = selected.copy()
    selected.remove(key) if key in selected else selected.append(key)
    await state.update_data(social_keys=selected)
    await callback.message.edit_reply_markup(
        reply_markup=menu(SOCIALS, selected, "s", "Готово ✓", back_callback="s:back")
    )
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
        await message.answer(
            f"Теперь ссылку на <b>{SOCIALS[keys[index]]}</b>.",
            reply_markup=step_back_keyboard("s:back"),
        )
    else:
        await state.update_data(social_values=values)
        await complete_social_module(message, state)


@router.callback_query(Form.social_link, F.data == "s:back")
async def social_link_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    if (await state.get_data()).get("return_to_review"):
        await show_review(callback.message, state)
    else:
        await start_module_selection(callback.message, state, preserve_completed=True)
    await callback.answer()


@router.callback_query(Form.messengers, F.data.startswith("m:"))
async def messengers(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("messenger_keys", [])
    if key == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        if data.get("return_to_review"):
            await show_review(callback.message, state)
        else:
            await start_module_selection(callback.message, state, preserve_completed=True)
        await callback.answer()
        return
    if key == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        if selected:
            values = {k: v for k, v in data.get("messenger_values", {}).items() if k in selected and k != "phone"}
            to_fill = [k for k in selected if k != "phone" and k not in values]
            await state.update_data(
                messenger_values=values,
                messenger_input_keys=to_fill,
                messenger_index=0,
                phone_values=phone_values(data) if "phone" in selected else [],
            )
            if to_fill:
                await ask_current_contact(callback.message, state)
            else:
                await continue_contact_collection(callback.message, state)
        else:
            await complete_contact_module(callback.message, state)
        await callback.answer()
        return
    selected = selected.copy()
    selected.remove(key) if key in selected else selected.append(key)
    await state.update_data(messenger_keys=selected)
    await callback.message.edit_reply_markup(
        reply_markup=menu(MESSENGERS, selected, "m", "Готово ✓", back_callback="m:back")
    )
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
        await ask_current_contact(message, state)
    else:
        await state.update_data(messenger_values=values)
        await continue_contact_collection(message, state)


@router.callback_query(Form.messenger_value, F.data == "m:back")
async def messenger_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    if (await state.get_data()).get("return_to_review"):
        await show_review(callback.message, state)
    else:
        await start_module_selection(callback.message, state, preserve_completed=True)
    await callback.answer()


async def ask_current_contact(message, state):
    data = await state.get_data()
    keys, index = data["messenger_input_keys"], data["messenger_index"]
    key = keys[index]
    if key == "other":
        await state.set_state(Form.other_messenger_name)
        await message.answer(
            "Напиши название мессенджера или другого способа связи. Например: Signal или Discord.",
            reply_markup=step_back_keyboard("other:name:back"),
        )
        return
    await state.set_state(Form.messenger_value)
    await message.answer(contact_prompt(key), reply_markup=step_back_keyboard("m:back"))


@router.message(Form.other_messenger_name, F.text)
async def other_messenger_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Напиши название мессенджера или способа связи.")
        return
    await state.update_data(current_other_messenger_name=name)
    await state.set_state(Form.other_messenger_value)
    await message.answer(
        f"Теперь пришли контакт или ссылку для <b>{escape(name)}</b>.",
        reply_markup=step_back_keyboard("other:value:back"),
    )


@router.callback_query(Form.other_messenger_name, F.data == "other:name:back")
async def other_messenger_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_contacts(callback.message, state)
    await callback.answer()


@router.message(Form.other_messenger_value, F.text)
async def other_messenger_value(message: Message, state: FSMContext):
    value = message.text.strip()
    if not value:
        await message.answer("Пришли контакт или ссылку либо вернись назад.")
        return
    data = await state.get_data()
    keys, index = data["messenger_input_keys"], data["messenger_index"]
    values = dict(data.get("messenger_values", {}))
    values["other"] = {
        "name": data.get("current_other_messenger_name", "Другой контакт"),
        "value": value,
    }
    index += 1
    await state.update_data(
        messenger_values=values,
        messenger_index=index,
        current_other_messenger_name=None,
    )
    if index < len(keys):
        await ask_current_contact(message, state)
    else:
        await continue_contact_collection(message, state)


@router.callback_query(Form.other_messenger_value, F.data == "other:value:back")
async def other_messenger_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.other_messenger_name)
    current = (await state.get_data()).get("current_other_messenger_name", "")
    await callback.message.answer(
        f"Название мессенджера или способа связи (сейчас: {escape(current) or 'не указано'}).",
        reply_markup=step_back_keyboard("other:name:back"),
    )
    await callback.answer()


async def continue_contact_collection(message, state):
    data = await state.get_data()
    if "phone" in data.get("messenger_keys", []):
        await start_phone_collection(message, state)
    elif data.get("return_to_review"):
        await show_review(message, state)
    else:
        await complete_contact_module(message, state)


def phone_keyboard(data):
    count = len(phone_values(data))
    rows = [[InlineKeyboardButton(text=f"＋ {label}", callback_data=f"phone:{key}")] for key, label in PHONE_LABELS.items()]
    rows += [
        [InlineKeyboardButton(text="← Назад", callback_data="phone:back")],
        [InlineKeyboardButton(text="Пропустить", callback_data="phone:skip")],
        [InlineKeyboardButton(text=f"Готово ✓ ({count})", callback_data="phone:done")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def start_phone_collection(message, state):
    data = await state.get_data()
    await state.set_state(Form.phone_label)
    await message.answer(
        progress_text(data, CONTACT_MODULE) + "Добавьте нужные номера телефона. У каждого номера будет понятная подпись.",
        reply_markup=phone_keyboard(data),
    )


@router.callback_query(Form.phone_label, F.data.startswith("phone:"))
async def phone_label(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await start_contacts(callback.message, state)
    elif action == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        await continue_contact_after_phones(callback.message, state)
    elif action == "skip":
        data = await state.get_data()
        if not phone_values(data):
            await state.update_data(phone_values=[])
        await callback.message.edit_reply_markup(reply_markup=None)
        await continue_contact_after_phones(callback.message, state)
    else:
        await state.update_data(current_phone_label=PHONE_LABELS[action])
        await state.set_state(Form.phone_value)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Номер телефона — <b>{PHONE_LABELS[action]}</b>:",
            reply_markup=step_back_keyboard("phone:value:back"),
        )
    await callback.answer()


@router.message(Form.phone_value, F.text)
async def phone_value(message: Message, state: FSMContext):
    number = message.text.strip()
    if not number:
        await message.answer("Напиши номер телефона или вернись назад.")
        return
    data = await state.get_data()
    phones = phone_values(data)
    phones.append({"label": data.get("current_phone_label", "Другой"), "number": number})
    await state.update_data(phone_values=phones, current_phone_label=None)
    await start_phone_collection(message, state)


@router.callback_query(Form.phone_value, F.data == "phone:value:back")
async def phone_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_phone_collection(callback.message, state)
    await callback.answer()


async def continue_contact_after_phones(message, state):
    data = await state.get_data()
    if data.get("return_to_review"):
        await show_review(message, state)
    else:
        await complete_contact_module(message, state)


@router.message(Form.location_city, F.text)
async def location_city(message: Message, state: FSMContext):
    city = message.text.strip()
    if not city:
        await message.answer("Напиши город или пропусти локацию кнопкой.")
        return
    await state.update_data(city=city)
    await state.set_state(Form.location_address)
    await message.answer(
        progress_text(await state.get_data(), LOCATION_MODULE) + "Укажи адрес или место работы. Если не хочешь публиковать точный адрес, пропусти этот шаг.",
        reply_markup=location_address_keyboard(),
    )


@router.callback_query(Form.location_city, F.data.startswith("loc:"))
async def location_city_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "back":
        await start_module_selection(callback.message, state, preserve_completed=True)
    else:
        await state.update_data(city="", workplace_address="")
        await complete_location_module(callback.message, state)
    await callback.answer()


@router.callback_query(Form.location_address, F.data.startswith("loc:address:"))
async def location_address_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.rsplit(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "back":
        await state.set_state(Form.location_city)
        await callback.message.answer("В каком городе вы принимаете клиентов?", reply_markup=location_city_keyboard())
    else:
        await state.update_data(workplace_address="")
        await complete_location_module(callback.message, state)
    await callback.answer()


@router.message(Form.location_address, F.text)
async def location_address(message: Message, state: FSMContext):
    await state.update_data(workplace_address=message.text.strip())
    await complete_location_module(message, state)


def final_comment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Вернуться к проверке", callback_data="comment:back")],
        [InlineKeyboardButton(text="Пропустить и продолжить", callback_data="comment:skip")],
    ])


async def ask_final_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(Form.final_comment)
    await message.answer(
        progress_text(data, "review")
        + "<b>Есть вопрос, комментарий или дополнительная информация?</b>\n\n"
        "Если хотите что-то уточнить или добавить то, для чего не нашли подходящего поля, напишите это одним сообщением. Этот шаг можно пропустить. Информация сохранится вместе с заявкой и не станет отдельным разделом визитки.",
        reply_markup=final_comment_keyboard(),
    )


async def ask_payment_method(message, state):
    await state.set_state(Form.payment_method)
    await message.answer(
        "<b>Выберите удобный способ оплаты</b>\n\n"
        "После проверки заявки мы пришлём реквизиты выбранным способом. Автоматической оплаты в боте нет.",
        reply_markup=payment_method_keyboard(),
    )


async def ask_confirmation(message, state):
    data = await state.get_data()
    await state.set_state(Form.confirmation)
    await message.answer(
        "<b>Подтвердите отправку заявки.</b>\n\n"
        f"Стоимость: <b>{tariff_text(data)}</b>\n"
        f"Способ оплаты: <b>{escape(data.get('payment_method', 'не выбран'))}</b>",
        reply_markup=confirmation_keyboard(),
    )


def application(data, user, client_id=None, application_id=None):
    socials = "\n".join(f"• {SOCIALS.get(k, k)}: {escape(v)}" for k, v in data.get("social_values", {}).items()) or "не выбрано"
    contacts = "\n".join(
        f"• {escape(contact_value_text(k, v))}"
        for k, v in data.get("messenger_values", {}).items()
        if k != "phone"
    ) or "не выбрано"
    phones = "\n".join(f"• {escape(phone['label'])}: {escape(phone['number'])}" for phone in phone_values(data)) or "не указано"
    username = f" (@{user.username})" if user.username else ""
    price = price_info(data)
    payment_method = escape(data.get("payment_method", "не выбран"))
    client_draft = f"Привет, {user.full_name}! Мы проверили заявку и пришлём реквизиты для оплаты {tariff_text(data)}."
    return (
        "<b>НОВАЯ ЗАЯВКА НА ВИЗИТКУ</b>\n\n"
        f"<b>Клиент:</b> {escape(user.full_name)}{username}\n\n"
        f"<b>Client ID:</b> {escape(client_id or 'не создан')}\n"
        f"<b>Application ID:</b> {escape(application_id or 'не создан')}\n\n"
        f"<b>Имя:</b> {escape(data['name'])}\n"
        f"<b>Желаемое имя ссылки:</b> {escape(data.get('preferred_card_name', 'не указано'))}\n"
        f"<b>Язык:</b> {escape(language_names(data))}\n"
        f"<b>Стоимость:</b> {tariff_text(data)}\n"
        f"<b>Способ оплаты:</b> {payment_method}\n\n"
        f"<b>О себе:</b> {escape(data['about'])}\n\n"
        f"<b>Комментарий:</b> {escape(data.get('client_comment', 'не указано'))}\n\n"
        f"<b>Соцсети:</b>\n{socials}\n\n"
        f"<b>Связь:</b>\n{contacts}\n"
        f"<b>Телефоны:</b>\n{phones}\n\n"
        f"<b>Проекты и ссылки:</b> {len(data.get('product_values', []))}\n\n"
        f"<b>Скопируй и отправь клиенту:</b>\n<code>{escape(client_draft)}</code>"
    )


def owner_keyboard(user, data):
    rows = []
    if user.username:
        draft = quote(f"Привет, {user.full_name}! Мы проверили заявку и пришлём реквизиты для оплаты {tariff_text(data)}.")
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
    # Opening Review is not confirmation. This explicit action is.
    data = confirmed_submission_data(await state.get_data())
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
        release_2_services = build_release_2_card_draft_services_from_environment()
        await create_card_draft_from_confirmed_application(
            submission.application,
            services=release_2_services,
        )
    except Exception:
        logging.exception("Could not create Client Data Package, Card and Draft")
        await message.answer(
            "Заявку получили, но данные требуют дополнительной проверки. Мы свяжемся с тобой, чтобы всё уточнить.",
            reply_markup=support_button(),
        )
        await state.clear()
        return True

    try:
        if submission.created:
            if data.get("photo_id"):
                await bot.send_photo(int(OWNER_CHAT_ID), data["photo_id"], caption=f"<b>{escape(data.get('image_kind', 'Изображение'))} к заявке</b>")
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
        text = (
            "<b>Готово, заявку получили.</b>\n\n"
            "Мы получили данные и проверим информацию. Затем пришлём реквизиты для выбранного способа оплаты. "
            "После оплаты подготовим предварительную ссылку на визитку. Вы проверите её, сообщите необходимые правки, подтвердите итог и получите финальную визитку."
        )
    except Exception:
        logging.exception("Could not send application")
        text = "Не получилось передать заявку автоматически. Напиши нам напрямую."
    await message.answer(text, reply_markup=support_button())
    await state.clear()
    return text != "Не получилось передать заявку автоматически. Напиши нам напрямую."


@router.message(Form.final_comment, F.text)
async def final_comment(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(client_comment=message.text.strip())
    await message.answer("Комментарий сохранён.", reply_markup=ReplyKeyboardRemove())
    await ask_payment_method(message, state)


@router.callback_query(Form.final_comment, F.data.startswith("comment:"))
async def final_comment_action(callback: CallbackQuery, state: FSMContext, bot: Bot):
    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "back":
        await show_review(callback.message, state)
    else:
        await ask_payment_method(callback.message, state)
    await callback.answer()


@router.callback_query(Form.payment_method, F.data.startswith("pay:"))
async def payment_method(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "back":
        await ask_final_comment(callback.message, state)
    elif action == "other":
        await state.set_state(Form.payment_method_other)
        await callback.message.answer("Напиши удобный способ оплаты.", reply_markup=step_back_keyboard("pay:other:back"))
    else:
        await state.update_data(payment_method=PAYMENT_METHODS[action])
        await ask_confirmation(callback.message, state)
    await callback.answer()


@router.message(Form.payment_method_other, F.text)
async def payment_method_other(message: Message, state: FSMContext):
    value = message.text.strip()
    await state.update_data(payment_method=value or PAYMENT_METHODS["other"])
    await ask_confirmation(message, state)


@router.callback_query(Form.payment_method_other, F.data == "pay:other:back")
async def payment_method_other_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await ask_payment_method(callback.message, state)
    await callback.answer()


@router.callback_query(Form.confirmation, F.data.startswith("confirm:"))
async def confirmation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "back":
        await ask_payment_method(callback.message, state)
    else:
        await send_application(callback.message, state, bot, callback.from_user)
    await callback.answer()


@router.callback_query(Form.review, F.data.startswith("rv:"))
async def review(callback: CallbackQuery, state: FSMContext, bot: Bot):
    key = callback.data.split(":", 1)[1]
    if key == "send":
        await callback.message.edit_reply_markup(reply_markup=None)
        await ask_final_comment(callback.message, state)
        await callback.answer()
    elif key == "modules":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.update_data(
            module_selection_return_to_review=True,
            return_to_review=False,
        )
        await start_module_selection(callback.message, state, preserve_completed=True)
        await callback.answer()
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
    elif key == "card-name":
        await state.set_state(Form.card_name)
        await state.update_data(return_to_review=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Напиши желаемое имя ссылки.")
    elif key == "photo":
        await state.update_data(return_to_review=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await ask_media_choice(callback.message, state)
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
        await callback.message.answer("Выбери актуальные соцсети. Новые пункты нужно будет заполнить ссылками.", reply_markup=menu(SOCIALS, selected, "s", "Готово ✓", back_callback="s:back"))
    elif key == "messengers":
        data = await state.get_data()
        selected = data.get("messenger_keys", [])
        if phone_values(data) and "phone" not in selected:
            selected = [*selected, "phone"]
        await state.update_data(return_to_review=True)
        await state.set_state(Form.messengers)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Выбери актуальные контакты. Новые пункты нужно будет заполнить.", reply_markup=menu(MESSENGERS, selected, "m", "Готово ✓", back_callback="m:back"))
    elif key == "products":
        await state.update_data(return_to_review=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await start_products(callback.message, state)
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
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
