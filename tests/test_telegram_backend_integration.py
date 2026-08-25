import unittest
from unittest.mock import patch

from services.telegram_submission_contract import confirmed_submission_data, core_profession_required
from models import Application, ApplicationStatus, ClientDataPackageStatus
from services.application_card_draft_orchestration import ClientDataPackageNotReadyError
from services.application_lifecycle import ApplicationLifecycleService
from services.card_service import CardService
from services.client_data_package import ClientDataPackageService
from services.client_draft_configuration import ClientDraftConfigurationService
from services.telegram_backend_integration import (
    Release2CardDraftServices,
    create_card_draft_from_confirmed_application,
)


class FakeRepository:
    def __init__(self):
        self.applications, self.packages = {}, {}
        self.cards_by_id, self.cards_by_application, self.configurations = {}, {}, {}
        self.created_cards, self.created_configurations = [], []

    async def find_by_application_id(self, application_id): return self.applications.get(application_id)
    async def update_application(self, application): self.applications[application.application_id] = application
    async def create_application(self, application): self.applications[application.application_id] = application
    async def get_client_data_package_by_package_id(self, package_id): return next((p for p in self.packages.values() if p.package_id == package_id), None)
    async def get_client_data_package_by_application_id(self, application_id): return self.packages.get(application_id)
    async def create_client_data_package(self, package): self.packages[package.application_id] = package
    async def find_card_by_application_id(self, application_id): return self.cards_by_application.get(application_id)
    async def find_card_by_card_id(self, card_id): return self.cards_by_id.get(card_id)
    async def create_card(self, card):
        self.cards_by_id[card.card_id] = card
        self.cards_by_application[card.application_id] = card
        self.created_cards.append(card)
    async def get_current_client_draft_configuration(self, card_id): return self.configurations.get(card_id)
    async def create_client_draft_configuration(self, configuration):
        self.configurations[configuration.card_id] = configuration
        self.created_configurations.append(configuration)
    async def update_client_draft_configuration(self, configuration): self.configurations[configuration.card_id] = configuration


def application_for_mode(mode, *, profession="Косметолог", modules=None, confirmation=True):
    modules = modules or ["core", "social", "contact", "products"]
    configuration = {"core": {"name": "Клиент"}}
    if "social" in modules: configuration["social"] = {"instagram": "https://instagram.com/example"}
    if "contact" in modules: configuration["contact"] = {"telegram": "@example"}
    if "products" in modules: configuration["products"] = {"items": [{"name": "Услуга", "description": "", "link": "https://example.com"}]}
    data = {
        "adaptive_mode": mode, "name": "Клиент", "profession": profession,
        "about": "Подтверждённое описание", "language_values": ["Русский"],
        "selected_modules": modules, "module_configuration": configuration,
        "social_values": configuration.get("social", {}),
        "messenger_values": configuration.get("contact", {}),
        "product_values": configuration.get("products", {}).get("items", []),
    }
    if mode == "about": data.update(work_context="offline", preset_reference="beauty_offline")
    if confirmation: data["client_confirmation_date"] = "2026-08-25T12:00:00+00:00"
    return Application(
        application_id=f"APPLICATION-{mode}", client_id=f"CLIENT-{mode}", request_key=f"telegram:{mode}",
        source="Telegram Bot", application_status=ApplicationStatus.SUBMITTED, price_snapshot={},
        submission_data=data, file_references={"profile_photo": {"file_id": "photo-1"}},
        created_at="2026-08-25T00:00:00+00:00", updated_at="2026-08-25T00:00:00+00:00",
    )


class TelegramBackendIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRepository()
        lifecycle = ApplicationLifecycleService(applications=self.repository)
        packages = ClientDataPackageService(applications=self.repository, packages=self.repository)
        cards = CardService(applications=self.repository, cards=self.repository)
        configurations = ClientDraftConfigurationService(applications=self.repository, cards=self.repository, configurations=self.repository)
        from services.application_card_draft_orchestration import ApplicationCardDraftOrchestrationService
        self.services = Release2CardDraftServices(
            packages=packages,
            orchestration=ApplicationCardDraftOrchestrationService(lifecycle=lifecycle, packages=packages, cards=cards, configurations=configurations),
        )

    async def submit(self, application):
        self.repository.applications[application.application_id] = application
        return await create_card_draft_from_confirmed_application(application, services=self.services)

    async def test_adaptive_mode_preserves_profession_preset_and_final_modules(self):
        result = await self.submit(application_for_mode("about", modules=["core", "social", "contact"]))
        snapshot = result.workflow.configuration.client_data_snapshot
        self.assertEqual(result.package.package_status, ClientDataPackageStatus.READY_FOR_PRODUCTION_PREPARATION)
        self.assertEqual(snapshot["profession"], "Косметолог")
        self.assertEqual(snapshot["preset_reference"], "beauty_offline")
        self.assertEqual(result.workflow.configuration.selected_modules, ("core", "social", "contact"))

    async def test_direct_mode_preserves_profession_without_preset(self):
        result = await self.submit(application_for_mode("direct", profession="Фотограф", modules=["core", "products"]))
        snapshot = result.workflow.configuration.client_data_snapshot
        self.assertEqual(snapshot["profession"], "Фотограф")
        self.assertNotIn("work_context", snapshot)
        self.assertNotIn("preset_reference", snapshot)
        self.assertEqual(result.workflow.configuration.selected_modules, ("core", "products"))

    async def test_repeat_submission_reuses_package_card_and_draft(self):
        application = application_for_mode("about")
        first, second = await self.submit(application), await self.submit(application)
        self.assertEqual(first.package, second.package)
        self.assertEqual(first.workflow.card, second.workflow.card)
        self.assertEqual(first.workflow.configuration, second.workflow.configuration)
        self.assertEqual(len(self.repository.created_cards), 1)
        self.assertEqual(len(self.repository.created_configurations), 1)

    async def test_missing_confirmation_or_profession_blocks_before_card_creation(self):
        for application in (application_for_mode("direct", confirmation=False), application_for_mode("direct", profession="")):
            with self.subTest(application=application.application_id):
                self.repository.applications[application.application_id] = application
                with self.assertRaises(ClientDataPackageNotReadyError):
                    await create_card_draft_from_confirmed_application(application, services=self.services)
                self.assertFalse(self.repository.created_cards)


class TelegramCoreDecisionTest(unittest.TestCase):
    def test_direct_mode_requires_profession_inside_core_but_adaptive_does_not_repeat_it(self):
        self.assertTrue(core_profession_required({"adaptive_mode": "direct"}))
        self.assertFalse(core_profession_required({"adaptive_mode": "about", "profession": "Косметолог"}))

    def test_opening_review_does_not_confirm_and_final_action_does(self):
        original = {"name": "Клиент"}
        with patch("services.telegram_submission_contract.utc_now", return_value="2026-08-25T12:00:00+00:00"):
            confirmed = confirmed_submission_data(original)
        self.assertNotIn("client_confirmation_date", original)
        self.assertEqual(confirmed["client_confirmation_date"], "2026-08-25T12:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
