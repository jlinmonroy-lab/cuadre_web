"""AC-22 y AC-23 · Las políticas del bucket `invoices` contra la API REAL de Storage, con tokens ES256 de GoTrue (SPEC-W-007 §5.2, Anexo B.1-C).

`test_invoices_storage.py` prueba la lógica por SQL. Esto prueba el cableado y lo que midió el spike del hito 0: la política de INSERT se evalúa al
firmar (y exige el rol `usuario`), los límites del bucket (1 MiB: 413; solo PDF: 415), que repetir la subida da 409 («ya está»), que reemplazar o borrar
un PDF ya subido da 403 (no hay política de UPDATE ni de DELETE) y que leer lo hacen el dueño y un gestor con vínculo activo, y nadie más (404).

Requiere `npx supabase start` y `TEST_SUPABASE_ANON_KEY`. Crea usuarios nuevos con contraseña propia (no usa los del seed). Un PDF subido no lo borra
su dueño (ese es el objeto de la prueba): al terminar se retira con la clave de servicio de la pila local, si el `.env` la trae.
"""

import os
import secrets
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import httpx2 as httpx
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Pool, apply_scenario, make_cast, password_grant

pytestmark = pytest.mark.live

STORAGE = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1"
ORIGIN = "http://localhost:3000"
MIB = 1_048_576
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
SHA16 = "0123456789abcdef"


@dataclass
class Session:
    cast: Cast
    tokens: dict[str, str]
    uploaded: list[str]  # rutas subidas, para retirarlas al terminar

    def headers(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[key]}"}


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
            f"{STORAGE}/object/invoices",
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
            json={"prefixes": current.uploaded},
            timeout=30,
        )


def code(resp: httpx.Response) -> int:
    """Storage responde casi todo con HTTP 400 y el estado real en el cuerpo (`statusCode`)."""
    if resp.status_code < 400:
        return resp.status_code
    try:
        return int(resp.json()["statusCode"])
    except (ValueError, KeyError):
        return resp.status_code


def new_path(s: Session, who: str) -> str:
    return f"{s.cast[who].id}/{uuid.uuid4()}-{SHA16}.pdf"


def sign_upload(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.post(f"{STORAGE}/object/upload/sign/invoices/{path}", headers=s.headers(who), timeout=20)


def put_file(url: str, data: bytes, content_type: str = "application/pdf") -> httpx.Response:
    """Lo que hará el servicio: solo Content-Type, sin Authorization ni apikey (la URL firmada lleva el permiso)."""
    return httpx.put(url, content=data, headers={"Content-Type": content_type, "Origin": ORIGIN}, timeout=60)


def upload(
    s: Session, who: str, data: bytes = PDF, content_type: str = "application/pdf"
) -> tuple[str, httpx.Response]:
    path = new_path(s, who)
    signed = sign_upload(s, who, path)
    assert signed.status_code == 200, signed.text
    s.uploaded.append(path)
    return path, put_file(f"{STORAGE}{signed.json()['url']}", data, content_type)


def sign_read(s: Session, who: str, path: str, seconds: int = 60) -> httpx.Response:
    return httpx.post(
        f"{STORAGE}/object/sign/invoices/{path}", headers=s.headers(who), json={"expiresIn": seconds}, timeout=20
    )


def info(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.get(f"{STORAGE}/object/info/authenticated/invoices/{path}", headers=s.headers(who), timeout=20)


def delete(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.delete(f"{STORAGE}/object/invoices/{path}", headers=s.headers(who), timeout=20)


# --- Firmar la subida -----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto"])
def test_a_usuario_gets_a_signed_upload_for_their_own_folder(session: Session, who: str) -> None:
    signed = sign_upload(session, who, new_path(session, who))
    assert signed.status_code == 200
    assert set(signed.json()) == {"url", "token"}
    assert signed.json()["url"].startswith("/object/upload/sign/invoices/"), "la URL es relativa a /storage/v1"


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_even_sign_an_upload_to_their_own_folder(session: Session, who: str) -> None:
    assert code(sign_upload(session, who, new_path(session, who))) == 403


def test_nobody_signs_an_upload_to_another_persons_folder_or_to_a_bad_name(session: Session) -> None:
    cast = session.cast
    assert code(sign_upload(session, "alicia", f"{cast.beto.id}/{uuid.uuid4()}-{SHA16}.pdf")) == 403
    for name in (
        "factura.pdf",
        f"{uuid.uuid4()}.pdf",
        f"{uuid.uuid4()}-{SHA16}.png",
        f"{uuid.uuid4()}-{SHA16}.PDF",
        f"{uuid.uuid4()}-{SHA16[:15]}.pdf",
        f"{str(uuid.uuid4()).upper()}-{SHA16}.pdf",
        f"x/{uuid.uuid4()}-{SHA16}.pdf",
    ):
        assert code(sign_upload(session, "alicia", f"{cast.alicia.id}/{name}")) == 403, name


# --- Subir: los límites del bucket --------------------------------------------------------------------------------------------------------------


def test_one_mebibyte_is_accepted_and_one_byte_more_is_not(session: Session) -> None:
    exact = PDF + b"\x00" * (MIB - len(PDF))
    path, ok = upload(session, "alicia", exact)
    assert ok.status_code == 200 and info(session, "alicia", path).json()["size"] == MIB
    _, too_big = upload(session, "alicia", exact + b"\x00")
    assert code(too_big) == 413


@pytest.mark.parametrize("content_type", ["image/png", "image/jpeg", "text/plain", "application/json", "text/html"])
def test_other_types_are_refused_with_415(session: Session, content_type: str) -> None:
    assert code(upload(session, "alicia", b"x", content_type)[1]) == 415


def test_a_content_type_with_parameters_is_accepted(session: Session) -> None:
    assert upload(session, "alicia", PDF, "application/pdf; charset=binary")[1].status_code == 200


def test_a_signed_url_admits_one_upload_only_and_the_second_means_it_is_already_there(session: Session) -> None:
    """El prefijo de la huella en la ruta hace idempotente la subida: un 409 es «ya está»."""
    path = new_path(session, "alicia")
    url = f"{STORAGE}{sign_upload(session, 'alicia', path).json()['url']}"
    session.uploaded.append(path)
    assert put_file(url, PDF).status_code == 200
    assert code(put_file(url, PDF)) == 409


def test_storage_does_not_look_inside_the_file(session: Session) -> None:
    """Por eso la huella SHA-256 que guarda `invoice_files` es la que manda en cada descarga (T7-10)."""
    path, put = upload(session, "alicia", b"esto no es un PDF")
    assert put.status_code == 200
    meta = info(session, "alicia", path).json()
    assert (meta["size"], meta["content_type"]) == (17, "application/pdf")


# --- Reemplazar y borrar --------------------------------------------------------------------------------------------------------------------


def test_nobody_replaces_or_deletes_an_uploaded_pdf(session: Session) -> None:
    path, put = upload(session, "alicia")
    assert put.status_code == 200
    replace = httpx.post(
        f"{STORAGE}/object/invoices/{path}",
        headers={**session.headers("alicia"), "x-upsert": "true", "Content-Type": "application/pdf"},
        content=PDF + b"otro",
        timeout=20,
    )
    assert code(replace) == 403, "no hay política de UPDATE: reemplazar da 403"
    for who in ("alicia", "beto", "gina", "gus", "adan"):
        assert code(delete(session, who, path)) in {403, 404}, who
    assert info(session, "alicia", path).json()["size"] == len(PDF), "el PDF sigue siendo el primero"


# --- Leer ---------------------------------------------------------------------------------------------------------------------------------


def test_the_owner_signs_a_read_and_the_url_serves_the_pdf_without_headers(session: Session) -> None:
    path, _ = upload(session, "alicia")
    signed = sign_read(session, "alicia", path, 60)
    assert signed.status_code == 200
    got = httpx.get(f"{STORAGE}{signed.json()['signedURL']}", timeout=20)
    assert got.status_code == 200 and got.content == PDF and got.headers["content-type"] == "application/pdf"


def test_a_signed_read_expires(session: Session) -> None:
    path, _ = upload(session, "alicia")
    url = f"{STORAGE}{sign_read(session, 'alicia', path, 2).json()['signedURL']}"
    assert httpx.get(url, timeout=20).status_code == 200
    time.sleep(3.2)
    assert code(httpx.get(url, timeout=20)) == 400


@pytest.mark.parametrize("scenario", ["baseline", "pending", "active", "revoked", "declined"])
def test_signed_reads_follow_the_link_state(app_pool: Pool, session: Session, scenario: str) -> None:
    apply_scenario(app_pool, session.cast, scenario)
    path, _ = upload(session, "alicia")
    expected = {"alicia": 200, "beto": 404, "gina": 200 if scenario == "active" else 404, "gus": 404, "adan": 404}
    for who, status in expected.items():
        assert code(sign_read(session, who, path)) == status, f"{scenario}: {who}"
    missing = f"{session.cast.alicia.id}/{uuid.uuid4()}-{SHA16}.pdf"
    assert code(sign_read(session, "alicia", missing)) == 404, "una ruta inexistente"


def test_an_active_gestor_reads_but_neither_deletes_nor_uploads(app_pool: Pool, session: Session) -> None:
    apply_scenario(app_pool, session.cast, "active")
    path, _ = upload(session, "alicia")
    assert info(session, "gina", path).status_code == 200
    assert code(delete(session, "gina", path)) in {403, 404}
    assert code(sign_upload(session, "gina", new_path(session, "alicia"))) == 403


def test_an_upload_nobody_registers_leaves_an_orphan_object(admin: Connection[DictRow], session: Session) -> None:
    """Ya excluido en §4: Storage guarda el objeto aunque la API no llegue a llamar a `attach_invoice_pdf`."""
    path, put = upload(session, "alicia")
    assert put.status_code == 200
    stored = admin.execute(
        "select count(*) as n from storage.objects where bucket_id = 'invoices' and name = %s", (path,)
    ).fetchone()
    files = admin.execute("select count(*) as n from public.invoice_files where storage_path = %s", (path,)).fetchone()
    assert stored == {"n": 1} and files == {"n": 0}
