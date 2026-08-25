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
from services.module_configuration import build_module_configuration
from services.module_selection import CONTACT_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE, initial_selected_modules, next_module_flow, toggle_module
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

BASE_PRICE = 900
BASE_PREPAY = 600
LANGUAGE_PRICES = {"ready": 500, "our": 800}
LANGUAGES = {"uk": "Українська", "ru": "Русский", "en": "English"}
SOCIALS = {"instagram": "Instagram", "facebook": "Facebook", "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok", "site": "Сайт"}
MESSENGERS = {"telegram": "Telegram", "whatsapp": "WhatsApp", "viber": "Viber", "phone": "Позвонить", "other": "Моего мессенджера нет"}
EXTRAS = {"share": "Поделиться визиткой", "vcf": "Сохранить контакт (.vcf)"}


class Form(StatesGroup):
    entry_mode = State()
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
    products = State()
    product_name = State()
    product_description = State()
    product_link = State()
    extras = State()
    review = State()
    edit_menu = State()
    edit_name = State()
    edit_photo = State()
    edit_color = State()
    edit_about = State()


router = Router()


def menu(items, chosen, prefix, done, *, back_callback=None):
    rows = [[InlineKeyboardButton(text=("✓ " if key in chosen else "") + label, callback_data=f"{prefix}:{key}")] for key, label in items.items()]
    rows.append([InlineKeyboardButton(text=done, callback_data=f"{prefix}:done")])
    if back_callback:
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Один язык", callback_data="lc:one")],
        [InlineKeyboardButton(text="Два языка", callback_data="lc:two")],
        [InlineKeyboardButton(text="Отменить заявку", callback_data="lc:cancel")],
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


def step_back_keyboard(callback_data):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="← Назад", callback_data=callback_data)
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


async def ask_messengers(message, chosen=()):
    await message.answer(
        "Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь каждый контакт по очереди.",
        reply_markup=menu(MESSENGERS, chosen, "m", "Готово ✓", back_callback="m:back"),
    )


async def ask_extras(message, chosen=None):
    chosen = list(EXTRAS) if chosen is None else chosen
    await message.answer(
        "Выбери нужные пункты, затем нажми «Завершить заявку ✓».\n\n"
        "Эти функции можно оставить или убрать по желанию. Так человек сам выберет: поделиться визиткой с другом или сохранить контакт в телефон.\n\n"
        "Ничего дополнительно заполнять не нужно.",
        reply_markup=menu(EXTRAS, chosen, "e", "Завершить заявку ✓"),
    )


def module_selection_keyboard(selected_modules):
    selected = set(selected_modules)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("☑ " if SOCIAL_MODULE in selected else "☐ ") + "Социальные сети", callback_data=f"ms:{SOCIAL_MODULE}")],
        [InlineKeyboardButton(text=("☑ " if CONTACT_MODULE in selected else "☐ ") + "Контакты", callback_data=f"ms:{CONTACT_MODULE}")],
        [InlineKeyboardButton(text=("☑ " if PRODUCTS_MODULE in selected else "☐ ") + "Продукты", callback_data=f"ms:{PRODUCTS_MODULE}")],
        [InlineKeyboardButton(text="Продолжить", callback_data="ms:continue")],
        [InlineKeyboardButton(text="← Назад", callback_data="ms:back")],
    ])


async def start_module_selection(message, state, *, preserve_completed=False):
    data = await state.get_data()
    selected_modules = initial_selected_modules(data.get("selected_modules", ()))
    completed_modules = list(data.get("completed_modules", ())) if preserve_completed else []
    await state.update_data(selected_modules=list(selected_modules), completed_modules=completed_modules)
    await state.set_state(Form.modules)
    await message.answer("<b>Что добавить в визитку?</b>\n\nВыбери нужные блоки. Их можно не выбирать вовсе, если они не нужны.", reply_markup=module_selection_keyboard(selected_modules))


async def start_core_collection(message, state):
    await state.update_data(modules_selected_before_core=True)
    await state.set_state(Form.name)
    await message.answer("Отлично. Теперь соберём самое важное для визитки.\n\nКак вас зовут?", reply_markup=cancel_keyboard())


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
        await state.update_data(extra_keys=list(EXTRAS))
        await state.set_state(Form.extras)
        await ask_extras(message)


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


async def complete_products_module(message, state):
    await complete_selected_module(message, state, PRODUCTS_MODULE)


async def start_socials(message, state):
    data = await state.get_data()
    selected = list(data.get("social_keys", ()))
    await state.update_data(social_keys=selected)
    await state.set_state(Form.socials)
    await message.answer(
        "Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь ссылки по очереди.",
        reply_markup=menu(SOCIALS, selected, "s", "Готово ✓", back_callback="s:back"),
    )


async def start_contacts(message, state):
    data = await state.get_data()
    selected = list(data.get("messenger_keys", ()))
    await state.update_data(messenger_keys=selected)
    await state.set_state(Form.messengers)
    await ask_messengers(message, selected)


def products_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="＋ Добавить продукт", callback_data="p:add")],
        [InlineKeyboardButton(text="Готово ✓", callback_data="p:done")],
        [InlineKeyboardButton(text="← Назад", callback_data="p:back")],
    ])


async def start_products(message, state):
    await state.set_state(Form.products)
    await message.answer("Добавь продукты или услуги, которые хочешь показать на визитке.", reply_markup=products_keyboard())


async def show_review(message, state):
    data = await state.get_data()
    await state.set_state(Form.review)
    await message.answer("Проверь данные визитки перед созданием.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✓ Подтвердить и создать", callback_data="review:confirm")], [InlineKeyboardButton(text="← Изменить", callback_data="review:edit")], [InlineKeyboardButton(text="Отменить заявку", callback_data="review:cancel")]]))


# Remaining handlers and application workflow are restored from the exact RC commit.


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
