"""Release 2 UX wrapper. Keeps the existing backend and collection handlers intact."""
from __future__ import annotations

import asyncio
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

import bot as legacy
from services.adaptive_recommendation import GOALS, recommend_structure
from services.module_selection import CONTACT_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE, initial_selected_modules, toggle_module
from services.pilot_i18n import language_from, language_from_telegram, t

router = Router()


def entry_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Выбрать самостоятельно", callback_data="ux:direct")],
        [InlineKeyboardButton(text="✨ Помоги подобрать", callback_data="ux:adaptive")],
    ])


def goal_keyboard(chosen: list[str]):
    rows = [[InlineKeyboardButton(text=("☑ " if label in chosen else "☐ ") + label, callback_data=f"goal:{i}")] for i, label in enumerate(GOALS)]
    rows += [[InlineKeyboardButton(text="Готово", callback_data="goal:done")], [InlineKeyboardButton(text="← Назад", callback_data="goal:back")], [InlineKeyboardButton(text="✕ Отменить", callback_data="goal:cancel")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ux_modules_keyboard(selected, language="ru"):
    selected = set(selected)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("☑ " if SOCIAL_MODULE in selected else "☐ ") + t(language, "social"), callback_data=f"uxm:{SOCIAL_MODULE}")],
        [InlineKeyboardButton(text=("☑ " if CONTACT_MODULE in selected else "☐ ") + t(language, "contacts"), callback_data=f"uxm:{CONTACT_MODULE}")],
        [InlineKeyboardButton(text=("☑ " if PRODUCTS_MODULE in selected else "☐ ") + t(language, "projects"), callback_data=f"uxm:{PRODUCTS_MODULE}")],
        [InlineKeyboardButton(text=t(language, "back"), callback_data="uxm:back")],
        [InlineKeyboardButton(text=t(language, "cancel"), callback_data="uxm:cancel")],
        [InlineKeyboardButton(text=t(language, "continue"), callback_data="uxm:done")],
    ])


def recommendation_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="→ Подходит, продолжить", callback_data="rec:accept")],
        [InlineKeyboardButton(text="✎ Изменить", callback_data="rec:edit")],
        [InlineKeyboardButton(text="← Назад", callback_data="rec:back")],
        [InlineKeyboardButton(text="✕ Отменить", callback_data="rec:cancel")],
    ])


def review_keyboard_v2(language="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить данные", callback_data="uxrv:edit")],
        [InlineKeyboardButton(text="← Назад", callback_data="uxrv:back")],
        [InlineKeyboardButton(text=t(language, "cancel"), callback_data="uxrv:cancel")],
        [InlineKeyboardButton(text=t(language, "continue_submission"), callback_data="uxrv:send")],
    ])


async def show_start(message: Message, state: FSMContext):
    await state.clear()
    telegram_language = getattr(getattr(message, "from_user", None), "language_code", None)
    detected_interface_language = language_from_telegram(telegram_language)
    interface_language = "ru"
    await state.update_data(
        telegram_language=telegram_language,
        detected_interface_language=detected_interface_language,
        interface_language=interface_language,
        adaptive_mode="guided", selected_modules=[], completed_modules=[], language_before_core=True,
    )
    await message.answer(
        t(interface_language, "start_intro")
    )
    await message.answer(t(interface_language, "price_intro"))
    await legacy.ask_language(message, state)


@router.callback_query(legacy.Form.entry_mode, F.data.startswith("ui:"))
async def choose_interface_language(callback: CallbackQuery, state: FSMContext):
    language = callback.data.split(":", 1)[1]
    await state.update_data(interface_language=language, adaptive_mode="guided", selected_modules=[], completed_modules=[], language_before_core=True)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        t(language, "price_intro"),
    )
    await legacy.ask_language(callback.message, state)
    await callback.answer()


@router.callback_query(legacy.Form.entry_mode, F.data.startswith("ux:"))
async def entry(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)
    if mode == "direct":
        await state.update_data(adaptive_mode="direct", selected_modules=[], completed_modules=[])
        await ux_start_modules(callback.message, state)
    else:
        await state.update_data(adaptive_mode="adaptive", selected_modules=[], completed_modules=[])
        await state.set_state(legacy.Form.profession)
        await callback.message.answer("Как вас зовут?", reply_markup=legacy.cancel_keyboard())
    await callback.answer()


@router.message(legacy.Form.profession, F.text)
async def adaptive_name(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("adaptive_mode") != "adaptive":
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(legacy.Form.translation_text)
    await message.answer("Чем вы занимаетесь? Можно написать своими словами.")


@router.message(legacy.Form.translation_text, F.text)
async def adaptive_profession(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("adaptive_mode") != "adaptive":
        return
    profession = message.text.strip()
    if not profession:
        await message.answer("Напиши, пожалуйста, чем ты занимаешься.")
        return
    await state.update_data(profession=profession)
    await state.set_state(legacy.Form.work_context)
    await message.answer("Как вы обычно работаете?", reply_markup=legacy.work_context_keyboard())


@router.callback_query(legacy.Form.work_context, F.data.startswith("context:"))
async def adaptive_context(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("adaptive_mode") != "adaptive":
        return
    context = callback.data.split(":", 1)[1]
    if context == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.set_state(legacy.Form.translation_text)
        await callback.message.answer("Чем вы занимаетесь?")
        await callback.answer()
        return
    await state.update_data(work_context=context, client_goal=[])
    await state.set_state(legacy.Form.preset)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("<b>Что визитка должна помогать вам делать?</b>\n\nМожно выбрать не более двух вариантов.", reply_markup=goal_keyboard([]))
    await callback.answer()


@router.callback_query(legacy.Form.preset, F.data.startswith("goal:"))
async def adaptive_goal(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("adaptive_mode") != "adaptive":
        return
    action = callback.data.split(":", 1)[1]
    chosen = list(data.get("client_goal", []))
    if action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.set_state(legacy.Form.work_context)
        await callback.message.answer("Как вы обычно работаете?", reply_markup=legacy.work_context_keyboard())
    elif action == "cancel":
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    elif action == "done":
        if not chosen:
            await callback.answer("Выбери хотя бы один вариант.", show_alert=True)
            return
        recommendation = recommend_structure(data.get("profession", ""), data.get("work_context", ""), tuple(chosen))
        selected = initial_selected_modules(recommendation.selected_modules)
        await state.update_data(preset_reference=None, recommendation_scenario=recommendation.scenario, recommendation_explanation=recommendation.explanation, selected_modules=list(selected), completed_modules=[])
        await callback.message.edit_reply_markup(reply_markup=None)
        await show_recommendation(callback.message, state)
    else:
        index = int(action)
        label = GOALS[index]
        if label in chosen:
            chosen.remove(label)
        elif len(chosen) < 2:
            chosen.append(label)
        else:
            await callback.answer("Можно выбрать максимум два варианта.", show_alert=True)
            return
        await state.update_data(client_goal=chosen)
        await callback.message.edit_reply_markup(reply_markup=goal_keyboard(chosen))
    await callback.answer()


@router.callback_query(legacy.Form.preset, F.data.startswith("rec:"))
async def recommendation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("adaptive_mode") != "adaptive":
        return
    action = callback.data.split(":", 1)[1]
    if action == "accept":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.update_data(modules_selected_before_core=True)
        await legacy.ask_language(callback.message, state)
    elif action == "edit":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.update_data(module_selection_return_to_recommendation=True)
        await ux_start_modules(callback.message, state)
    elif action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.set_state(legacy.Form.work_context)
        await callback.message.answer("Как вы обычно работаете?", reply_markup=legacy.work_context_keyboard())
    else:
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    await callback.answer()


async def ux_start_modules(message: Message, state: FSMContext):
    data = await state.get_data()
    language = language_from(data)
    selected = initial_selected_modules(data.get("selected_modules", ()))
    await state.update_data(selected_modules=list(selected), completed_modules=list(data.get("completed_modules", ())))
    await state.set_state(legacy.Form.modules)
    await message.answer(
        "<b>Основная информация — обязательный раздел.</b>\n\nВыберите разделы, которые хотите добавить в визитку.",
        reply_markup=ux_modules_keyboard(selected, language),
    )


@router.callback_query(legacy.Form.name, F.data == "core:name:back")
async def core_name_back(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await ux_start_modules(callback.message, state)
    await callback.answer()


@router.callback_query(legacy.Form.modules, F.data.startswith("uxm:"))
async def modules(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    action = callback.data.split(":", 1)[1]
    selected = initial_selected_modules(data.get("selected_modules", ()))
    if action in {SOCIAL_MODULE, CONTACT_MODULE, PRODUCTS_MODULE}:
        selected = toggle_module(selected, action)
        await state.update_data(selected_modules=list(selected))
        await callback.message.edit_reply_markup(reply_markup=ux_modules_keyboard(selected, language_from(data)))
    elif action == "done":
        await callback.message.edit_reply_markup(reply_markup=None)
        if data.get("core_complete"):
            await legacy.start_next_selected_module(callback.message, state)
        else:
            await legacy.start_core_collection(callback.message, state)
    elif action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        if data.get("module_selection_return_to_recommendation"):
            await state.update_data(module_selection_return_to_recommendation=False)
            await show_recommendation(callback.message, state)
        elif data.get("module_selection_return_to_review"):
            await state.update_data(module_selection_return_to_review=False)
            await show_review_v2(callback.message, state)
        elif data.get("core_complete"):
            await legacy.ask_about(callback.message, state)
        else:
            await legacy.ask_language(callback.message, state)
    else:
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Заявка отменена. Когда будешь готов, отправь /start.", reply_markup=ReplyKeyboardRemove())
    await callback.answer()


async def show_recommendation(message: Message, state: FSMContext):
    data = await state.get_data()
    selected = initial_selected_modules(data.get("selected_modules", ()))
    labels = {SOCIAL_MODULE: "Социальные сети", CONTACT_MODULE: "Контакты", PRODUCTS_MODULE: "Проекты и ссылки"}
    listed = "\n".join(f"☑ {labels[m]}" for m in selected if m != "core") or "— дополнительных разделов пока нет"
    await state.set_state(legacy.Form.preset)
    await message.answer(
        "<b>Я предложил такую структуру.</b>\n\n"
        + escape(data.get("recommendation_explanation", "Структура основана на ваших ответах."))
        + "\n\n<b>Основная информация:</b> имя, сфера работы, фото/логотип/без изображения, описание и язык.\n\n<b>Дополнительно:</b>\n"
        + listed,
        reply_markup=recommendation_keyboard(),
    )


async def show_review_v2(message: Message, state: FSMContext):
    data = await state.get_data()
    language = language_from(data)
    selected_modules, module_configuration = legacy.build_module_configuration(data, selected_modules=tuple(data.get("selected_modules", ())))
    await state.update_data(module_configuration=module_configuration, return_to_review=False)
    social_lines = []
    for key, value in data.get("social_values", {}).items():
        if isinstance(value, dict):
            label, rendered = value.get("name", legacy.localized_socials(language).get(key, key)), value.get("value", "")
        else:
            label, rendered = legacy.localized_socials(language).get(key, key), value
        social_lines.append(f"• {escape(str(label))} — {escape(str(rendered))}")
    socials = "\n".join(social_lines) or t(language, "not_selected")
    contacts = legacy.contacts_review_text(data)
    messengers = legacy.messengers_review_text(data)
    products = data.get("product_values", [])
    await state.set_state(legacy.Form.review)
    selected_labels = {"core": t(language, "core_section"), SOCIAL_MODULE: t(language, "social"), legacy.MESSENGER_MODULE: "Мессенджеры", CONTACT_MODULE: t(language, "contacts"), PRODUCTS_MODULE: t(language, "projects"), "location": "Location"}
    selected_text = ", ".join(selected_labels.get(module, module) for module in selected_modules)
    await message.answer(
        legacy.progress_text(data, "review")
        + t(language, "review_title") + "\n\n"
        + f"<b>{t(language, 'sections')}:</b> {selected_text}\n"
        + f"<b>Основная информация</b>\n"
        + f"<b>{t(language, 'preferred_link')}:</b> {escape(data.get('preferred_card_name') or t(language, 'not_specified'))}\n"
        + f"<b>{t(language, 'name')}:</b> {escape(data.get('name', ''))}\n"
        + f"<b>{t(language, 'profession_label')}:</b> {escape(data.get('profession', ''))}\n"
        + f"<b>{t(language, 'card_languages')}:</b> {escape(legacy.language_names(data))}\n"
        + f"<b>{t(language, 'image')}:</b> {escape(data.get('image_kind') or t(language, 'not_specified'))}\n"
        + f"\n<b>Социальные сети:</b>\n{socials}\n"
        + f"\n<b>Контакты:</b> {contacts}\n"
        + f"<b>Мессенджеры:</b> {messengers}\n"
        + f"\n<b>Проекты и ссылки:</b>\n{legacy.projects_review_text(data)}\n"
        + f"<b>{t(language, 'price')}:</b> {legacy.tariff_text(data)}\n\n"
        + t(language, "review_note"),
        reply_markup=review_keyboard_v2(language),
    )


legacy.show_review = show_review_v2


@router.callback_query(legacy.Form.review, F.data.startswith("uxrv:"))
async def review(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":", 1)[1]
    if action == "send":
        await callback.message.edit_reply_markup(reply_markup=None)
        await legacy.ask_final_comment(callback.message, state)
        await callback.answer()
    elif action == "edit":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.set_state(legacy.Form.edit_menu)
        data = await state.get_data()
        await callback.message.answer(t(language_from(data), "edit_prompt"), reply_markup=legacy.edit_keyboard(language_from(data)))
        await callback.answer()
    elif action == "back":
        await callback.message.edit_reply_markup(reply_markup=None)
        await state.update_data(module_selection_return_to_review=True)
        await ux_start_modules(callback.message, state)
        await callback.answer()
    else:
        language = language_from(await state.get_data())
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t(language, "cancelled"), reply_markup=ReplyKeyboardRemove())
        await callback.answer()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await show_start(message, state)


async def main():
    if not legacy.BOT_TOKEN or not legacy.OWNER_CHAT_ID:
        raise RuntimeError("Set BOT_TOKEN and OWNER_CHAT_ID in Railway Variables. Never save a token in GitHub.")
    bot_instance = Bot(legacy.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.include_router(legacy.router)
    await dp.start_polling(bot_instance)


if __name__ == "__main__":
    asyncio.run(main())
