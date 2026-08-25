import unittest

from services.adaptive_preset import (
    profession_needs_context,
    recommend_preset,
)
from services.module_selection import initial_selected_modules, toggle_module


class AdaptivePresetTest(unittest.TestCase):
    def test_cosmetologist_offline_recommends_only_available_modules(self):
        recommendation = recommend_preset("Косметолог", "offline")

        self.assertEqual(recommendation.reference, "beauty_offline")
        self.assertEqual(
            initial_selected_modules(recommendation.selected_modules),
            ("core", "social", "contact", "products"),
        )

    def test_online_coach_recommendation(self):
        recommendation = recommend_preset("coach", "online")

        self.assertEqual(recommendation.reference, "online_coach")
        self.assertEqual(recommendation.selected_modules, ("social", "contact"))

    def test_unknown_profession_falls_back_to_module_selection(self):
        self.assertFalse(profession_needs_context("фотограф"))
        self.assertIsNone(recommend_preset("фотограф", "offline"))

    def test_client_can_add_and_remove_recommended_modules(self):
        recommendation = recommend_preset("косметолог", "offline")
        without_products = toggle_module(recommendation.selected_modules, "products")
        with_products_again = toggle_module(without_products, "products")

        self.assertEqual(without_products, ("core", "social", "contact"))
        self.assertEqual(with_products_again, ("core", "social", "contact", "products"))


if __name__ == "__main__":
    unittest.main()
