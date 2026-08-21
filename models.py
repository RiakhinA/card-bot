"""Persistent data models for Telegram Bot Evolution Release 1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_client_id() -> str:
    return f"CLIENT-{uuid4().hex[:12].upper()}"


def new_application_id() -> str:
    return f"APPLICATION-{uuid4().hex[:12].upper()}"


@dataclass(frozen=True)
class Client:
    client_id: str
    telegram_user_id: int
    name: str
    source: str
    interface_language: str | None
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        telegram_user_id: int,
        name: str,
        interface_language: str | None = None,
        source: str = "Telegram Bot",
    ) -> "Client":
        now = utc_now()
        return cls(
            client_id=new_client_id(),
            telegram_user_id=telegram_user_id,
            name=name,
            source=source,
            interface_language=interface_language,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Application:
    application_id: str
    client_id: str
    request_key: str
    source: str
    application_status: str
    price_snapshot: dict[str, int]
    submission_data: dict[str, Any]
    file_references: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        client_id: str,
        request_key: str,
        price_snapshot: dict[str, int],
        submission_data: dict[str, Any],
        file_references: dict[str, Any],
        source: str = "Telegram Bot",
    ) -> "Application":
        now = utc_now()
        return cls(
            application_id=new_application_id(),
            client_id=client_id,
            request_key=request_key,
            source=source,
            application_status="SUBMITTED",
            price_snapshot=price_snapshot,
            submission_data=submission_data,
            file_references=file_references,
            created_at=now,
            updated_at=now,
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Payment:
    application_id: str
    payment_method_selected: str | None = None
    payment_status: str = "NOT_SELECTED"
    payment_created_at: str | None = None
    payment_updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)
