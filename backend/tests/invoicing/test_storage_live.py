"""AC-16 · `HttpStorage` (subir y descargar el PDF) contra el Storage REAL, con tokens ES256 de GoTrue (SPEC-W-007 §5.4, B.1-C).

`test_pdf_storage_client.py` prueba el cliente contra un servidor guionado; `tests/rls/test_invoices_storage_live.py`, las políticas con HTTP a mano. Esto
prueba que el cliente de la aplicación y el Storage real se entienden: 200 al subir, **409 al repetir** (que el cliente da por «ya está»), la descarga con
su huella, un objeto ajeno como inexistente, los límites del bucket y que nadie reemplaza ni borra un PDF.

Requiere `npx supabase start` y `TEST_SUPABASE_ANON_KEY`. Crea usuarios nuevos con contraseña propia (no usa los del seed). Un PDF subido no lo borra su
dueño (esa es la regla): al terminar se retira con la clave de servicio de la pila local, solo aquí y si el `.env` la trae.
"""

import hashlib
import os
import secrets
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import httpx2 as httpx
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.documents.storage import StorageDenied, StorageNotFound, StorageUnavailable
from cuadre.invoicing.storage import invoice_storage
from tests.support import Cast, Pool, apply_scenario, make_cast, password_grant

pytestmark = pytest.mark.live

SUPABASE_URL = os.environ["SUPABASE_URL"]
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
MIB = 1_048_576


@dataclass
class Session:
    cast: Cast
    tokens: dict[str, str]
    uploaded: list[str]

    def new_path(self, who: str, data: bytes = PDF) -> str:
        path = f"{self.cast[who].id}/{uuid.uuid4()}-{hashlib.sha256(data).hexdigest()[:16]}.pdf"
        self.uploaded.append(path)
        return path


@pytest.fixture
def session(admin: Connection[DictRow]) -> Iterator[Session]:
    if not os.environ.get("TEST_SUPABASE_ANON_KEY"):
        pytest.skip("Falta TEST_SUPABASE_ANON_KEY (clave publicable de la pila local, en el .env)")
    password = secrets.token_urlsafe(18)
    cast = make_cast(admin, password=password)
    tokens: dict[str, str] = {}
    for person in cast.everyone():
        grant = password_grant(person.email, password)
        assert grant.status_code == 200, f"no se pudo iniciar sesión como {person.key}: {grant.status_code}"
        tokens[person.key] = grant.json()["access_token"]
    current = Session(cast, tokens, [])
    yield current
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if service_key and current.uploaded:
        httpx.request(
            "DELETE",
            f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/invoices",
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
            json={"prefixes": current.uploaded},
            timeout=30,
        )


STORAGE = invoice_storage(SUPABASE_URL)


def test_a_pdf_goes_up_and_comes_back_byte_for_byte(session: Session) -> None:
    path = session.new_path("alicia")
    token = session.tokens["alicia"]
    assert STORAGE.upload(path, PDF, "application/pdf", token=token) == "created"
    data = STORAGE.download(path, token=token, max_bytes=MIB)
    assert data == PDF and hashlib.sha256(data).hexdigest() == hashlib.sha256(PDF).hexdigest()
    info = STORAGE.object_info(path, token=token)
    assert info is not None and (info.size, info.content_type) == (len(PDF), "application/pdf")


def test_uploading_the_same_path_again_is_already_there_and_changes_nothing(session: Session) -> None:
    path = session.new_path("alicia")
    token = session.tokens["alicia"]
    assert STORAGE.upload(path, PDF, "application/pdf", token=token) == "created"
    assert STORAGE.upload(path, PDF, "application/pdf", token=token) == "exists"
    assert (
        STORAGE.upload(path, PDF + b"otro", "application/pdf", token=token) == "exists"
    )  # no se reemplaza: el primero manda
    assert STORAGE.download(path, token=token, max_bytes=MIB) == PDF


def test_a_manager_with_an_active_link_reads_but_everyone_else_finds_nothing(app_pool: Pool, session: Session) -> None:
    apply_scenario(app_pool, session.cast, "active")
    path = session.new_path("alicia")
    STORAGE.upload(path, PDF, "application/pdf", token=session.tokens["alicia"])
    assert STORAGE.download(path, token=session.tokens["gina"], max_bytes=MIB) == PDF
    for who in ("beto", "gus", "adan"):
        with pytest.raises(StorageNotFound):
            STORAGE.download(path, token=session.tokens[who], max_bytes=MIB)


def test_a_revoked_manager_finds_nothing(app_pool: Pool, session: Session) -> None:
    apply_scenario(app_pool, session.cast, "revoked")
    path = session.new_path("alicia")
    STORAGE.upload(path, PDF, "application/pdf", token=session.tokens["alicia"])
    with pytest.raises(StorageNotFound):
        STORAGE.download(path, token=session.tokens["gina"], max_bytes=MIB)


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_manager_or_an_admin_cannot_upload_not_even_to_their_own_folder(session: Session, who: str) -> None:
    with pytest.raises(StorageDenied):
        STORAGE.upload(session.new_path(who), PDF, "application/pdf", token=session.tokens[who])


def test_nobody_uploads_to_another_persons_folder(session: Session) -> None:
    path = f"{session.cast.beto.id}/{uuid.uuid4()}-{hashlib.sha256(PDF).hexdigest()[:16]}.pdf"
    with pytest.raises(StorageDenied):
        STORAGE.upload(path, PDF, "application/pdf", token=session.tokens["alicia"])


def test_nobody_replaces_or_deletes_an_uploaded_pdf(session: Session) -> None:
    path = session.new_path("alicia")
    token = session.tokens["alicia"]
    STORAGE.upload(path, PDF, "application/pdf", token=token)
    with pytest.raises(StorageDenied):
        STORAGE.delete(path, token=token)  # no hay política de DELETE
    assert STORAGE.download(path, token=token, max_bytes=MIB) == PDF


def test_the_bucket_limits_one_mebibyte_and_pdf_only(session: Session) -> None:
    token = session.tokens["alicia"]
    exact = PDF + b"\x00" * (MIB - len(PDF))
    assert STORAGE.upload(session.new_path("alicia", exact), exact, "application/pdf", token=token) == "created"
    with pytest.raises(StorageUnavailable):  # 413
        STORAGE.upload(session.new_path("alicia", exact + b"\x00"), exact + b"\x00", "application/pdf", token=token)
    with pytest.raises(StorageUnavailable):  # 415
        STORAGE.upload(session.new_path("alicia"), PDF, "text/plain", token=token)


def test_download_has_a_ceiling_and_a_missing_object_is_not_found(session: Session) -> None:
    token = session.tokens["alicia"]
    path = session.new_path("alicia")
    STORAGE.upload(path, PDF, "application/pdf", token=token)
    assert (
        len(STORAGE.download(path, token=token, max_bytes=10)) == 11
    )  # el byte de más delata un objeto demasiado grande
    with pytest.raises(StorageNotFound):
        STORAGE.download(session.new_path("alicia", b"otro"), token=token, max_bytes=MIB)
