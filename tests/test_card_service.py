import unittest

from models import Application, ApplicationStatus
from services.card_service import (
    ApplicationNotFoundError,
    CardCreationNotAllowed,
    CardService,
)


class FakeRepository:
    def __init__(self):
        self.applications = {}
        self.cards = {}
        self.created_cards = []

    async def find_by_application_id(self, application_id):
        return self.applications.get(application_id)

    async def find_card_by_application_id(self, application_id):
        return self.cards.get(application_id)

    async def create_card(self, card):
        self.cards[card.application_id] = card
        self.created_cards.append(card)


def make_application(status=ApplicationStatus.CREATING):
    return Application(
        application_id="APPLICATION-TEST",
        client_id="CLIENT-TEST",
        request_key="telegram:test",
        source="Telegram Bot",
        application_status=status,
        price_snapshot={"total": 900},
        submission_data={},
        file_references={},
        created_at="2026-08-25T00:00:00+00:00",
        updated_at="2026-08-25T00:00:00+00:00",
    )


class CardServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.service = CardService(
            applications=self.repository,
            cards=self.repository,
        )

    async def test_creates_card_for_creating_application(self):
        application = make_application()
        self.repository.applications[application.application_id] = application

        card = await self.service.create_card_for_application(application.application_id)

        self.assertTrue(card.card_id.startswith("CARD-"))
        self.assertEqual(card.client_id, application.client_id)
        self.assertEqual(card.application_id, application.application_id)
        self.assertEqual(len(self.repository.created_cards), 1)

    async def test_gets_card_by_application(self):
        application = make_application()
        self.repository.applications[application.application_id] = application
        created = await self.service.create_card_for_application(application.application_id)

        found = await self.service.get_card_by_application(application.application_id)

        self.assertEqual(found, created)

    async def test_duplicate_creation_returns_existing_card(self):
        application = make_application()
        self.repository.applications[application.application_id] = application

        first = await self.service.create_card_for_application(application.application_id)
        second = await self.service.create_card_for_application(application.application_id)

        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.created_cards), 1)

    async def test_unknown_application_is_controlled(self):
        with self.assertRaises(ApplicationNotFoundError):
            await self.service.create_card_for_application("APPLICATION-MISSING")

    async def test_card_creation_requires_creating_application(self):
        application = make_application(ApplicationStatus.APPROVED)
        self.repository.applications[application.application_id] = application

        with self.assertRaises(CardCreationNotAllowed):
            await self.service.create_card_for_application(application.application_id)

        self.assertEqual(self.repository.created_cards, [])


if __name__ == "__main__":
    unittest.main()
