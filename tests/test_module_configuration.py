import unittest

from services.module_configuration import build_module_configuration, normalize_communication


class ModuleConfigurationFoundationTest(unittest.TestCase):
    def test_existing_social_data_is_one_social_module(self):
        selected, configuration = build_module_configuration({
            "name": "Test User",
            "social_values": {
                "instagram": "https://instagram.com/test",
                "linkedin": "https://linkedin.com/in/test",
            },
        })

        self.assertIn("core", selected)
        self.assertIn("social", selected)
        self.assertNotIn("instagram", selected)
        self.assertEqual(
            configuration["social"],
            {
                "instagram": "https://instagram.com/test",
                "linkedin": "https://linkedin.com/in/test",
            },
        )

    def test_other_social_is_preserved_in_social_module(self):
        selected, configuration = build_module_configuration({
            "social_values": {
                "instagram": "https://instagram.com/test",
                "other": "https://mastodon.social/@test",
            },
        })
        self.assertIn("social", selected)
        self.assertEqual(configuration["social"]["instagram"], "https://instagram.com/test")
        self.assertEqual(configuration["social"]["other"], "https://mastodon.social/@test")

    def test_legacy_messengers_and_products_are_preserved_as_semantic_modules(self):
        selected, configuration = build_module_configuration({
            "messenger_values": {
                "telegram": "@test",
                "whatsapp": "+380000000000",
            },
            "product_values": [
                {"name": "Consultation", "description": "One hour", "link": "https://example.com"}
            ],
        })

        self.assertIn("messenger", selected)
        self.assertEqual(configuration["messenger"]["telegram"][0]["value"], "@test")
        self.assertNotIn("contact", configuration)
        self.assertIn("products", selected)
        self.assertEqual(configuration["products"]["items"][0]["name"], "Consultation")

    def test_email_is_preserved_as_a_contact(self):
        selected, configuration = build_module_configuration(
            {"messenger_values": {"email": "hello@example.com"}},
            selected_modules=("core", "contact"),
        )
        self.assertIn("contact", selected)
        self.assertEqual(configuration["contact"]["emails"][0]["value"], "hello@example.com")
        self.assertNotIn("messenger", configuration)

    def test_empty_optional_modules_are_not_selected(self):
        selected, configuration = build_module_configuration({"name": "Test User"})

        self.assertEqual(selected, ("core",))
        self.assertEqual(set(configuration), {"core"})

    def test_location_and_legacy_phone_are_mapped_without_scalar_phone(self):
        selected, configuration = build_module_configuration({
            "messenger_values": {"telegram": "@test", "phone": "+380000000000"},
            "city": "Київ",
            "workplace_address": "вул. Прикладна, 1",
        })

        self.assertIn("location", selected)
        self.assertEqual(
            configuration["location"],
            {"city": "Київ", "workplace_address": "вул. Прикладна, 1"},
        )
        self.assertEqual(
            configuration["contact"]["phones"],
            [{
                "id": configuration["contact"]["phones"][0]["id"],
                "label": "Другой",
                "number": "+380000000000",
            }],
        )
        self.assertNotIn("phone", configuration["contact"])

    def test_communication_adapter_separates_legacy_and_new_repeatable_values(self):
        legacy = {
            "phone_values": [
                {"label": "Рабочий", "number": "+380501112233"},
                {"label": "Личный", "number": "+380671234567"},
            ],
            "messenger_values": {
                "email": "legacy@example.com",
                "telegram": "@legacy",
                "viber": "+380501112233",
            },
        }
        normalized = normalize_communication(legacy)
        self.assertEqual([item["number"] for item in normalized["contacts"]["phones"]], ["+380501112233", "+380671234567"])
        self.assertEqual(normalized["contacts"]["emails"][0]["value"], "legacy@example.com")
        self.assertEqual(normalized["messengers"]["telegram"][0]["value"], "@legacy")
        self.assertEqual(normalized["messengers"]["viber"][0]["value"], "+380501112233")
        self.assertTrue(all(item["id"] for group in (*normalized["contacts"].values(), *normalized["messengers"].values()) for item in group))

        _, configuration = build_module_configuration(
            {"email_values": [{"id": "email-1", "value": "one@example.com"}, {"id": "email-2", "email": "two@example.com"}],
             "messenger_values": {"whatsapp": "https://wa.me/380501112233"}},
            selected_modules=("core", "contact"),
        )
        self.assertEqual([item["id"] for item in configuration["contact"]["emails"]], ["email-1", "email-2"])
        self.assertEqual(configuration["messenger"]["whatsapp"][0]["value"], "https://wa.me/380501112233")

    def test_phone_source_ids_are_preserved_and_legacy_phone_ids_remain_compatible(self):
        normalized = normalize_communication({
            "phone_values": [
                {"id": "phone-source-1", "label": "Салон", "number": "+380501112233"},
                {"item_id": "phone-source-2", "label": "Для записи", "number": "+380671234567"},
                {"label": "Исторический", "number": "+380931112233"},
            ],
        })
        phones = normalized["contacts"]["phones"]
        self.assertEqual([phone["id"] for phone in phones[:2]], ["phone-source-1", "phone-source-2"])
        self.assertEqual(
            [(phone["label"], phone["number"]) for phone in phones],
            [("Салон", "+380501112233"), ("Для записи", "+380671234567"), ("Исторический", "+380931112233")],
        )
        self.assertTrue(phones[2]["id"].startswith("phone-"))


if __name__ == "__main__":
    unittest.main()
