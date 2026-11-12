"""Fixtures de la API del acceso del gestor: la aplicación REAL con base de datos real y el correo en memoria (SPEC-W-010 hito 1).

Los tokens son los de la clave de prueba de `tests/api/conftest.py`. Los datos son sintéticos y reconocibles.
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
from cuadre.notifications import MemoryEmailSender
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.support import Cast, Person


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer
    cast: Cast
    sender: MemoryEmailSender

    def request(self, method: str, url: str, person: Person | None, **kwargs: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.signer.token(person)}"} if person is not None else {}
        return self.client.request(method, url, headers=headers, **kwargs)

    def invite(self, person: Person | None, email: object) -> httpx.Response:
        return self.request("POST", "/api/gestor/accesos", person, json={"email": email})

    def accesses(self, person: Person | None) -> httpx.Response:
        return self.request("GET", "/api/gestor/accesos", person)

    def revoke(self, person: Person | None, access_id: object) -> httpx.Response:
        return self.request("POST", f"/api/gestor/accesos/{access_id}/revocar", person)

    def invitations(self, person: Person | None) -> httpx.Response:
        return self.request("GET", "/api/gestor/invitaciones", person)

    def accept(self, person: Person | None, access_id: object) -> httpx.Response:
        return self.request("POST", f"/api/gestor/invitaciones/{access_id}/aceptar", person)

    def decline(self, person: Person | None, access_id: object) -> httpx.Response:
        return self.request("POST", f"/api/gestor/invitaciones/{access_id}/rechazar", person)

    def invited(self, owner: Person, email: str) -> str:
        response = self.invite(owner, email)
        assert response.status_code == 201, response.text
        return response.json()["id"]


@pytest.fixture
def app(jwks_client: FakeJwksClient) -> FastAPI:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.state.email_sender = MemoryEmailSender()
    return application


@pytest.fixture
def api(app: FastAPI, signer: Signer, cast: Cast) -> Iterator[Api]:  # noqa: F811
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(app, client, signer, cast, app.state.email_sender)
