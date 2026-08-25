import unittest

from services.module_configuration import build_module_configuration


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

    def test_contact_and_products_are_preserved_as_modules(self):
        selected, configuration = build_module_configuration({
            "messenger_values": {
                "telegram": "@test",
                "whatsapp": "+380000000000",
            },
            "product_values": [
                {"name": "Consultation", "description": "One hour", "link": "https://example.com"}
            ],
        })

        self.assertIn("contact", selected)
        self.assertEqual(configuration["contact"]["telegram"], "@test")
        self.assertIn("products", selected)
        self.assertEqual(configuration["products"]["items"][0]["name"], "Consultation")

    def test_empty_optional_modules_are_not_selected(self):
        selected, configuration = build_module_configuration({"name": "Test User"})

        self.assertEqual(selected, ("core",))
        self.assertEqual(set(configuration), {"core"})


if __name__ == "__main__":
    unittest.main()
