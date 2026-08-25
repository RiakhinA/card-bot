import unittest
from dataclasses import replace
import sys
from types import ModuleType


try:
    import google.oauth2.service_account  # noqa: F401
    import googleapiclient.discovery  # noqa: F401
except ModuleNotFoundError:
    google = ModuleType("google")
    oauth2 = ModuleType("google.oauth2")
    service_account = ModuleType("google.oauth2.service_account")
    service_account.Credentials = type("Credentials", (), {})
    googleapiclient = ModuleType("googleapiclient")
    discovery = ModuleType("googleapiclient.discovery")
    discovery.build = lambda *args, **kwargs: None
    sys.modules.update({
        "google": google,
        "google.oauth2": oauth2,
        "google.oauth2.service_account": service_account,
        "googleapiclient": googleapiclient,
        "googleapiclient.discovery": discovery,
    })

from models import Payment, PaymentStatus
from storage.google_sheets import GoogleSheetsAdapter, SHEETS


class FakePaymentAdapter(GoogleSheetsAdapter):
    """In-memory adapter exercising the public Payment storage contract."""

    def __init__(self):
        self.rows = []

    async def _ensure_schema(self):
        return None

    def _append(self, title, values):
        self.assertEqual(title, "Payments")
        self.rows.append(dict(zip(SHEETS["Payments"], values)))

    def _read_rows(self, title):
        self.assertEqual(title, "Payments")
        return list(self.rows)

    def _update_payment(self, payment):
        for index, row in enumerate(self.rows):
            if row["payment_id"] == payment.payment_id:
                self.rows[index] = dict(zip(SHEETS["Payments"], self._payment_values(payment)))
                return
        raise RuntimeError(f"Payment not found: {payment.payment_id}")

    def assertEqual(self, left, right):
        if left != right:
            raise AssertionError(f"{left!r} != {right!r}")


def make_payment():
    return Payment(
        payment_id="PAYMENT-TEST",
        application_id="APPLICATION-TEST",
        amount=0,
        currency="UAH",
        status=PaymentStatus.WAITING_PAYMENT,
        created_at="2026-08-25T10:00:00+00:00",
        updated_at="2026-08-25T10:05:00+00:00",
        metadata={"source": "manual", "note": "test"},
    )


class PaymentStorageContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_persists_every_payment_field(self):
        adapter = FakePaymentAdapter()
        payment = make_payment()

        await adapter.create_payment(payment)

        self.assertEqual(adapter.rows[0], {
            "payment_id": "PAYMENT-TEST",
            "application_id": "APPLICATION-TEST",
            "amount": "0",
            "currency": "UAH",
            "status": "WAITING_PAYMENT",
            "created_at": "2026-08-25T10:00:00+00:00",
            "updated_at": "2026-08-25T10:05:00+00:00",
            "metadata": '{"source": "manual", "note": "test"}',
        })

    async def test_get_by_application_id_round_trips_payment(self):
        adapter = FakePaymentAdapter()
        payment = make_payment()
        await adapter.create_payment(payment)

        restored = await adapter.get_payment_by_application_id(payment.application_id)

        self.assertEqual(restored, payment)

    async def test_get_by_application_id_returns_none_when_missing(self):
        self.assertIsNone(await FakePaymentAdapter().get_payment_by_application_id("APPLICATION-MISSING"))

    async def test_update_replaces_existing_payment_without_losing_fields(self):
        adapter = FakePaymentAdapter()
        payment = make_payment()
        await adapter.create_payment(payment)
        updated = replace(
            payment,
            amount=1200,
            status=PaymentStatus.PAID,
            updated_at="2026-08-25T11:00:00+00:00",
            metadata={"source": "manual", "receipt": "R-1"},
        )

        await adapter.update_payment(updated)

        self.assertEqual(len(adapter.rows), 1)
        self.assertEqual(await adapter.get_payment_by_application_id(updated.application_id), updated)

    def test_serialization_deserialization_preserves_empty_optional_amount(self):
        payment = Payment(payment_id="PAYMENT-EMPTY", application_id="APPLICATION-TEST")

        values = GoogleSheetsAdapter._payment_values(payment)
        restored = GoogleSheetsAdapter._payment_from_row(dict(zip(SHEETS["Payments"], values)))

        self.assertEqual(restored, payment)


if __name__ == "__main__":
    unittest.main()
