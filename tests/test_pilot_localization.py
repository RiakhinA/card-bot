"""Focused contract tests for the active Pilot interface localization."""

import unittest

from test_back_navigation_handlers import FakeCallback, FakeMessage, FakeState, bot, bot_v2, pilot_patch
from services.pilot_i18n import language_from_telegram, t


class PilotLocalizationTest(unittest.IsolatedAsyncioTestCase):
    EXPECTED = {
        "ru": ("Стоимость визитки", "Сколько языков", "Что будет", "Отлично", "Расскажите", "Социальные", "Контакты", "Проекты", "Проверьте", "Есть вопрос", "Выберите удобный", "Подтвердите", "Готово"),
        "uk": ("Вартість візитки", "Скільки мов", "Що буде", "Чудово", "Розкажіть", "Соціальні", "Контакти", "Проєкти", "Перевірте", "Є запитання", "Виберіть зручний", "Підтвердьте", "Готово"),
        "en": ("Card price", "How many languages", "What will", "Great", "What should", "Social", "Contacts", "Projects", "Review", "Any questions", "Choose a payment", "Confirm", "Done"),
    }

    def test_central_copy_covers_every_active_area_in_all_languages(self):
        keys = (
            "price_intro", "card_language_count", "modules_title", "core_name",
            "about_prompt", "social", "contacts", "projects", "review_title",
            "final_comment", "payment_prompt", "confirmation", "success",
        )
        for language, expected in self.EXPECTED.items():
            with self.subTest(language=language):
                rendered = [t(language, key, tariff="1200 грн / $29", method="PayPal") for key in keys]
                for marker, value in zip(expected, rendered):
                    self.assertIn(marker, value)

    def test_telegram_language_codes_resolve_to_supported_initial_defaults(self):
        expected = {
            "ru": "ru", "ru-RU": "ru", "ru_ru": "ru",
            "uk": "uk", "uk-UA": "uk", "uk_ua": "uk",
            "en": "en", "en-US": "en", "en-GB": "en",
            "pl": "ru", "de-DE": "ru", None: "ru", "": "ru",
        }
        for telegram_code, interface_language in expected.items():
            with self.subTest(telegram_code=telegram_code):
                self.assertEqual(language_from_telegram(telegram_code), interface_language)

    async def test_pilot_entry_records_detection_but_uses_temporary_ru_interface(self):
        for telegram_code, language in (("ru-RU", "ru"), ("uk-UA", "uk"), ("en-GB", "en"), ("pl", "ru"), (None, "ru")):
            with self.subTest(telegram_code=telegram_code):
                state = FakeState()
                message = FakeMessage(telegram_code)
                await bot_v2.start(message, state)
                self.assertEqual(state.data["telegram_language"], telegram_code)
                self.assertEqual(state.data["detected_interface_language"], language)
                self.assertEqual(state.data["interface_language"], "ru")
                self.assertIn(t("ru", "start_intro"), message.answers[0][0])
                self.assertIs(state.current_state, bot.Form.language)
                callbacks = [button.callback_data for answer in message.answers for row in answer[1].get("reply_markup", type("M", (), {"inline_keyboard": []})()).inline_keyboard for button in row]
                self.assertFalse(any(value.startswith("ui:") for value in callbacks))

    async def test_manual_override_wins_and_detection_does_not_change_card_languages(self):
        scenarios = (("uk", "en"), ("en-US", "ru"), ("ru-RU", "uk"))
        for detected, manual in scenarios:
            with self.subTest(detected=detected, manual=manual):
                state = FakeState({"language_values": ["Polski", "English"]})
                message = FakeMessage(detected)
                await bot_v2.start(message, state)
                await state.update_data(language_values=["Polski", "English"])
                await bot_v2.choose_interface_language(FakeCallback(f"ui:{manual}", message), state)
                self.assertEqual(state.data["interface_language"], manual)
                self.assertEqual(state.data["detected_interface_language"], language_from_telegram(detected))
                self.assertEqual(state.data["telegram_language"], detected)
                self.assertEqual(state.data["language_values"], ["Polski", "English"])
                self.assertIn(t(manual, "price_intro"), message.answers[-2][0])

    async def test_manual_selection_controls_next_screen_without_changing_card_language(self):
        for language, marker in (("ru", "Стоимость"), ("uk", "Вартість"), ("en", "Card price")):
            state = FakeState({"language_values": ["English"]})
            message = FakeMessage()
            await bot_v2.choose_interface_language(FakeCallback(f"ui:{language}", message), state)
            self.assertEqual(state.data["interface_language"], language)
            self.assertEqual(state.data.get("language_values"), ["English"])
            self.assertIn(marker, message.answers[-2][0])
            self.assertIn(t(language, "card_language_count").split("?", 1)[0], message.answers[-1][0])

    async def test_active_handlers_use_selected_language_and_preserve_user_content(self):
        for language in ("ru", "uk", "en"):
            state = FakeState({
                "interface_language": language, "selected_modules": ["core", "social", "contact", "products"],
                "completed_modules": ["social", "contact", "products"], "name": "Signal Person",
                "profession": "Creator", "about": "My exact text", "language_values": ["Українська"],
                "social_values": {"other": "https://social.example/me"},
                "messenger_values": {"other": {"name": "Signal", "value": "https://signal.me/example"}},
                "product_values": [{"name": "Exact Project", "description": "", "link": "https://example.com"}],
                "image_kind": "Без изображения", "payment_method": "PayPal",
            })
            message = FakeMessage()
            await pilot_patch.ask_about(message, state)
            self.assertIn(t(language, "about_prompt"), message.answers[-1][0])
            await bot.start_socials(message, state)
            self.assertIn(t(language, "social_prompt"), message.answers[-1][0])
            await bot.start_contacts(message, state)
            self.assertIn(t(language, "contacts_prompt"), message.answers[-1][0])
            await pilot_patch.start_products(message, state)
            self.assertIn(t(language, "projects_prompt"), message.answers[-1][0])
            await bot_v2.show_review_v2(message, state)
            review = message.answers[-1][0]
            for exact in ("Signal", "https://signal.me/example", "Exact Project", "https://example.com"):
                self.assertIn(exact, review)
            self.assertIn(t(language, "review_title"), review)

    def test_callbacks_and_canonical_values_remain_stable(self):
        for language in ("ru", "uk", "en"):
            self.assertEqual(bot.language_menu(language).inline_keyboard[0][0].callback_data, "lc:one")
            self.assertEqual(bot.payment_method_keyboard(language).inline_keyboard[0][0].callback_data, "pay:privatbank")
            self.assertEqual(bot.PAYMENT_METHODS["paypal"], "PayPal")
            self.assertEqual(bot.LANGUAGES["en"], "English")
        self.assertEqual(t("unsupported", "continue"), t("ru", "continue"))

    async def test_validation_preferred_link_edit_finish_and_errors_are_localized(self):
        for language in ("ru", "uk", "en"):
            state = FakeState({"interface_language": language, "selected_modules": ["core"], "language_values": ["English"]})
            message = FakeMessage()
            await pilot_patch.ask_card_name_end(message, state)
            self.assertIn(t(language, "link_title"), message.answers[-1][0])
            await bot.ask_final_comment(message, state)
            self.assertIn(t(language, "final_comment"), message.answers[-1][0])
            await bot.ask_payment_method(message, state)
            self.assertIn("После проверки заявки я пришлю реквизиты", message.answers[-1][0])
            state.data["payment_method"] = "PayPal"
            await bot.ask_confirmation(message, state)
            self.assertIn(t(language, "submit"), message.answers[-1][1]["reply_markup"].inline_keyboard[1][0].text)
            self.assertEqual(t(language, "project_url_invalid"), t(language, "project_url_invalid"))
            self.assertEqual(bot_v2.review_keyboard_v2(language).inline_keyboard[0][0].text, "Изменить данные")


if __name__ == "__main__":
    unittest.main()
