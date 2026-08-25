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
    sys.modules.update(modules)


install_aiogram_stub()
bot = importlib.import_module("bot")


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


if __name__ == "__main__":
    unittest.main()
