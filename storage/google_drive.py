"""Google Drive adapter for client photos and original submission materials."""

from __future__ import annotations

import asyncio
import io
import json
import os
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


SCOPES = ("https://www.googleapis.com/auth/drive",)
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class GoogleDriveAdapter:
    def __init__(self, *, root_folder_id: str, credentials_info: dict[str, Any]) -> None:
        credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        self._root_folder_id = root_folder_id
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    @classmethod
    def from_environment(cls) -> "GoogleDriveAdapter":
        try:
            credentials_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        except (KeyError, json.JSONDecodeError) as error:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must contain service-account JSON") from error
        return cls(root_folder_id=os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"], credentials_info=credentials_info)

    async def upload_telegram_file(
        self,
        *,
        bot: Any,
        client_id: str,
        application_id: str,
        telegram_file_id: str,
        category: str,
        filename: str,
    ) -> dict[str, str]:
        telegram_file = await bot.get_file(telegram_file_id)
        content = await bot.download_file(telegram_file.file_path)
        if hasattr(content, "seek"):
            content.seek(0)
        elif isinstance(content, bytes):
            content = io.BytesIO(content)
        return await asyncio.to_thread(
            self._upload_sync,
            client_id,
            application_id,
            category,
            filename,
            content,
        )

    def _upload_sync(
        self,
        client_id: str,
        application_id: str,
        category: str,
        filename: str,
        content: io.BytesIO,
    ) -> dict[str, str]:
        client_folder_id = self._get_or_create_folder(client_id, self._root_folder_id)
        category_folder_id = self._get_or_create_folder(category, client_folder_id)
        stored_name = f"{application_id}_{filename}"
        existing = self._find_file(stored_name, category_folder_id)
        if existing:
            return {
                "file_id": existing["id"],
                "name": existing["name"],
                "web_view_link": existing.get("webViewLink", ""),
            }
        media = MediaIoBaseUpload(content, mimetype="image/jpeg", resumable=False)
        created = self._service.files().create(
            body={"name": stored_name, "parents": [category_folder_id]},
            media_body=media,
            fields="id,name,webViewLink",
        ).execute()
        return {
            "file_id": created["id"],
            "name": created["name"],
            "web_view_link": created.get("webViewLink", ""),
        }

    def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        query = (
            f"name = '{self._escape_query_value(name)}' and "
            f"'{parent_id}' in parents and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"
        )
        response = self._service.files().list(
            q=query, spaces="drive", fields="files(id,name)", pageSize=1
        ).execute()
        files = response.get("files", [])
        if files:
            return files[0]["id"]
        folder = self._service.files().create(
            body={"name": name, "mimeType": FOLDER_MIME_TYPE, "parents": [parent_id]},
            fields="id",
        ).execute()
        return folder["id"]

    def _find_file(self, name: str, parent_id: str) -> dict[str, str] | None:
        query = (
            f"name = '{self._escape_query_value(name)}' and "
            f"'{parent_id}' in parents and trashed = false"
        )
        response = self._service.files().list(
            q=query, spaces="drive", fields="files(id,name,webViewLink)", pageSize=1
        ).execute()
        files = response.get("files", [])
        return files[0] if files else None

    @staticmethod
    def _escape_query_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")
