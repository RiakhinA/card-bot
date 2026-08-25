"""Pure submission rules shared by the Telegram handler and backend tests."""

from __future__ import annotations

from models import utc_now


def core_profession_required(data: dict) -> bool:
    """Direct mode collects profession as part of mandatory Core data."""
    return not str(data.get("profession") or "").strip()


def confirmed_submission_data(data: dict) -> dict:
    """Return a submission snapshot marked only by the final client action."""
    confirmed = dict(data)
    confirmed["client_confirmation_date"] = utc_now()
    return confirmed
