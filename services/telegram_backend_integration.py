"""Composition helpers joining confirmed Telegram submissions to Release 2 services."""

from __future__ import annotations

from dataclasses import dataclass

from models import Application, ClientDataPackage
from services.application_card_draft_orchestration import (
    ApplicationCardDraftOrchestrationService,
    ApplicationCardDraftResult,
)
from services.application_lifecycle import ApplicationLifecycleService
from services.card_service import CardService
from services.client_data_package import ClientDataPackageService
from services.client_draft_configuration import ClientDraftConfigurationService
from services.personal_card_policy import CardTemplatePolicy, current_personal_card_policy


@dataclass(frozen=True)
class Release2CardDraftServices:
    packages: ClientDataPackageService
    orchestration: ApplicationCardDraftOrchestrationService


@dataclass(frozen=True)
class TelegramBackendIntegrationResult:
    package: ClientDataPackage
    workflow: ApplicationCardDraftResult


def build_release_2_card_draft_services_from_environment() -> Release2CardDraftServices:
    """Build existing Release 2 services over the configured Google Sheets adapter."""
    from storage.google_sheets import GoogleSheetsAdapter

    sheets = GoogleSheetsAdapter.from_environment()
    lifecycle = ApplicationLifecycleService(applications=sheets)
    packages = ClientDataPackageService(applications=sheets, packages=sheets)
    cards = CardService(applications=sheets, cards=sheets)
    configurations = ClientDraftConfigurationService(
        applications=sheets, cards=sheets, configurations=sheets
    )
    return Release2CardDraftServices(
        packages=packages,
        orchestration=ApplicationCardDraftOrchestrationService(
            lifecycle=lifecycle,
            packages=packages,
            cards=cards,
            configurations=configurations,
        ),
    )


async def create_card_draft_from_confirmed_application(
    application: Application,
    *,
    services: Release2CardDraftServices,
    policy: CardTemplatePolicy | None = None,
) -> TelegramBackendIntegrationResult:
    """Create/reuse Package, Card and Draft after explicit Telegram confirmation."""
    policy = policy or current_personal_card_policy()
    package = await services.packages.create_package_for_application(
        application.application_id,
        card_type=policy.card_type,
        template_reference=policy.template_reference,
    )
    workflow = await services.orchestration.create_card_draft_for_application(
        application.application_id
    )
    return TelegramBackendIntegrationResult(package=package, workflow=workflow)
