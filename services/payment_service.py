"""Release 2 business service for provider-independent Payment records."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from models import Application, Payment, PaymentStatus, new_payment_id, utc_now


class PaymentServiceError(RuntimeError):
    """Base error for controlled Payment Service failures."""


class ApplicationNotFoundError(PaymentServiceError):
    """Raised when a Payment references an unknown Application."""


class PaymentNotFoundError(PaymentServiceError):
    """Raised when a Payment operation references an unknown Application."""


class InvalidPaymentTransition(PaymentServiceError):
    """Raised when a requested Payment status transition is not allowed."""


class ApplicationRepository(Protocol):
    async def find_by_application_id(self, application_id: str) -> Application | None: ...


class PaymentRepository(Protocol):
    async def create_payment(self, payment: Payment) -> None: ...

    async def get_payment_by_application_id(self, application_id: str) -> Payment | None: ...

    async def update_payment(self, payment: Payment) -> None: ...


class PaymentService:
    """Owns Payment records and their lifecycle, independently of UI and providers."""

    _ALLOWED_TRANSITIONS = {
        PaymentStatus.NOT_SELECTED: {PaymentStatus.WAITING_PAYMENT},
        PaymentStatus.WAITING_PAYMENT: {PaymentStatus.PAID, PaymentStatus.FAILED},
        PaymentStatus.PAID: {PaymentStatus.REFUNDED},
    }

    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        payments: PaymentRepository,
    ) -> None:
        self._applications = applications
        self._payments = payments

    async def create_payment(
        self,
        application_id: str,
        *,
        amount: int | None = None,
        currency: str = "UAH",
        metadata: dict[str, Any] | None = None,
    ) -> Payment:
        application = await self._applications.find_by_application_id(application_id)
        if application is None:
            raise ApplicationNotFoundError(f"Application not found: {application_id}")

        existing = await self._payments.get_payment_by_application_id(application_id)
        if existing:
            return existing

        now = utc_now()
        payment = Payment(
            payment_id=new_payment_id(),
            application_id=application.application_id,
            amount=amount,
            currency=currency,
            status=PaymentStatus.WAITING_PAYMENT,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        await self._payments.create_payment(payment)
        return payment

    async def get_payment_by_application_id(self, application_id: str) -> Payment | None:
        return await self._payments.get_payment_by_application_id(application_id)

    async def update_payment_status(self, application_id: str, target_status: str) -> Payment:
        payment = await self._payments.get_payment_by_application_id(application_id)
        if payment is None:
            raise PaymentNotFoundError(f"Payment not found for Application: {application_id}")

        if payment.status == target_status:
            return payment

        allowed = self._ALLOWED_TRANSITIONS.get(payment.status, set())
        if target_status not in allowed:
            raise InvalidPaymentTransition(
                f"Cannot transition {payment.status} to {target_status}"
            )

        updated = replace(payment, status=target_status, updated_at=utc_now())
        await self._payments.update_payment(updated)
        return updated
