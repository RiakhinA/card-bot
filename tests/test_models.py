import unittest

from models import Application, Client, Payment


class ModelsTest(unittest.TestCase):
    def test_client_creation_uses_stable_typed_identifier(self):
        client = Client.create(telegram_user_id=42, name="Test User", interface_language="uk")

        self.assertTrue(client.client_id.startswith("CLIENT-"))
        self.assertEqual(client.telegram_user_id, 42)
        self.assertEqual(client.status, "ACTIVE")

    def test_application_creation_has_submitted_status_and_snapshot(self):
        application = Application.create(
            client_id="CLIENT-TEST",
            request_key="telegram:42:42:1",
            price_snapshot={"total": 900, "prepay": 600, "addon": 0, "balance": 300},
            submission_data={"name": "Test"},
            file_references={},
        )

        self.assertTrue(application.application_id.startswith("APPLICATION-"))
        self.assertEqual(application.application_status, "SUBMITTED")
        self.assertEqual(application.price_snapshot["total"], 900)

    def test_payment_is_prepared_without_enabling_payment_flow(self):
        payment = Payment(payment_id="PAYMENT-TEST", application_id="APPLICATION-TEST")

        self.assertEqual(payment.status, "NOT_SELECTED")
        self.assertEqual(payment.metadata, {})


if __name__ == "__main__":
    unittest.main()
