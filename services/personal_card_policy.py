"""Central Release 2 policy for the currently supported Personal Card."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CardTemplatePolicy:
    card_type: str
    template_reference: str


PERSONAL_CARD_POLICY = CardTemplatePolicy(
    card_type="Personal Card",
    template_reference="b574c163160e35966a821a74598a2e503abab0a7",
)


def current_personal_card_policy() -> CardTemplatePolicy:
    """Return the approved current Personal Card structural baseline."""
    return PERSONAL_CARD_POLICY
