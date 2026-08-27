"""Handler-level checks for Telegram Back navigation without a live bot."""

import importlib
import sys
import types
import unittest


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
    def __init__(self): self.answers = []; self.markup = object()
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
        self.assertIs(state.current_state, bot.Form.messengers)
        self.assertEqual(state.data["messenger_keys"], ["telegram"])

    async def test_product_step_backs_keep_current_and_saved_products(self):
        state = FakeState({
            "selected_modules": ["core", "products"],
            "product_values": [{"name": "Saved", "description": "", "link": ""}],
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

        self.assertIs(state.current_state, bot.Form.entry_mode)
        self.assertIn("цифровая визитка", message.answers[0][0])
        self.assertIn("Сначала вы увидите структуру", message.answers[0][0])

    async def test_direct_selection_exposes_core_and_optional_structure(self):
        state = FakeState()
        message = FakeMessage()
        await bot_v2.entry(FakeCallback("ux:direct", message), state)
        self.assertIs(state.current_state, bot.Form.modules)
        self.assertIn("Основная информация", message.answers[-1][0])
        self.assertIn("Дополнительные разделы", message.answers[-1][0])

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
        self.assertIs(state.current_state, bot.Form.language_select)
        await bot.color_back(FakeCallback("core:color:back", message), state)
        self.assertIs(state.current_state, bot.Form.photo)
        await bot.about_back(FakeCallback("core:about:back", message), state)
        self.assertIs(state.current_state, bot.Form.color)

    async def test_review_moves_to_optional_comment_before_submission(self):
        state = FakeState({"name": "Анна", "profession": "Коуч", "selected_modules": ["core"]})
        message = FakeMessage()
        await bot_v2.review(FakeCallback("uxrv:send", message), state, bot_instance=None)
        self.assertIs(state.current_state, bot.Form.final_comment)
        self.assertIn("важное пожелание", message.answers[-1][0])

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
    async def test_location_back_and_skip_preserve_city_and_render_in_review(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание",
            "language_values": ["Русский"], "selected_modules": ["core", "location"],
            "return_to_review": True, "city": "Київ", "workplace_address": "Студія 5",
        })
        message = FakeMessage()
        await bot.location_address_action(FakeCallback("loc:address:back", message), state)
        self.assertIs(state.current_state, bot.Form.location_city)
        self.assertEqual(state.data["city"], "Київ")
        await bot.location_address_action(FakeCallback("loc:address:skip", message), state)
        self.assertIs(state.current_state, bot.Form.review)
        self.assertEqual(state.data["city"], "Київ")
        self.assertEqual(state.data["workplace_address"], "")
        self.assertIn("Локация:</b> Київ", message.answers[-1][0])

    async def test_repeatable_phone_collection_keeps_labels_and_back_does_not_lose_entries(self):
        state = FakeState({"selected_modules": ["core", "contact"], "messenger_keys": ["phone"]})
        message = FakeMessage()
        await bot.phone_label(FakeCallback("phone:work", message), state)
        self.assertIs(state.current_state, bot.Form.phone_value)
        self.assertEqual(state.data["current_phone_label"], "Рабочий")
        message.text = "+380501112233"
        await bot.phone_value(message, state)
        self.assertIs(state.current_state, bot.Form.phone_label)
        self.assertEqual(state.data["phone_values"], [{"label": "Рабочий", "number": "+380501112233"}])
        await bot.phone_label(FakeCallback("phone:personal", message), state)
        await bot.phone_value_back(FakeCallback("phone:value:back", message), state)
        self.assertIs(state.current_state, bot.Form.phone_label)
        self.assertEqual(state.data["phone_values"], [{"label": "Рабочий", "number": "+380501112233"}])

    async def test_phone_skip_is_safe_and_legacy_scalar_is_shown_as_phone(self):
        state = FakeState({
            "name": "Анна", "profession": "Коуч", "about": "Описание",
            "language_values": ["Русский"], "selected_modules": ["core", "contact"],
            "return_to_review": True, "messenger_values": {"phone": "+380671234567"},
        })
        message = FakeMessage()
        await bot.phone_label(FakeCallback("phone:skip", message), state)
        self.assertIs(state.current_state, bot.Form.review)
        self.assertIn("Другой: +380671234567", message.answers[-1][0])
        self.assertIn("Контакты:</b> не выбрано", message.answers[-1][0])

    async def test_legacy_phone_is_migrated_when_contact_collection_continues(self):
        state = FakeState({
            "selected_modules": ["core", "contact"], "messenger_keys": ["phone"],
            "messenger_values": {"phone": "+380671234567"},
        })
        message = FakeMessage()
        await bot.messengers(FakeCallback("m:done", message), state)
        self.assertIs(state.current_state, bot.Form.phone_label)
        self.assertEqual(
            state.data["phone_values"],
            [{"label": "Другой", "number": "+380671234567"}],
        )

    async def test_pilot_price_is_full_payment_and_has_no_legacy_components(self):
        one = bot.price_info({"language_values": ["Русский"]})
        two = bot.price_info({"language_values": ["Русский", "Українська"]})
        self.assertEqual(one["total"], 1200)
        self.assertEqual(two["total"], 1700)
        self.assertEqual(one["payment_policy"], "100% до начала работы")
        self.assertFalse({"base", "prepay", "addon", "balance"} & set(one))

    async def test_owner_notification_lists_all_phones_location_and_full_payment(self):
        user = types.SimpleNamespace(full_name="Анна", username=None)
        text = bot.application({
            "name": "Анна", "about": "Описание", "language_values": ["Русский", "Українська"],
            "phone_values": [
                {"label": "Рабочий", "number": "+380501112233"},
                {"label": "Салон", "number": "+380671234567"},
            ],
            "city": "Київ", "workplace_address": "Студія 5",
        }, user)
        self.assertIn("Рабочий: +380501112233", text)
        self.assertIn("Салон: +380671234567", text)
        self.assertIn("Київ, Студія 5", text)
        self.assertIn("1700 грн, оплата 100%", text)


if __name__ == "__main__":
    unittest.main()
