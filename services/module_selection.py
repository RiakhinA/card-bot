"""Selection rules for the modules the current Telegram flow can collect."""
from __future__ import annotations
from services.module_configuration import CONTACT_MODULE, CORE_MODULE, LOCATION_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE
# Location is retained as a future contract, but is not collectable in the
# approved Pilot route until its Web Card representation is validated.
AVAILABLE_MODULES = (SOCIAL_MODULE, CONTACT_MODULE, PRODUCTS_MODULE)
def initial_selected_modules(selected_modules):
    selected = set(selected_modules)
    return (CORE_MODULE,) + tuple(module for module in AVAILABLE_MODULES if module in selected)
def toggle_module(selected_modules, module):
    if module not in AVAILABLE_MODULES:
        raise ValueError(f"Module is not available in Telegram collection: {module}")
    selected = set(initial_selected_modules(selected_modules))
    if module in selected: selected.remove(module)
    else: selected.add(module)
    return initial_selected_modules(tuple(selected))
def next_module_flow(selected_modules, completed_modules):
    selected, completed = set(initial_selected_modules(selected_modules)), set(completed_modules)
    for module in AVAILABLE_MODULES:
        if module in selected and module not in completed: return module
    return "extras"
