"""Fixtures de la API de facturas: la aplicación REAL con base de datos real (SPEC-W-007 hito 3).

Los tokens son los de la clave de prueba de `tests/api/conftest.py`. Las pruebas de dominio de este directorio no usan nada de aquí. Se usa el reloj
REAL: la base comprueba «no futura» con el suyo, así que las fechas son fijas y pasadas (de marzo de 2026) o relativas a hoy. Los datos de ejemplo
(nombre, NIF, domicilio, concepto) son sintéticos y reconocibles, para que `test_no_sensitive_logs` pueda buscarlos.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.auth import JwksTokenVerifier
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.rls.invoices_support import D1, D2, D3, Ready, ready, today
from tests.support import Cast, Person

CONCEPT = "Concepto sintético 7731"


def invoice_body(client_id: object, **fields: Any) -> dict[str, Any]:
    """Una factura válida (base 1.000,00 €) con lo que se quiera cambiar. `series_id` vacío es la predeterminada."""
    body: dict[str, Any] = {
        "client_id": str(client_id),
        "series_id": None,
        "issue_date": D1.isoformat(),
        "concept": CONCEPT,
        "base_cents": 100_000,
        "vat_rate": None,
    }
    return {**body, **fields}


def rectification_body(**fields: Any) -> dict[str, Any]:
    return {"reason": "Importe mal calculado", "corrected_base_cents": 80_000, "issue_date": D2.isoformat(), **fields}


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer
    cast: Cast
    admin: Connection[DictRow]
    world: Ready

    def headers(self, person: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.signer.token(person)}"}

    def request(self, method: str, url: str, person: Person, **kwargs: Any) -> httpx.Response:
        return self.client.request(method, url, headers=self.headers(person), **kwargs)

    def today(self) -> date:
        return today(self.admin)

    def cid(self, scope: str = "national", kind: str = "business") -> object:
        return self.world.clients[(scope, kind)]

    # --- Rutas --------------------------------------------------------------------------------------------------------

    def preview(self, person: Person, body: dict[str, Any]) -> httpx.Response:
        return self.request("POST", "/api/invoices/preview", person, json=body)

    def issue(self, person: Person, body: dict[str, Any]) -> httpx.Response:
        return self.request("POST", "/api/invoices", person, json=body)

    def made(self, person: Person, scope: str = "national", kind: str = "business", **fields: Any) -> dict[str, Any]:
        response = self.issue(person, invoice_body(self.cid(scope, kind), **fields))
        assert response.status_code == 201, response.text
        return response.json()

    def rectify(self, person: Person, invoice_id: object, **fields: Any) -> httpx.Response:
        return self.request(
            "POST", f"/api/invoices/{invoice_id}/rectifications", person, json=rectification_body(**fields)
        )

    def get(self, person: Person, invoice_id: object) -> httpx.Response:
        return self.request("GET", f"/api/invoices/{invoice_id}", person)

    def pay(self, person: Person, invoice_id: object, paid: object) -> httpx.Response:
        return self.request("PUT", f"/api/invoices/{invoice_id}/payment", person, json={"paid": paid})

    def listing(self, person: Person, **params: Any) -> list[dict[str, Any]]:
        response = self.request("GET", "/api/invoices", person, params=params or None)
        assert response.status_code == 200, response.text
        return response.json()

    def billing(self, person: Person, **params: Any) -> httpx.Response:
        return self.request("GET", "/api/clients/billing", person, params=params or None)


@pytest.fixture
def app(jwks_client: FakeJwksClient) -> FastAPI:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    return application


@pytest.fixture
def api(app: FastAPI, signer: Signer, cast: Cast, admin: Connection[DictRow]) -> Iterator[Api]:  # noqa: F811
    """Alicia con el perfil completo, la retención del 15 %, la serie `2026` y un cliente de cada ámbito y tipo."""
    world = ready(admin, cast.alicia)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(app, client, signer, cast, admin, world)


__all__ = ["D1", "D2", "D3", "Api", "CONCEPT", "api", "app", "invoice_body", "rectification_body"]
