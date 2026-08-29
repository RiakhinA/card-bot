import asyncio
import logging
import os
from uuid import uuid4
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.parse import urlparse

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
from services.module_configuration import (
    MESSENGER_MODULE,
    build_module_configuration,
    normalize_email_values,
    normalize_messenger_values,
    normalize_phone_values,
)
from services.module_selection import CONTACT_MODULE, LOCATION_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE, initial_selected_modules, next_module_flow, toggle_module
from services.products_collection import ProductValidationError, add_product
from services.pilot_i18n import language_from, t
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
    contacts = State()
    social_link = State()
    other_social_name = State()
    other_social_value = State()
    messengers = State()
    messenger_value = State()
    other_messenger_name = State()
    other_messenger_value = State()
    phone_label = State()
    phone_value = State()
    email_existing_label = State()
    email_new_label = State()
    email_value = State()
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
    edit_profession = State()
    edit_photo = State()
    edit_color = State()
    edit_about = State()
    contact_manage = State()
    contact_item = State()
    contact_delete = State()
    contact_edit_label = State()
    contact_edit_value = State()


router = Router()


def localized_socials(language):
    return {**SOCIALS, "other": t(language, "other_social")} if "other" in SOCIALS else dict(SOCIALS)


def localized_messengers(language):
    return {
        **MESSENGERS,
        "phone": t(language, "phone"),
        "email": t(language, "email"),
        "other": t(language, "other_contact"),
    }


def localized_phone_labels(language):
    return {
        "work": t(language, "phone_work"), "personal": t(language, "phone_personal"),
        "salon": t(language, "phone_salon"), "other": t(language, "phone_other"),
    }


def valid_http_url(value):
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def menu(items, chosen, prefix, done, *, back_callback=None, language="ru"):
    rows = [[InlineKeyboardButton(text=("✓ " if key in chosen else "") + label, callback_data=f"{prefix}:{key}")] for key, label in items.items()]
    if back_callback:
        rows.append([InlineKeyboardButton(text=t(language, "back"), callback_data=back_callback)])
    rows.append([InlineKeyboardButton(text=done, callback_data=f"{prefix}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(language, "one_language"), callback_data="lc:one")],
        [InlineKeyboardButton(text=t(language, "two_languages"), callback_data="lc:two")],
        [InlineKeyboardButton(text=t(language, "back"), callback_data="lc:back")],
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


def language_select_menu(mode, chosen, language="ru"):
    rows = [[InlineKeyboardButton(text=("✓ " if label in chosen else "") + label, callback_data=f"ls:{code}")] for code, label in LANGUAGES.items()]
    confirm = t(language, "confirm_language") if len(chosen) == 1 and mode == "one" else t(language, "confirm_two_languages") if len(chosen) == 2 and mode == "two" else t(language, "choose_language") if mode == "one" else t(language, "choose_two_languages")
    custom = [value for value in chosen if value not in LANGUAGES.values()]
    rows += [
        [InlineKeyboardButton(text=("✓ " + custom[0]) if custom else t(language, "other_language"), callback_data="ls:custom")],
        [InlineKeyboardButton(text=t(language, "back"), callback_data="ls:back")],
    ]
    if mode == "two" or custom:
        rows.append([InlineKeyboardButton(text=confirm, callback_data="ls:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def translation_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пришлю готовый перевод", callback_data="tr:ready")],
        [InlineKeyboardButton(text="Нужна помощь с переводом", callback_data="tr:our")],
        [InlineKeyboardButton(text="← Изменить языки", callback_data="tr:languages")],
        [InlineKeyboardButton(text="Оставить один язык", callback_data="tr:one")],
    ])


def media_keyboard(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(language, "photo"), callback_data="media:photo")],
        [InlineKeyboardButton(text=t(language, "logo"), callback_data="media:logo")],
        [InlineKeyboardButton(text=t(language, "no_image"), callback_data="media:none")],
        [InlineKeyboardButton(text=t(language, "back"), callback_data="media:back")],
    ])


PAYMENT_METHODS = {
    "privatbank": "PrivatBank",
    "paypal": "PayPal",
    "payoneer": "Payoneer",
    "skrill": "Skrill",
    "crypto": "Криптовалюта",
    "other": "Другой способ",
}


def payment_method_keyboard(language="ru"):
    labels = {**PAYMENT_METHODS, "crypto": t(language, "crypto"), "other": t(language, "payment_other")}
    rows = [[InlineKeyboardButton(text=label, callback_data=f"pay:{key}")] for key, label in labels.items()]
    rows.append([InlineKeyboardButton(text=t(language, "back_review"), callback_data="pay:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirmation_keyboard(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(language, "change_payment"), callback_data="confirm:back")],
        [InlineKeyboardButton(text=t(language, "submit"), callback_data="confirm:submit")],
    ])


def support_button(language="ru"):
    draft = quote("Привет, у меня вопрос по визитке: ")
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(language, "support"), url=f"tg://resolve?domain={OWNER_USERNAME}&text={draft}")
    ]])


def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отменить заявку")]], resize_keyboard=True)


def step_back_keyboard(callback_data, language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(language, "back"), callback_data=callback_data)
    ]])


def progress_text(data, section):
    """Small data-driven progress for the current intake flow."""
    language = language_from(data)
    labels = {
        "core": t(language, "core_section"), SOCIAL_MODULE: t(language, "social"),
        MESSENGER_MODULE: "Мессенджеры", CONTACT_MODULE: t(language, "contacts"), PRODUCTS_MODULE: t(language, "projects"),
        LOCATION_MODULE: "Location", "review": t(language, "review_section"),
    }
    selected = initial_selected_modules(data.get("selected_modules", ()))
    sequence = ["core", *(module for module in selected if module != "core"), "review"]
    current = sequence.index(section) + 1 if section in sequence else len(sequence)
    return f"<b>{t(language, 'step', current=current, total=len(sequence))}</b>\n{t(language, 'current_section')}: <b>{labels[section]}</b>\n\n"


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


def email_values(data):
    return normalize_email_values(data)


def contacts_count(data):
    """Count persisted Phone and Email entries, never selected platforms."""
    return len(phone_values(data)) + len(email_values(data))


def new_contact_item_id(kind):
    return f"{kind}-{uuid4().hex[:12]}"


def contact_items(data, kind):
    """Return the C1 repeatable contacts without changing legacy storage."""
    return phone_values(data) if kind == "phone" else email_values(data)


def identified_contact_items(data, kind):
    """Give legacy in-memory entries an ID before a user manages them.

    Historical payloads stay readable; an ID is persisted only when the
    current application snapshot is subsequently saved.
    """
    return [
        item if item.get("id") else {**item, "id": new_contact_item_id(kind)}
        for item in contact_items(data, kind)
    ]


def contact_item_text(kind, item):
    if kind == "phone":
        return f"{item.get('label') or 'Без подписи'}: {item.get('number') or ''}"
    return f"{item.get('label') + ': ' if item.get('label') else ''}{item.get('value') or ''}"


def contact_management_keyboard(kind, items):
    rows = [
        [InlineKeyboardButton(text=contact_item_text(kind, item), callback_data=f"cm:item:{item['id']}")]
        for item in items
    ]
    rows.extend([
        [InlineKeyboardButton(text="＋ Добавить новый", callback_data="cm:add")],
        [InlineKeyboardButton(text="← К контактам", callback_data="cm:back")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contact_item_keyboard(kind, item):
    rows = []
    if kind == "phone" or item.get("label"):
        rows.append([InlineKeyboardButton(text="Изменить подпись", callback_data="ci:label")])
    rows.extend([
        [InlineKeyboardButton(text="Изменить номер" if kind == "phone" else "Изменить Email", callback_data="ci:value")],
        [InlineKeyboardButton(text="Удалить", callback_data="ci:delete")],
        [InlineKeyboardButton(text="← К списку", callback_data="ci:back")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contact_delete_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить", callback_data="cd:yes")],
        [InlineKeyboardButton(text="← Не удалять", callback_data="cd:no")],
    ])


def phones_text(data):
    phones = phone_values(data)
    language = language_from(data)
    reverse_labels = {value: key for key, value in PHONE_LABELS.items()}
    return ", ".join(
        f"{localized_phone_labels(language).get(reverse_labels.get(phone['label']), phone['label'])}: {phone['number']}"
        for phone in phones
    ) or t(language, "not_specified")


def contact_value_text(key, value):
    if key == "other" and isinstance(value, dict):
        name = str(value.get("name") or "Другой контакт").strip()
        contact = str(value.get("value") or "").strip()
        return f"{name}: {contact}" if contact else name
    return f"{MESSENGERS.get(key, key)}: {value}"


def contacts_review_text(data):
    """Render Contacts as Phone and Email only; collection remains unchanged."""
    language = language_from(data)
    rendered = [phones_text(data)] if phone_values(data) else []
    rendered.extend(f"{t(language, 'email')}: {email['value']}" for email in normalize_email_values(data))
    return ", ".join(rendered) or t(language, "not_selected")


def messengers_review_text(data):
    language = language_from(data)
    values = normalize_messenger_values(data)
    rendered = [
        (f"{localized_messengers(language).get(key, key)}: {entry['value']}" if key != "other" else contact_value_text(key, entry))
        for key, entries in values.items()
        for entry in entries
    ]
    return ", ".join(rendered) or t(language, "not_selected")


def projects_review_text(data):
    projects = data.get("product_values", [])
    if not projects:
        return t(language_from(data), "not_added")
    return "\n".join(
        f"• {escape(str(project.get('name') or 'Без названия'))}: {escape(str(project.get('link') or ''))}\n  {escape(str(project.get('description') or ''))}"
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
    language = language_from(await state.get_data())
    await state.set_state(Form.photo)
    await message.answer(
        progress_text(await state.get_data(), "core")
        + t(language, "media_question"),
        reply_markup=media_keyboard(language),
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
    language = language_from(data)
    labels = {"phone": f"{t(language, 'phone')} ({len(phone_values(data))})", "email": f"{t(language, 'email')} ({len(email_values(data))})"}
    await message.answer(
        progress_text(data, CONTACT_MODULE) + t(language, "contacts_prompt"),
        reply_markup=menu(labels, chosen, "m", t(language, "contacts_done", count=contacts_count(data)), back_callback="m:back", language=language),
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
        [InlineKeyboardButton(text=("☑ " if MESSENGER_MODULE in selected else "☐ ") + "Мессенджеры", callback_data=f"ms:{MESSENGER_MODULE}")],
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
    elif next_flow == MESSENGER_MODULE:
        await start_messengers(message, state)
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


async def complete_messenger_module(message, state):
    await complete_selected_module(message, state, MESSENGER_MODULE)


async def complete_location_module(message, state):
    await complete_selected_module(message, state, LOCATION_MODULE)


async def complete_products_module(message, state):
    await complete_selected_module(message, state, PRODUCTS_MODULE)


async def start_socials(message, state):
    data = await state.get_data()
    language = language_from(data)
    selected = list(data.get("social_values", {}).keys())
    await state.update_data(social_keys=selected)
    await state.set_state(Form.socials)
    await message.answer(
        progress_text(data, SOCIAL_MODULE) + t(language, "social_prompt"),
        reply_markup=menu(localized_socials(language), selected, "s", t(language, "done"), back_callback="s:back", language=language),
    )


async def start_contacts(message, state):
    data = await state.get_data()
    selected = [key for key in ("phone", "email") if contact_items(data, key)]
    await state.update_data(contact_keys=selected)
    await state.set_state(Form.contacts)
    await ask_messengers(message, state, selected)


async def start_messengers(message, state):
    data = await state.get_data()
    language = language_from(data)
    values = normalize_messenger_values(data)
    labels = {key: localized_messengers(language)[key] for key in ("telegram", "whatsapp", "viber", "other")}
    selected = [key for key, entries in values.items() if entries]
    await state.update_data(messenger_keys=selected)
    await state.set_state(Form.messengers)
    await message.answer(
        progress_text(data, MESSENGER_MODULE) + "Добавьте нужные мессенджеры.",
        reply_markup=menu(labels, selected, "msg", t(language, "done"), back_callback="msg:back", language=language),
    )


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


def products_keyboard(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="＋ Добавить ещё", callback_data="p:add")],
        [InlineKeyboardButton(text=t(language, "back"), callback_data="p:back")],
        [InlineKeyboardButton(text=t(language, "done"), callback_data="p:done")],
    ])


async def start_products(message, state):
    data = await state.get_data()
    language = language_from(data)
    await state.set_state(Form.products)
    await message.answer(progress_text(data, PRODUCTS_MODULE) + t(language, "projects_prompt"), reply_markup=products_keyboard(language))


@router.callback_query(Form.products, F.data.startswith("p:"))
async def products(callback: CallbackQuery, state: FSMContext):
    language = language_from(await state.get_data())
    key = callback.data.split(":", 1)[1]
    if key == "add":
        await state.update_data(current_product={})
        await state.set_state(Form.product_name)
        await callback.message.answer(t(language, "project_name"), reply_markup=step_back_keyboard("pstep:name:back", language))
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
    language = language_from(await state.get_data())
    value = message.text.strip()
    if not value:
        await message.answer(t(language, "project_name_required"))
        return
    await state.update_data(current_product={"name": value})
    await state.set_state(Form.product_description)
    await message.answer(
        t(language, "project_description"),
        reply_markup=step_back_keyboard("pstep:description:back", language),
    )


@router.message(Form.product_description, F.text)
async def product_description(message: Message, state: FSMContext):
    language = language_from(await state.get_data())
    current = dict((await state.get_data()).get("current_product", {}))
    description = message.text.strip()
    if not description or description == "-":
        await message.answer("Описание проекта обязательно. Напишите его, пожалуйста.")
        return
    current["description"] = description
    await state.update_data(current_product=current)
    await state.set_state(Form.product_link)
    await message.answer(
        t(language, "project_url"),
        reply_markup=step_back_keyboard("pstep:link:back", language),
    )


@router.message(Form.product_link, F.text)
async def product_link(message: Message, state: FSMContext):
    data = await state.get_data()
    current = dict(data.get("current_product", {}))
    link = message.text.strip()
    try:
        products = add_product(data.get("product_values", []), current.get("name", ""), current.get("description", ""), link)
    except ProductValidationError as error:
        language = language_from(data)
        key = "project_url_required" if not link or link == "-" else "project_url_invalid"
        await message.answer(t(language, key))
        return
    await state.update_data(product_values=products, current_product=None)
    await state.set_state(Form.products)
    language = language_from(await state.get_data())
    await message.answer(t(language, "project_added"), reply_markup=products_keyboard(language))


@router.callback_query(Form.product_name, F.data == "pstep:name:back")
async def product_name_back(callback: CallbackQuery, state: FSMContext):
    language = language_from(await state.get_data())
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.products)
    await callback.message.answer(t(language, "projects_prompt"), reply_markup=products_keyboard(language))
    await callback.answer()


@router.callback_query(Form.product_description, F.data == "pstep:description:back")
async def product_description_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    language = language_from(data)
    current = data.get("current_product", {})
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.product_name)
    await callback.message.answer(
        t(language, "project_name") + f" {escape(current.get('name', ''))}",
        reply_markup=step_back_keyboard("pstep:name:back", language),
    )
    await callback.answer()


@router.callback_query(Form.product_link, F.data == "pstep:link:back")
async def product_link_back(callback: CallbackQuery, state: FSMContext):
    current = (await state.get_data()).get("current_product", {})
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.product_description)
    await callback.message.answer(
        f"Описание обязательно (сейчас: {escape(current.get('description', '')) or 'не указано'}). Отправьте новое значение.",
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


def edit_keyboard(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(language, "preferred_link"), callback_data="ed:card-name")],
        [InlineKeyboardButton(text=t(language, "name"), callback_data="ed:name")],
        [InlineKeyboardButton(text=t(language, "profession_label"), callback_data="ed:profession")],
        [InlineKeyboardButton(text=t(language, "card_languages"), callback_data="ed:language")],
        [InlineKeyboardButton(text=t(language, "image"), callback_data="ed:photo")],
        [InlineKeyboardButton(text=t(language, "about_prompt").split("\n", 1)[0], callback_data="ed:about")],
        [InlineKeyboardButton(text=t(language, "social_label"), callback_data="ed:socials")],
        [InlineKeyboardButton(text=t(language, "contacts_label"), callback_data="ed:messengers")],
        [InlineKeyboardButton(text=t(language, "projects_label"), callback_data="ed:products")],
        [InlineKeyboardButton(text=t(language, "back_review"), callback_data="ed:review")],
        [InlineKeyboardButton(text=t(language, "cancel_application"), callback_data="ed:cancel")],
    ])


async def show_review(message, state):
    data = await state.get_data()
    selected_modules, module_configuration = build_module_configuration(data, selected_modules=tuple(data.get("selected_modules", ())))
    await state.update_data(module_configuration=module_configuration)
    socials = ", ".join(SOCIALS.get(k, k) for k in data.get("social_values", {})) or "не выбрано"
    contacts = contacts_review_text(data)
    messengers = messengers_review_text(data)
    products = data.get("product_values", [])
    selected_labels = {"core": "Основная информация", SOCIAL_MODULE: "Социальные сети", MESSENGER_MODULE: "Мессенджеры", CONTACT_MODULE: "Контакты", PRODUCTS_MODULE: "Проекты и ссылки"}
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
        f"<b>Контакты:</b> {contacts}\n"
        f"<b>Мессенджеры:</b> {messengers}\n"
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
            progress_text(data, "core") + t(language_from(data), "profession"),
            reply_markup=step_back_keyboard("core:profession:back", language_from(data)),
        )
        return
    await ask_media_choice(message, state)


@router.message(Form.card_name, F.text)
async def card_name(message: Message, state: FSMContext):
    language = language_from(await state.get_data())
    value = message.text.strip()
    if not value:
        await message.answer(t(language, "link_prompt"))
        return
    await state.update_data(preferred_card_name=value)
    if (await state.get_data()).get("return_to_review"):
        await show_review(message, state)
        return
    await state.set_state(Form.name)
    await message.answer(
        progress_text(await state.get_data(), "core") + t(language, "core_name"),
        reply_markup=step_back_keyboard("core:name:back", language),
    )


@router.callback_query(Form.card_name, F.data == "core:card-name:back")
async def card_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_module_selection(callback.message, state)
    await callback.answer()


async def ask_language(message, state):
    await state.set_state(Form.language)
    data = await state.get_data()
    language = language_from(data)
    await message.answer(
        f"<b>{t(language, 'step', current=1, total=2)}</b>\n\n" + t(language, "card_language_count"),
        reply_markup=language_menu(language),
    )


@router.message(Form.core_profession, F.text)
async def collect_core_profession(message: Message, state: FSMContext):
    profession = message.text.strip()
    if not profession:
        await message.answer(t(language_from(await state.get_data()), "profession_required"))
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
    language = language_from(data)
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "cancelled"), reply_markup=ReplyKeyboardRemove())
    elif key == "back":
        if data.get("language_before_core"):
            await state.set_state(Form.entry_mode)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(t(language, "interface_language"), reply_markup=interface_language_keyboard())
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
        intro = t(language, "choose_card_language") if mode == "one" else t(language, "choose_two_card_languages")
        await callback.message.answer(intro, reply_markup=language_select_menu(mode, [], language))
    await callback.answer()


@router.callback_query(Form.language_select, F.data.startswith("ls:"))
async def choose_language(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    language = language_from(data)
    mode = data.get("language_mode", "one")
    selected = data.get("language_values", [])
    if key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "cancelled"), reply_markup=ReplyKeyboardRemove())
    elif key == "back":
        await state.update_data(language_values=[], translation_mode=None)
        await state.set_state(Form.language)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "card_language_count"), reply_markup=language_menu(language))
    elif key == "custom":
        if len(selected) >= (1 if mode == "one" else 2):
            await callback.answer("Сначала убери выбранный язык.", show_alert=True)
            return
        await state.set_state(Form.custom_language)
        await callback.message.answer(t(language, "custom_language_prompt"))
    elif key == "done":
        need = 1 if mode == "one" else 2
        if len(selected) != need:
            await callback.answer(t(language, "select_exact_languages"), show_alert=True)
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
        if mode == "one":
            await state.update_data(language_values=[label])
            await callback.message.edit_reply_markup(reply_markup=None)
            if data.get("return_to_review"):
                await show_review(callback.message, state)
            elif data.get("language_before_core"):
                await state.update_data(language_before_core=False)
                await start_module_selection(callback.message, state)
            else:
                await ask_media_choice(callback.message, state)
            await callback.answer()
            return
        selected = selected.copy()
        if label in selected:
            selected.remove(label)
        elif len(selected) < (1 if mode == "one" else 2):
            selected.append(label)
        else:
            await callback.answer("Сначала убери выбранный язык.", show_alert=True)
            return
        await state.update_data(language_values=selected)
        await callback.message.edit_reply_markup(reply_markup=language_select_menu(mode, selected, language))
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
    language = language_from(data)
    await message.answer(t(language, "custom_language_added"), reply_markup=language_select_menu(mode, selected, language))


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
        await callback.message.answer(t(language, "card_language_count"), reply_markup=language_menu(language))
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
    data = await state.get_data()
    kind = data.get("image_kind", "Фото")
    await state.update_data(photo_id=message.photo[-1].file_id, image_kind=kind)
    if data.get("editing_photo"):
        await state.update_data(editing_photo=False)
        await show_review(message, state)
        return
    await ask_about(message, state)


@router.callback_query(Form.photo, F.data.startswith("media:"))
async def media_choice(callback: CallbackQuery, state: FSMContext):
    language = language_from(await state.get_data())
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
        if (await state.get_data()).get("editing_photo"):
            await state.update_data(editing_photo=False)
            await show_review(callback.message, state)
            await callback.answer()
            return
        await ask_about(callback.message, state)
    else:
        kind = "Фото" if action == "photo" else "Логотип"
        await state.update_data(image_kind=kind)
        await callback.message.answer(
            progress_text(await state.get_data(), "core") + t(language, "send_media", kind=t(language, action)),
            reply_markup=step_back_keyboard("core:photo:back", language),
        )
    await callback.answer()


@router.message(Form.photo)
async def need_photo(message: Message, state: FSMContext):
    await message.answer(t(language_from(await state.get_data()), "media_required"))


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
    if key in {SOCIAL_MODULE, MESSENGER_MODULE, CONTACT_MODULE, PRODUCTS_MODULE}:
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
    language = language_from(data)
    selected = list(data.get("social_values", {}).keys())
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
        await complete_social_module(callback.message, state)
        await callback.answer()
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    if key == "other":
        await state.set_state(Form.other_social_name)
        await callback.message.answer("Напишите название социальной сети.", reply_markup=step_back_keyboard("social:name:back", language))
    else:
        await state.update_data(current_social_key=key)
        await state.set_state(Form.social_link)
        await callback.message.answer(t(language, "send_social", name=localized_socials(language)[key]), reply_markup=step_back_keyboard("s:back", language))
    await callback.answer()


@router.message(Form.social_link, F.text)
async def social_link(message: Message, state: FSMContext):
    data = await state.get_data()
    language = language_from(data)
    value = message.text.strip()
    if not valid_http_url(value):
        await message.answer(t(language, "project_url_invalid"))
        return
    values = dict(data.get("social_values", {}))
    values[data["current_social_key"]] = value
    await state.update_data(social_values=values, current_social_key=None)
    await start_socials(message, state)


@router.callback_query(Form.social_link, F.data == "s:back")
async def social_link_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_socials(callback.message, state)
    await callback.answer()


@router.message(Form.other_social_name, F.text)
async def other_social_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Название социальной сети обязательно.")
        return
    await state.update_data(current_other_social_name=name)
    await state.set_state(Form.other_social_value)
    await message.answer(f"Пришлите ссылку для <b>{escape(name)}</b>.", reply_markup=step_back_keyboard("social:value:back"))


@router.callback_query(Form.other_social_name, F.data == "social:name:back")
async def other_social_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_socials(callback.message, state)
    await callback.answer()


@router.message(Form.other_social_value, F.text)
async def other_social_value(message: Message, state: FSMContext):
    data = await state.get_data()
    value = message.text.strip()
    if not valid_http_url(value):
        await message.answer(t(language_from(data), "project_url_invalid"))
        return
    values = dict(data.get("social_values", {}))
    values["other"] = {"name": data["current_other_social_name"], "value": value}
    await state.update_data(social_values=values, current_other_social_name=None)
    await start_socials(message, state)


@router.callback_query(Form.other_social_value, F.data == "social:value:back")
async def other_social_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.other_social_name)
    await callback.message.answer("Напишите название социальной сети.", reply_markup=step_back_keyboard("social:name:back"))
    await callback.answer()


@router.callback_query(Form.contacts, F.data.startswith("m:"))
async def messengers(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    language = language_from(data)
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
        await complete_contact_module(callback.message, state)
        await callback.answer()
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    if key == "phone":
        await state.update_data(phone_values=phone_values(data))
        if phone_values(data):
            await start_contact_management(callback.message, state, "phone")
        else:
            await start_phone_collection(callback.message, state)
    elif key == "email":
        if email_values(data):
            await start_contact_management(callback.message, state, "email")
        else:
            await start_email_collection(callback.message, state)
    await callback.answer()


@router.callback_query(Form.messengers, F.data.startswith("msg:"))
async def messenger_menu(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    language = language_from(data)
    await callback.message.edit_reply_markup(reply_markup=None)
    if key == "back":
        if data.get("return_to_review"):
            await show_review(callback.message, state)
        else:
            await start_module_selection(callback.message, state, preserve_completed=True)
    elif key == "done":
        await complete_messenger_module(callback.message, state)
    elif key == "other":
        await state.update_data(messenger_source="separate")
        await state.set_state(Form.other_messenger_name)
        await callback.message.answer(t(language, "other_name"), reply_markup=step_back_keyboard("msg:back", language))
    else:
        await state.update_data(current_messenger_key=key, messenger_source="separate")
        await state.set_state(Form.messenger_value)
        await callback.message.answer(t(language, "send_contact", name=localized_messengers(language)[key]), reply_markup=step_back_keyboard("msg:back", language))
    await callback.answer()


@router.message(Form.messenger_value, F.text)
async def messenger_value(message: Message, state: FSMContext):
    data = await state.get_data()
    value = message.text.strip()
    if not value:
        await message.answer("Контакт не может быть пустым.")
        return
    values = dict(data.get("messenger_values", {}))
    values[data["current_messenger_key"]] = value
    await state.update_data(messenger_values=values, current_messenger_key=None)
    if data.get("messenger_source") == "separate":
        await start_messengers(message, state)
    else:
        await start_contacts(message, state)


@router.callback_query(Form.messenger_value, F.data.startswith("m:"))
@router.callback_query(Form.messenger_value, F.data.startswith("msg:"))
async def messenger_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    if (await state.get_data()).get("messenger_source") == "separate":
        await start_messengers(callback.message, state)
    else:
        await start_contacts(callback.message, state)
    await callback.answer()


async def ask_current_contact(message, state):
    data = await state.get_data()
    language = language_from(data)
    keys, index = data["messenger_input_keys"], data["messenger_index"]
    key = keys[index]
    if key == "other":
        await state.set_state(Form.other_messenger_name)
        await message.answer(
            t(language, "other_name"),
            reply_markup=step_back_keyboard("other:name:back", language),
        )
        return
    await state.set_state(Form.messenger_value)
    await message.answer(t(language, "send_contact", name=localized_messengers(language)[key]), reply_markup=step_back_keyboard("m:back", language))


@router.message(Form.other_messenger_name, F.text)
async def other_messenger_name(message: Message, state: FSMContext):
    language = language_from(await state.get_data())
    name = message.text.strip()
    if not name:
        await message.answer(t(language, "other_name_required"))
        return
    await state.update_data(current_other_messenger_name=name)
    await state.set_state(Form.other_messenger_value)
    await message.answer(
        t(language, "other_value", name=escape(name)),
        reply_markup=step_back_keyboard("other:value:back", language),
    )


@router.callback_query(Form.other_messenger_name, F.data == "other:name:back")
@router.callback_query(Form.other_messenger_name, F.data == "msg:back")
async def other_messenger_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    if (await state.get_data()).get("messenger_source") == "separate":
        await start_messengers(callback.message, state)
    else:
        await start_contacts(callback.message, state)
    await callback.answer()


@router.message(Form.other_messenger_value, F.text)
async def other_messenger_value(message: Message, state: FSMContext):
    language = language_from(await state.get_data())
    value = message.text.strip()
    if not value:
        await message.answer(t(language, "other_value_required"))
        return
    data = await state.get_data()
    values = dict(data.get("messenger_values", {}))
    values["other"] = {
        "name": data.get("current_other_messenger_name", "Другой контакт"),
        "value": value,
    }
    await state.update_data(
        messenger_values=values,
        current_other_messenger_name=None,
    )
    if data.get("messenger_source") == "separate":
        await start_messengers(message, state)
    else:
        await start_contacts(message, state)


@router.callback_query(Form.other_messenger_value, F.data == "other:value:back")
async def other_messenger_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(Form.other_messenger_name)
    current = (await state.get_data()).get("current_other_messenger_name", "")
    language = language_from(await state.get_data())
    await callback.message.answer(
        t(language, "other_name") + f" ({escape(current) or t(language, 'not_specified')})",
        reply_markup=step_back_keyboard("other:name:back", language),
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


async def start_phone_collection(message, state):
    data = await state.get_data()
    language = language_from(data)
    await state.set_state(Form.phone_label)
    await message.answer(
        progress_text(data, CONTACT_MODULE) + t(language, "phone_label_prompt"),
        reply_markup=step_back_keyboard("phone:label:back", language),
    )


async def start_contact_management(message, state, kind):
    data = await state.get_data()
    items = identified_contact_items(data, kind)
    if items != contact_items(data, kind):
        await state.update_data(**({"phone_values": items} if kind == "phone" else {"email_values": items}))
    await state.update_data(manage_contact_kind=kind, managed_contact_id=None)
    await state.set_state(Form.contact_manage)
    title = "номеров телефона" if kind == "phone" else "Email"
    await message.answer(
        f"Сохранённые {title}. Выберите запись для изменения или добавьте новую.",
        reply_markup=contact_management_keyboard(kind, items),
    )


def managed_contact(data):
    kind = data.get("manage_contact_kind")
    item_id = data.get("managed_contact_id")
    for item in contact_items(data, kind):
        if item.get("id") == item_id:
            return item
    return None


async def show_contact_item(message, state):
    data = await state.get_data()
    kind = data.get("manage_contact_kind")
    item = managed_contact(data)
    if not item:
        await start_contact_management(message, state, kind)
        return
    await state.set_state(Form.contact_item)
    await message.answer(contact_item_text(kind, item), reply_markup=contact_item_keyboard(kind, item))


@router.callback_query(Form.contact_manage, F.data.startswith("cm:"))
async def contact_manage(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 2)[1]
    data = await state.get_data()
    kind = data.get("manage_contact_kind")
    await callback.message.edit_reply_markup(reply_markup=None)
    if action == "add":
        if kind == "phone":
            await start_phone_collection(callback.message, state)
        else:
            await start_email_collection(callback.message, state)
    elif action == "back":
        await start_contacts(callback.message, state)
    elif action == "item":
        item_id = callback.data.rsplit(":", 1)[1]
        if any(item.get("id") == item_id for item in contact_items(data, kind)):
            await state.update_data(managed_contact_id=item_id)
            await show_contact_item(callback.message, state)
        else:
            await start_contact_management(callback.message, state, kind)
    await callback.answer()


@router.callback_query(Form.contact_item, F.data.startswith("ci:"))
async def contact_item_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    kind = data.get("manage_contact_kind")
    item = managed_contact(data)
    await callback.message.edit_reply_markup(reply_markup=None)
    if not item:
        await start_contact_management(callback.message, state, kind)
    elif action == "back":
        await start_contact_management(callback.message, state, kind)
    elif action == "delete":
        await state.set_state(Form.contact_delete)
        await callback.message.answer(f"Удалить «{escape(contact_item_text(kind, item))}»?", reply_markup=contact_delete_keyboard())
    elif action == "label":
        await state.set_state(Form.contact_edit_label)
        await callback.message.answer("Напишите новую подпись.", reply_markup=step_back_keyboard("ci:back"))
    elif action == "value":
        await state.set_state(Form.contact_edit_value)
        prompt = "Напишите новый номер." if kind == "phone" else "Напишите новый Email."
        await callback.message.answer(prompt, reply_markup=step_back_keyboard("ci:back"))
    await callback.answer()


@router.callback_query(Form.contact_delete, F.data.startswith("cd:"))
async def contact_delete(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kind = data.get("manage_contact_kind")
    if callback.data == "cd:yes":
        item_id = data.get("managed_contact_id")
        items = [item for item in contact_items(data, kind) if item.get("id") != item_id]
        await state.update_data(**({"phone_values": items} if kind == "phone" else {"email_values": items}))
        await callback.message.edit_reply_markup(reply_markup=None)
        await start_contact_management(callback.message, state, kind)
    else:
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_contact_item(callback.message, state)
    await callback.answer()


@router.callback_query(Form.contact_edit_label, F.data == "ci:back")
@router.callback_query(Form.contact_edit_value, F.data == "ci:back")
async def contact_edit_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_contact_item(callback.message, state)
    await callback.answer()


@router.message(Form.contact_edit_label, F.text)
async def contact_edit_label(message: Message, state: FSMContext):
    label = message.text.strip()
    if not label:
        await message.answer("Подпись обязательна.")
        return
    data = await state.get_data()
    kind, item_id = data.get("manage_contact_kind"), data.get("managed_contact_id")
    items = [{**item, "label": label} if item.get("id") == item_id else item for item in contact_items(data, kind)]
    await state.update_data(**({"phone_values": items} if kind == "phone" else {"email_values": items}))
    await start_contact_management(message, state, kind)


@router.message(Form.contact_edit_value, F.text)
async def contact_edit_value(message: Message, state: FSMContext):
    value = message.text.strip()
    if not value:
        await message.answer("Значение обязательно.")
        return
    data = await state.get_data()
    kind, item_id = data.get("manage_contact_kind"), data.get("managed_contact_id")
    field = "number" if kind == "phone" else "value"
    items = [{**item, field: value} if item.get("id") == item_id else item for item in contact_items(data, kind)]
    await state.update_data(**({"phone_values": items} if kind == "phone" else {"email_values": items}))
    await start_contact_management(message, state, kind)


@router.message(Form.phone_label, F.text)
async def phone_label(message: Message, state: FSMContext):
    label = message.text.strip()
    language = language_from(await state.get_data())
    if not label:
        await message.answer(t(language, "phone_label_required"))
        return
    await state.update_data(current_phone_label=label)
    await state.set_state(Form.phone_value)
    await message.answer(
        t(language, "phone_value", label=escape(label)),
        reply_markup=step_back_keyboard("phone:value:back", language),
    )


@router.callback_query(Form.phone_label, F.data == "phone:label:back")
async def phone_label_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_contacts(callback.message, state)
    await callback.answer()


@router.message(Form.phone_value, F.text)
async def phone_value(message: Message, state: FSMContext):
    number = message.text.strip()
    if not number:
        await message.answer(t(language_from(await state.get_data()), "phone_required"))
        return
    data = await state.get_data()
    phones = phone_values(data)
    phones.append({
        "id": new_contact_item_id("phone"),
        "label": data.get("current_phone_label", ""),
        "number": number,
    })
    await state.update_data(phone_values=phones, current_phone_label=None)
    await start_contacts(message, state)


@router.callback_query(Form.phone_value, F.data == "phone:value:back")
async def phone_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_phone_collection(callback.message, state)
    await callback.answer()


async def start_email_collection(message, state):
    data = await state.get_data()
    language = language_from(data)
    emails = email_values(data)
    if not emails:
        await state.update_data(current_email_label=None, email_mode="first")
        await state.set_state(Form.email_value)
        await message.answer(t(language, "email_value_prompt"), reply_markup=step_back_keyboard("email:value:back", language))
        return
    unlabeled_index = next((index for index, email in enumerate(emails) if not str(email.get("label") or "").strip()), None)
    if unlabeled_index is not None:
        await state.update_data(email_values=emails, pending_existing_email_index=unlabeled_index, email_mode="repeatable")
        await state.set_state(Form.email_existing_label)
        await message.answer(
            t(language, "email_existing_label_prompt", value=escape(emails[unlabeled_index]["value"])),
            reply_markup=step_back_keyboard("email:existing-label:back", language),
        )
        return
    await state.update_data(current_email_label=None, email_mode="repeatable")
    await state.set_state(Form.email_new_label)
    await message.answer(t(language, "email_new_label_prompt"), reply_markup=step_back_keyboard("email:new-label:back", language))


@router.message(Form.email_existing_label, F.text)
async def email_existing_label(message: Message, state: FSMContext):
    label = message.text.strip()
    language = language_from(await state.get_data())
    if not label:
        await message.answer(t(language, "email_label_required"))
        return
    data = await state.get_data()
    emails = email_values(data)
    index = data.get("pending_existing_email_index", 0)
    emails[index] = {**emails[index], "label": label}
    await state.update_data(email_values=emails, pending_existing_email_index=None)
    await state.set_state(Form.email_new_label)
    await message.answer(t(language, "email_new_label_prompt"), reply_markup=step_back_keyboard("email:new-label:back", language))


@router.callback_query(Form.email_existing_label, F.data == "email:existing-label:back")
async def email_existing_label_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_contacts(callback.message, state)
    await callback.answer()


@router.message(Form.email_new_label, F.text)
async def email_new_label(message: Message, state: FSMContext):
    label = message.text.strip()
    language = language_from(await state.get_data())
    if not label:
        await message.answer(t(language, "email_label_required"))
        return
    await state.update_data(current_email_label=label)
    await state.set_state(Form.email_value)
    await message.answer(t(language, "email_value_prompt"), reply_markup=step_back_keyboard("email:value:back", language))


@router.callback_query(Form.email_new_label, F.data == "email:new-label:back")
async def email_new_label_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_contacts(callback.message, state)
    await callback.answer()


@router.message(Form.email_value, F.text)
async def email_value(message: Message, state: FSMContext):
    value = message.text.strip()
    language = language_from(await state.get_data())
    if not value:
        await message.answer(t(language, "email_required"))
        return
    data = await state.get_data()
    email = {"id": new_contact_item_id("email"), "value": value}
    if data.get("current_email_label"):
        email["label"] = data["current_email_label"]
    emails = email_values(data)
    emails.append(email)
    await state.update_data(email_values=emails, current_email_label=None, email_mode=None)
    await start_contacts(message, state)


@router.callback_query(Form.email_value, F.data == "email:value:back")
async def email_value_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    if (await state.get_data()).get("email_mode") == "repeatable":
        await state.set_state(Form.email_new_label)
        language = language_from(await state.get_data())
        await callback.message.answer(t(language, "email_new_label_prompt"), reply_markup=step_back_keyboard("email:new-label:back", language))
    else:
        await start_contacts(callback.message, state)
    await callback.answer()


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


def final_comment_keyboard(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(language, "back_review"), callback_data="comment:back")],
        [InlineKeyboardButton(text=t(language, "skip_continue"), callback_data="comment:skip")],
    ])


async def ask_final_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    language = language_from(data)
    await state.set_state(Form.final_comment)
    await message.answer(
        progress_text(data, "review") + t(language, "final_comment"),
        reply_markup=final_comment_keyboard(language),
    )


async def ask_payment_method(message, state):
    language = language_from(await state.get_data())
    await state.set_state(Form.payment_method)
    await message.answer(
        "После проверки заявки я пришлю реквизиты для оплаты.\n\n"
        "Способы оплаты:\n• PrivatBank\n• PayPal\n• Payoneer\n• Skrill\n• Криптовалюта\n• Другой способ\n\n"
        "После оплаты мы создадим первый вариант визитки и пришлём его вам на согласование.",
        reply_markup=payment_method_keyboard(language),
    )


async def ask_confirmation(message, state):
    data = await state.get_data()
    language = language_from(data)
    await state.set_state(Form.confirmation)
    await message.answer(
        t(language, "confirmation", tariff=tariff_text(data), method=escape(data.get('payment_method') or t(language, 'not_selected'))),
        reply_markup=confirmation_keyboard(language),
    )


def application(data, user, client_id=None, application_id=None):
    socials = "\n".join(
        f"• {escape(str(v.get('name', SOCIALS.get(k, k))))}: {escape(str(v.get('value', '')))}"
        if isinstance(v, dict) else f"• {SOCIALS.get(k, k)}: {escape(str(v))}"
        for k, v in data.get("social_values", {}).items()
    ) or "не выбрано"
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
        f"<b>Проекты и ссылки:</b>\n{projects_review_text(data)}\n\n"
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
    language = language_from(data)
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
        await message.answer(t(language, "persistence_error"), reply_markup=support_button(language))
        return False

    try:
        release_2_services = build_release_2_card_draft_services_from_environment()
        await create_card_draft_from_confirmed_application(
            submission.application,
            services=release_2_services,
        )
    except Exception:
        logging.exception("Could not create Client Data Package, Card and Draft")
        await message.answer(t(language, "draft_error"), reply_markup=support_button(language))
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
        text = t(language, "success")
    except Exception:
        logging.exception("Could not send application")
        text = t(language, "persistence_error")
    await message.answer(text, reply_markup=support_button(language))
    await state.clear()
    return text != t(language, "persistence_error")


@router.message(Form.final_comment, F.text)
async def final_comment(message: Message, state: FSMContext, bot: Bot):
    language = language_from(await state.get_data())
    await state.update_data(client_comment=message.text.strip())
    await message.answer(t(language, "comment_saved"), reply_markup=ReplyKeyboardRemove())
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
        language = language_from(await state.get_data())
        await state.set_state(Form.payment_method_other)
        await callback.message.answer(t(language, "payment_other_prompt"), reply_markup=step_back_keyboard("pay:other:back", language))
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
    language = language_from(await state.get_data())
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
        await callback.message.answer(t(language, "edit_prompt"), reply_markup=edit_keyboard(language))
        await callback.answer()
    else:
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "cancelled"), reply_markup=ReplyKeyboardRemove())
        await callback.answer()


@router.callback_query(Form.edit_menu, F.data.startswith("ed:"))
async def edit(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    language = language_from(await state.get_data())
    if key == "review":
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_review(callback.message, state)
    elif key == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "cancelled"), reply_markup=ReplyKeyboardRemove())
    elif key == "name":
        await state.set_state(Form.edit_name)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "core_name"))
    elif key == "profession":
        await state.set_state(Form.edit_profession)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "profession"))
    elif key == "card-name":
        await state.set_state(Form.card_name)
        await state.update_data(return_to_review=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "link_prompt"))
    elif key == "photo":
        await state.update_data(return_to_review=True, editing_photo=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await ask_media_choice(callback.message, state)
    elif key == "color":
        await state.set_state(Form.edit_color)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Пришли новый скрин шапки Instagram или напиши цвет словами.")
    elif key == "about":
        await state.set_state(Form.edit_about)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "about_prompt"))
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
        await callback.message.answer(t(language, "social_prompt"), reply_markup=menu(localized_socials(language), selected, "s", t(language, "done"), back_callback="s:back", language=language))
    elif key == "messengers":
        await state.update_data(return_to_review=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        await start_contacts(callback.message, state)
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


@router.message(Form.edit_profession, F.text)
async def edit_profession(message: Message, state: FSMContext):
    profession = message.text.strip()
    if not profession:
        await message.answer(t(language_from(await state.get_data()), "profession_required"))
        return
    await state.update_data(profession=profession)
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
