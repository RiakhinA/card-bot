"""Release 2 business service linking one Application to one Card."""

from __future__ import annotations

from typing import Protocol

from models import Application, ApplicationStatus, Card


class CardServiceError(RuntimeError):
    """Base error for controlled Card Service failures."""


class ApplicationNotFoundError(CardServiceError):
    """Raised when card creation references an unknown Application."""


class CardCreationNotAllowed(CardServiceError):
    """Raised when an Application is not ready for Card creation."""


class ApplicationRepository(Protocol):
    async def find_by_application_id(self, application_id: str) -> Application | None: ...


class CardRepository(Protocol):
    async def find_card_by_application_id(self, application_id: str) -> Card | None: ...

    async def create_card(self, card: Card) -> None: ...


class CardService:
    """Creates one durable Card for an Application already in CREATING state."""

    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        cards: CardRepository,
    ) -> None:
        self._applications = applications
        self._cards = cards

    async def create_card_for_application(
        self,
        application_id: str,
        *,
        language: str | None = None,
    ) -> Card:
        application = await self._applications.find_by_application_id(application_id)
        if application is None:
            raise ApplicationNotFoundError(f"Application not found: {application_id}")

        if application.application_status != ApplicationStatus.CREATING:
            raise CardCreationNotAllowed(
                "Card creation requires Application status CREATING; "
                f"received {application.application_status}"
            )

        existing = await self._cards.find_card_by_application_id(application_id)
        if existing:
            return existing

        card = Card.create(
            client_id=application.client_id,
            application_id=application.application_id,
            language=language,
        )
        await self._cards.create_card(card)
        return card

    async def get_card_by_application(self, application_id: str) -> Card | None:
        return await self._cards.find_card_by_application_id(application_id)
