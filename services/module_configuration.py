"""Minimal module-oriented mapping for persisted Telegram card submissions."""

from __future__ import annotations

from typing import Any

CORE_MODULE = "core"
SOCIAL_MODULE = "social"
CONTACT_MODULE = "contact"
PRODUCTS_MODULE = "products"

SOCIAL_FIELDS = ("instagram", "facebook", "linkedin", "youtube", "tiktok", "site")
CONTACT_FIELDS = ("telegram", "whatsapp", "viber", "phone", "other")


def build_module_configuration(
    submission_data: dict[str, Any],
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    """Map the existing Telegram submission shape into neutral Card modules.

    This is a foundation, not a registry or a UI selector. Empty optional modules
    are omitted; a later collection flow can supply products without changing
    the Card or Client Draft architecture.
    """
    configuration: dict[str, dict[str, Any]] = {
        CORE_MODULE: {
            "name": submission_data.get("name"),
            "description": submission_data.get("about"),
            "languages": {
                "mode": submission_data.get("language_mode"),
                "values": list(submission_data.get("language_values", [])),
                "translation_mode": submission_data.get("translation_mode"),
                "translation_text": submission_data.get("translation_text"),
            },
            "style": {
                "color_note": submission_data.get("color_note"),
            },
            "additional_actions": list(submission_data.get("extra_keys", [])),
        }
    }

    social = _selected_values(submission_data.get("social_values"), SOCIAL_FIELDS)
    if social:
        configuration[SOCIAL_MODULE] = social

    contact = _selected_values(submission_data.get("messenger_values"), CONTACT_FIELDS)
    if contact:
        configuration[CONTACT_MODULE] = contact

    products = submission_data.get("product_values", submission_data.get("products"))
    if products:
        configuration[PRODUCTS_MODULE] = {"items": products}

    selected_modules = tuple(configuration.keys())
    return selected_modules, configuration


def _selected_values(values: Any, allowed_fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(values, dict):
        return {}
    return {
        field: values[field]
        for field in allowed_fields
        if values.get(field) not in (None, "")
    }
