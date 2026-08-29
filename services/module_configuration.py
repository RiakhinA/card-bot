"""Minimal module-oriented mapping for persisted Telegram card submissions."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

CORE_MODULE = "core"
SOCIAL_MODULE = "social"
CONTACT_MODULE = "contact"
MESSENGER_MODULE = "messenger"
PRODUCTS_MODULE = "products"
LOCATION_MODULE = "location"

SOCIAL_FIELDS = ("instagram", "facebook", "linkedin", "youtube", "tiktok", "other")
MESSENGER_FIELDS = ("telegram", "whatsapp", "viber", "other")


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
    communication = normalize_communication(submission_data)
    contact = communication["contacts"]
    if contact or CONTACT_MODULE in explicitly_selected:
        configuration[CONTACT_MODULE] = contact
    messengers = communication["messengers"]
    if messengers:
        configuration[MESSENGER_MODULE] = messengers
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
    ordered = (CORE_MODULE, SOCIAL_MODULE, MESSENGER_MODULE, CONTACT_MODULE, LOCATION_MODULE, PRODUCTS_MODULE)
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
            {
                **({"id": str(phone["id"])} if phone.get("id") else {}),
                **({"item_id": str(phone["item_id"])} if not phone.get("id") and phone.get("item_id") else {}),
                "label": str(phone.get("label") or "Другой"),
                "number": str(phone.get("number") or ""),
            }
            for phone in phones
            if isinstance(phone, dict) and str(phone.get("number") or "").strip()
        ]
    legacy_phone = (submission_data.get("messenger_values") or {}).get("phone")
    return [{"label": "Другой", "number": str(legacy_phone)}] if legacy_phone else []


def normalize_email_values(submission_data: dict[str, Any]) -> list[dict[str, str]]:
    """Read target email items and the legacy scalar email without mutation."""
    emails = submission_data.get("email_values")
    if isinstance(emails, list):
        return [
            _identified_item("email", item, "value")
            for item in emails
            if isinstance(item, dict) and str(item.get("value") or item.get("email") or "").strip()
        ]
    legacy_email = (submission_data.get("messenger_values") or {}).get("email")
    if legacy_email in (None, ""):
        return []
    return [_identified_item("email", {"value": legacy_email}, "value", legacy=True)]


def normalize_messenger_values(submission_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Normalize legacy scalar messenger fields into identifiable entries."""
    values = submission_data.get("messenger_values")
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    for key in MESSENGER_FIELDS:
        value = values.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, list):
            entries = [
                _identified_item(key, item, "value")
                for item in value
                if isinstance(item, dict) and str(item.get("value") or "").strip()
            ]
        elif isinstance(value, dict):
            entries = [_identified_item(key, value, "value", legacy=True)]
        else:
            entries = [_identified_item(key, {"value": value}, "value", legacy=True)]
        if entries:
            normalized[key] = entries
    return normalized


def normalize_communication(submission_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the non-destructive Contacts/Messengers downstream contract."""
    phones = [_identified_item("phone", phone, "number") for phone in normalize_phone_values(submission_data)]
    emails = normalize_email_values(submission_data)
    contacts: dict[str, Any] = {}
    if phones:
        contacts["phones"] = phones
    if emails:
        contacts["emails"] = emails
    return {"contacts": contacts, "messengers": normalize_messenger_values(submission_data)}


def module_configuration_matches_selected(
    selected_modules: tuple[str, ...], module_configuration: dict[str, Any]
) -> bool:
    """Accept a normalized Messenger expansion of the legacy contact selection."""
    expected = set(selected_modules)
    if CONTACT_MODULE in expected and MESSENGER_MODULE in module_configuration:
        expected.add(MESSENGER_MODULE)
    return set(module_configuration) == expected


def _identified_item(kind: str, item: dict[str, Any], value_key: str, *, legacy: bool = False) -> dict[str, Any]:
    value = item.get(value_key) or item.get("email") or ""
    normalized = {key: value for key, value in item.items() if key not in {"id", "item_id", "email"}}
    normalized[value_key] = str(value)
    stable_id = item.get("id") or item.get("item_id")
    if not stable_id:
        seed = f"{kind}:{normalized.get('label', '')}:{normalized.get('name', '')}:{normalized[value_key]}"
        prefix = "legacy" if legacy else kind
        stable_id = f"{prefix}-{sha256(seed.encode('utf-8')).hexdigest()[:12]}"
    return {"id": str(stable_id), **normalized}
