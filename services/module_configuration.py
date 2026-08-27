"""Minimal module-oriented mapping for persisted Telegram card submissions."""

from __future__ import annotations

from typing import Any

CORE_MODULE = "core"
SOCIAL_MODULE = "social"
CONTACT_MODULE = "contact"
PRODUCTS_MODULE = "products"
LOCATION_MODULE = "location"

SOCIAL_FIELDS = ("instagram", "facebook", "linkedin", "youtube", "tiktok", "site")
CONTACT_FIELDS = ("telegram", "whatsapp", "viber", "phone", "other")


def build_module_configuration(
    submission_data: dict[str, Any],
    *,
    selected_modules: tuple[str, ...] | None = None,
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

    explicitly_selected = set(selected_modules or ())
    social = _selected_values(submission_data.get("social_values"), SOCIAL_FIELDS)
    if social or SOCIAL_MODULE in explicitly_selected:
        configuration[SOCIAL_MODULE] = social
    contact = _selected_values(submission_data.get("messenger_values"), CONTACT_FIELDS)
    phones = normalize_phone_values(submission_data)
    contact.pop("phone", None)
    if phones:
        contact["phones"] = phones
    if contact or CONTACT_MODULE in explicitly_selected:
        configuration[CONTACT_MODULE] = contact
    location = {
        key: submission_data[key]
        for key in ("city", "workplace_address")
        if submission_data.get(key) not in (None, "")
    }
    if location or LOCATION_MODULE in explicitly_selected:
        configuration[LOCATION_MODULE] = location
    products = submission_data.get("product_values", submission_data.get("products"))
    if products or PRODUCTS_MODULE in explicitly_selected:
        configuration[PRODUCTS_MODULE] = {"items": products or []}
    ordered = (CORE_MODULE, SOCIAL_MODULE, CONTACT_MODULE, LOCATION_MODULE, PRODUCTS_MODULE)
    return tuple(module for module in ordered if module in configuration), configuration


def _selected_values(values: Any, allowed_fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(values, dict):
        return {}
    return {
        field: values[field]
        for field in allowed_fields
        if values.get(field) not in (None, "")
    }


def normalize_phone_values(submission_data: dict[str, Any]) -> list[dict[str, str]]:
    """Expose Pilot phone collection while preserving a legacy scalar phone."""
    phones = submission_data.get("phone_values")
    if isinstance(phones, list):
        return [
            {"label": str(phone.get("label") or "Другой"), "number": str(phone.get("number") or "")}
            for phone in phones
            if isinstance(phone, dict) and str(phone.get("number") or "").strip()
        ]
    legacy_phone = (submission_data.get("messenger_values") or {}).get("phone")
    return [{"label": "Другой", "number": str(legacy_phone)}] if legacy_phone else []
