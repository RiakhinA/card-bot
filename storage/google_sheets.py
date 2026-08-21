"""Google Sheets adapter for durable Client, Application and Payment records."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from models import Application, Client, Payment


SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
SHEETS: dict[str, list[str]] = {
    "Clients": [
        "client_id", "telegram_user_id", "name", "source", "interface_language",
        "status", "created_at", "updated_at",
    ],
    "Applications": [
        "application_id", "client_id", "request_key", "source", "application_status",
        "price_snapshot", "submission_data", "file_references", "created_at", "updated_at",
    ],
    "Payments": [
        "application_id", "payment_method_selected", "payment_status",
        "payment_created_at", "payment_updated_at", "metadata",
    ],
}


class GoogleSheetsAdapter:
    def __init__(self, *, spreadsheet_id: str, credentials_info: dict[str, Any]) -> None:
        credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        self._spreadsheet_id = spreadsheet_id
        self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._schema_ready = False

    @classmethod
    def from_environment(cls) -> "GoogleSheetsAdapter":
        try:
            credentials_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
        except (KeyError, json.JSONDecodeError) as error:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must contain service-account JSON") from error
        return cls(spreadsheet_id=os.environ["GOOGLE_SHEETS_ID"], credentials_info=credentials_info)

    async def find_by_telegram_user_id(self, telegram_user_id: int) -> Client | None:
        await self._ensure_schema()
        rows = await asyncio.to_thread(self._read_rows, "Clients")
        for row in rows:
            if row.get("telegram_user_id") == str(telegram_user_id):
                return Client(
                    client_id=row["client_id"],
                    telegram_user_id=int(row["telegram_user_id"]),
                    name=row.get("name", ""),
                    source=row.get("source", "Telegram Bot"),
                    interface_language=row.get("interface_language") or None,
                    status=row.get("status", "ACTIVE"),
                    created_at=row.get("created_at", ""),
                    updated_at=row.get("updated_at", ""),
                )
        return None

    async def create_client(self, client: Client) -> None:
        await self._ensure_schema()
        await asyncio.to_thread(self._append, "Clients", self._client_values(client))

    async def find_by_request_key(self, request_key: str) -> Application | None:
        await self._ensure_schema()
        rows = await asyncio.to_thread(self._read_rows, "Applications")
        for row in rows:
            if row.get("request_key") == request_key:
                return Application(
                    application_id=row["application_id"],
                    client_id=row["client_id"],
                    request_key=row["request_key"],
                    source=row.get("source", "Telegram Bot"),
                    application_status=row.get("application_status", "SUBMITTED"),
                    price_snapshot=json.loads(row.get("price_snapshot") or "{}"),
                    submission_data=json.loads(row.get("submission_data") or "{}"),
                    file_references=json.loads(row.get("file_references") or "{}"),
                    created_at=row.get("created_at", ""),
                    updated_at=row.get("updated_at", ""),
                )
        return None

    async def create_application(self, application: Application) -> None:
        await self._ensure_schema()
        await asyncio.to_thread(self._append, "Applications", self._application_values(application))

    async def create_payment(self, payment: Payment) -> None:
        await self._ensure_schema()
        await asyncio.to_thread(self._append, "Payments", self._payment_values(payment))

    async def _ensure_schema(self) -> None:
        if not self._schema_ready:
            await asyncio.to_thread(self._ensure_schema_sync)
            self._schema_ready = True

    def _ensure_schema_sync(self) -> None:
        metadata = self._service.spreadsheets().get(spreadsheetId=self._spreadsheet_id).execute()
        existing = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
        missing = [title for title in SHEETS if title not in existing]
        if missing:
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=self._spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": title}}} for title in missing]},
            ).execute()
        for title, headers in SHEETS.items():
            current = self._service.spreadsheets().values().get(
                spreadsheetId=self._spreadsheet_id, range=f"{title}!1:1"
            ).execute().get("values", [])
            if not current:
                self._service.spreadsheets().values().update(
                    spreadsheetId=self._spreadsheet_id,
                    range=f"{title}!A1",
                    valueInputOption="RAW",
                    body={"values": [headers]},
                ).execute()

    def _read_rows(self, title: str) -> list[dict[str, str]]:
        values = self._service.spreadsheets().values().get(
            spreadsheetId=self._spreadsheet_id, range=f"{title}!A:Z"
        ).execute().get("values", [])
        if not values:
            return []
        headers = values[0]
        return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in values[1:]]

    def _append(self, title: str, values: list[str]) -> None:
        self._service.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{title}!A:Z",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [values]},
        ).execute()

    @staticmethod
    def _client_values(client: Client) -> list[str]:
        record = client.to_record()
        return [str(record.get(key) or "") for key in SHEETS["Clients"]]

    @staticmethod
    def _application_values(application: Application) -> list[str]:
        record = application.to_record()
        return [
            json.dumps(record[key], ensure_ascii=False) if key in {"price_snapshot", "submission_data", "file_references"}
            else str(record.get(key) or "")
            for key in SHEETS["Applications"]
        ]

    @staticmethod
    def _payment_values(payment: Payment) -> list[str]:
        record = payment.to_record()
        return [
            json.dumps(record[key], ensure_ascii=False) if key == "metadata" else str(record.get(key) or "")
            for key in SHEETS["Payments"]
        ]
