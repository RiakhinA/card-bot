"""Release 2 business service for durable Application lifecycle transitions."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from models import Application, ApplicationStatus, utc_now


class ApplicationLifecycleError(RuntimeError):
    """Base error for controlled application-lifecycle failures."""


class ApplicationNotFoundError(ApplicationLifecycleError):
    """Raised when an operation references an unknown application."""


class InvalidApplicationTransition(ApplicationLifecycleError):
    """Raised when a requested status transition is not allowed."""


class ApplicationLifecycleRepository(Protocol):
    async def find_by_application_id(self, application_id: str) -> Application | None: ...

    async def create_application(self, application: Application) -> None: ...

    async def update_application(self, application: Application) -> None: ...


class ApplicationLifecycleService:
    """Owns Release 2 Application status transitions outside Telegram UI."""

    _ALLOWED_TRANSITIONS = {
        ApplicationStatus.SUBMITTED: {
            ApplicationStatus.APPROVED,
            ApplicationStatus.CANCELLED,
        },
        ApplicationStatus.APPROVED: {
            ApplicationStatus.CREATING,
            ApplicationStatus.CANCELLED,
        },
        ApplicationStatus.CREATING: {
            ApplicationStatus.COMPLETED,
            ApplicationStatus.CANCELLED,
        },
    }

    def __init__(self, *, applications: ApplicationLifecycleRepository) -> None:
        self._applications = applications

    async def create_application(self, application: Application) -> Application:
        existing = await self._applications.find_by_application_id(application.application_id)
        if existing:
            return existing
        await self._applications.create_application(application)
        return application

    async def approve_application(self, application_id: str) -> Application:
        return await self._transition(application_id, ApplicationStatus.APPROVED)

    async def start_card_creation(self, application_id: str) -> Application:
        return await self._transition(application_id, ApplicationStatus.CREATING)

    async def complete_application(self, application_id: str) -> Application:
        return await self._transition(application_id, ApplicationStatus.COMPLETED)

    async def cancel_application(self, application_id: str) -> Application:
        return await self._transition(application_id, ApplicationStatus.CANCELLED)

    async def _transition(self, application_id: str, target_status: str) -> Application:
        application = await self._applications.find_by_application_id(application_id)
        if application is None:
            raise ApplicationNotFoundError(f"Application not found: {application_id}")

        allowed = self._ALLOWED_TRANSITIONS.get(application.application_status, set())
        if target_status not in allowed:
            raise InvalidApplicationTransition(
                f"Cannot transition {application.application_status} to {target_status}"
            )

        updated = replace(
            application,
            application_status=target_status,
            updated_at=utc_now(),
        )
        await self._applications.update_application(updated)
        return updated
