"""Release 1 persistence orchestration, isolated from Telegram UI handlers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from models import Application, Client


class StorageError(RuntimeError):
    """Raised when Release 1 storage cannot safely persist a submission."""


class ClientRepository(Protocol):
    async def find_by_telegram_user_id(self, telegram_user_id: int) -> Client | None: ...

    async def create_client(self, client: Client) -> None: ...


class ApplicationRepository(Protocol):
    async def find_by_request_key(self, request_key: str) -> Application | None: ...

    async def create_application(self, application: Application) -> None: ...


class FileRepository(Protocol):
    async def upload_telegram_file(
        self,
        *,
        bot: Any,
        client_id: str,
        application_id: str,
        telegram_file_id: str,
        category: str,
        filename: str,
    ) -> dict[str, str]: ...


@dataclass(frozen=True)
class SubmissionResult:
    client: Client
    application: Application
    created: bool


class ApplicationService:
    """Creates durable Client and Application records after user confirmation."""

    def __init__(
        self,
        *,
        clients: ClientRepository,
        applications: ApplicationRepository,
        files: FileRepository,
    ) -> None:
        self._clients = clients
        self._applications = applications
        self._files = files

    async def persist_submission(
        self,
        *,
        bot: Any,
        telegram_user: Any,
        data: dict[str, Any],
        price_snapshot: dict[str, int],
        request_key: str,
    ) -> SubmissionResult:
        existing_application = await self._applications.find_by_request_key(request_key)
        if existing_application:
            client = await self._clients.find_by_telegram_user_id(telegram_user.id)
            if not client:
                raise StorageError("Existing application has no matching Client record")
            return SubmissionResult(client=client, application=existing_application, created=False)

        client = await self._clients.find_by_telegram_user_id(telegram_user.id)
        if not client:
            client = Client.create(
                telegram_user_id=telegram_user.id,
                name=telegram_user.full_name,
                interface_language=getattr(telegram_user, "language_code", None),
            )
            await self._clients.create_client(client)

        submission_data = dict(data)
        application = Application.create(
            client_id=client.client_id,
            request_key=request_key,
            price_snapshot=price_snapshot,
            submission_data=submission_data,
            file_references={},
        )
        file_references, upload_errors = await self._upload_submission_files(
            bot=bot,
            client_id=client.client_id,
            application_id=application.application_id,
            data=data,
        )
        if upload_errors:
            submission_data["media_upload_status"] = {"status": "partial" if file_references else "failed", "failed": upload_errors}
        elif data.get("photo_id") or data.get("color_photo_id"):
            submission_data["media_upload_status"] = {"status": "complete", "failed": []}
        application = Application(**{**application.to_record(), "submission_data": submission_data, "file_references": file_references})
        await self._applications.create_application(application)
        return SubmissionResult(client=client, application=application, created=True)

    async def _upload_submission_files(
        self,
        *,
        bot: Any,
        client_id: str,
        application_id: str,
        data: dict[str, Any],
    ) -> tuple[dict[str, dict[str, str]], list[str]]:
        references: dict[str, dict[str, str]] = {}
        errors: list[str] = []
        photo_id = data.get("photo_id")
        if photo_id:
            try:
                references["profile_photo"] = await self._files.upload_telegram_file(
                    bot=bot, client_id=client_id, application_id=application_id,
                    telegram_file_id=photo_id, category="photos", filename="profile-photo.jpg",
                )
            except Exception:
                errors.append("profile_photo")
        color_photo_id = data.get("color_photo_id")
        if color_photo_id:
            try:
                references["style_reference"] = await self._files.upload_telegram_file(
                    bot=bot, client_id=client_id, application_id=application_id,
                    telegram_file_id=color_photo_id, category="files", filename="style-reference.jpg",
                )
            except Exception:
                errors.append("style_reference")
        return references, errors


def build_application_service_from_environment() -> ApplicationService:
    """Build adapters lazily so bot startup and tests do not require Google SDKs."""
    required = (
        "GOOGLE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_SHEETS_ID",
        "GOOGLE_DRIVE_ROOT_FOLDER_ID",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise StorageError("Missing Release 1 storage configuration: " + ", ".join(missing))

    from storage.google_drive import GoogleDriveAdapter
    from storage.google_sheets import GoogleSheetsAdapter

    sheets = GoogleSheetsAdapter.from_environment()
    drive = GoogleDriveAdapter.from_environment()
    return ApplicationService(clients=sheets, applications=sheets, files=drive)
