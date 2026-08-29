import unittest

from models import (
    Application,
    ApplicationStatus,
    ClientDataPackage,
    ClientDataPackageStatus,
)
from services.application_card_draft_orchestration import (
    ApplicationCardDraftOrchestrationService,
    ApplicationWorkflowNotAllowed,
    ClientDataPackageNotFoundError,
    ClientDataPackageNotReadyError,
)
from services.application_lifecycle import ApplicationLifecycleService, ApplicationNotFoundError
from services.card_service import CardService, CardServiceError
from services.client_data_package import ClientDataPackageService
from services.client_draft_configuration import (
    ClientDraftConfigurationError,
    ClientDraftConfigurationService,
)


TEMPLATE_REFERENCE = "b574c163160e35966a821a74598a2e503abab0a7"


class FakeRepository:
    def __init__(self):
        self.applications = {}
        self.packages = {}
        self.cards_by_id = {}
        self.cards_by_application = {}
        self.configurations = {}
        self.created_cards = []
        self.created_configurations = []

    async def find_by_application_id(self, application_id):
        return self.applications.get(application_id)

    async def update_application(self, application):
        self.applications[application.application_id] = application

    async def create_application(self, application):
        self.applications[application.application_id] = application

    async def get_client_data_package_by_package_id(self, package_id):
        return next((p for p in self.packages.values() if p.package_id == package_id), None)

    async def get_client_data_package_by_application_id(self, application_id):
        return self.packages.get(application_id)

    async def create_client_data_package(self, package):
        self.packages[package.application_id] = package

    async def find_card_by_application_id(self, application_id):
        return self.cards_by_application.get(application_id)

    async def find_card_by_card_id(self, card_id):
        return self.cards_by_id.get(card_id)

    async def create_card(self, card):
        self.cards_by_id[card.card_id] = card
        self.cards_by_application[card.application_id] = card
        self.created_cards.append(card)

    async def get_current_client_draft_configuration(self, card_id):
        return self.configurations.get(card_id)

    async def create_client_draft_configuration(self, configuration):
        self.configurations[configuration.card_id] = configuration
        self.created_configurations.append(configuration)

    async def update_client_draft_configuration(self, configuration):
        self.configurations[configuration.card_id] = configuration


def make_application(status=ApplicationStatus.SUBMITTED):
    return Application(
        application_id="APPLICATION-TEST", client_id="CLIENT-TEST", request_key="telegram:test",
        source="Telegram Bot", application_status=status, price_snapshot={},
        submission_data={"unconfirmed": "must not be used for the draft"}, file_references={},
        created_at="2026-08-25T00:00:00+00:00", updated_at="2026-08-25T00:00:00+00:00",
    )


def make_package(application, status=ClientDataPackageStatus.READY_FOR_PRODUCTION_PREPARATION):
    confirmed_data = {
        "name": "Антон Ряхин",
        "profession": "Косметолог",
        "about": "Подтверждённое описание",
        "adaptive_mode": "about",
        "work_context": "offline",
        "preset_reference": "beauty_offline",
        "selected_modules": ["core", "social", "contact", "products"],
        "module_configuration": {
            "core": {"name": "Антон Ряхин"},
            "social": {"instagram": "https://instagram.com/riakhin"},
            "contact": {"telegram": "@riakhin"},
            "products": {"items": [{"name": "Услуга", "description": "", "link": "https://example.com"}]},
        },
        "messenger_values": {"telegram": "@riakhin"},
    }
    return ClientDataPackage.create(
        application_id=application.application_id, client_id=application.client_id,
        card_type="Personal Card", package_status=status, confirmed_data=confirmed_data,
        file_references={"profile_photo": {"file_id": "photo-1"}},
        template_reference=TEMPLATE_REFERENCE, client_confirmation_date="2026-08-25",
    )


class FailCardService:
    async def create_card_for_application(self, application_id):
        raise CardServiceError("card storage failed")


class FailOnceDraftService:
    def __init__(self, service):
        self._service = service
        self._failed = False

    async def create_configuration(self, *args, **kwargs):
        if not self._failed:
            self._failed = True
            raise ClientDraftConfigurationError("draft storage failed")
        return await self._service.create_configuration(*args, **kwargs)


class ApplicationCardDraftOrchestrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.application = make_application()
        self.repository.applications[self.application.application_id] = self.application
        self.package = make_package(self.application)
        self.repository.packages[self.application.application_id] = self.package
        self.lifecycle = ApplicationLifecycleService(applications=self.repository)
        self.package_service = ClientDataPackageService(
            applications=self.repository, packages=self.repository
        )
        self.card_service = CardService(applications=self.repository, cards=self.repository)
        self.draft_service = ClientDraftConfigurationService(
            applications=self.repository, cards=self.repository, configurations=self.repository
        )
        self.service = self.make_service()

    def make_service(self, *, cards=None, configurations=None):
        return ApplicationCardDraftOrchestrationService(
            lifecycle=self.lifecycle, packages=self.package_service,
            cards=cards or self.card_service, configurations=configurations or self.draft_service,
        )

    async def execute_workflow(self):
        return await self.service.create_card_draft_for_application(self.application.application_id)

    async def test_submitted_ready_package_creates_card_and_draft(self):
        result = await self.execute_workflow()
        self.assertEqual(result.application.application_status, ApplicationStatus.CREATING)
        self.assertEqual(self.repository.applications[self.application.application_id].application_status, ApplicationStatus.CREATING)
        self.assertEqual(result.card.application_id, self.application.application_id)
        self.assertEqual(result.configuration.card_id, result.card.card_id)

    async def test_draft_uses_package_reference_template_and_confirmed_snapshot(self):
        result = await self.execute_workflow()
        configuration = result.configuration
        self.assertEqual(configuration.client_data_package_id, self.package.package_id)
        self.assertEqual(configuration.template_reference, self.package.template_reference)
        self.assertEqual(configuration.client_data_snapshot, self.package.confirmed_data)
        self.assertNotIn("unconfirmed", configuration.client_data_snapshot)

    async def test_modules_are_preserved_in_draft(self):
        configuration = (await self.execute_workflow()).configuration
        self.assertEqual(configuration.selected_modules, ("core", "social", "messenger", "contact", "products"))
        self.assertEqual(configuration.module_configuration["messenger"]["telegram"][0]["value"], "@riakhin")
        self.assertNotIn("telegram", configuration.module_configuration["contact"])
        self.assertEqual(self.package.confirmed_data["module_configuration"]["contact"]["telegram"], "@riakhin")

    async def test_approved_application_skips_duplicate_approval(self):
        self.application = make_application(ApplicationStatus.APPROVED)
        self.repository.applications[self.application.application_id] = self.application
        self.package = make_package(self.application)
        self.repository.packages[self.application.application_id] = self.package
        result = await self.execute_workflow()
        self.assertEqual(result.application.application_status, ApplicationStatus.CREATING)

    async def test_creating_application_is_resumed_without_transition(self):
        self.application = make_application(ApplicationStatus.CREATING)
        self.repository.applications[self.application.application_id] = self.application
        self.package = make_package(self.application)
        self.repository.packages[self.application.application_id] = self.package
        result = await self.execute_workflow()
        self.assertEqual(result.application.application_status, ApplicationStatus.CREATING)

    async def test_repeat_call_reuses_card_and_draft(self):
        first = await self.execute_workflow()
        second = await self.execute_workflow()
        self.assertEqual(first.card, second.card)
        self.assertEqual(first.configuration, second.configuration)
        self.assertEqual(len(self.repository.created_cards), 1)
        self.assertEqual(len(self.repository.created_configurations), 1)

    async def test_unknown_application_is_controlled(self):
        with self.assertRaises(ApplicationNotFoundError):
            await self.service.create_card_draft_for_application("APPLICATION-MISSING")

    async def test_missing_package_does_not_change_application(self):
        self.repository.packages.clear()
        with self.assertRaises(ClientDataPackageNotFoundError):
            await self.execute_workflow()
        self.assertEqual(self.repository.applications[self.application.application_id].application_status, ApplicationStatus.SUBMITTED)

    async def test_incomplete_and_unconfirmed_packages_are_rejected_without_transition(self):
        for status in (
            ClientDataPackageStatus.INCOMPLETE,
            ClientDataPackageStatus.NEEDS_CONFIRMATION,
        ):
            with self.subTest(status=status):
                self.repository.packages[self.application.application_id] = make_package(self.application, status)
                with self.assertRaises(ClientDataPackageNotReadyError):
                    await self.execute_workflow()
                self.assertEqual(self.repository.applications[self.application.application_id].application_status, ApplicationStatus.SUBMITTED)

    async def test_invalid_application_state_is_rejected(self):
        self.application = make_application(ApplicationStatus.CANCELLED)
        self.repository.applications[self.application.application_id] = self.application
        self.repository.packages[self.application.application_id] = make_package(self.application)
        with self.assertRaises(ApplicationWorkflowNotAllowed):
            await self.execute_workflow()

    async def test_card_failure_leaves_resumable_creating_state_without_draft(self):
        self.service = self.make_service(cards=FailCardService())
        with self.assertRaises(CardServiceError):
            await self.execute_workflow()
        self.assertEqual(self.repository.applications[self.application.application_id].application_status, ApplicationStatus.CREATING)
        self.assertFalse(self.repository.created_cards)
        self.assertFalse(self.repository.created_configurations)

    async def test_draft_failure_reuses_existing_card_on_retry(self):
        self.service = self.make_service(configurations=FailOnceDraftService(self.draft_service))
        with self.assertRaises(ClientDraftConfigurationError):
            await self.execute_workflow()
        self.assertEqual(len(self.repository.created_cards), 1)
        self.assertFalse(self.repository.created_configurations)
        result = await self.execute_workflow()
        self.assertEqual(result.card, self.repository.created_cards[0])
        self.assertEqual(len(self.repository.created_cards), 1)
        self.assertEqual(len(self.repository.created_configurations), 1)


if __name__ == "__main__":
    unittest.main()
