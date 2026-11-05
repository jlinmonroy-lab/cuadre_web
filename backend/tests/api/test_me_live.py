"""Contra la pila REAL de Supabase: un token emitido por GoTrue se verifica con su JWKS y devuelve la cuenta.

Es la prueba de que el camino de producción (JWKS asimétrico, ES256) funciona de punta a punta. Requiere `npx supabase start` y
`TEST_SUPABASE_ANON_KEY` (la clave `sb_publishable_…` local, en el `.env`).
"""

import os
from collections.abc import Callable

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from cuadre.config import Settings
from cuadre.main import create_app
from tests.api.conftest import bearer
from tests.support import password_grant as grant

pytestmark = pytest.mark.live

SEED_PASSWORD = "cuadre-demo-2026"


def password_grant(email: str, password: str = SEED_PASSWORD) -> httpx.Response:
    return grant(email, password)


@pytest.fixture(scope="module")
def real_client() -> TestClient:
    if not os.environ.get("TEST_SUPABASE_ANON_KEY"):
        pytest.skip("Falta TEST_SUPABASE_ANON_KEY (clave publicable de la pila local, en el .env)")
    with TestClient(create_app(Settings())) as test_client:  # type: ignore[call-arg]
        yield test_client


@pytest.mark.parametrize(
    ("email", "role"),
    [("alicia@example.test", "usuario"), ("gina@example.test", "gestor"), ("adan@example.test", "admin")],
)
def test_a_real_gotrue_token_is_accepted(real_client: TestClient, email: str, role: str) -> None:
    grant = password_grant(email)
    assert grant.status_code == 200, grant.text
    token = grant.json()["access_token"]

    response = real_client.get("/api/me", headers=bearer(token))
    assert response.status_code == 200, response.text
    assert response.json()["email"] == email
    assert response.json()["role"] == role


def test_a_real_token_with_a_tampered_signature_is_rejected(real_client: TestClient) -> None:
    token = password_grant("alicia@example.test").json()["access_token"]
    header, payload, signature = token.split(".")
    flipped: Callable[[str], str] = lambda s: s[:-2] + ("AA" if s[-2:] != "AA" else "BB")  # noqa: E731
    response = real_client.get("/api/me", headers=bearer(f"{header}.{payload}.{flipped(signature)}"))
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_a_wrong_password_never_yields_a_token() -> None:
    if not os.environ.get("TEST_SUPABASE_ANON_KEY"):
        pytest.skip("Falta TEST_SUPABASE_ANON_KEY")
    grant = password_grant("alicia@example.test", "contraseña-incorrecta")
    assert grant.status_code == 400
    assert grant.json()["error_code"] == "invalid_credentials"
