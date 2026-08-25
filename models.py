"""Persistent data models for Telegram Bot Evolution Release 2."""

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


def new_card_id() -> str:
    return f"CARD-{uuid4().hex[:12].upper()}"


def new_payment_id() -> str:
    return f"PAYMENT-{uuid4().hex[:12].upper()}"


def new_client_draft_configuration_id() -> str:
    return f"DRAFT-CONFIG-{uuid4().hex[:12].upper()}"


def new_client_data_package_id() -> str:
    return f"CLIENT-DATA-PACKAGE-{uuid4().hex[:12].upper()}"


class ApplicationStatus:
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    CREATING = "CREATING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CardStatus:
    DRAFT = "DRAFT"
    CREATING = "CREATING"
    READY = "READY"
    DELIVERED = "DELIVERED"
    ARCHIVED = "ARCHIVED"


class PaymentStatus:
    NOT_SELECTED = "NOT_SELECTED"
    WAITING_PAYMENT = "WAITING_PAYMENT"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class ClientDataPackageStatus:
    INCOMPLETE = "INCOMPLETE"
    NEEDS_CONFIRMATION = "NEEDS CONFIRMATION"
    READY_FOR_PRODUCTION_PREPARATION = "READY FOR PRODUCTION PREPARATION"


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
            application_status=ApplicationStatus.SUBMITTED,
            price_snapshot=price_snapshot,
            submission_data=submission_data,
            file_references=file_references,
            created_at=now,
            updated_at=now,
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Card:
    card_id: str
    client_id: str
    application_id: str
    status: str
    url: str | None
    language: str | None
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        client_id: str,
        application_id: str,
        language: str | None = None,
    ) -> "Card":
        now = utc_now()
        return cls(
            card_id=new_card_id(),
            client_id=client_id,
            application_id=application_id,
            status=CardStatus.DRAFT,
            url=None,
            language=language,
            created_at=now,
            updated_at=now,
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClientDraftConfiguration:
    """Current client-specific Draft Configuration for one durable Card."""

    configuration_id: str
    card_id: str
    application_id: str
    client_data_package_id: str
    client_data_snapshot: dict[str, Any]
    template_reference: str
    selected_modules: tuple[str, ...]
    module_configuration: dict[str, Any]
    configuration_version: int
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        card_id: str,
        application_id: str,
        client_data_package_id: str,
        client_data_snapshot: dict[str, Any],
        template_reference: str,
        selected_modules: tuple[str, ...] = (),
        module_configuration: dict[str, Any] | None = None,
    ) -> "ClientDraftConfiguration":
        now = utc_now()
        return cls(
            configuration_id=new_client_draft_configuration_id(),
            card_id=card_id,
            application_id=application_id,
            client_data_package_id=client_data_package_id,
            client_data_snapshot=client_data_snapshot,
            template_reference=template_reference,
            selected_modules=selected_modules,
            module_configuration=module_configuration or {},
            configuration_version=1,
            created_at=now,
            updated_at=now,
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClientDataPackage:
    """Validated production input prepared from one submitted Application."""

    package_id: str
    application_id: str
    client_id: str
    card_type: str
    package_status: str
    confirmed_data: dict[str, Any]
    file_references: dict[str, Any]
    template_reference: str
    missing_required_data: tuple[str, ...]
    client_confirmation_date: str | None
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        application_id: str,
        client_id: str,
        card_type: str,
        package_status: str,
        confirmed_data: dict[str, Any],
        file_references: dict[str, Any],
        template_reference: str,
        missing_required_data: tuple[str, ...] = (),
        client_confirmation_date: str | None = None,
    ) -> "ClientDataPackage":
        now = utc_now()
        return cls(
            package_id=new_client_data_package_id(),
            application_id=application_id,
            client_id=client_id,
            card_type=card_type,
            package_status=package_status,
            confirmed_data=dict(confirmed_data),
            file_references=dict(file_references),
            template_reference=template_reference,
            missing_required_data=tuple(missing_required_data),
            client_confirmation_date=client_confirmation_date,
            created_at=now,
            updated_at=now,
        )

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Payment:
    payment_id: str
    application_id: str
    amount: int | None = None
    currency: str = "UAH"
    status: str = PaymentStatus.NOT_SELECTED
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)
