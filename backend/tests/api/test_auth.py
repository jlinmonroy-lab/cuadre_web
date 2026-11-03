"""AC-04 y AC-05 · Sin sesión no se accede; tokens inválidos y cuentas suspendidas (SPEC-W-001 §5.1)."""

import logging
import time
import uuid
from typing import Annotated

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.auth import CurrentUser, require_role
from tests.api.conftest import FakeJwksClient, Signer, bearer
from tests.support import Cast, Person


def assert_problem(response: Response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert (body["status"], body["code"]) == (status, code)
    assert body["request_id"] == response.headers["x-request-id"]
    assert "Traceback" not in response.text
    return body


# --- Camino feliz ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("key", "role"), [("alicia", "usuario"), ("gina", "gestor"), ("adan", "admin")])
def test_a_valid_token_returns_the_account_and_its_role(
    client: TestClient, signer: Signer, cast: Cast, key: str, role: str
) -> None:
    person = cast[key]
    response = client.get("/api/me", headers=bearer(signer.token(person)))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": str(person.id),
        "email": person.email,
        "display_name": key.capitalize(),
        "role": role,
        "status": "active",
    }
    assert response.headers["x-request-id"]


def test_the_role_comes_from_the_database_not_from_the_token(
    client: TestClient, signer: Signer, cast: Cast, admin: Connection[DictRow]
) -> None:
    """Mismo token, dos peticiones: cambiar el rol en la base de datos rige en la siguiente (T-12, ADR-0005)."""
    token = signer.token(cast.gina, app_metadata={"role": "admin"}, user_metadata={"role": "admin"})
    assert client.get("/api/me", headers=bearer(token)).json()["role"] == "gestor", "el token pide admin y se ignora"
    admin.execute("update public.profiles set role = 'usuario' where id = %s", (cast.gina.id,))
    assert client.get("/api/me", headers=bearer(token)).json()["role"] == "usuario"


def test_the_jwks_is_cached_between_requests(
    client: TestClient, signer: Signer, cast: Cast, jwks_client: FakeJwksClient
) -> None:
    for _ in range(3):
        assert client.get("/api/me", headers=bearer(signer.token(cast.alicia))).status_code == 200
    assert jwks_client.downloads == 1


# --- AC-04 · sin sesión ----------------------------------------------------------------------------------------------------


def test_no_authorization_header_is_401(client: TestClient) -> None:
    response = client.get("/api/me")
    assert_problem(response, 401, "unauthenticated")
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic dXNlcjpwYXNz", "Bearer", "Bearer ", "bearer", "Token abc"])
def test_wrong_scheme_or_empty_credentials_is_401(client: TestClient, header: str) -> None:
    assert_problem(client.get("/api/me", headers={"Authorization": header}), 401, "unauthenticated")


@pytest.mark.parametrize("token", ["no-es-un-jwt", "a.b.c", "....", "x" * 5000])
def test_a_malformed_token_is_401(client: TestClient, token: str) -> None:
    assert_problem(client.get("/api/me", headers=bearer(token)), 401, "unauthenticated")


# --- AC-05 · tokens inválidos ----------------------------------------------------------------------------------------------


def test_an_expired_token_is_401(client: TestClient, signer: Signer, cast: Cast) -> None:
    token = signer.token(cast.alicia, exp=int(time.time()) - 10)
    assert_problem(client.get("/api/me", headers=bearer(token)), 401, "unauthenticated")


def test_a_token_that_is_not_valid_yet_is_401(client: TestClient, signer: Signer, cast: Cast) -> None:
    token = signer.token(cast.alicia, nbf=int(time.time()) + 600)
    assert_problem(client.get("/api/me", headers=bearer(token)), 401, "unauthenticated")


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "service_role"},
        {"aud": "otra-app"},
        {"iss": "https://otro.example.test/auth/v1"},
        {"exp": None},
        {"sub": "no-es-un-uuid"},
        {"sub": None},
    ],
    ids=["aud-service_role", "aud-otra", "iss-ajeno", "sin-exp", "sub-no-uuid", "sin-sub"],
)
def test_invalid_claims_are_401(client: TestClient, signer: Signer, cast: Cast, overrides: dict) -> None:
    assert_problem(
        client.get("/api/me", headers=bearer(signer.token(cast.alicia, **overrides))), 401, "unauthenticated"
    )


def test_a_token_signed_with_another_key_is_401(client: TestClient, signer: Signer, cast: Cast) -> None:
    attacker = ec.generate_private_key(ec.SECP256R1())
    token = signer.token(cast.alicia, key=attacker)  # mismo `kid`, firma de otra clave
    assert_problem(client.get("/api/me", headers=bearer(token)), 401, "unauthenticated")


def test_a_tampered_payload_is_401(client: TestClient, signer: Signer, cast: Cast) -> None:
    header, _payload, signature = signer.token(cast.alicia).split(".")
    forged = signer.token(cast.beto).split(".")[1]  # el payload de otra persona con la firma de Alicia
    assert_problem(client.get("/api/me", headers=bearer(f"{header}.{forged}.{signature}")), 401, "unauthenticated")


@pytest.mark.parametrize("kid", ["otra-clave", None], ids=["kid-desconocido", "sin-kid"])
def test_an_unknown_or_missing_kid_is_401(client: TestClient, signer: Signer, cast: Cast, kid: str | None) -> None:
    assert_problem(client.get("/api/me", headers=bearer(signer.token(cast.alicia, kid=kid))), 401, "unauthenticated")


def test_alg_none_is_401(client: TestClient, signer: Signer, cast: Cast) -> None:
    assert_problem(client.get("/api/me", headers=bearer(signer.alg_none(cast.alicia))), 401, "unauthenticated")


def test_the_hs256_algorithm_confusion_attack_is_401(client: TestClient, signer: Signer, cast: Cast) -> None:
    """HS256 firmado con la clave pública como secreto: solo se aceptan ES256 y RS256."""
    assert_problem(client.get("/api/me", headers=bearer(signer.hs256_confusion(cast.alicia))), 401, "unauthenticated")


def test_an_unreachable_jwks_is_503_not_401_or_500(
    client: TestClient, signer: Signer, cast: Cast, jwks_client: FakeJwksClient
) -> None:
    jwks_client.down = True
    response = client.get("/api/me", headers=bearer(signer.token(cast.alicia)))
    assert_problem(response, 503, "auth_unavailable")
    assert response.headers["retry-after"]


# --- AC-05 · cuenta ---------------------------------------------------------------------------------------------------------


def test_a_suspended_account_is_403(client: TestClient, signer: Signer, cast: Cast, admin: Connection[DictRow]) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert_problem(client.get("/api/me", headers=bearer(signer.token(cast.alicia))), 403, "account_suspended")


def test_a_valid_token_without_a_profile_is_403(client: TestClient, signer: Signer) -> None:
    ghost = Person("alicia", uuid.uuid4(), "fantasma@example.test")
    assert_problem(client.get("/api/me", headers=bearer(signer.token(ghost))), 403, "profile_missing")


# --- require_role -----------------------------------------------------------------------------------------------------------


def test_require_role_allows_only_the_listed_roles(
    app: FastAPI, client: TestClient, signer: Signer, cast: Cast
) -> None:
    def admin_only(user: Annotated[CurrentUser, Depends(require_role("admin"))]) -> dict[str, str]:
        return {"role": user.role}

    def staff(user: Annotated[CurrentUser, Depends(require_role("admin", "gestor"))]) -> dict[str, str]:
        return {"role": user.role}

    app.add_api_route("/_t/admin-only", admin_only, methods=["GET"], operation_id="get_probe_admin")
    app.add_api_route("/_t/staff", staff, methods=["GET"], operation_id="get_probe_staff")

    def status(path: str, person: Person) -> int:
        return client.get(path, headers=bearer(signer.token(person))).status_code

    assert status("/_t/admin-only", cast.adan) == 200
    assert_problem(client.get("/_t/admin-only", headers=bearer(signer.token(cast.alicia))), 403, "forbidden")
    assert_problem(client.get("/_t/admin-only", headers=bearer(signer.token(cast.gina))), 403, "forbidden")
    assert [status("/_t/staff", p) for p in (cast.adan, cast.gina, cast.alicia)] == [200, 200, 403]
    assert_problem(client.get("/_t/staff"), 401, "unauthenticated")


# --- Registro ---------------------------------------------------------------------------------------------------------------


def test_uvicorns_own_access_log_is_off_because_it_prints_the_query_string(client: TestClient) -> None:
    assert logging.getLogger("uvicorn.access").disabled is True


def test_requests_are_logged_without_tokens_or_emails(client: TestClient, signer: Signer, cast: Cast) -> None:
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("cuadre.request")
    handler = Collect()
    logger.addHandler(handler)
    try:
        token = signer.token(cast.alicia)
        client.get("/api/me?token=secreto-en-query", headers=bearer(token))
        client.get("/api/me", headers=bearer("token-invalido-con-secreto"))
    finally:
        logger.removeHandler(handler)

    lines = [r for r in records if r.getMessage() == "request"]
    assert len(lines) == 2
    dump = repr([r.__dict__ for r in records])
    for secret in (token, "secreto-en-query", "token-invalido-con-secreto", cast.alicia.email):
        assert secret not in dump, f"el registro contiene {secret[:12]}…"
    first = lines[0].__dict__
    assert (first["route"], first["status"], first["user_id"]) == ("/api/me", 200, str(cast.alicia.id))
    assert lines[1].__dict__["status"] == 401
