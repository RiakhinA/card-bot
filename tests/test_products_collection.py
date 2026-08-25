import unittest
from services.module_configuration import build_module_configuration
from services.module_selection import PRODUCTS_MODULE, next_module_flow, toggle_module
from services.products_collection import ProductValidationError, add_product

class ProductsModuleTest(unittest.TestCase):
    def test_products_module_can_be_selected(self):
        selected = toggle_module(("core",), PRODUCTS_MODULE)
        self.assertEqual(selected, ("core", "products")); self.assertEqual(next_module_flow(selected, ()), PRODUCTS_MODULE)
    def test_products_module_is_skipped_when_not_selected(self): self.assertEqual(next_module_flow(("core",), ()), "extras")
    def test_add_one_product(self):
        self.assertEqual(add_product([], "Consultation", "One hour", "https://example.com"), [{"name":"Consultation","description":"One hour","link":"https://example.com"}])
    def test_add_multiple_products_without_mutating_previous_items(self):
        first=add_product([], "One"); second=add_product(first, "Two", "Description", "https://example.com/two")
        self.assertEqual(len(first),1); self.assertEqual([item["name"] for item in second],["One","Two"])
    def test_name_is_required(self):
        with self.assertRaises(ProductValidationError): add_product([], "   ")
    def test_description_and_link_are_optional(self): self.assertEqual(add_product([], "Item")[0], {"name":"Item","description":"","link":""})
    def test_invalid_link_is_rejected(self):
        with self.assertRaises(ProductValidationError): add_product([], "Item", link="example.com")
    def test_selected_empty_products_are_preserved(self):
        selected, configuration=build_module_configuration({"name":"Test"}, selected_modules=("core","products"))
        self.assertEqual(selected,("core","products")); self.assertEqual(configuration["products"],{"items":[]})
    def test_products_are_mapped_to_module_configuration(self):
        items=add_product([], "Course", "Details", "https://example.com/course")
        selected, configuration=build_module_configuration({"product_values":items}, selected_modules=("core","products"))
        self.assertIn("products", selected); self.assertEqual(configuration["products"]["items"],items)
if __name__=="__main__": unittest.main()
