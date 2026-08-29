import unittest
from unittest.mock import patch

from models import Application, ApplicationStatus, Card
from services.client_draft_configuration import (
    CardNotFoundError,
    ClientDraftConfigurationNotFoundError,
    ClientDraftConfigurationService,
)


class FakeRepository:
    def __init__(self):
        self.applications = {}
        self.cards = {}
        self.configurations = {}
        self.created_configurations = []
        self.updated_configurations = []

    async def find_by_application_id(self, application_id):
        return self.applications.get(application_id)

    async def find_card_by_card_id(self, card_id):
        return self.cards.get(card_id)

    async def get_current_client_draft_configuration(self, card_id):
        return self.configurations.get(card_id)

    async def create_client_draft_configuration(self, configuration):
        self.configurations[configuration.card_id] = configuration
        self.created_configurations.append(configuration)

    async def update_client_draft_configuration(self, configuration):
        self.configurations[configuration.card_id] = configuration
        self.updated_configurations.append(configuration)


def make_application():
    return Application(
        application_id="APPLICATION-TEST", client_id="CLIENT-TEST",
        request_key="telegram:test", source="Telegram Bot",
        application_status=ApplicationStatus.CREATING, price_snapshot={},
        submission_data={}, file_references={},
        created_at="2026-08-25T00:00:00+00:00",
        updated_at="2026-08-25T00:00:00+00:00",
    )


def make_card():
    return Card(
        card_id="CARD-TEST", client_id="CLIENT-TEST",
        application_id="APPLICATION-TEST", status="DRAFT", url=None,
        language="ru", created_at="2026-08-25T00:00:00+00:00",
        updated_at="2026-08-25T00:00:00+00:00",
    )


class ClientDraftConfigurationServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.application = make_application()
        self.card = make_card()
        self.repository.applications[self.application.application_id] = self.application
        self.repository.cards[self.card.card_id] = self.card
        self.service = ClientDraftConfigurationService(
            applications=self.repository, cards=self.repository,
            configurations=self.repository,
        )

    async def create(self):
        return await self.service.create_configuration(
            self.card.card_id,
            client_data_package_id="PACKAGE-TEST",
            client_data_snapshot={"name": "Антон", "contacts": ["telegram"]},
            template_reference="personal-card-template-v1.0",
            selected_modules=("social", "qr"),
            module_configuration={"social": {"enabled": True}, "qr": {"enabled": True}},
        )

    async def test_creates_configuration_with_required_relationships_and_contract(self):
        configuration = await self.create()
        self.assertEqual(configuration.card_id, self.card.card_id)
        self.assertEqual(configuration.application_id, self.application.application_id)
        self.assertEqual(configuration.client_data_package_id, "PACKAGE-TEST")
        self.assertEqual(configuration.client_data_snapshot["name"], "Антон")
        self.assertEqual(configuration.template_reference, "personal-card-template-v1.0")
        self.assertEqual(configuration.selected_modules, ("social", "qr"))
        self.assertEqual(configuration.module_configuration["qr"]["enabled"], True)
        self.assertEqual(configuration.configuration_version, 1)

    async def test_builds_configuration_from_persisted_bot_submission(self):
        self.application = Application(
            **{
                **self.application.to_record(),
                "submission_data": {
                    "name": "Антон Ряхин",
                    "about": "Помогаю разобраться",
                    "language_values": ["Русский", "Українська"],
                    "social_values": {"instagram": "https://instagram.com/riakhin"},
                    "messenger_values": {"telegram": "@riakhin_anton"},
                },
            }
        )
        self.repository.applications[self.application.application_id] = self.application

        configuration = await self.service.create_configuration_from_application(
            self.card.card_id,
            client_data_package_id="PACKAGE-TEST",
            template_reference="personal-card-template-v1.0",
        )

        self.assertEqual(configuration.selected_modules, ("core", "social", "messenger"))
        self.assertEqual(
            configuration.module_configuration["social"]["instagram"],
            "https://instagram.com/riakhin",
        )
        self.assertEqual(
            configuration.module_configuration["messenger"]["telegram"][0]["value"],
            "@riakhin_anton",
        )
        self.assertEqual(configuration.client_data_snapshot["name"], "Антон Ряхин")

    async def test_gets_current_configuration(self):
        created = await self.create()
        found = await self.service.get_current_configuration(self.card.card_id)
        self.assertEqual(found, created)

    async def test_duplicate_create_returns_current_configuration(self):
        first = await self.create()
        second = await self.create()
        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.created_configurations), 1)

    async def test_update_replaces_current_configuration_and_increments_version(self):
        await self.create()
        with patch("services.client_draft_configuration.utc_now", return_value="2026-08-25T01:00:00+00:00"):
            updated = await self.service.update_configuration(
                self.card.card_id,
                client_data_snapshot={"name": "Антон Ряхин"},
                template_reference="personal-card-template-v1.0",
                selected_modules=("social", "products"),
                module_configuration={"products": {"enabled": True}},
            )
        self.assertEqual(updated.configuration_version, 2)
        self.assertEqual(updated.updated_at, "2026-08-25T01:00:00+00:00")
        self.assertEqual(updated.selected_modules, ("social", "products"))
        self.assertEqual(self.repository.configurations[self.card.card_id], updated)

    async def test_unknown_card_is_controlled(self):
        with self.assertRaises(CardNotFoundError):
            await self.service.create_configuration(
                "CARD-MISSING", client_data_package_id="PACKAGE-TEST",
                client_data_snapshot={}, template_reference="template",
            )

    async def test_update_without_current_configuration_is_controlled(self):
        with self.assertRaises(ClientDraftConfigurationNotFoundError):
            await self.service.update_configuration(
                self.card.card_id, client_data_snapshot={}, template_reference="template",
                selected_modules=(), module_configuration={},
            )


if __name__ == "__main__":
    unittest.main()
