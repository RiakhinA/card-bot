"""Small rules-based recommendations for the existing Telegram modules."""

from __future__ import annotations

from dataclasses import dataclass

from services.module_configuration import CONTACT_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE


@dataclass(frozen=True)
class PresetRecommendation:
    reference: str
    selected_modules: tuple[str, ...]


_CONTEXTUAL_PROFESSIONS = {
    "косметолог",
    "cosmetologist",
    "коуч",
    "coach",
}

_PRESETS = {
    ("косметолог", "offline"): PresetRecommendation(
        "beauty_offline", (SOCIAL_MODULE, CONTACT_MODULE, PRODUCTS_MODULE)
    ),
    ("cosmetologist", "offline"): PresetRecommendation(
        "beauty_offline", (SOCIAL_MODULE, CONTACT_MODULE, PRODUCTS_MODULE)
    ),
    ("коуч", "online"): PresetRecommendation(
        "online_coach", (SOCIAL_MODULE, CONTACT_MODULE)
    ),
    ("coach", "online"): PresetRecommendation(
        "online_coach", (SOCIAL_MODULE, CONTACT_MODULE)
    ),
}


def normalize_profession(value: str) -> str:
    return " ".join(value.strip().lower().replace("ё", "е").split())


def profession_needs_context(profession: str) -> bool:
    return normalize_profession(profession) in _CONTEXTUAL_PROFESSIONS


def recommend_preset(profession: str, work_context: str) -> PresetRecommendation | None:
    return _PRESETS.get((normalize_profession(profession), work_context))
