"""Release 2 service for a Card's current Client Draft Configuration."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Protocol

from models import Application, Card, ClientDraftConfiguration, utc_now


class ClientDraftConfigurationError(RuntimeError):
    """Base error for controlled Client Draft Configuration failures."""


class CardNotFoundError(ClientDraftConfigurationError):
    """Raised when a configuration references an unknown Card."""


class ApplicationNotFoundError(ClientDraftConfigurationError):
    """Raised when the Card's Application is unavailable."""


class ClientDraftConfigurationNotFoundError(ClientDraftConfigurationError):
    """Raised when no current configuration exists for a Card."""


class ApplicationRepository(Protocol):
    async def find_by_application_id(self, application_id: str) -> Application | None: ...


class CardRepository(Protocol):
    async def find_card_by_card_id(self, card_id: str) -> Card | None: ...


class ClientDraftConfigurationRepository(Protocol):
    async def get_current_client_draft_configuration(
        self, card_id: str
    ) -> ClientDraftConfiguration | None: ...

    async def create_client_draft_configuration(
        self, configuration: ClientDraftConfiguration
    ) -> None: ...

    async def update_client_draft_configuration(
        self, configuration: ClientDraftConfiguration
    ) -> None: ...


class ClientDraftConfigurationService:
    """Owns one current, versioned Draft Configuration per durable Card."""

    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        cards: CardRepository,
        configurations: ClientDraftConfigurationRepository,
    ) -> None:
        self._applications = applications
        self._cards = cards
        self._configurations = configurations

    async def create_configuration(
        self,
        card_id: str,
        *,
        client_data_package_id: str,
        client_data_snapshot: dict[str, Any],
        template_reference: str,
        selected_modules: tuple[str, ...] = (),
        module_configuration: dict[str, Any] | None = None,
    ) -> ClientDraftConfiguration:
        card, application = await self._validate_card_and_application(card_id)
        existing = await self._configurations.get_current_client_draft_configuration(card.card_id)
        if existing:
            return existing

        configuration = ClientDraftConfiguration.create(
            card_id=card.card_id,
            application_id=application.application_id,
            client_data_package_id=client_data_package_id,
            client_data_snapshot=dict(client_data_snapshot),
            template_reference=template_reference,
            selected_modules=tuple(selected_modules),
            module_configuration=dict(module_configuration or {}),
        )
        await self._configurations.create_client_draft_configuration(configuration)
        return configuration

    async def get_current_configuration(
        self, card_id: str
    ) -> ClientDraftConfiguration | None:
        return await self._configurations.get_current_client_draft_configuration(card_id)

    async def update_configuration(
        self,
        card_id: str,
        *,
        client_data_snapshot: dict[str, Any],
        template_reference: str,
        selected_modules: tuple[str, ...],
        module_configuration: dict[str, Any],
    ) -> ClientDraftConfiguration:
        await self._validate_card_and_application(card_id)
        current = await self._configurations.get_current_client_draft_configuration(card_id)
        if current is None:
            raise ClientDraftConfigurationNotFoundError(
                f"Client Draft Configuration not found for Card: {card_id}"
            )

        updated = replace(
            current,
            client_data_snapshot=dict(client_data_snapshot),
            template_reference=template_reference,
            selected_modules=tuple(selected_modules),
            module_configuration=dict(module_configuration),
            configuration_version=current.configuration_version + 1,
            updated_at=utc_now(),
        )
        await self._configurations.update_client_draft_configuration(updated)
        return updated

    async def _validate_card_and_application(self, card_id: str) -> tuple[Card, Application]:
        card = await self._cards.find_card_by_card_id(card_id)
        if card is None:
            raise CardNotFoundError(f"Card not found: {card_id}")

        application = await self._applications.find_by_application_id(card.application_id)
        if application is None:
            raise ApplicationNotFoundError(
                f"Application not found: {card.application_id}"
            )
        if application.client_id != card.client_id:
            raise ClientDraftConfigurationError(
                "Card and Application must belong to the same Client"
            )
        return card, application
