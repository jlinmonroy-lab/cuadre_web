"""Fixtures de la API de documentos: la aplicación REAL con base de datos real, un Storage en memoria y el agente simulado.

Los tokens son los de la clave de prueba de `tests/api/conftest.py` (la API los verifica con su JWKS). Storage real no los aceptaría,
por eso hay un doble en memoria; `test_documents_live.py` repite lo esencial contra Storage real con tokens de GoTrue.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import FakeAgentsClient
from cuadre.agents.fake import ScriptItem
from cuadre.core.auth import JwksTokenVerifier
from cuadre.documents.limits import MIME_EXTENSIONS
from cuadre.main import create_app
from tests.agents.conftest import server  # noqa: F401 - fixture de otro conftest
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.documents.fakes import FakeStorage
from tests.support import Cast, Person

PDF = "application/pdf"
FILENAME = "factura-privada-de-alicia-2026.pdf"  # reconocible: ninguna prueba de registros debe encontrarlo

# Contenidos mínimos con la firma correcta de cada tipo (T2-08). Sintéticos (RES-07).
SAMPLES: dict[str, bytes] = {
    "application/pdf": b"%PDF-1.4\n% factura sintetica\n" + b"0" * 100 + b"\n%%EOF\n",
    "image/jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100,
    "image/png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
    "image/heic": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heicmif1" + b"\x00" * 100,
    "image/webp": b"RIFF\x64\x00\x00\x00WEBPVP8 " + b"\x00" * 100,
}
assert set(SAMPLES) == set(MIME_EXTENSIONS)


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer
    cast: Cast
    storage: FakeStorage

    # --- Peticiones --------------------------------------------------------------------------------------------------------

    def token(self, person: Person) -> str:
        return self.signer.token(person)

    def headers(self, person: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(person)}"}

    def request(self, method: str, url: str, person: Person, **kwargs: Any) -> httpx.Response:
        return self.client.request(method, url, headers=self.headers(person), **kwargs)

    def script(self, *items: ScriptItem) -> None:
        """El agente simulado devolverá exactamente esto, en orden (y fallará si se le pide más)."""
        self.app.state.agents_client = FakeAgentsClient(items)

    # --- Flujo de una factura ----------------------------------------------------------------------------------------------

    def path_of(self, person: Person, document_id: UUID | str, mime: str = PDF) -> str:
        return f"{person.id}/{document_id}.{MIME_EXTENSIONS[mime]}"

    def reserve(
        self,
        person: Person,
        *,
        filename: str = FILENAME,
        mime: str = PDF,
        size: int | None = None,
        source: str = "file",
    ) -> httpx.Response:
        return self.request(
            "POST",
            "/api/documents",
            person,
            json={
                "filename": filename,
                "mime_type": mime,
                "size_bytes": len(SAMPLES.get(mime, b"x")) if size is None else size,
                "source": source,
            },
        )

    def uploaded(
        self,
        person: Person,
        *,
        mime: str = PDF,
        data: bytes | None = None,
        registered_type: str | None = None,
        declared_size: int | None = None,
        filename: str = FILENAME,
    ) -> UUID:
        """Reserva el documento y deja el archivo en Storage como lo haría el navegador. `uploading` todavía."""
        content = SAMPLES[mime] if data is None else data
        reserved = self.reserve(
            person, filename=filename, mime=mime, size=len(content) if declared_size is None else declared_size
        )
        assert reserved.status_code == 201, reserved.text
        document_id = UUID(reserved.json()["id"])
        self.storage.put(self.path_of(person, document_id, mime), content, registered_type or mime)
        return document_id

    def complete(self, person: Person, document_id: UUID | str) -> httpx.Response:
        return self.request("POST", f"/api/documents/{document_id}/complete", person)

    def read(self, person: Person, **kwargs: Any) -> UUID:
        """Subida + `complete`: el documento queda en `review` (con el simulado por defecto) o `extraction_failed`."""
        document_id = self.uploaded(person, **kwargs)
        done = self.complete(person, document_id)
        assert done.status_code == 200, done.text
        return document_id

    def get(self, person: Person, document_id: UUID | str) -> httpx.Response:
        return self.request("GET", f"/api/documents/{document_id}", person)

    def retry(self, person: Person, document_id: UUID | str) -> httpx.Response:
        return self.request("POST", f"/api/documents/{document_id}/retry", person)

    def discard(self, person: Person, document_id: UUID | str) -> httpx.Response:
        return self.request("DELETE", f"/api/documents/{document_id}", person)

    def preview(self, person: Person, document_id: UUID | str) -> httpx.Response:
        return self.request("GET", f"/api/documents/{document_id}/preview", person)

    def save_review(self, person: Person, document_id: UUID | str, body: dict[str, Any]) -> httpx.Response:
        return self.request("PUT", f"/api/documents/{document_id}/review", person, json=body)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def app(jwks_client: FakeJwksClient, storage: FakeStorage) -> FastAPI:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.state.storage = storage
    return application


@pytest.fixture
def api(app: FastAPI, signer: Signer, cast: Cast, storage: FakeStorage) -> Iterator[Api]:  # noqa: F811
    """`raise_server_exceptions=False`: un error inesperado se ve como lo vería un cliente real (un 500)."""
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Api(app, client, signer, cast, storage)


# --- Estado de la base de datos (solo para comprobar) ------------------------------------------------------------------------


def db_row(admin: Connection[DictRow], document_id: UUID | str) -> DictRow:
    row = admin.execute(
        "select status::text as status, error_code, extraction, review, injection_suspected, agent_trace_id "
        "from public.documents where id = %s",
        (document_id,),
    ).fetchone()
    assert row is not None
    return row


def age(admin: Connection[DictRow], document_id: UUID | str, seconds: int) -> None:
    """Envejece una fila (el trigger deja fijar `updated_at` a propósito): simula una lectura interrumpida hace `seconds`."""
    admin.execute(
        "update public.documents set updated_at = now() - make_interval(secs => %s) where id = %s",
        (seconds, document_id),
    )
