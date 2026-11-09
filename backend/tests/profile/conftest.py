"""Fixtures de la API del perfil: la aplicación REAL con base de datos real y un Storage de logos en memoria.

Los tokens son los de la clave de prueba de `tests/api/conftest.py`. Storage real no los acepta; `FakeStorage` registra cada llamada con el
JWT recibido. Los datos de ejemplo (NIF, IBAN, domicilio) son sintéticos y reconocibles, para que `test_no_sensitive_logs` pueda buscarlos.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuadre.core.auth import JwksTokenVerifier
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.clocks import FixedClock
from tests.documents.fakes import FakeStorage
from tests.support import Cast, Person

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
NIF = "12345678Z"
IBAN = "ES9121000418450200051332"
ADDRESS = "Calle Ficticia 1, 28001 Madrid"
NAME = "Alicia Sintetica SL"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
WEBP = b"RIFF\x64\x00\x00\x00WEBPVP8 " + b"\x00" * 100
VALID = {"legal_name": NAME, "tax_id": NIF, "fiscal_address": ADDRESS}
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer
    cast: Cast
    storage: FakeStorage

    def headers(self, person: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.signer.token(person)}"}

    def request(self, method: str, url: str, person: Person, **kwargs: Any) -> httpx.Response:
        return self.client.request(method, url, headers=self.headers(person), **kwargs)

    def profile(self, person: Person) -> httpx.Response:
        return self.request("GET", "/api/profile", person)

    def save(self, person: Person, **fields: Any) -> httpx.Response:
        return self.request("PUT", "/api/profile", person, json=fields)

    def series(self, person: Person) -> list[dict[str, Any]]:
        response = self.request("GET", "/api/invoice-series", person)
        assert response.status_code == 200, response.text
        return response.json()

    def logo(
        self,
        person: Person,
        *,
        data: bytes = PNG,
        mime: str = "image/png",
        registered: str | None = None,
        declared: int | None = None,
    ) -> UUID:
        """Anuncia, sube como lo haría el navegador y deja el objeto en Storage. No completa."""
        reserved = self.request(
            "POST",
            "/api/profile/logo",
            person,
            json={"mime_type": mime, "size_bytes": len(data) if declared is None else declared},
        )
        assert reserved.status_code == 201, reserved.text
        upload_id = UUID(reserved.json()["upload_id"])
        self.storage.put(f"{person.id}/{upload_id}.{EXTENSIONS[mime]}", data, registered or mime)
        return upload_id

    def complete(self, person: Person, upload_id: UUID | str) -> httpx.Response:
        return self.request("POST", f"/api/profile/logo/{upload_id}/complete", person)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def app(jwks_client: FakeJwksClient, storage: FakeStorage) -> FastAPI:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.state.logo_storage = storage
    application.state.clock = FixedClock(NOW)
    return application


@pytest.fixture
def api(app: FastAPI, signer: Signer, cast: Cast, storage: FakeStorage) -> Iterator[Api]:  # noqa: F811
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(app, client, signer, cast, storage)
