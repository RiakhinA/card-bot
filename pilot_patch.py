"""Focused Pilot UX stabilization after the first real mobile pass.

Temporary compatibility layer: keeps the proven backend and existing handlers,
while overriding only the small UX points found in the mobile test.
"""
import asyncio

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import bot as legacy
import bot_v2
from services.module_selection import PRODUCTS_MODULE

patch_router = Router()

# Keep recognizable networks, but allow one free-form additional network.
legacy.SOCIALS["other"] = "Другая соцсеть (название + ссылка)"


def about_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть примеры", callback_data="about:examples")],
        [InlineKeyboardButton(text="← Назад", callback_data="core:about:back")],
    ])


async def ask_about(message: Message, state: FSMContext):
    await state.set_state(legacy.Form.about)
    await message.answer(
        legacy.progress_text(await state.get_data(), "core")
        + "Расскажи, что человеку важно узнать о тебе в первую очередь.\n\n"
        "Можно написать, чем ты занимаешься, как помогаешь, работаешь онлайн или офлайн, "
        "в каких городах принимаешь и другую важную рабочую информацию.\n\n"
        "До 600 символов.",
        reply_markup=about_keyboard(),
    )


legacy.ask_about = ask_about


@patch_router.callback_query(legacy.Form.about, F.data == "about:examples")
async def about_examples(callback: CallbackQuery):
    await callback.message.answer(
        "<b>Примеры описания</b>\n\n"
        "<b>Коуч:</b> помогаю не потеряться между работой, отношениями и своими желаниями. "
        "Вместе находим опору, ясность и следующий шаг.\n\n"
        "<b>Массажист:</b> работаю с напряжением в теле, восстановлением и бережной заботой о себе. "
        "Подбираю формат массажа под самочувствие и запрос.\n\n"
        "<b>Блогер и инфлюенсер:</b> создаю контент о путешествиях, стиле жизни и красивых местах Киева. "
        "Сотрудничаю с брендами.\n\n"
        "Можно также указать формат работы, город или несколько городов и другую важную информацию."
    )
    await callback.answer()


async def start_core_collection(message: Message, state: FSMContext):
    await state.update_data(modules_selected_before_core=True)
    await state.set_state(legacy.Form.name)
    await message.answer(
        legacy.progress_text(await state.get_data(), "core")
        + "Отлично. Начнём с основной информации.\n\n"
        "Какое имя или название будет показано на визитке?",
        reply_markup=legacy.step_back_keyboard("core:name:back"),
    )


legacy.start_core_collection = start_core_collection


def card_name_end_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="cardname:skip")],
        [InlineKeyboardButton(text="← Назад", callback_data="cardname:back")],
    ])


async def ask_card_name_end(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("preferred_card_name"):
        await bot_v2.show_review_v2(message, state)
        return
    await state.update_data(return_to_review=True)
    await state.set_state(legacy.Form.card_name)
    await message.answer(
        "<b>Адрес вашей визитки</b>\n\n"
        "Если хотите, укажите короткое имя для ссылки. Например: "
        "<code>anna-koval</code> → <code>anna-koval.my-webcard.workers.dev</code>.\n\n"
        "Это пожелание к адресу: доступность мы проверим позже. Этот шаг можно пропустить.",
        reply_markup=card_name_end_keyboard(),
    )


async def start_next_selected_module(message: Message, state: FSMContext):
    data = await state.get_data()
    next_flow = legacy.next_module_flow(data.get("selected_modules", ()), data.get("completed_modules", ()))
    if next_flow == legacy.SOCIAL_MODULE:
        await legacy.start_socials(message, state)
    elif next_flow == legacy.CONTACT_MODULE:
        await legacy.start_contacts(message, state)
    elif next_flow == legacy.PRODUCTS_MODULE:
        await legacy.start_products(message, state)
    else:
        await ask_card_name_end(message, state)


legacy.start_next_selected_module = start_next_selected_module


@patch_router.callback_query(legacy.Form.card_name, F.data == "cardname:skip")
async def card_name_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(preferred_card_name="", return_to_review=False)
    await callback.message.edit_reply_markup(reply_markup=None)
    await bot_v2.show_review_v2(callback.message, state)
    await callback.answer()


@patch_router.callback_query(legacy.Form.card_name, F.data == "cardname:back")
async def card_name_back(callback: CallbackQuery, state: FSMContext):
    await state.update_data(return_to_review=False, module_selection_return_to_review=True)
    await callback.message.edit_reply_markup(reply_markup=None)
    await bot_v2.ux_start_modules(callback.message, state)
    await callback.answer()


async def start_products(message: Message, state: FSMContext):
    await state.set_state(legacy.Form.products)
    await message.answer(
        legacy.progress_text(await state.get_data(), PRODUCTS_MODULE)
        + "Добавь проекты и ссылки: сайты, боты, портфолио, курсы, акции или другие внешние ресурсы.\n\n"
        "Можно добавить несколько проектов или ссылок. После каждого бот предложит добавить следующий.",
        reply_markup=legacy.products_keyboard(),
    )


legacy.start_products = start_products


# Intercept the v2 review CTA before the old router. The old handler used a
# dependency parameter name that Aiogram does not inject, which made the button
# flash without advancing.
@patch_router.callback_query(legacy.Form.review, F.data == "uxrv:send")
async def review_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_reply_markup(reply_markup=None)
    await legacy.ask_final_comment(callback.message, state)
    await callback.answer()


async def main():
    if not legacy.BOT_TOKEN or not legacy.OWNER_CHAT_ID:
        raise RuntimeError("Set BOT_TOKEN and OWNER_CHAT_ID in Railway Variables. Never save a token in GitHub.")
    bot = Bot(legacy.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(patch_router)
    dp.include_router(bot_v2.router)
    dp.include_router(legacy.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
