import sys
import unittest
from types import ModuleType

try:
    import google.oauth2.service_account  # noqa: F401
    import googleapiclient.discovery  # noqa: F401
except ModuleNotFoundError:
    google = ModuleType("google")
    oauth2 = ModuleType("google.oauth2")
    service_account = ModuleType("google.oauth2.service_account")
    service_account.Credentials = type("Credentials", (), {})
    googleapiclient = ModuleType("googleapiclient")
    discovery = ModuleType("googleapiclient.discovery")
    discovery.build = lambda *args, **kwargs: None
    sys.modules.update({
        "google": google,
        "google.oauth2": oauth2,
        "google.oauth2.service_account": service_account,
        "googleapiclient": googleapiclient,
        "googleapiclient.discovery": discovery,
    })

from models import Application, ApplicationStatus, ClientDataPackageStatus
from services.client_data_package import (
    ApplicationNotFoundError,
    ClientDataPackageService,
    PERSONAL_CARD_TEMPLATE_V1_REFERENCE,
    PERSONAL_CARD_TYPE,
)
from storage.google_sheets import GoogleSheetsAdapter, SHEETS


class FakeRepository:
    def __init__(self):
        self.applications = {}
        self.packages_by_id = {}
        self.packages_by_application = {}
        self.created_packages = []

    async def find_by_application_id(self, application_id):
        return self.applications.get(application_id)

    async def get_client_data_package_by_package_id(self, package_id):
        return self.packages_by_id.get(package_id)

    async def get_client_data_package_by_application_id(self, application_id):
        return self.packages_by_application.get(application_id)

    async def create_client_data_package(self, package):
        self.packages_by_id[package.package_id] = package
        self.packages_by_application[package.application_id] = package
        self.created_packages.append(package)


class FakeClientDataPackageAdapter(GoogleSheetsAdapter):
    """In-memory adapter exercising the public Client Data Package storage contract."""

    def __init__(self):
        self.rows = []

    async def _ensure_schema(self):
        return None

    def _append(self, title, values):
        self.assertEqual(title, "ClientDataPackages")
        self.rows.append(dict(zip(SHEETS["ClientDataPackages"], values)))

    def _read_rows(self, title):
        self.assertEqual(title, "ClientDataPackages")
        return list(self.rows)

    def assertEqual(self, left, right):
        if left != right:
            raise AssertionError(f"{left!r} != {right!r}")


def application(*, complete=True, confirmation_date=None):
    data = {
        "name": "Антон Ряхин",
        "profession": "Косметолог",
        "about": "Описание визитки",
        "language_values": ["Русский", "Українська"],
        "adaptive_mode": "about",
        "work_context": "offline",
        "preset_reference": "beauty_offline",
        "selected_modules": ["core", "social", "contact", "products"],
        "module_configuration": {
            "core": {"name": "Антон Ряхин"},
            "social": {"instagram": "https://instagram.com/riakhin"},
            "contact": {"telegram": "@riakhin"},
            "products": {"items": [{"name": "Услуга", "description": "Описание", "link": "https://example.com"}]},
        },
        "social_values": {"instagram": "https://instagram.com/riakhin"},
        "messenger_values": {"telegram": "@riakhin"},
        "product_values": [{"name": "Услуга", "description": "Описание", "link": "https://example.com"}],
    }
    if confirmation_date:
        data["client_confirmation_date"] = confirmation_date
    if not complete:
        data.pop("profession")
        data["module_configuration"] = {"core": {}}
    return Application(
        application_id="APPLICATION-TEST", client_id="CLIENT-TEST", request_key="telegram:test",
        source="Telegram Bot", application_status=ApplicationStatus.SUBMITTED,
        price_snapshot={}, submission_data=data,
        file_references={} if not complete else {"profile_photo": {"file_id": "photo-1"}},
        created_at="2026-08-25T00:00:00+00:00", updated_at="2026-08-25T00:00:00+00:00",
    )


class ClientDataPackageTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.application = application()
        self.repository.applications[self.application.application_id] = self.application
        self.service = ClientDataPackageService(
            applications=self.repository, packages=self.repository
        )

    async def create(self):
        return await self.service.create_package_for_application(
            self.application.application_id,
            card_type=PERSONAL_CARD_TYPE,
            template_reference=PERSONAL_CARD_TEMPLATE_V1_REFERENCE,
        )

    async def test_creates_package_with_identity_template_and_file_references(self):
        package = await self.create()
        self.assertTrue(package.package_id.startswith("CLIENT-DATA-PACKAGE-"))
        self.assertEqual(package.application_id, self.application.application_id)
        self.assertEqual(package.client_id, self.application.client_id)
        self.assertEqual(package.card_type, PERSONAL_CARD_TYPE)
        self.assertEqual(package.template_reference, PERSONAL_CARD_TEMPLATE_V1_REFERENCE)
        self.assertEqual(package.confirmed_data["name"], "Антон Ряхин")
        self.assertIn("profile_photo", package.file_references)

    async def test_complete_unconfirmed_package_needs_confirmation(self):
        package = await self.create()
        self.assertEqual(package.package_status, ClientDataPackageStatus.NEEDS_CONFIRMATION)
        self.assertEqual(package.missing_required_data, ())

    async def test_confirmation_makes_complete_package_ready(self):
        self.application = application(confirmation_date="2026-08-25")
        self.repository.applications[self.application.application_id] = self.application
        package = await self.create()
        self.assertEqual(package.package_status, ClientDataPackageStatus.READY_FOR_PRODUCTION_PREPARATION)

    async def test_photo_logo_or_no_image_do_not_block_validated_package(self):
        self.application = application(confirmation_date="2026-08-25")
        self.application = Application(**{**self.application.to_record(), "file_references": {}})
        self.repository.applications[self.application.application_id] = self.application
        package = await self.create()
        self.assertEqual(package.package_status, ClientDataPackageStatus.READY_FOR_PRODUCTION_PREPARATION)
        self.assertNotIn("profile_photo", package.missing_required_data)

    async def test_incomplete_application_is_preserved_as_incomplete_package(self):
        self.application = application(complete=False)
        self.repository.applications[self.application.application_id] = self.application
        package = await self.create()
        self.assertEqual(package.package_status, ClientDataPackageStatus.INCOMPLETE)
        self.assertIn("profession", package.missing_required_data)
        self.assertNotIn("profile_photo", package.missing_required_data)

    async def test_preserves_adaptive_and_module_data(self):
        package = await self.create()
        self.assertEqual(package.confirmed_data["preset_reference"], "beauty_offline")
        self.assertEqual(package.confirmed_data["selected_modules"], ["core", "social", "contact", "products"])
        self.assertEqual(package.confirmed_data["module_configuration"]["products"]["items"][0]["name"], "Услуга")
        self.assertEqual(package.confirmed_data["social_values"]["instagram"], "https://instagram.com/riakhin")
        self.assertEqual(package.confirmed_data["messenger_values"]["telegram"], "@riakhin")

    async def test_accepts_normalized_messenger_expansion_without_rewriting_snapshot(self):
        self.application.submission_data["module_configuration"] = {
            "core": {"name": "Антон Ряхин"},
            "social": {"instagram": "https://instagram.com/riakhin"},
            "contact": {"phones": [{"id": "phone-1", "label": "Рабочий", "number": "+380501112233"}]},
            "messenger": {"telegram": [{"id": "legacy-telegram", "value": "@riakhin"}]},
            "products": {"items": self.application.submission_data["product_values"]},
        }
        package = await self.create()
        self.assertEqual(package.package_status, ClientDataPackageStatus.NEEDS_CONFIRMATION)
        self.assertEqual(package.confirmed_data["messenger_values"]["telegram"], "@riakhin")
        self.assertIn("messenger", package.confirmed_data["module_configuration"])

    async def test_gets_package_by_id_and_application(self):
        created = await self.create()
        self.assertEqual(await self.service.get_package_by_id(created.package_id), created)
        self.assertEqual(await self.service.get_package_by_application(created.application_id), created)

    async def test_duplicate_creation_returns_existing_package(self):
        first = await self.create()
        second = await self.create()
        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.created_packages), 1)

    async def test_unknown_application_is_controlled(self):
        with self.assertRaises(ApplicationNotFoundError):
            await self.service.create_package_for_application(
                "APPLICATION-MISSING", card_type=PERSONAL_CARD_TYPE,
                template_reference=PERSONAL_CARD_TEMPLATE_V1_REFERENCE,
            )

    async def test_invalid_product_link_makes_package_incomplete(self):
        self.application.submission_data["product_values"][0]["link"] = "not-a-url"
        package = await self.create()
        self.assertIn("products.validation", package.missing_required_data)

    def test_google_sheets_round_trip_preserves_every_package_field(self):
        package = None
        # The model factory is synchronous; this test uses an equivalent package fixture.
        from models import ClientDataPackage
        package = ClientDataPackage.create(
            application_id="APPLICATION-TEST", client_id="CLIENT-TEST", card_type=PERSONAL_CARD_TYPE,
            package_status=ClientDataPackageStatus.NEEDS_CONFIRMATION,
            confirmed_data={"social": {"instagram": "https://instagram.com/riakhin"}},
            file_references={"profile_photo": {"file_id": "photo-1"}},
            template_reference=PERSONAL_CARD_TEMPLATE_V1_REFERENCE,
            missing_required_data=("profession",), client_confirmation_date=None,
        )
        values = GoogleSheetsAdapter._client_data_package_values(package)
        restored = GoogleSheetsAdapter._client_data_package_from_row(
            dict(zip(SHEETS["ClientDataPackages"], values))
        )
        self.assertEqual(restored, package)

    async def test_google_sheets_create_and_get_by_both_identifiers(self):
        package = await self.create()
        adapter = FakeClientDataPackageAdapter()
        await adapter.create_client_data_package(package)
        self.assertEqual(
            await adapter.get_client_data_package_by_package_id(package.package_id), package
        )
        self.assertEqual(
            await adapter.get_client_data_package_by_application_id(package.application_id), package
        )


if __name__ == "__main__":
    unittest.main()
