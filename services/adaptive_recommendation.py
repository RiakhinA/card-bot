"""User-facing adaptive recommendation rules for the Release 2 Telegram UX."""
from __future__ import annotations

from dataclasses import dataclass

from services.module_configuration import CONTACT_MODULE, PRODUCTS_MODULE, SOCIAL_MODULE

GOALS = (
    "Получать обращения",
    "Удобно передавать контакты",
    "Рассказывать о себе",
    "Показывать услуги",
    "Показывать работы и проекты",
    "Получать записи",
    "Собрать ссылки в одном месте",
)

@dataclass(frozen=True)
class AdaptiveRecommendation:
    scenario: str
    selected_modules: tuple[str, ...]
    explanation: str


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("ё", "е").split())


def recommend_structure(profession: str, work_context: str, goals: tuple[str, ...]) -> AdaptiveRecommendation:
    p = _norm(profession)
    goal_set = set(goals)

    if any(x in p for x in ("фотограф", "дизайнер", "видеограф", "видео", "модель")):
        scenario = "creative_portfolio"
    elif any(x in p for x in ("косметолог", "визажист", "маникюр", "бровист", "парикмахер", "мастер")):
        scenario = "visual_service"
    elif any(x in p for x in ("массаж", "тренер", "йог", "фитнес", "нутрициолог")):
        scenario = "body_wellness"
    elif any(x in p for x in ("психолог", "коуч", "консульт", "преподав", "учител", "эксперт")):
        scenario = "online_expert"
    else:
        scenario = "generic"

    modules = []
    if goal_set & {"Получать обращения", "Удобно передавать контакты", "Получать записи"}:
        modules.append(CONTACT_MODULE)
    if goal_set & {"Показывать услуги", "Получать записи"}:
        modules.append(PRODUCTS_MODULE)
    if goal_set & {"Рассказывать о себе", "Показывать работы и проекты", "Собрать ссылки в одном месте"}:
        modules.append(SOCIAL_MODULE)

    if scenario == "creative_portfolio" and SOCIAL_MODULE not in modules:
        modules.append(SOCIAL_MODULE)
    if scenario in {"visual_service", "body_wellness", "online_expert"}:
        if SOCIAL_MODULE not in modules:
            modules.append(SOCIAL_MODULE)
        if PRODUCTS_MODULE not in modules and ("Получать обращения" in goal_set or "Показывать услуги" in goal_set):
            modules.append(PRODUCTS_MODULE)
    if not modules:
        modules = [SOCIAL_MODULE, CONTACT_MODULE]

    labels = {SOCIAL_MODULE: "соцсети", CONTACT_MODULE: "контакты", PRODUCTS_MODULE: "услуги"}
    listed = ", ".join(labels[m] for m in modules)
    context_text = {"online": "онлайн", "offline": "офлайн", "hybrid": "онлайн и офлайн"}.get(work_context, "в вашем формате работы")
    explanation = f"Вы указали профессию «{profession}» и формат «{context_text}». Поэтому я предложил {listed}."
    return AdaptiveRecommendation(scenario, tuple(modules), explanation)
