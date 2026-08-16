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
PRICE = os.getenv("PRICE", "900 грн")
PREPAY = os.getenv("PREPAY", "600 грн")
ASSETS = Path(__file__).parent / "assets"

SOCIALS = {"instagram": "Instagram", "facebook": "Facebook", "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok", "site": "Сайт"}
MESSENGERS = {"telegram": "Telegram", "whatsapp": "WhatsApp", "viber": "Viber", "phone": "Позвонить"}
EXTRAS = {"share": "Поделиться визиткой", "vcf": "Сохранить контакт (.vcf)", "language": "Второй язык"}


class Form(StatesGroup):
    name = State()
    photo = State()
    color = State()
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


def support_button():
    draft = quote("Привет, у меня вопрос по визитке: ")
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Есть вопрос? Написать в поддержку", url=f"tg://resolve?domain={OWNER_USERNAME}&text={draft}")
    ]])


def owner_keyboard(user):
    rows = []
    if user.username:
        draft = quote(f"Привет, {user.full_name}! Мы посмотрели материалы, всё хорошо. Для начала работы нужна предоплата {PREPAY}. Вот реквизиты: [впиши сам]. Как удобно оплатить?")
        rows.append([InlineKeyboardButton(text="Написать клиенту", url=f"tg://resolve?domain={user.username}&text={draft}")])
    rows.append([InlineKeyboardButton(text="Визитка отправлена", callback_data=f"delivery:{user.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def examples(message):
    paths = [ASSETS / x for x in ("01-anton.png", "02-male.png", "03-female.png", "04-builder.png")]
    if all(p.exists() for p in paths):
        await message.answer_media_group([InputMediaPhoto(media=FSInputFile(p)) for p in paths])
    else:
        await message.answer("Примеры визиток пока загружаются. Мы пришлём их отдельно.")


async def ask_about(message, state):
    await state.set_state(Form.about)
    await message.answer(
        "Коротко расскажи о себе: чем полезен людям или с каким запросом к тебе приходят.\n\n"
        "Здесь не надо ужиматься как в Instagram. Места хватит на всё что важно. Можно писать до 600 символов.\n\n"
        "Например: делаю кухни под заказ, веду клиента от замера до установки. Или: помогаю людям понять почему прежний путь не работает и найти новый. Или: снимаю портреты и события в Киеве."
    )


async def ask_messengers(message):
    await message.answer("Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь каждый контакт по очереди.", reply_markup=menu(MESSENGERS, [], "m", "Готово ✓"))


async def ask_extras(message):
    await message.answer("Выбери нужные пункты, затем нажми «Завершить заявку ✓». Ничего дополнительно заполнять не нужно.", reply_markup=menu(EXTRAS, [], "e", "Завершить заявку ✓"))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await examples(message)
    await message.answer(
        "<b>Привет!</b> Я помогу собрать данные для минималистичной онлайн-визитки.\n\n"
        "Это небольшая страница с самым важным о тебе: её можно поставить в Instagram, отправлять клиентам ссылкой.\n\n"
        "Посмотреть пример готовой визитки: <a href=\"https://riakhin-card.my-webcard.workers.dev\">https://riakhin-card.my-webcard.workers.dev</a>\n\n"
        "Ниже: несколько вариантов оформления и конструктор блоков.\n\n"
        f"Базовая визитка: <b>{PRICE}</b>.\n\n"
        "Как тебя зовут и чем занимаешься?\n\nНесколько примеров:\n\n"
        "Лёгкий тон: Марина, делаю массаж и возвращаю людей в тело. Или: Катя, коуч, помогаю не потеряться между работой и собой.\n\n"
        "Серьёзный тон: Антон, помогаю выйти из кризиса и найти опору для следующего шага. Или: Олег, психолог, работаю с тревогой и выгоранием.\n\n"
        "Коротко: Марина, массажист. Олег, дизайн кухонь. Катя, коуч."
    )
    await state.set_state(Form.name)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Сбор данных отменён. Когда будешь готов, отправь /start.")


@router.message(Form.name, F.text)
async def name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.photo)
    await message.answer("Теперь пришли фото для визитки.")


@router.message(Form.photo, F.photo)
async def photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(Form.color)
    await message.answer(
        "Фото получил. Какой цвет хочешь на визитке?\n\nТри варианта:\n\n"
        "- Пришли скрин шапки Instagram: подберём под твой стиль\n"
        "- Напиши цвет словами: тёмно-зелёный, бежевый, синий\n"
        "- Напиши «не знаю»: подберём сами по фото"
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
    await state.set_state(Form.socials)
    await message.answer("Выбери нужные пункты, затем нажми «Готово ✓» - после этого заполнишь ссылки по очереди.", reply_markup=menu(SOCIALS, [], "s", "Готово ✓"))


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
            await callback.message.answer(f"Пришли контакт для <b>{MESSENGERS[selected[0]]}</b>.")
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
        await message.answer(f"Теперь контакт для <b>{MESSENGERS[keys[index]]}</b>.")
    else:
        await state.update_data(messenger_values=values, extra_keys=[])
        await state.set_state(Form.extras)
        await ask_extras(message)


def application(data, user):
    socials = "\n".join(f"• {SOCIALS[k]}: {escape(v)}" for k, v in data.get("social_values", {}).items()) or "не выбрано"
    contacts = "\n".join(f"• {MESSENGERS[k]}: {escape(v)}" for k, v in data.get("messenger_values", {}).items()) or "не выбрано"
    extras = ", ".join(EXTRAS[k] for k in data.get("extra_keys", [])) or "не выбрано"
    username = f" (@{user.username})" if user.username else ""
    client_draft = f"Привет, {user.full_name}! Мы посмотрели материалы, всё хорошо. Для начала работы нужна предоплата {PREPAY}. Вот реквизиты: [впиши сам]. Как удобно оплатить?"
    return (
        "<b>НОВАЯ ЗАЯВКА НА ВИЗИТКУ</b>\n\n"
        f"<b>Клиент:</b> {escape(user.full_name)}{username}\n\n"
        f"<b>Имя и сфера:</b> {escape(data['name'])}\n"
        f"<b>О себе:</b> {escape(data['about'])}\n\n"
        f"<b>Цвет:</b> {escape(data.get('color_note', 'не указан'))}\n\n"
        f"<b>Соцсети / сайт:</b>\n{socials}\n\n"
        f"<b>Связь:</b>\n{contacts}\n\n"
        f"<b>Дополнительно:</b> {extras}\n\n"
        f"<b>Скопируй и отправь клиенту:</b>\n<code>{escape(client_draft)}</code>"
    )


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
    try:
        await bot.send_photo(int(OWNER_CHAT_ID), data["photo_id"], caption="<b>Фото к заявке</b>")
        if data.get("color_photo_id"):
            await bot.send_photo(int(OWNER_CHAT_ID), data["color_photo_id"], caption="<b>Скрин стиля для визитки</b>")
        await bot.send_message(int(OWNER_CHAT_ID), application(data, callback.from_user), reply_markup=owner_keyboard(callback.from_user))
        text = (
            "<b>Готово, заявку получили.</b>\n\n"
            f"Стоимость визитки: <b>{PRICE}</b>. Чтобы начать работу, нужна предоплата <b>{PREPAY}</b>. "
            "Мы посмотрим материалы и пришлём реквизиты для оплаты. Готовую визитку получишь в течение 24 часов после предоплаты.\n\n"
            "В течение недели можно внести правки: текст, соцсети, мессенджер, цвет - всё за один раз бесплатно. Если что-то работает некорректно по нашей вине, исправим бесплатно.\n\n"
            "После согласования готовой визитки, перед публикацией, оплачивается остаток <b>300 грн</b>."
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
