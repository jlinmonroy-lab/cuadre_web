"""Autenticación y autorización de la API (SPEC-W-001 §5.1, ADR-0005).

Flujo de una petición autenticada:

1. `get_claims`: lee `Authorization: Bearer`, verifica el JWT de Supabase Auth por JWKS y devuelve sus claims.
2. `get_tx`: abre la transacción del usuario (`SET LOCAL ROLE authenticated` + claims) y la mantiene abierta durante la ruta.
3. `get_current_user`: lee `profiles` DENTRO de esa transacción. El rol sale de la base de datos, nunca del token: así una baja,
   una degradación o una suspensión surten efecto en la petición siguiente, sin esperar a que caduque el token.
4. `require_role(...)`: 403 si el rol no está permitido.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.errors import (
    account_suspended,
    auth_unavailable,
    forbidden,
    profile_missing,
    unauthenticated,
)
from cuadre.db import user_transaction

Role = Literal["usuario", "gestor", "admin"]
ALGORITHMS = ["ES256", "RS256"]  # únicamente asimétricos: ni HS256 ni `none` (T-12)
AUDIENCE = "authenticated"


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]: ...


class JwksTokenVerifier:
    """Verifica tokens de Supabase Auth contra el JWKS publicado por el propio proyecto.

    `PyJWKClient` guarda las claves en caché y las recarga si ve un `kid` que no conoce (rotación de claves).
    """

    def __init__(self, supabase_url: str, *, jwk_client: PyJWKClient | None = None) -> None:
        self.issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self._jwks = jwk_client or PyJWKClient(
            f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=600, timeout=5
        )

    def verify(self, token: str) -> dict[str, Any]:
        try:
            signing_key = self._jwks.get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError as exc:
            raise auth_unavailable() from exc
        except (PyJWKClientError, PyJWTError) as exc:  # kid desconocido, cabecera ausente o token mal formado
            raise unauthenticated() from exc

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=ALGORITHMS,
                audience=AUDIENCE,
                issuer=self.issuer,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except PyJWTError as exc:
            raise unauthenticated() from exc

        try:
            UUID(str(claims["sub"]))
        except ValueError as exc:
            raise unauthenticated() from exc
        return claims


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str
    display_name: str
    role: Role
    status: str
    claims: dict[str, Any]


_bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth", description="JWT de Supabase Auth")


def get_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier


def get_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
) -> dict[str, Any]:
    if credentials is None:
        raise unauthenticated()
    return verifier.verify(credentials.credentials)


def get_tx(request: Request, claims: Annotated[dict[str, Any], Depends(get_claims)]) -> Iterator[Connection[DictRow]]:
    """Transacción del usuario durante toda la ruta. Commit al terminar sin error; rollback si la ruta falla."""
    with user_transaction(request.app.state.db_pool, claims["sub"], claims) as conn:
        yield conn


# `scope="function"`: la dependencia termina (y se hace el COMMIT) ANTES de enviar la respuesta. Con el ámbito por defecto
# («request») se confirmaría después de responder y un fallo de commit sería invisible para el cliente.
Tx = Annotated[Connection[DictRow], Depends(get_tx, scope="function")]


def get_current_user(request: Request, conn: Tx, claims: Annotated[dict[str, Any], Depends(get_claims)]) -> CurrentUser:
    row = conn.execute(
        "SELECT id, email, display_name, role::text AS role, status::text AS status "
        "FROM public.profiles WHERE id = (SELECT auth.uid())"
    ).fetchone()
    if row is None:
        raise profile_missing()
    request.state.user_id = str(row["id"])  # para el registro de la petición (solo el identificador)
    if row["status"] != "active":
        raise account_suspended()
    return CurrentUser(row["id"], row["email"], row["display_name"], row["role"], row["status"], claims)


def require_role(*roles: Role):  # noqa: ANN201 - devuelve una dependencia de FastAPI
    """Dependencia que exige uno de los roles indicados: `Depends(require_role("admin"))`."""

    def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.role not in roles:
            raise forbidden()
        return user

    return dependency


__all__ = [
    "CurrentUser",
    "JwksTokenVerifier",
    "Role",
    "TokenVerifier",
    "Tx",
    "get_claims",
    "get_current_user",
    "get_tx",
    "get_verifier",
    "require_role",
]
