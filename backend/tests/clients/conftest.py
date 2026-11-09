"""Fixtures de la API de clientes: la aplicación REAL con base de datos real (SPEC-W-006 hito 3).

Los tokens son los de la clave de prueba de `tests/api/conftest.py`. Las pruebas de dominio de este directorio no usan nada de aquí. Los datos de
ejemplo (nombre, NIF, domicilio) son sintéticos y reconocibles, para que `test_no_sensitive_logs` pueda buscarlos.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuadre.core.auth import JwksTokenVerifier
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.support import Cast, Person

NIF = "B00000018"
VAT_DE = "DE534861408"
VAT_FR = "FR89195505110"
BODY: dict[str, Any] = {
    "name": "Estudio Norte S.L.",
    "kind": "business",
    "country": "ES",
    "tax_id": NIF,
    "address": "Calle Inventada 4, Madrid",
}
GERMAN: dict[str, Any] = {
    "name": "Kreativ GmbH",
    "kind": "business",
    "country": "DE",
    "tax_id": VAT_DE,
    "address": None,
}
MEXICAN: dict[str, Any] = {
    "name": "Taller Zocalo",
    "kind": "business",
    "country": "MX",
    "tax_id": "MXTEST0001",
    "address": None,
}
AMERICAN: dict[str, Any] = {
    "name": "Sam Rivers",
    "kind": "individual",
    "country": "US",
    "tax_id": None,
    "address": None,
}


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer
    cast: Cast

    def headers(self, person: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.signer.token(person)}"}

    def request(self, method: str, url: str, person: Person, **kwargs: Any) -> httpx.Response:
        return self.client.request(method, url, headers=self.headers(person), **kwargs)

    def create(self, person: Person, **fields: Any) -> httpx.Response:
        return self.request("POST", "/api/clients", person, json={**BODY, **fields})

    def made(self, person: Person, **fields: Any) -> dict[str, Any]:
        response = self.create(person, **fields)
        assert response.status_code == 201, response.text
        return response.json()

    def update(self, person: Person, client_id: object, **fields: Any) -> httpx.Response:
        return self.request("PUT", f"/api/clients/{client_id}", person, json={**BODY, **fields})

    def archive(self, person: Person, client_id: object, archived: object) -> httpx.Response:
        return self.request("PUT", f"/api/clients/{client_id}/archived", person, json={"archived": archived})

    def get(self, person: Person, client_id: object) -> httpx.Response:
        return self.request("GET", f"/api/clients/{client_id}", person)

    def listing(self, person: Person, *, archived: bool = False) -> list[dict[str, Any]]:
        response = self.request(
            "GET", "/api/clients", person, params={"include_archived": archived} if archived else None
        )
        assert response.status_code == 200, response.text
        return response.json()


@pytest.fixture
def app(jwks_client: FakeJwksClient) -> FastAPI:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    return application


@pytest.fixture
def api(app: FastAPI, signer: Signer, cast: Cast) -> Iterator[Api]:  # noqa: F811
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(app, client, signer, cast)
