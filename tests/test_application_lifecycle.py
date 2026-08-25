import unittest
from unittest.mock import patch

from models import Application, ApplicationStatus
from services.application_lifecycle import (
    ApplicationLifecycleService,
    InvalidApplicationTransition,
)


class FakeApplicationRepository:
    def __init__(self):
        self.applications = {}
        self.updated = []

    async def find_by_application_id(self, application_id):
        return self.applications.get(application_id)

    async def create_application(self, application):
        self.applications[application.application_id] = application

    async def update_application(self, application):
        self.applications[application.application_id] = application
        self.updated.append(application)


def make_application(status=ApplicationStatus.SUBMITTED):
    return Application(
        application_id="APPLICATION-TEST",
        client_id="CLIENT-TEST",
        request_key="telegram:test",
        source="Telegram Bot",
        application_status=status,
        price_snapshot={"total": 900},
        submission_data={},
        file_references={},
        created_at="2026-08-22T00:00:00+00:00",
        updated_at="2026-08-22T00:00:00+00:00",
    )


class ApplicationLifecycleServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeApplicationRepository()
        self.service = ApplicationLifecycleService(applications=self.repository)

    async def _store(self, application):
        await self.service.create_application(application)

    async def test_submitted_to_approved(self):
        application = make_application()
        await self._store(application)

        with patch("services.application_lifecycle.utc_now", return_value="2026-08-22T01:00:00+00:00"):
            updated = await self.service.approve_application(application.application_id)

        self.assertEqual(updated.application_status, ApplicationStatus.APPROVED)
        self.assertEqual(self.repository.applications[application.application_id], updated)

    async def test_approved_to_creating(self):
        application = make_application(ApplicationStatus.APPROVED)
        await self._store(application)

        updated = await self.service.start_card_creation(application.application_id)

        self.assertEqual(updated.application_status, ApplicationStatus.CREATING)

    async def test_creating_to_completed(self):
        application = make_application(ApplicationStatus.CREATING)
        await self._store(application)

        updated = await self.service.complete_application(application.application_id)

        self.assertEqual(updated.application_status, ApplicationStatus.COMPLETED)

    async def test_submitted_to_cancelled(self):
        application = make_application()
        await self._store(application)

        updated = await self.service.cancel_application(application.application_id)

        self.assertEqual(updated.application_status, ApplicationStatus.CANCELLED)

    async def test_invalid_transition_is_controlled_and_does_not_change_state(self):
        application = make_application(ApplicationStatus.COMPLETED)
        await self._store(application)

        with self.assertRaises(InvalidApplicationTransition):
            await self.service.approve_application(application.application_id)

        unchanged = self.repository.applications[application.application_id]
        self.assertEqual(unchanged.application_status, ApplicationStatus.COMPLETED)
        self.assertEqual(unchanged.updated_at, application.updated_at)
        self.assertEqual(self.repository.updated, [])

    async def test_transition_updates_timestamp(self):
        application = make_application()
        await self._store(application)

        with patch("services.application_lifecycle.utc_now", return_value="2026-08-22T01:00:00+00:00"):
            updated = await self.service.approve_application(application.application_id)

        self.assertEqual(updated.updated_at, "2026-08-22T01:00:00+00:00")
        self.assertNotEqual(updated.updated_at, application.updated_at)


if __name__ == "__main__":
    unittest.main()
