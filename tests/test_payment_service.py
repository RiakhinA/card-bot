import unittest
from unittest.mock import patch

from models import Application, ApplicationStatus, Payment, PaymentStatus
from services.payment_service import (
    ApplicationNotFoundError,
    InvalidPaymentTransition,
    PaymentNotFoundError,
    PaymentService,
)


class FakeRepository:
    def __init__(self):
        self.applications = {}
        self.payments = {}
        self.created_payments = []
        self.updated_payments = []

    async def find_by_application_id(self, application_id):
        return self.applications.get(application_id)

    async def create_payment(self, payment):
        self.payments[payment.application_id] = payment
        self.created_payments.append(payment)

    async def get_payment_by_application_id(self, application_id):
        return self.payments.get(application_id)

    async def update_payment(self, payment):
        self.payments[payment.application_id] = payment
        self.updated_payments.append(payment)


def make_application():
    return Application(
        application_id="APPLICATION-TEST",
        client_id="CLIENT-TEST",
        request_key="telegram:test",
        source="Telegram Bot",
        application_status=ApplicationStatus.SUBMITTED,
        price_snapshot={},
        submission_data={},
        file_references={},
        created_at="2026-08-25T00:00:00+00:00",
        updated_at="2026-08-25T00:00:00+00:00",
    )


class PaymentServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.application = make_application()
        self.repository.applications[self.application.application_id] = self.application
        self.service = PaymentService(
            applications=self.repository,
            payments=self.repository,
        )

    async def create_payment(self):
        with patch("services.payment_service.utc_now", return_value="2026-08-25T10:00:00+00:00"):
            return await self.service.create_payment(
                self.application.application_id,
                amount=900,
                metadata={"method": "manual"},
            )

    async def test_creates_waiting_payment_with_stable_identifier(self):
        payment = await self.create_payment()

        self.assertTrue(payment.payment_id.startswith("PAYMENT-"))
        self.assertEqual(payment.application_id, self.application.application_id)
        self.assertEqual(payment.status, PaymentStatus.WAITING_PAYMENT)
        self.assertEqual(payment.amount, 900)
        self.assertEqual(payment.currency, "UAH")
        self.assertEqual(payment.created_at, "2026-08-25T10:00:00+00:00")
        self.assertEqual(payment.updated_at, payment.created_at)

    async def test_gets_payment_by_application_id(self):
        created = await self.create_payment()
        self.assertEqual(
            await self.service.get_payment_by_application_id(self.application.application_id),
            created,
        )

    async def test_duplicate_create_returns_existing_payment(self):
        first = await self.create_payment()
        second = await self.create_payment()

        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.created_payments), 1)

    async def test_unknown_application_is_controlled(self):
        with self.assertRaises(ApplicationNotFoundError):
            await self.service.create_payment("APPLICATION-MISSING")

    async def test_not_selected_to_waiting_payment(self):
        self.repository.payments[self.application.application_id] = Payment(
            payment_id="PAYMENT-TEST", application_id=self.application.application_id,
            status=PaymentStatus.NOT_SELECTED,
            created_at="2026-08-25T09:00:00+00:00",
            updated_at="2026-08-25T09:00:00+00:00",
        )

        updated = await self.service.update_payment_status(
            self.application.application_id, PaymentStatus.WAITING_PAYMENT
        )

        self.assertEqual(updated.status, PaymentStatus.WAITING_PAYMENT)

    async def test_waiting_payment_can_be_paid_or_failed(self):
        await self.create_payment()
        paid = await self.service.update_payment_status(
            self.application.application_id, PaymentStatus.PAID
        )
        self.assertEqual(paid.status, PaymentStatus.PAID)

        self.repository.payments[self.application.application_id] = Payment(
            payment_id="PAYMENT-FAILED-TEST",
            application_id=self.application.application_id,
            status=PaymentStatus.WAITING_PAYMENT,
            created_at="2026-08-25T10:00:00+00:00",
            updated_at="2026-08-25T10:00:00+00:00",
        )
        failed = await self.service.update_payment_status(
            self.application.application_id, PaymentStatus.FAILED
        )
        self.assertEqual(failed.status, PaymentStatus.FAILED)

    async def test_paid_can_be_refunded(self):
        await self.create_payment()
        await self.service.update_payment_status(self.application.application_id, PaymentStatus.PAID)

        refunded = await self.service.update_payment_status(
            self.application.application_id, PaymentStatus.REFUNDED
        )

        self.assertEqual(refunded.status, PaymentStatus.REFUNDED)

    async def test_invalid_transition_keeps_existing_payment_unchanged(self):
        payment = await self.create_payment()

        with self.assertRaises(InvalidPaymentTransition):
            await self.service.update_payment_status(self.application.application_id, PaymentStatus.REFUNDED)

        self.assertEqual(self.repository.payments[self.application.application_id], payment)
        self.assertEqual(self.repository.updated_payments, [])

    async def test_repeated_paid_is_idempotent(self):
        await self.create_payment()
        paid = await self.service.update_payment_status(self.application.application_id, PaymentStatus.PAID)
        repeated = await self.service.update_payment_status(self.application.application_id, PaymentStatus.PAID)

        self.assertEqual(repeated, paid)
        self.assertEqual(len(self.repository.updated_payments), 1)

    async def test_paid_to_waiting_and_refunded_to_paid_are_rejected(self):
        await self.create_payment()
        await self.service.update_payment_status(self.application.application_id, PaymentStatus.PAID)

        with self.assertRaises(InvalidPaymentTransition):
            await self.service.update_payment_status(self.application.application_id, PaymentStatus.WAITING_PAYMENT)

        await self.service.update_payment_status(self.application.application_id, PaymentStatus.REFUNDED)
        with self.assertRaises(InvalidPaymentTransition):
            await self.service.update_payment_status(self.application.application_id, PaymentStatus.PAID)

    async def test_transition_updates_updated_at_and_preserves_created_at(self):
        payment = await self.create_payment()

        with patch("services.payment_service.utc_now", return_value="2026-08-25T11:00:00+00:00"):
            updated = await self.service.update_payment_status(
                self.application.application_id, PaymentStatus.PAID
            )

        self.assertEqual(updated.created_at, payment.created_at)
        self.assertEqual(updated.updated_at, "2026-08-25T11:00:00+00:00")

    async def test_unknown_payment_is_controlled(self):
        with self.assertRaises(PaymentNotFoundError):
            await self.service.update_payment_status("APPLICATION-WITHOUT-PAYMENT", PaymentStatus.PAID)


if __name__ == "__main__":
    unittest.main()
