"""Fixtures de los tests de la API: tokens firmados con una clave EC de prueba y una aplicación que confía en ella.

El verificador es el REAL (`JwksTokenVerifier` sobre `PyJWKClient`); lo único que se sustituye es la descarga del JWKS, que sirve
la clave pública de prueba. Así se ejercita la lógica de `kid`, caché y algoritmos sin depender de la red.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from cuadre.config import Settings
from cuadre.core.auth import JwksTokenVerifier
from cuadre.main import create_app
from tests.support import Person

KID = "test-key-1"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeJwksClient(PyJWKClient):
    """`PyJWKClient` real, con la descarga sustituida. `down = True` simula un Supabase inaccesible."""

    def __init__(self, jwks: dict[str, Any]) -> None:
        super().__init__("http://jwks.invalid/.well-known/jwks.json", cache_keys=True, lifespan=600)
        self.jwks = jwks
        self.down = False
        self.downloads = 0

    def fetch_data(self) -> Any:
        if self.down:
            raise PyJWKClientConnectionError("JWKS inaccesible (simulado)")
        self.downloads += 1
        return self.jwks


@dataclass
class Signer:
    private_key: ec.EllipticCurvePrivateKey
    public_pem: bytes
    jwks: dict[str, Any]
    issuer: str

    def claims(self, person: Person, **overrides: Any) -> dict[str, Any]:
        now = int(time.time())
        base = {
            "iss": self.issuer,
            "aud": "authenticated",
            "sub": str(person.id),
            "email": person.email,
            "role": "authenticated",
            "iat": now,
            "exp": now + 3600,
        }
        base.update(overrides)
        return {k: v for k, v in base.items() if v is not None}

    def token(
        self, person: Person, *, key: ec.EllipticCurvePrivateKey | None = None, kid: str | None = KID, **overrides: Any
    ) -> str:
        headers = {"kid": kid} if kid else {}
        return jwt.encode(self.claims(person, **overrides), key or self.private_key, algorithm="ES256", headers=headers)

    def hs256_confusion(self, person: Person) -> str:
        """Ataque de confusión de algoritmo: HS256 firmado con la CLAVE PÚBLICA como secreto."""
        header = b64url(json.dumps({"alg": "HS256", "typ": "JWT", "kid": KID}).encode())
        payload = b64url(json.dumps(self.claims(person)).encode())
        signature = hmac.new(self.public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest()
        return f"{header}.{payload}.{b64url(signature)}"

    def alg_none(self, person: Person) -> str:
        header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        return f"{header}.{b64url(json.dumps(self.claims(person)).encode())}."


@pytest.fixture(scope="session")
def signer() -> Signer:
    key = ec.generate_private_key(ec.SECP256R1())
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": KID, "alg": "ES256", "use": "sig"})
    issuer = f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1"
    return Signer(key, public_pem, {"keys": [jwk]}, issuer)


@pytest.fixture
def jwks_client(signer: Signer) -> FakeJwksClient:
    return FakeJwksClient(signer.jwks)


@pytest.fixture
def app(jwks_client: FakeJwksClient) -> FastAPI:
    application = create_app(Settings())  # type: ignore[call-arg]
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """`raise_server_exceptions=False`: un error inesperado debe verse como lo vería un cliente real (un 500), no como una excepción."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
