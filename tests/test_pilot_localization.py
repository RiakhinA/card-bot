"""Focused contract tests for the active Pilot interface localization."""

import unittest

from test_back_navigation_handlers import FakeCallback, FakeMessage, FakeState, bot, bot_v2, pilot_patch
from services.pilot_i18n import t


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
            self.assertIn(t(language, "payment_prompt"), message.answers[-1][0])
            state.data["payment_method"] = "PayPal"
            await bot.ask_confirmation(message, state)
            self.assertIn(t(language, "submit"), message.answers[-1][1]["reply_markup"].inline_keyboard[1][0].text)
            self.assertEqual(t(language, "project_url_invalid"), t(language, "project_url_invalid"))
            self.assertIn(t(language, "edit"), bot_v2.review_keyboard_v2(language).inline_keyboard[0][0].text)


if __name__ == "__main__":
    unittest.main()
