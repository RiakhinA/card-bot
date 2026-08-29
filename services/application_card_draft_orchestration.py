"""Release 2 backend orchestration from a ready Package to Card Draft."""

from __future__ import annotations

from dataclasses import dataclass

from models import (
    Application,
    ApplicationStatus,
    Card,
    ClientDataPackage,
    ClientDataPackageStatus,
    ClientDraftConfiguration,
)
from services.application_lifecycle import ApplicationLifecycleService
from services.card_service import CardService
from services.client_data_package import ClientDataPackageService
from services.client_draft_configuration import ClientDraftConfigurationService
from services.module_configuration import build_module_configuration


class ApplicationCardDraftOrchestrationError(RuntimeError):
    """Base error for controlled Application-to-Draft orchestration failures."""


class ClientDataPackageNotFoundError(ApplicationCardDraftOrchestrationError):
    """Raised when an Application has no durable Client Data Package."""


class ClientDataPackageNotReadyError(ApplicationCardDraftOrchestrationError):
    """Raised when a Package has not passed the production-preparation gate."""


class ClientDataPackageMismatchError(ApplicationCardDraftOrchestrationError):
    """Raised when a Package does not belong to the requested Application."""


class ApplicationWorkflowNotAllowed(ApplicationCardDraftOrchestrationError):
    """Raised when this operation cannot safely resume an Application state."""


@dataclass(frozen=True)
class ApplicationCardDraftResult:
    application: Application
    package: ClientDataPackage
    card: Card
    configuration: ClientDraftConfiguration


class ApplicationCardDraftOrchestrationService:
    """Coordinates existing business services without Telegram or Payment concerns."""

    def __init__(
        self,
        *,
        lifecycle: ApplicationLifecycleService,
        packages: ClientDataPackageService,
        cards: CardService,
        configurations: ClientDraftConfigurationService,
    ) -> None:
        self._lifecycle = lifecycle
        self._packages = packages
        self._cards = cards
        self._configurations = configurations

    async def create_card_draft_for_application(
        self, application_id: str
    ) -> ApplicationCardDraftResult:
        application = await self._lifecycle.get_application(application_id)
        package = await self._packages.get_package_by_application(application.application_id)
        if package is None:
            raise ClientDataPackageNotFoundError(
                f"Client Data Package not found for Application: {application.application_id}"
            )
        self._validate_package(application, package)
        application = await self._advance_to_creating(application)

        # CardService is idempotent and returns the existing Card when present.
        card = await self._cards.create_card_for_application(application.application_id)
        data = package.confirmed_data
        selected_modules, module_configuration = build_module_configuration(
            data, selected_modules=tuple(data.get("selected_modules", ()))
        )
        # Draft Service is idempotent and returns the current configuration when present.
        configuration = await self._configurations.create_configuration(
            card.card_id,
            client_data_package_id=package.package_id,
            client_data_snapshot=dict(data),
            template_reference=package.template_reference,
            selected_modules=selected_modules,
            module_configuration=module_configuration,
        )
        return ApplicationCardDraftResult(
            application=application,
            package=package,
            card=card,
            configuration=configuration,
        )

    @staticmethod
    def _validate_package(application: Application, package: ClientDataPackage) -> None:
        if package.application_id != application.application_id or package.client_id != application.client_id:
            raise ClientDataPackageMismatchError(
                "Client Data Package must belong to the requested Application and Client"
            )
        if package.package_status != ClientDataPackageStatus.READY_FOR_PRODUCTION_PREPARATION:
            raise ClientDataPackageNotReadyError(
                "Client Data Package must be READY FOR PRODUCTION PREPARATION; "
                f"received {package.package_status}"
            )

    async def _advance_to_creating(self, application: Application) -> Application:
        if application.application_status == ApplicationStatus.SUBMITTED:
            application = await self._lifecycle.approve_application(application.application_id)
        if application.application_status == ApplicationStatus.APPROVED:
            application = await self._lifecycle.start_card_creation(application.application_id)
        if application.application_status != ApplicationStatus.CREATING:
            raise ApplicationWorkflowNotAllowed(
                "Application-to-Draft orchestration requires SUBMITTED, APPROVED, or "
                f"CREATING; received {application.application_status}"
            )
        return application
