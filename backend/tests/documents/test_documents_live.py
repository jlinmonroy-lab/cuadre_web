"""Punta a punta contra la pila REAL de Supabase: tokens ES256 de GoTrue, Storage real y el agente simulado (SPEC-W-002 AC-01, AC-04, AC-07, AC-13).

Es lo más parecido a lo que hará el navegador sin navegador: la API reserva y firma con el JWT de la persona, el «navegador» sube con
la URL firmada y SOLO `Content-Type`, la API comprueba el archivo contra Storage de verdad y el agente lee con una URL firmada que se
puede abrir sin ninguna cabecera. El CORS desde un navegador real queda para el E2E del hito 5 (Anexo B.2).

Requiere `npx supabase start` y `TEST_SUPABASE_ANON_KEY`. Crea usuarios nuevos con contraseña propia y borra lo que sube.
"""

import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.agents import FakeAgentsClient
from cuadre.documents.limits import MIME_EXTENSIONS
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.documents.conftest import FILENAME, PDF, SAMPLES
from tests.support import Cast, make_cast, password_grant

pytestmark = pytest.mark.live

STORAGE = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1"
ORIGIN = "http://localhost:3000"


@dataclass
class Live:
    client: TestClient
    cast: Cast
    tokens: dict[str, str]
    paths: list[tuple[str, str]] = field(default_factory=list)  # (clave del dueño, ruta) para limpiar

    def headers(self, who: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[who]}"}

    def call(self, who: str, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return self.client.request(method, url, headers=self.headers(who), **kwargs)

    def reserve(self, who: str = "alicia", *, mime: str = PDF, size: int | None = None) -> tuple[UUID, str]:
        response = self.call(
            who,
            "POST",
            "/api/documents",
            json={
                "filename": FILENAME,
                "mime_type": mime,
                "size_bytes": len(SAMPLES[mime]) if size is None else size,
                "source": "camera",
            },
        )
        assert response.status_code == 201, response.text
        document_id = UUID(response.json()["id"])
        self.paths.append((who, f"{self.cast[who].id}/{document_id}.{MIME_EXTENSIONS[mime]}"))
        return document_id, response.json()["upload"]["url"]

    @staticmethod
    def browser_put(url: str, data: bytes, content_type: str = PDF) -> httpx.Response:
        """Lo que hará el navegador: solo Content-Type (y su Origin), sin Authorization ni apikey."""
        return httpx.put(url, content=data, headers={"Content-Type": content_type, "Origin": ORIGIN}, timeout=30)


@pytest.fixture
def live(admin: Connection[DictRow]) -> Iterator[Live]:
    if not os.environ.get("TEST_SUPABASE_ANON_KEY"):
        pytest.skip("Falta TEST_SUPABASE_ANON_KEY (clave publicable de la pila local, en el .env)")
    password = secrets.token_urlsafe(18)
    cast = make_cast(admin, password=password)
    tokens = {}
    for person in cast.everyone():
        grant = password_grant(person.email, password)
        assert grant.status_code == 200, f"no se pudo iniciar sesión como {person.key}: {grant.status_code}"
        tokens[person.key] = grant.json()["access_token"]

    app = create_app(make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"]))
    app.state.agents_client = FakeAgentsClient(["invoice_ok"] * 5)
    with TestClient(app, raise_server_exceptions=False) as client:
        session = Live(client, cast, tokens)
        yield session
    for owner, path in session.paths:  # el dueño borra lo que subió; si ya no está, no pasa nada
        httpx.request("DELETE", f"{STORAGE}/object/documents/{path}", headers=session.headers(owner), timeout=20)


def stored(admin: Connection[DictRow], path: str) -> dict[str, Any] | None:
    return admin.execute(
        "select (metadata->>'size')::int as size, metadata->>'mimetype' as mimetype from storage.objects "
        "where bucket_id = 'documents' and name = %s",
        (path,),
    ).fetchone()


def status_of(admin: Connection[DictRow], document_id: UUID) -> str:
    row = admin.execute("select status::text as status from public.documents where id = %s", (document_id,)).fetchone()
    assert row is not None
    return str(row["status"])


def test_the_whole_flow_against_real_storage(live: Live, admin: Connection[DictRow]) -> None:
    document_id, upload_url = live.reserve()
    path = live.paths[-1][1]
    assert upload_url.startswith(f"{STORAGE}/object/upload/sign/documents/{path}?token="), "URL completa de Storage"

    put = live.browser_put(upload_url, SAMPLES[PDF])
    assert put.status_code == 200, put.text
    assert stored(admin, path) == {"size": len(SAMPLES[PDF]), "mimetype": PDF}

    done = live.call("alicia", "POST", f"/api/documents/{document_id}/complete")
    assert done.status_code == 200 and done.json() == {"id": str(document_id), "status": "review"}, done.text
    detail = live.call("alicia", "GET", f"/api/documents/{document_id}").json()
    assert detail["extraction"]["total_cents"] == 3000 and detail["status"] == "review"

    # La vista previa: una URL firmada de 60 s que se abre sin ninguna cabecera y devuelve el archivo.
    preview = live.call("alicia", "GET", f"/api/documents/{document_id}/preview").json()
    assert preview["expires_in"] == 60 and preview["previewable"] is True
    opened = httpx.get(preview["url"], timeout=20)
    assert opened.status_code == 200 and opened.content == SAMPLES[PDF] and opened.headers["content-type"] == PDF

    # El agente recibió una URL de lectura de 120 s, abierta también sin cabeceras.
    (request,) = live.client.app.state.agents_client.calls  # type: ignore[attr-defined]
    assert httpx.get(str(request.document_url), timeout=20).content == SAMPLES[PDF]

    # Otra persona no ve el documento ni puede firmar su archivo.
    assert live.call("beto", "GET", f"/api/documents/{document_id}").status_code == 404
    assert live.call("beto", "GET", f"/api/documents/{document_id}/preview").status_code == 404
    direct = httpx.post(
        f"{STORAGE}/object/sign/documents/{path}", headers=live.headers("beto"), json={"expiresIn": 60}, timeout=20
    )
    assert direct.json()["statusCode"] == "404", "un archivo ajeno responde como uno inexistente"

    # Descartar borra el archivo de verdad.
    assert live.call("alicia", "DELETE", f"/api/documents/{document_id}").status_code == 204
    assert stored(admin, path) is None
    assert status_of(admin, document_id) == "discarded"


def test_a_file_whose_content_is_not_a_pdf_is_rejected_and_deleted_from_storage(
    live: Live, admin: Connection[DictRow]
) -> None:
    """Storage acepta cualquier contenido con un tipo permitido (Anexo B.1): la firma la comprueba la API."""
    fake = b"esto no es un pdf, aunque lo diga la cabecera"
    document_id, url = live.reserve(size=len(fake))
    path = live.paths[-1][1]
    assert live.browser_put(url, fake).status_code == 200
    assert stored(admin, path) is not None

    response = live.call("alicia", "POST", f"/api/documents/{document_id}/complete")
    assert response.status_code == 422 and response.json()["code"] == "file_type_mismatch"
    assert stored(admin, path) is None, "el archivo se borra"
    assert status_of(admin, document_id) == "discarded"
    assert len(live.client.app.state.agents_client.calls) == 0  # type: ignore[attr-defined]


def test_a_type_registered_by_storage_that_differs_from_the_declared_one_is_rejected(
    live: Live, admin: Connection[DictRow]
) -> None:
    document_id, url = live.reserve()
    path = live.paths[-1][1]
    assert (
        live.browser_put(url, SAMPLES[PDF], content_type="image/png").status_code == 200
    )  # Storage lo registra como PNG
    assert stored(admin, path) == {"size": len(SAMPLES[PDF]), "mimetype": "image/png"}

    response = live.call("alicia", "POST", f"/api/documents/{document_id}/complete")
    assert response.status_code == 422 and response.json()["code"] == "file_type_mismatch"
    assert stored(admin, path) is None


def test_a_size_that_differs_from_the_declared_one_is_rejected(live: Live, admin: Connection[DictRow]) -> None:
    document_id, url = live.reserve(size=len(SAMPLES[PDF]) + 7)
    path = live.paths[-1][1]
    assert live.browser_put(url, SAMPLES[PDF]).status_code == 200

    response = live.call("alicia", "POST", f"/api/documents/{document_id}/complete")
    assert response.status_code == 422 and response.json()["code"] == "upload_size_mismatch"
    assert stored(admin, path) is None and status_of(admin, document_id) == "discarded"


def test_completing_before_the_upload_finishes_is_409_and_works_once_it_has(
    live: Live, admin: Connection[DictRow]
) -> None:
    document_id, url = live.reserve()
    early = live.call("alicia", "POST", f"/api/documents/{document_id}/complete")
    assert early.status_code == 409 and early.json()["code"] == "upload_missing"
    assert status_of(admin, document_id) == "uploading"

    assert live.browser_put(url, SAMPLES[PDF]).status_code == 200
    assert live.call("alicia", "POST", f"/api/documents/{document_id}/complete").json()["status"] == "review"


@pytest.mark.parametrize("mime", ["image/jpeg", "image/png", "image/heic", "image/webp"])
def test_every_image_type_goes_through_real_storage(live: Live, admin: Connection[DictRow], mime: str) -> None:
    document_id, url = live.reserve(mime=mime)
    assert live.browser_put(url, SAMPLES[mime], content_type=mime).status_code == 200
    done = live.call("alicia", "POST", f"/api/documents/{document_id}/complete")
    assert done.status_code == 200 and done.json()["status"] == "review", done.text
    preview = live.call("alicia", "GET", f"/api/documents/{document_id}/preview").json()
    assert preview["previewable"] is (mime != "image/heic")


def test_the_url_of_another_persons_reservation_cannot_be_used_to_reserve_for_oneself(live: Live) -> None:
    """Storage evalúa la política al firmar: Beto no puede firmar la subida de una ruta reservada por Alicia."""
    document_id, _ = live.reserve("alicia")
    path = live.paths[-1][1]
    attempt = httpx.post(f"{STORAGE}/object/upload/sign/documents/{path}", headers=live.headers("beto"), timeout=20)
    assert attempt.json()["statusCode"] == "403"
    assert document_id
