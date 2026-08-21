import unittest
from types import SimpleNamespace

from models import Application, Client
from services.application_service import ApplicationService


class FakeSheets:
    def __init__(self):
        self.clients = {}
        self.applications = {}

    async def find_by_telegram_user_id(self, telegram_user_id):
        return self.clients.get(telegram_user_id)

    async def create_client(self, client):
        self.clients[client.telegram_user_id] = client

    async def find_by_request_key(self, request_key):
        return self.applications.get(request_key)

    async def create_application(self, application):
        self.applications[application.request_key] = application


class FakeDrive:
    def __init__(self):
        self.calls = []

    async def upload_telegram_file(self, **kwargs):
        self.calls.append(kwargs)
        return {"file_id": kwargs["telegram_file_id"], "name": kwargs["filename"], "web_view_link": ""}


class ApplicationServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sheets = FakeSheets()
        self.drive = FakeDrive()
        self.service = ApplicationService(clients=self.sheets, applications=self.sheets, files=self.drive)
        self.user = SimpleNamespace(id=17, full_name="Test User", language_code="uk")
        self.data = {"name": "Test User", "photo_id": "photo-1", "color_photo_id": "color-1"}
        self.price = {"total": 900, "prepay": 600, "addon": 0, "balance": 300}

    async def test_new_submission_creates_client_application_and_file_references(self):
        result = await self.service.persist_submission(
            bot=object(), telegram_user=self.user, data=self.data,
            price_snapshot=self.price, request_key="telegram:17:17:1",
        )

        self.assertTrue(result.created)
        self.assertEqual(result.client.telegram_user_id, 17)
        self.assertEqual(result.application.client_id, result.client.client_id)
        self.assertEqual(result.application.application_status, "SUBMITTED")
        self.assertEqual(len(self.drive.calls), 2)
        self.assertIn("profile_photo", result.application.file_references)

    async def test_repeat_callback_reuses_existing_application_without_duplicate_files(self):
        first = await self.service.persist_submission(
            bot=object(), telegram_user=self.user, data=self.data,
            price_snapshot=self.price, request_key="telegram:17:17:1",
        )
        second = await self.service.persist_submission(
            bot=object(), telegram_user=self.user, data=self.data,
            price_snapshot=self.price, request_key="telegram:17:17:1",
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.application.application_id, second.application.application_id)
        self.assertEqual(len(self.drive.calls), 2)

    async def test_existing_user_keeps_existing_client_id(self):
        existing = Client.create(telegram_user_id=17, name="Old Name")
        await self.sheets.create_client(existing)

        result = await self.service.persist_submission(
            bot=object(), telegram_user=self.user, data=self.data,
            price_snapshot=self.price, request_key="telegram:17:17:2",
        )

        self.assertEqual(result.client.client_id, existing.client_id)


if __name__ == "__main__":
    unittest.main()
