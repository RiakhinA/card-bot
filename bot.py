import asyncio
import logging
import os
from pathlib import Path

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
PRICE = os.getenv("PRICE", "2500 грн")
PREPAY = os.getenv("PREPAY", "1250 грн")
ASSETS = Path(__file__).parent / "assets"

SOCIALS = {"instagram": "Instagram", "facebook": "Facebook", "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok", "site": "Сайт"}
MESSENGERS = {"telegram": "Telegram", "whatsapp": "WhatsApp", "viber": "Viber", "phone": "Позвонить"}
EXTRAS = {"share": "Поделиться визиткой", "vcf": "Сохранить контакт (.vcf)", "language": "Второй язык", "qr": "QR-код"}

class Form(StatesGroup):
    photo = State()
    name = State()
    about = State()
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

def write_anton():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Написать Антону", url=f"https://t.me/{OWNER_USERNAME}")
    ]])

async def examples(message):
    paths = [ASSETS / x for x in ("01-anton.png", "02-male.png", "03-female.png", "04-builder.png")]
    if all(p.exists() for p in paths):
        await message.answer_media_group([InputMediaPhoto(media=FSInputFile(p)) for p in paths])
    else:
        await message.answer("Примеры визиток пока загружаются. Антон пришлёт их отдельно.")

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await examples(message)
    await message.answer(
        "<b>Привет!</b> Я помогу собрать данные для минималистичной онлайн-визитки.\n\n"
        "Это небольшая страница с самым важным о тебе: её можно поставить в Instagram, отправлять клиентам ссылкой или добавить в QR-код.\n\n"
        f"Базовая визитка — <b>от {PRICE}</b>. Антон подтвердит точный состав и стоимость после просмотра материалов.\n\n"
        "Начнём: пришли одно фото для визитки.", reply_markup=write_anton())
    await state.set_state(Form.photo)

@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Сбор данных отменён. Когда будешь готов, отправь /start.")

@router.message(Form.photo, F.photo)
async def photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(Form.name)
    await message.answer("Фото получил. Как тебя зовут и чем занимаешься?\n\nНапример: «Марина, бровист».")

@router.message(Form.photo)
async def need_photo(message: Message):
    await message.answer("Прикрепи, пожалуйста, именно фотографию.")

@router.message(Form.name, F.text)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.about)
    await message.answer("Коротко расскажи о себе: чем полезен людям или с каким запросом к тебе приходят. Достаточно 1–3 предложений.")

@router.message(Form.about, F.text)
async def about(message: Message, state: FSMContext):
    await state.update_data(about=message.text.strip(), social_keys=[])
    await state.set_state(Form.socials)
    await message.answer("Выбери соцсети или сайт. Можно выбрать несколько, затем нажми «Готово».", reply_markup=menu(SOCIALS, [], "s", "Готово →"))

async def contacts_menu(callback, state):
    await state.update_data(messenger_keys=[])
    await state.set_state(Form.messengers)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Выбери способы связи. Можно выбрать несколько, затем нажми «Готово».", reply_markup=menu(MESSENGERS, [], "m", "Готово →"))

@router.callback_query(Form.socials, F.data.startswith("s:"))
async def socials(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data(); selected = data.get("social_keys", [])
    if key == "done":
        if not selected:
            await contacts_menu(callback, state)
        else:
            await state.update_data(social_values={}, social_index=0)
            await state.set_state(Form.social_link)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"Пришли ссылку на <b>{SOCIALS[selected[0]]}</b>.")
        await callback.answer(); return
    selected = selected.copy()
    selected.remove(key) if key in selected else selected.append(key)
    await state.update_data(social_keys=selected)
    await callback.message.edit_reply_markup(reply_markup=menu(SOCIALS, selected, "s", "Готово →"))
    await callback.answer()

@router.message(Form.social_link, F.text)
async def social_link(message: Message, state: FSMContext):
    data = await state.get_data(); keys = data["social_keys"]; index = data["social_index"]
    values = data["social_values"]; values[keys[index]] = message.text.strip(); index += 1
    if index < len(keys):
        await state.update_data(social_values=values, social_index=index)
        await message.answer(f"Теперь ссылку на <b>{SOCIALS[keys[index]]}</b>.")
    else:
        await state.update_data(social_values=values)
        class Dummy: pass
        await state.update_data(messenger_keys=[])
        await state.set_state(Form.messengers)
        await message.answer("Выбери способы связи. Можно выбрать несколько, затем нажми «Готово».", reply_markup=menu(MESSENGERS, [], "m", "Готово →"))

async def extras_menu(callback, state):
    await state.update_data(extra_keys=[])
    await state.set_state(Form.extras)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Что добавить дополнительно? Выбери нужное или сразу нажми «Завершить заявку».", reply_markup=menu(EXTRAS, [], "e", "Завершить заявку →"))

@router.callback_query(Form.messengers, F.data.startswith("m:"))
async def messengers(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data(); selected = data.get("messenger_keys", [])
    if key == "done":
        if not selected:
            await extras_menu(callback, state)
        else:
            await state.update_data(messenger_values={}, messenger_index=0)
            await state.set_state(Form.messenger_value)
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(f"Пришли контакт для <b>{MESSENGERS[selected[0]]}</b>.")
        await callback.answer(); return
    selected = selected.copy()
    selected.remove(key) if key in selected else selected.append(key)
    await state.update_data(messenger_keys=selected)
    await callback.message.edit_reply_markup(reply_markup=menu(MESSENGERS, selected, "m", "Готово →"))
    await callback.answer()

@router.message(Form.messenger_value, F.text)
async def messenger_value(message: Message, state: FSMContext):
    data = await state.get_data(); keys = data["messenger_keys"]; index = data["messenger_index"]
    values = data["messenger_values"]; values[keys[index]] = message.text.strip(); index += 1
    if index < len(keys):
        await state.update_data(messenger_values=values, messenger_index=index)
        await message.answer(f"Теперь контакт для <b>{MESSENGERS[keys[index]]}</b>.")
    else:
        await state.update_data(messenger_values=values, extra_keys=[])
        await state.set_state(Form.extras)
        await message.answer("Что добавить дополнительно? Выбери нужное или сразу нажми «Завершить заявку».", reply_markup=menu(EXTRAS, [], "e", "Завершить заявку →"))

def application(data, user):
    socials = "\n".join(f"• {SOCIALS[k]}: {v}" for k, v in data.get("social_values", {}).items()) or "не выбрано"
    contacts = "\n".join(f"• {MESSENGERS[k]}: {v}" for k, v in data.get("messenger_values", {}).items()) or "не выбрано"
    extras = ", ".join(EXTRAS[k] for k in data.get("extra_keys", [])) or "не выбрано"
    username = f" (@{user.username})" if user.username else ""
    return f"<b>НОВАЯ ЗАЯВКА НА ВИЗИТКУ</b>\n\n<b>Клиент:</b> {user.full_name}{username}\n\n<b>Имя и сфера:</b> {data['name']}\n<b>О себе:</b> {data['about']}\n\n<b>Соцсети / сайт:</b>\n{socials}\n\n<b>Связь:</b>\n{contacts}\n\n<b>Дополнительно:</b> {extras}"

@router.callback_query(Form.extras, F.data.startswith("e:"))
async def extras(callback: CallbackQuery, state: FSMContext, bot: Bot):
    key = callback.data.split(":", 1)[1]
    data = await state.get_data(); selected = data.get("extra_keys", [])
    if key != "done":
        selected = selected.copy()
        selected.remove(key) if key in selected else selected.append(key)
        await state.update_data(extra_keys=selected)
        await callback.message.edit_reply_markup(reply_markup=menu(EXTRAS, selected, "e", "Завершить заявку →"))
        await callback.answer(); return
    try:
        await bot.send_photo(int(OWNER_CHAT_ID), data["photo_id"], caption="<b>Фото к заявке</b>")
        await bot.send_message(int(OWNER_CHAT_ID), application(data, callback.from_user))
        text = f"<b>Готово, заявку получил Антон.</b>\n\nБазовая визитка — от <b>{PRICE}</b>. После проверки материалов Антон подтвердит точную стоимость. Старт работы — после предоплаты <b>{PREPAY}</b>."
    except Exception:
        logging.exception("Could not send application")
        text = "Не получилось передать заявку автоматически. Нажми кнопку ниже и напиши Антону напрямую."
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(text, reply_markup=write_anton())
    await state.clear(); await callback.answer("Заявка отправлена")

async def main():
    if not BOT_TOKEN or not OWNER_CHAT_ID:
        raise RuntimeError("Set BOT_TOKEN and OWNER_CHAT_ID in Railway Variables. Never save a token in GitHub.")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage()); dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
