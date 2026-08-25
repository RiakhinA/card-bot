import unittest
from services.module_configuration import build_module_configuration
from services.module_selection import CONTACT_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE, initial_selected_modules, next_module_flow, toggle_module
class ModuleSelectionTest(unittest.TestCase):
    def test_core_is_always_selected(self): self.assertEqual(initial_selected_modules(()), ("core",))
    def test_social_selected_starts_social_flow(self): self.assertEqual(next_module_flow(toggle_module(("core",), SOCIAL_MODULE), ()), SOCIAL_MODULE)
    def test_contact_selected_starts_contact_flow(self): self.assertEqual(next_module_flow(toggle_module(("core",), CONTACT_MODULE), ()), CONTACT_MODULE)
    def test_social_and_contact_run_in_order(self):
        selected=toggle_module(toggle_module(("core",), SOCIAL_MODULE), CONTACT_MODULE)
        self.assertEqual(next_module_flow(selected, ()), SOCIAL_MODULE); self.assertEqual(next_module_flow(selected, (SOCIAL_MODULE,)), CONTACT_MODULE)
    def test_products_selected_starts_products_flow(self): self.assertEqual(next_module_flow(toggle_module(("core",), PRODUCTS_MODULE), ()), PRODUCTS_MODULE)
    def test_selected_modules_run_in_supported_order(self):
        selected=toggle_module(toggle_module(toggle_module(("core",), SOCIAL_MODULE), CONTACT_MODULE), PRODUCTS_MODULE)
        self.assertEqual(next_module_flow(selected, (SOCIAL_MODULE, CONTACT_MODULE)), PRODUCTS_MODULE)
    def test_no_selection_skips_to_extras(self): self.assertEqual(next_module_flow(("core",), ()), "extras")
    def test_selected_module_is_in_configuration_without_fields(self):
        selected, configuration=build_module_configuration({"name":"Test"}, selected_modules=("core","social"))
        self.assertEqual(selected, ("core","social")); self.assertEqual(configuration["social"], {})
if __name__=="__main__": unittest.main()
