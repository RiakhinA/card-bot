"""Release 2 service for one validated Client Data Package per Application."""

from __future__ import annotations

from typing import Protocol

from models import Application, ClientDataPackage, ClientDataPackageStatus
from services.personal_card_policy import PERSONAL_CARD_POLICY
from services.products_collection import ProductValidationError, add_product


PERSONAL_CARD_TYPE = PERSONAL_CARD_POLICY.card_type
PERSONAL_CARD_TEMPLATE_V1_REFERENCE = PERSONAL_CARD_POLICY.template_reference


class ClientDataPackageError(RuntimeError):
    """Base error for controlled Client Data Package failures."""


class ApplicationNotFoundError(ClientDataPackageError):
    """Raised when a Package is requested for an unknown Application."""


class ApplicationRepository(Protocol):
    async def find_by_application_id(self, application_id: str) -> Application | None: ...


class ClientDataPackageRepository(Protocol):
    async def get_client_data_package_by_package_id(
        self, package_id: str
    ) -> ClientDataPackage | None: ...

    async def get_client_data_package_by_application_id(
        self, application_id: str
    ) -> ClientDataPackage | None: ...

    async def create_client_data_package(self, package: ClientDataPackage) -> None: ...


class ClientDataPackageService:
    """Creates a durable, validated package without changing Application state."""

    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        packages: ClientDataPackageRepository,
    ) -> None:
        self._applications = applications
        self._packages = packages

    async def create_package_for_application(
        self,
        application_id: str,
        *,
        card_type: str,
        template_reference: str,
    ) -> ClientDataPackage:
        application = await self._applications.find_by_application_id(application_id)
        if application is None:
            raise ApplicationNotFoundError(f"Application not found: {application_id}")

        existing = await self._packages.get_client_data_package_by_application_id(
            application.application_id
        )
        if existing:
            return existing

        missing_required_data = self._missing_required_data(
            application, card_type=card_type, template_reference=template_reference
        )
        confirmation_date = application.submission_data.get("client_confirmation_date")
        package_status = self._package_status(
            missing_required_data, confirmation_date=confirmation_date
        )
        package = ClientDataPackage.create(
            application_id=application.application_id,
            client_id=application.client_id,
            card_type=card_type,
            package_status=package_status,
            confirmed_data=application.submission_data,
            file_references=application.file_references,
            template_reference=template_reference,
            missing_required_data=missing_required_data,
            client_confirmation_date=confirmation_date,
        )
        await self._packages.create_client_data_package(package)
        return package

    async def get_package_by_id(self, package_id: str) -> ClientDataPackage | None:
        return await self._packages.get_client_data_package_by_package_id(package_id)

    async def get_package_by_application(
        self, application_id: str
    ) -> ClientDataPackage | None:
        return await self._packages.get_client_data_package_by_application_id(application_id)

    @staticmethod
    def _package_status(
        missing_required_data: tuple[str, ...], *, confirmation_date: str | None
    ) -> str:
        if missing_required_data:
            return ClientDataPackageStatus.INCOMPLETE
        if not confirmation_date:
            return ClientDataPackageStatus.NEEDS_CONFIRMATION
        return ClientDataPackageStatus.READY_FOR_PRODUCTION_PREPARATION

    @staticmethod
    def _missing_required_data(
        application: Application, *, card_type: str, template_reference: str
    ) -> tuple[str, ...]:
        data = application.submission_data
        missing: list[str] = []
        for key in ("name", "profession", "about"):
            if not str(data.get(key) or "").strip():
                missing.append(key)
        if not data.get("language_values"):
            missing.append("languages")
        if not application.file_references.get("profile_photo"):
            missing.append("profile_photo")
        if not str(card_type or "").strip():
            missing.append("card_type")
        if not str(template_reference or "").strip():
            missing.append("template_reference")
        if card_type == PERSONAL_CARD_TYPE and template_reference != PERSONAL_CARD_TEMPLATE_V1_REFERENCE:
            missing.append("personal_card_template_reference")

        selected_modules = tuple(data.get("selected_modules") or ())
        module_configuration = data.get("module_configuration")
        if "core" not in selected_modules:
            missing.append("selected_modules.core")
        if not isinstance(module_configuration, dict) or "core" not in module_configuration:
            missing.append("module_configuration.core")
        elif set(module_configuration) != set(selected_modules):
            missing.append("module_configuration.consistency")

        products = data.get("product_values", data.get("products", []))
        if "products" in selected_modules and not isinstance(products, list):
            missing.append("products.items")
        elif isinstance(products, list):
            for product in products:
                if not isinstance(product, dict):
                    missing.append("products.item")
                    break
                try:
                    add_product(
                        [],
                        product.get("name", ""),
                        product.get("description", ""),
                        product.get("link", ""),
                    )
                except ProductValidationError:
                    missing.append("products.validation")
                    break
        return tuple(dict.fromkeys(missing))
