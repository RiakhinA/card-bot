"""Handler-level checks for Telegram Back navigation without a live bot."""

import importlib
import inspect
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


def install_aiogram_stub():
    if "aiogram" in sys.modules:
        return

    class Filter:
        def __getattr__(self, _name): return self
        def startswith(self, _value): return self
        def __eq__(self, _value): return self

    class Router:
        def message(self, *_args, **_kwargs): return lambda function: function
        def callback_query(self, *_args, **_kwargs): return lambda function: function

    class State: pass
    class StatesGroup: pass
    class Markup:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)
    class Button:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)
    class DefaultBotProperties:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)

    modules = {
        "aiogram": types.ModuleType("aiogram"),
        "aiogram.client": types.ModuleType("aiogram.client"),
        "aiogram.client.default": types.ModuleType("aiogram.client.default"),
        "aiogram.enums": types.ModuleType("aiogram.enums"),
        "aiogram.filters": types.ModuleType("aiogram.filters"),
        "aiogram.fsm": types.ModuleType("aiogram.fsm"),
        "aiogram.fsm.context": types.ModuleType("aiogram.fsm.context"),
        "aiogram.fsm.state": types.ModuleType("aiogram.fsm.state"),
        "aiogram.fsm.storage": types.ModuleType("aiogram.fsm.storage"),
        "aiogram.fsm.storage.memory": types.ModuleType("aiogram.fsm.storage.memory"),
        "aiogram.types": types.ModuleType("aiogram.types"),
    }
    modules["aiogram"].Bot = type("Bot", (), {})
    modules["aiogram"].Dispatcher = type("Dispatcher", (), {})
    modules["aiogram"].F = Filter()
    modules["aiogram"].Router = Router
    modules["aiogram.client.default"].DefaultBotProperties = DefaultBotProperties
    modules["aiogram.enums"].ParseMode = type("ParseMode", (), {"HTML": "HTML"})
    modules["aiogram.filters"].Command = lambda *_args: Filter()
    modules["aiogram.filters"].CommandStart = lambda *_args: Filter()
    modules["aiogram.fsm.context"].FSMContext = type("FSMContext", (), {})
    modules["aiogram.fsm.state"].State = State
    modules["aiogram.fsm.state"].StatesGroup = StatesGroup
    modules["aiogram.fsm.storage.memory"].MemoryStorage = type("MemoryStorage", (), {})
    for name in (
        "CallbackQuery", "FSInputFile", "InputMediaPhoto", "KeyboardButton", "Message",
    ):
        setattr(modules["aiogram.types"], name, type(name, (), {}))
    modules["aiogram.types"].InlineKeyboardButton = Button
    modules["aiogram.types"].InlineKeyboardMarkup = Markup
    modules["aiogram.types"].ReplyKeyboardMarkup = Markup
    modules["aiogram.types"].ReplyKeyboardRemove = Markup
    modules["aiogram.types"].KeyboardButton = Button
    sys.modules.update(modules)


install_aiogram_stub()
bot = importlib.import_module("bot")
bot_v2 = importlib.import_module("bot_v2")
pilot_patch = importlib.import_module("pilot_patch")


class FakeState:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.current_state = None
        self.cleared = False

    async def get_data(self): return dict(self.data)
    async def update_data(self, **values): self.data.update(values)
    async def set_state(self, value): self.current_state = value
    async def clear(self): self.data.clear(); self.cleared = True


class FakeMessage:
    def __init__(self, language_code=None):
        self.answers = []
        self.markup = object()
        self.from_user = types.SimpleNamespace(language_code=language_code)
    async def answer(self, text, **kwargs): self.answers.append((text, kwargs))
    async def edit_reply_markup(self, **kwargs): self.markup = kwargs.get("reply_markup")


class FakeCallback:
    def __init__(self, data, message=None): self.data, self.message, self.answered = data, message or FakeMessage(), False
    async def answer(self, *_args, **_kwargs): self.answered = True


class BackNavigationHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_social_back_preserves_values_and_returns_to_module_selection(self):
        state = FakeState({
            "selected_modules": ["core", "social"],
            "social_keys": ["instagram"],
            "social_values": {"instagram": "https://instagram.com/example"},
        })
        await bot.socials(FakeCallback("s:back"), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertEqual(state.data["social_values"]["instagram"], "https://instagram.com/example")
        self.assertEqual(state.data["selected_modules"], ["core", "social"])
        await bot.start_socials(FakeMessage(), state)
        self.assertIs(state.current_state, bot.Form.socials)
        self.assertEqual(state.data["social_keys"], ["instagram"])

    async def test_contact_back_preserves_values_and_returns_to_module_selection(self):
        state = FakeState({
            "selected_modules": ["core", "contact"],
            "messenger_keys": ["telegram"],
            "messenger_values": {"telegram": "@example"},
        })
        await bot.messengers(FakeCallback("m:back"), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertEqual(state.data["messenger_values"]["telegram"], "@example")
        self.assertEqual(state.data["selected_modules"], ["core", "contact"])
        await bot.start_contacts(FakeMessage(), state)
        self.assertIs(state.current_state, bot.Form.contacts)
        self.assertEqual(state.data["messenger_keys"], ["telegram"])

    async def test_product_step_backs_keep_current_and_saved_products(self):
        state = FakeState({
            "selected_modules": ["core", "products"],
            "product_values": [{"name": "Saved", "description": "", "link": "https://example.com/saved"}],
            "current_product": {"name": "New", "description": "Draft"},
        })
        await bot.product_link_back(FakeCallback("pstep:link:back"), state)
        self.assertIs(state.current_state, bot.Form.product_description)
        self.assertEqual(state.data["current_product"]["name"], "New")
        await bot.product_description_back(FakeCallback("pstep:description:back"), state)
        self.assertIs(state.current_state, bot.Form.product_name)
        await bot.product_name_back(FakeCallback("pstep:name:back"), state)
        self.assertIs(state.current_state, bot.Form.products)
        self.assertEqual(state.data["product_values"][0]["name"], "Saved")
        await bot.products(FakeCallback("p:back"), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertEqual(state.data["product_values"][0]["name"], "Saved")
        await bot.start_products(FakeMessage(), state)
        self.assertIs(state.current_state, bot.Form.products)
        self.assertEqual(len(state.data["product_values"]), 1)

    async def test_review_back_returns_to_review_without_confirmation_or_business_objects(self):
        state = FakeState({
            "name": "Client", "profession": "Coach", "about": "Description",
            "language_values": ["Русский"], "selected_modules": ["core", "social"],
            "completed_modules": ["social"], "social_values": {"instagram": "https://instagram.com/example"},
        })
        await bot.review(FakeCallback("rv:modules"), state, bot=None)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertNotIn("client_confirmation_date", state.data)
        await bot.select_modules(FakeCallback("ms:back"), state)
        self.assertIs(state.current_state, bot.Form.review)
        self.assertNotIn("client_confirmation_date", state.data)

    async def test_cancel_clears_fsm_instead_of_returning(self):
        state = FakeState({"name": "Client", "selected_modules": ["core"]})
        await bot.cancel(FakeMessage(), state)
        self.assertTrue(state.cleared)
        self.assertEqual(state.data, {})


class SalesReadyActiveFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_requires_interface_language_then_card_language_before_intake(self):
        state, message = FakeState(), FakeMessage()
        await bot_v2.choose_interface_language(FakeCallback("ui:en", message), state)
        self.assertEqual(state.data["interface_language"], "en")
        self.assertTrue(state.data["language_before_core"])
        self.assertIs(state.current_state, bot.Form.language)
        self.assertIn("1200 грн / $29", message.answers[-2][0])

    def test_interface_and_card_language_keyboards_are_separate(self):
        interface = [button.text for row in bot.interface_language_keyboard().inline_keyboard for button in row]
        card = [button.text for row in bot.language_select_menu("one", []).inline_keyboard for button in row]
        self.assertEqual(interface, ["Українська", "Русский", "English"])
        self.assertIn("Другой язык", card)
        self.assertEqual(card[:4], ["Українська", "Русский", "English", "Другой язык"])
        self.assertNotIn("Нужна помощь с переводом", card)

    async def test_two_card_languages_continue_to_structure_without_translation_help(self):
        state = FakeState({"language_before_core": True, "language_mode": "two", "language_values": ["Українська", "English"]})
        message = FakeMessage()
        await bot.choose_language(FakeCallback("ls:done", message), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertFalse(state.data["language_before_core"])
        self.assertNotIn("перевод", message.answers[-1][0].lower())

    async def test_core_defers_requested_link_name_until_the_end(self):
        state, message = FakeState({"selected_modules": ["core"]}), FakeMessage()
        await bot.start_core_collection(message, state)
        self.assertNotIn("my-webcard.workers.dev", message.answers[-1][0])
        self.assertIs(state.current_state, bot.Form.name)
        await pilot_patch.ask_card_name_end(message, state)
        self.assertIn("anna-koval.my-webcard.workers.dev", message.answers[-1][0])
        message.text = "anna-koval"
        await bot.card_name(message, state)
        self.assertEqual(state.data["preferred_card_name"], "anna-koval")
        self.assertIs(state.current_state, bot.Form.review)

    async def test_start_explains_product_before_examples_and_enters_active_flow(self):
        state = FakeState()
        message = FakeMessage()
        original_examples = bot.examples

        async def no_examples(_message):
            return None

        bot.examples = no_examples
        try:
            await bot_v2.show_start(message, state)
        finally:
            bot.examples = original_examples

        self.assertIs(state.current_state, bot.Form.language)
        self.assertIn("цифровая визитка", message.answers[0][0])
        self.assertIn("Затем увидите структуру", message.answers[0][0])

    async def test_direct_selection_exposes_core_and_optional_structure(self):
        state = FakeState()
        message = FakeMessage()
        await bot_v2.entry(FakeCallback("ux:direct", message), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertIn("Основная информация", message.answers[-1][0])
        self.assertIn("Выберите разделы", message.answers[-1][0])

    async def test_adaptive_entry_starts_with_name_and_can_be_cancelled_later(self):
        state = FakeState()
        message = FakeMessage()
        await bot_v2.entry(FakeCallback("ux:adaptive", message), state)
        self.assertIs(state.current_state, bot.Form.profession)
        self.assertEqual(state.data["adaptive_mode"], "adaptive")
        self.assertIn("Как вас зовут", message.answers[-1][0])

    async def test_progress_uses_selected_sections_not_fixed_total(self):
        progress = bot.progress_text({"selected_modules": ["core", "social", "contact"]}, "contact")
        self.assertIn("Шаг 3 из 4", progress)
        self.assertIn("Контакты", progress)

    async def test_core_back_preserves_data_and_returns_to_selection(self):
        state = FakeState({"selected_modules": ["core", "social"], "name": "Анна"})
        message = FakeMessage()
        await bot_v2.core_name_back(FakeCallback("core:name:back", message), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertEqual(state.data["name"], "Анна")
        self.assertIn("Основная информация", message.answers[-1][0])

    async def test_core_step_backs_restore_expected_previous_steps(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "language_mode": "one",
            "language_values": ["Русский"], "selected_modules": ["core"],
            "color_note": "Бежевый",
        })
        message = FakeMessage()
        await bot.core_profession_back(FakeCallback("core:profession:back", message), state)
        self.assertIs(state.current_state, bot.Form.name)
        await bot.choose_language_count(FakeCallback("lc:back", message), state)
        self.assertIs(state.current_state, bot.Form.core_profession)
        await bot.photo_back(FakeCallback("core:photo:back", message), state)
        self.assertIs(state.current_state, bot.Form.photo)
        await bot.about_back(FakeCallback("core:about:back", message), state)
        self.assertIs(state.current_state, bot.Form.photo)

    async def test_review_moves_to_optional_comment_before_submission(self):
        state = FakeState({"name": "Анна", "profession": "Коуч", "selected_modules": ["core"]})
        message = FakeMessage()
        await bot_v2.review(FakeCallback("uxrv:send", message), state)
        self.assertIs(state.current_state, bot.Form.final_comment)
        self.assertIn("вопрос, комментарий или дополнительная информация", message.answers[-1][0])

    async def test_all_review_callbacks_are_reachable(self):
        message = FakeMessage()
        state = FakeState({"selected_modules": ["core"], "name": "Анна", "profession": "Коуч"})
        await bot_v2.review(FakeCallback("uxrv:edit", message), state)
        self.assertIs(state.current_state, bot.Form.edit_menu)
        state = FakeState({"selected_modules": ["core"]})
        await bot_v2.review(FakeCallback("uxrv:back", message), state)
        self.assertIs(state.current_state, bot.Form.modules)
        state = FakeState({"selected_modules": ["core"]})
        await bot_v2.review(FakeCallback("uxrv:cancel", message), state)
        self.assertEqual(state.data, {})
        state = FakeState({"selected_modules": ["core"]})
        await pilot_patch.review_send(FakeCallback("uxrv:send", message), state, bot=None)
        self.assertIs(state.current_state, bot.Form.final_comment)

    async def test_single_language_advances_without_confirm_and_two_language_caps_at_two(self):
        message = FakeMessage()
        state = FakeState({"language_mode": "one", "language_values": [], "selected_modules": ["core"]})
        await bot.choose_language(FakeCallback("ls:ru", message), state)
        self.assertEqual(state.data["language_values"], ["Русский"])
        self.assertIs(state.current_state, bot.Form.photo)
        state = FakeState({"language_mode": "two", "language_values": ["Русский", "English"]})
        callback = FakeCallback("ls:uk", message)
        await bot.choose_language(callback, state)
        self.assertEqual(state.data["language_values"], ["Русский", "English"])

    async def test_social_value_saves_and_returns_to_marked_menu(self):
        state, message = FakeState({"selected_modules": ["core", "social"]}), FakeMessage()
        await bot.socials(FakeCallback("s:instagram", message), state)
        self.assertIs(state.current_state, bot.Form.social_link)
        message.text = "https://instagram.com/anna"
        await bot.social_link(message, state)
        self.assertIs(state.current_state, bot.Form.socials)
        self.assertEqual(state.data["social_values"]["instagram"], message.text)
        labels = [button.text for row in message.answers[-1][1]["reply_markup"].inline_keyboard for button in row]
        self.assertIn("✓ Instagram", labels)

    async def test_custom_language_is_shown_by_name_and_can_go_back(self):
        state, message = FakeState({"language_mode": "one", "language_values": []}), FakeMessage()
        message.text = "Deutsch"
        await bot.custom_language(message, state)
        self.assertIs(state.current_state, bot.Form.language_select)
        labels = [button.text for row in message.answers[-1][1]["reply_markup"].inline_keyboard for button in row]
        self.assertIn("✓ Deutsch", labels)
        await bot.choose_language(FakeCallback("ls:back", message), state)
        self.assertIs(state.current_state, bot.Form.language)

    async def test_no_image_is_valid_and_payment_method_precedes_confirmation(self):
        state = FakeState({"name": "Анна", "profession": "Коуч", "selected_modules": ["core"]})
        message = FakeMessage()
        await bot.media_choice(FakeCallback("media:none", message), state)
        self.assertEqual(state.data["image_kind"], "Без изображения")
        self.assertIs(state.current_state, bot.Form.about)
        await bot.ask_payment_method(message, state)
        await bot.payment_method(FakeCallback("pay:paypal", message), state)
        self.assertEqual(state.data["payment_method"], "PayPal")
        self.assertIs(state.current_state, bot.Form.confirmation)
        self.assertIn("1200 грн / $29", message.answers[-1][0])

    async def test_photo_and_logo_routes_keep_file_for_optional_persistence(self):
        for callback_data, expected_kind in (("media:photo", "Фото"), ("media:logo", "Логотип")):
            with self.subTest(kind=expected_kind):
                state, message = FakeState(), FakeMessage()
                await bot.media_choice(FakeCallback(callback_data, message), state)
                message.photo = [types.SimpleNamespace(file_id="file-123")]
                await bot.photo(message, state)
                self.assertEqual(state.data["image_kind"], expected_kind)
                self.assertEqual(state.data["photo_id"], "file-123")
                self.assertIs(state.current_state, bot.Form.about)

    async def test_about_copy_accepts_work_context_without_new_modules(self):
        state, message = FakeState({"selected_modules": ["core"]}), FakeMessage()
        await bot.ask_about(message, state)
        text = message.answers[-1][0]
        self.assertIn("онлайн или офлайн", text)
        self.assertIn("городах", text)

    async def test_editing_projects_completes_directly_to_review(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание",
            "language_values": ["Русский"], "selected_modules": ["core", "products"],
            "return_to_review": True,
        })
        message = FakeMessage()
        await bot.products(FakeCallback("p:done", message), state)
        self.assertIs(state.current_state, bot.Form.review)

    async def test_comment_skip_and_wording_remain_optional(self):
        state, message = FakeState({"selected_modules": ["core"]}), FakeMessage()
        await bot.ask_final_comment(message, state)
        self.assertIn("дополнительная информация", message.answers[-1][0])
        self.assertEqual(message.answers[-1][1]["reply_markup"].inline_keyboard[-1][0].text, "Пропустить и продолжить")
        await bot.final_comment_action(FakeCallback("comment:skip", message), state, bot=None)
        self.assertIs(state.current_state, bot.Form.payment_method)
        self.assertEqual(sum("После проверки заявки я пришлю реквизиты" in answer[0] for answer in message.answers), 1)

    async def test_text_final_comment_opens_exactly_one_payment_prompt(self):
        state, message = FakeState({"selected_modules": ["core"]}), FakeMessage()
        message.text = "Нужна тёплая подача"
        await bot.final_comment(message, state, bot=None)
        self.assertEqual(state.data["client_comment"], "Нужна тёплая подача")
        self.assertIs(state.current_state, bot.Form.payment_method)
        self.assertEqual(sum("После проверки заявки я пришлю реквизиты" in answer[0] for answer in message.answers), 1)

    async def test_payment_choices_other_text_and_confirmation_tariffs(self):
        choices = [button.text for row in bot.payment_method_keyboard().inline_keyboard for button in row]
        self.assertEqual(choices[:6], ["PrivatBank", "PayPal", "Payoneer", "Skrill", "Криптовалюта", "Другой способ"])
        for languages, tariff in ((["Русский"], "1200 грн / $29"), (["Русский", "English"], "1700 грн / $39")):
            with self.subTest(tariff=tariff):
                state, message = FakeState({"language_values": languages}), FakeMessage()
                await bot.payment_method(FakeCallback("pay:other", message), state)
                self.assertIs(state.current_state, bot.Form.payment_method_other)
                message.text = "Revolut"
                await bot.payment_method_other(message, state)
                self.assertEqual(state.data["payment_method"], "Revolut")
                self.assertIs(state.current_state, bot.Form.confirmation)
                confirmation = message.answers[-1][0]
                self.assertIn(f"Стоимость: <b>{tariff}</b>", confirmation)
                self.assertIn("Способ оплаты: <b>Revolut</b>", confirmation)
                self.assertEqual(message.answers[-1][1]["reply_markup"].inline_keyboard[-1][0].text, "Отправить заявку")

    async def test_submission_only_happens_on_explicit_confirmation(self):
        state, message = FakeState(), FakeMessage()
        fake_send = AsyncMock(return_value=True)
        user = types.SimpleNamespace(id=7)
        callback = FakeCallback("confirm:back", message)
        callback.from_user = user
        with patch("bot.send_application", fake_send):
            await bot.confirmation(callback, state, bot=None)
        fake_send.assert_not_awaited()

    async def test_persistence_failure_never_notifies_owner(self):
        state = FakeState({"name": "Анна", "about": "Описание", "payment_method": "PayPal"})
        message = FakeMessage()
        message.chat = types.SimpleNamespace(id=11)
        message.message_id = 12
        user = types.SimpleNamespace(id=7, full_name="Анна", username=None)
        fake_bot = types.SimpleNamespace(send_message=AsyncMock(), send_photo=AsyncMock())
        with patch("bot.build_application_service_from_environment", side_effect=RuntimeError("storage unavailable")):
            result = await bot.send_application(message, state, fake_bot, user)
        self.assertFalse(result)
        fake_bot.send_message.assert_not_awaited()
        fake_bot.send_photo.assert_not_awaited()


class ActivePilotKeyboardHierarchyTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _rows(markup):
        return [[button.text for button in row] for row in markup.inline_keyboard]

    def _assert_primary_last(self, markup, primary):
        rows = self._rows(markup)
        flattened = [text for row in rows for text in row]
        self.assertEqual(flattened[-1], primary, rows)
        self.assertLess(flattened.index("← Назад") if "← Назад" in flattened else -1, len(flattened) - 1, rows)

    def test_active_pilot_keyboard_hierarchy(self):
        # This explicit list is the active Pilot route. Historical adaptive,
        # Location and Extras keyboards are intentionally not part of it.
        active = {
            "interface": (bot.interface_language_keyboard(), None),
            "language-count": (bot.language_menu(), None),
            "language-select": (bot.language_select_menu("one", ["Русский"]), None),
            "media": (bot.media_keyboard(), None),
            "modules": (bot.module_selection_keyboard(["core"]), "Продолжить"),
            "social": (bot.menu(bot.SOCIALS, [], "s", "Готово ✓", back_callback="s:back"), "Готово ✓"),
            "contacts": (bot.menu(bot.MESSENGERS, [], "m", "Готово ✓", back_callback="m:back"), "Готово ✓"),
            "projects": (bot.products_keyboard(), "Готово ✓"),
            "comment": (bot.final_comment_keyboard(), "Пропустить и продолжить"),
            "payment": (bot.payment_method_keyboard(), None),
            "confirmation": (bot.confirmation_keyboard(), "Отправить заявку"),
            "review": (bot_v2.review_keyboard_v2(), "Продолжить к отправке"),
            "edit": (bot.edit_keyboard(), None),
            "selector": (bot_v2.ux_modules_keyboard(["core"]), "Продолжить"),
        }
        for name, (markup, primary) in active.items():
            with self.subTest(keyboard=name):
                rows = self._rows(markup)
                flattened = [text for row in rows for text in row]
                back_indexes = [index for index, text in enumerate(flattened) if text.startswith("←")]
                if primary:
                    self.assertEqual(flattened[-1], primary, rows)
                    self.assertTrue(all(index < len(flattened) - 1 for index in back_indexes), rows)
                content_rows = [row for row in rows if any(not text.startswith(("←", "✕", "Отменить")) for text in row)]
                self.assertTrue(content_rows, rows)

    def test_selector_keeps_every_content_choice_above_service_controls(self):
        rows = self._rows(bot_v2.ux_modules_keyboard(["core"]))
        self.assertEqual(rows[:4], [["☐ Социальные сети"], ["☐ Мессенджеры"], ["☐ Контакты"], ["☐ Проекты и ссылки"]])
        self.assertEqual(rows[-1], ["Продолжить"])

    async def test_comment_back_returns_to_review_without_losing_comment(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание",
            "language_values": ["Русский"], "selected_modules": ["core"],
            "client_comment": "Нужна тёплая подача",
        })
        message = FakeMessage()
        await bot.final_comment_action(FakeCallback("comment:back", message), state, bot=None)
        self.assertIs(state.current_state, bot.Form.review)
        self.assertEqual(state.data["client_comment"], "Нужна тёплая подача")


class PilotDataBlockersTest(unittest.IsolatedAsyncioTestCase):
    def test_location_is_deferred_from_current_pilot_selector(self):
        keyboard = bot.module_selection_keyboard(["core"])
        labels = [button.text for row in keyboard.inline_keyboard for button in row]
        self.assertFalse(any("Локация" in label for label in labels))

    def test_active_optional_sections_are_social_contacts_and_projects_only(self):
        keyboard = bot_v2.ux_modules_keyboard(["core"])
        labels = [button.text for row in keyboard.inline_keyboard for button in row]
        self.assertEqual(labels[:4], ["☐ Социальные сети", "☐ Мессенджеры", "☐ Контакты", "☐ Проекты и ссылки"])
        self.assertFalse(any("Локация" in label or "Услуги" in label for label in labels))

    def test_social_has_networks_but_no_site_and_contacts_include_email(self):
        self.assertNotIn("site", bot.SOCIALS)
        self.assertEqual(set(bot.SOCIALS), {"instagram", "facebook", "linkedin", "youtube", "tiktok", "other"})
        self.assertEqual(bot.SOCIALS["other"], "Другая соцсеть (название + ссылка)")
        self.assertIn("email", bot.MESSENGERS)
        self.assertEqual(bot.MESSENGERS["email"], "Email")

    def test_projects_and_links_keep_products_backend_without_portfolio_module(self):
        keyboard = bot.products_keyboard()
        self.assertEqual(keyboard.inline_keyboard[0][0].text, "＋ Добавить ещё")
        self.assertFalse(hasattr(bot.Form, "portfolio"))

    async def test_phone_uses_required_free_text_label_and_returns_to_contacts(self):
        state = FakeState({"selected_modules": ["core", "contact"]})
        message = FakeMessage()
        await bot.messengers(FakeCallback("m:phone", message), state)
        self.assertIs(state.current_state, bot.Form.phone_label)
        labels = [button.text for row in message.answers[-1][1]["reply_markup"].inline_keyboard for button in row]
        self.assertNotIn("Рабочий", labels)
        self.assertNotIn("Личный", labels)
        message.text = "Салон на Подоле"
        await bot.phone_label(message, state)
        self.assertIs(state.current_state, bot.Form.phone_value)
        message.text = "+380501112233"
        await bot.phone_value(message, state)
        self.assertIs(state.current_state, bot.Form.contacts)
        phone = state.data["phone_values"][0]
        self.assertEqual(phone["label"], "Салон на Подоле")
        self.assertEqual(phone["number"], "+380501112233")
        self.assertTrue(phone["id"].startswith("phone-"))

    async def test_repeatable_phones_preserve_source_ids_order_and_values(self):
        state = FakeState({"selected_modules": ["core", "contact"]})
        message = FakeMessage()
        for index, (label, number) in enumerate((("Салон на Подоле", "+380501112233"), ("Для записи", "+380671234567"))):
            await bot.messengers(FakeCallback("m:phone", message), state)
            if index:
                self.assertIs(state.current_state, bot.Form.contact_manage)
                await bot.contact_manage(FakeCallback("cm:add", message), state)
            message.text = label
            await bot.phone_label(message, state)
            message.text = number
            await bot.phone_value(message, state)
        phones = state.data["phone_values"]
        self.assertEqual([(phone["label"], phone["number"]) for phone in phones], [
            ("Салон на Подоле", "+380501112233"), ("Для записи", "+380671234567"),
        ])
        self.assertEqual(len({phone["id"] for phone in phones}), 2)

    async def test_legacy_phone_is_readable_when_new_phone_collection_starts(self):
        state = FakeState({
            "selected_modules": ["core", "contact"], "messenger_keys": ["phone"],
            "messenger_values": {"phone": "+380671234567"},
        })
        message = FakeMessage()
        await bot.messengers(FakeCallback("m:phone", message), state)
        self.assertIs(state.current_state, bot.Form.contact_manage)
        self.assertEqual(state.data["phone_values"][0]["number"], "+380671234567")
        self.assertTrue(state.data["phone_values"][0]["id"].startswith("phone-"))

    async def test_repeatable_email_transitions_from_unlabeled_first_email(self):
        state = FakeState({"selected_modules": ["core", "contact"]})
        message = FakeMessage()
        await bot.messengers(FakeCallback("m:email", message), state)
        self.assertIs(state.current_state, bot.Form.email_value)
        message.text = "anna@example.com"
        await bot.email_value(message, state)
        self.assertIs(state.current_state, bot.Form.contacts)
        first = state.data["email_values"][0]
        self.assertNotIn("label", first)
        self.assertTrue(first["id"].startswith("email-"))

        await bot.messengers(FakeCallback("m:email", message), state)
        self.assertIs(state.current_state, bot.Form.contact_manage)
        await bot.contact_manage(FakeCallback("cm:add", message), state)
        self.assertIs(state.current_state, bot.Form.email_existing_label)
        message.text = "Личный"
        await bot.email_existing_label(message, state)
        self.assertIs(state.current_state, bot.Form.email_new_label)
        message.text = "Для записи"
        await bot.email_new_label(message, state)
        self.assertIs(state.current_state, bot.Form.email_value)
        message.text = "work@example.com"
        await bot.email_value(message, state)
        self.assertIs(state.current_state, bot.Form.contacts)
        emails = state.data["email_values"]
        self.assertEqual([(email["label"], email["value"]) for email in emails], [
            ("Личный", "anna@example.com"), ("Для записи", "work@example.com"),
        ])
        self.assertEqual(len({email["id"] for email in emails}), 2)

    async def test_third_email_requires_label_and_contacts_counter_excludes_messengers(self):
        state = FakeState({
            "selected_modules": ["core", "contact"],
            "phone_values": [{"id": "phone-1", "label": "Салон", "number": "+380501112233"}],
            "email_values": [
                {"id": "email-1", "label": "Личный", "value": "anna@example.com"},
                {"id": "email-2", "label": "Для записи", "value": "work@example.com"},
            ],
            "messenger_values": {"telegram": "@anna", "viber": "+380501112233"},
        })
        message = FakeMessage()
        self.assertEqual(bot.contacts_count(state.data), 3)
        await bot.messengers(FakeCallback("m:email", message), state)
        self.assertIs(state.current_state, bot.Form.contact_manage)
        await bot.contact_manage(FakeCallback("cm:add", message), state)
        self.assertIs(state.current_state, bot.Form.email_new_label)
        message.text = "Проекты"
        await bot.email_new_label(message, state)
        message.text = "projects@example.com"
        await bot.email_value(message, state)
        self.assertEqual(bot.contacts_count(state.data), 4)

    async def test_saved_phone_can_be_selected_edited_deleted_by_stable_id(self):
        state = FakeState({
            "selected_modules": ["core", "contact"],
            "phone_values": [
                {"id": "phone-a", "label": "Запись", "number": "+380501112233"},
                {"id": "phone-b", "label": "Студия", "number": "+380671234567"},
            ],
        })
        message = FakeMessage()
        await bot.messengers(FakeCallback("m:phone", message), state)
        self.assertIs(state.current_state, bot.Form.contact_manage)
        await bot.contact_manage(FakeCallback("cm:item:phone-b", message), state)
        self.assertEqual(state.data["managed_contact_id"], "phone-b")
        await bot.contact_item_action(FakeCallback("ci:value", message), state)
        message.text = "+380931234567"
        await bot.contact_edit_value(message, state)
        self.assertEqual(state.data["phone_values"][1]["id"], "phone-b")
        self.assertEqual(state.data["phone_values"][1]["number"], "+380931234567")
        await bot.contact_manage(FakeCallback("cm:item:phone-b", message), state)
        await bot.contact_item_action(FakeCallback("ci:delete", message), state)
        await bot.contact_delete(FakeCallback("cd:yes", message), state)
        self.assertEqual([item["id"] for item in state.data["phone_values"]], ["phone-a"])

    async def test_edit_name_and_profession_are_independent(self):
        state = FakeState({"name": "Old name", "profession": "Old profession"})
        await bot.edit(FakeCallback("ed:name"), state)
        self.assertIs(state.current_state, bot.Form.edit_name)
        message = FakeMessage(); message.text = "New name"
        await bot.edit_name(message, state)
        self.assertEqual(state.data["name"], "New name")
        self.assertEqual(state.data["profession"], "Old profession")
        await bot.edit(FakeCallback("ed:profession"), state)
        self.assertIs(state.current_state, bot.Form.edit_profession)
        message.text = "New profession"
        await bot.edit_profession(message, state)
        self.assertEqual(state.data["profession"], "New profession")

    async def test_edit_photo_without_image_returns_to_review_not_about(self):
        state = FakeState({"name": "A", "profession": "P", "return_to_review": False})
        message = FakeMessage()
        await bot.edit(FakeCallback("ed:photo", message), state)
        await bot.media_choice(FakeCallback("media:none", message), state)
        self.assertIs(state.current_state, bot.Form.review)
        self.assertEqual(state.data.get("about"), None)

    async def test_other_messenger_uses_name_then_value_and_back(self):
        state = FakeState({
            "selected_modules": ["core", "contact"],
            "messenger_keys": ["other"],
            "return_to_review": True,
        })
        message = FakeMessage()
        await bot.start_messengers(message, state)
        await bot.messenger_menu(FakeCallback("msg:other", message), state)
        self.assertIs(state.current_state, bot.Form.other_messenger_name)
        message.text = "Signal"
        await bot.other_messenger_name(message, state)
        self.assertIs(state.current_state, bot.Form.other_messenger_value)
        await bot.other_messenger_value_back(FakeCallback("other:value:back", message), state)
        self.assertIs(state.current_state, bot.Form.other_messenger_name)
        await bot.other_messenger_name(message, state)
        message.text = "https://signal.me/#p/test"
        await bot.other_messenger_value(message, state)
        self.assertEqual(
            state.data["messenger_values"]["other"],
            {"name": "Signal", "value": "https://signal.me/#p/test"},
        )
        self.assertIs(state.current_state, bot.Form.messengers)
        await bot.messenger_menu(FakeCallback("msg:done", message), state)
        self.assertIs(state.current_state, bot.Form.review)
        self.assertIn("Signal: https://signal.me/#p/test", message.answers[-1][0])

    async def test_contacts_and_messengers_use_separate_collection_menus(self):
        state = FakeState({"selected_modules": ["core", "contact", "messenger"]})
        message = FakeMessage()
        await bot.start_contacts(message, state)
        contact_buttons = [button.callback_data for row in message.answers[-1][1]["reply_markup"].inline_keyboard for button in row]
        self.assertEqual(state.current_state, bot.Form.contacts)
        self.assertIn("m:phone", contact_buttons)
        self.assertNotIn("m:telegram", contact_buttons)
        await bot.start_messengers(message, state)
        messenger_buttons = [button.callback_data for row in message.answers[-1][1]["reply_markup"].inline_keyboard for button in row]
        self.assertEqual(state.current_state, bot.Form.messengers)
        self.assertIn("msg:telegram", messenger_buttons)
        self.assertNotIn("msg:phone", messenger_buttons)

    async def test_other_social_reaches_runtime_review_and_module_configuration(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание",
            "language_values": ["Русский"], "selected_modules": ["core", "social"],
            "social_keys": ["instagram", "other"],
            "social_values": {
                "instagram": "https://instagram.com/anna",
                "other": "https://mastodon.social/@anna",
            },
        })
        message = FakeMessage()
        await bot_v2.show_review_v2(message, state)
        self.assertIn("Другая соцсеть", message.answers[-1][0])
        self.assertEqual(state.data["module_configuration"]["social"]["other"], "https://mastodon.social/@anna")
        self.assertEqual(state.data["module_configuration"]["social"]["instagram"], "https://instagram.com/anna")

    async def test_project_url_rejection_preserves_state_and_review_lists_details(self):
        state = FakeState({
            "selected_modules": ["core", "products"],
            "current_product": {"name": "Portfolio", "description": "Selected work"},
        })
        state.current_state = bot.Form.product_link
        message = FakeMessage()
        for invalid in ("", "-", "example.com"):
            message.text = invalid
            await bot.product_link(message, state)
            self.assertIs(state.current_state, bot.Form.product_link)
            self.assertEqual(state.data["current_product"], {"name": "Portfolio", "description": "Selected work"})
        message.text = "https://example.com/portfolio"
        await bot.product_link(message, state)
        self.assertIs(state.current_state, bot.Form.products)
        review_state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание",
            "language_values": ["Русский"], "selected_modules": ["core", "products"],
            "product_values": state.data["product_values"],
        })
        review_message = FakeMessage()
        await bot_v2.show_review_v2(review_message, review_state)
        self.assertIn("Portfolio: https://example.com/portfolio", review_message.answers[-1][0])

    async def test_pilot_patch_review_handler_reaches_final_comment(self):
        state = FakeState({"selected_modules": ["core"]})
        message = FakeMessage()
        await pilot_patch.review_send(FakeCallback("uxrv:send", message), state, bot=None)
        self.assertIs(state.current_state, bot.Form.final_comment)

    def test_pilot_patch_is_entrypoint_and_registers_router_first(self):
        self.assertEqual(Path("Procfile").read_text(encoding="utf-8").strip(), "worker: python pilot_patch.py")
        source = inspect.getsource(pilot_patch.main)
        self.assertLess(source.index("dp.include_router(patch_router)"), source.index("dp.include_router(bot_v2.router)"))
        self.assertLess(source.index("dp.include_router(bot_v2.router)"), source.index("dp.include_router(legacy.router)"))

    async def test_pilot_price_is_full_payment_and_has_no_legacy_components(self):
        one = bot.price_info({"language_values": ["Русский"]})
        two = bot.price_info({"language_values": ["Русский", "Українська"]})
        self.assertEqual(one["total"], 1200)
        self.assertEqual(two["total"], 1700)
        self.assertEqual(one["payment_policy"], "оплата после проверки заявки")
        self.assertEqual(one["usd_total"], 29)
        self.assertEqual(two["usd_total"], 39)
        self.assertFalse({"base", "prepay", "addon", "balance"} & set(one))

    async def test_owner_notification_lists_all_phones_and_payment_method(self):
        user = types.SimpleNamespace(full_name="Анна", username=None)
        text = bot.application({
            "name": "Анна", "about": "Описание", "language_values": ["Русский", "Українська"],
            "phone_values": [
                {"label": "Рабочий", "number": "+380501112233"},
                {"label": "Салон", "number": "+380671234567"},
            ],
            "payment_method": "PayPal",
        }, user, client_id="C-101", application_id="A-202")
        self.assertIn("Рабочий: +380501112233", text)
        self.assertIn("Салон: +380671234567", text)
        self.assertIn("1700 грн / $39", text)
        self.assertIn("Способ оплаты:</b> PayPal", text)
        self.assertIn("Client ID:</b> C-101", text)
        self.assertIn("Application ID:</b> A-202", text)

    async def test_owner_notification_renders_structured_other_messenger(self):
        user = types.SimpleNamespace(full_name="Анна", username=None)
        text = bot.application({
            "name": "Анна", "about": "Описание", "language_values": ["Русский"],
            "messenger_values": {
                "other": {"name": "Signal", "value": "https://signal.me/#p/anna"},
            },
        }, user)
        self.assertIn("Signal: https://signal.me/#p/anna", text)

    async def test_review_uses_semantic_contacts_and_messengers_without_changing_legacy_selection(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание", "language_values": ["Русский"],
            "selected_modules": ["core", "contact"],
            "phone_values": [{"label": "Рабочий", "number": "+380501112233"}],
            "messenger_values": {"email": "anna@example.com", "telegram": "@anna"},
        })
        message = FakeMessage()
        await bot.show_review(message, state)
        review = message.answers[-1][0]
        self.assertIn("<b>Контакты:</b> Рабочий: +380501112233, Email: anna@example.com", review)
        self.assertIn("<b>Мессенджеры:</b> Telegram: @anna", review)
        self.assertEqual(state.data["selected_modules"], ["core", "contact"])
        self.assertIn("messenger", state.data["module_configuration"])


if __name__ == "__main__":
    unittest.main()
