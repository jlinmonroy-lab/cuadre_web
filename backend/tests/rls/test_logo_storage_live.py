"""AC-14 a AC-17 · Las políticas del bucket `logos` contra la API REAL de Storage, con tokens ES256 de GoTrue (SPEC-W-005 §5.2, Anexo B.1).

`test_logo_storage.py` prueba la lógica por SQL. Esto prueba el cableado y lo que midió el spike del hito 0: la política de INSERT se evalúa al firmar
(y exige el rol `usuario`), los límites del bucket (1 MiB; 413 y 415), que Storage no mira el contenido, que `Range` devuelve los 12 primeros bytes
para comprobar la firma, la lectura firmada de 60 s y el borrado con el JWT del dueño. Si una versión nueva de Storage cambia algo, falla aquí.

Requiere `npx supabase start` y `TEST_SUPABASE_ANON_KEY`. Crea usuarios nuevos con contraseña propia (no usa los del seed).
"""

import os
import secrets
import struct
import time
import uuid
import zlib
from collections.abc import Iterator
from dataclasses import dataclass

import httpx2 as httpx
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Pool, apply_scenario, call, make_cast, password_grant

pytestmark = pytest.mark.live

STORAGE = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1"
ORIGIN = "http://localhost:3000"
MIB = 1_048_576


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    + _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
    + _chunk(b"IEND", b"")
)
JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")
WEBP = b"RIFF" + struct.pack("<I", 26) + b"WEBPVP8 " + b"\x00" * 10


@dataclass
class Session:
    cast: Cast
    tokens: dict[str, str]
    uploaded: list[tuple[str, str]]  # (clave del dueño, ruta) para limpiar al terminar

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
    for owner, path in current.uploaded:  # el dueño borra lo que subió; si ya no está, no pasa nada
        httpx.request("DELETE", f"{STORAGE}/object/logos/{path}", headers=current.headers(owner), timeout=20)


def code(resp: httpx.Response) -> int:
    """Storage responde casi todo con HTTP 400 y el estado real en el cuerpo (`statusCode`)."""
    if resp.status_code < 400:
        return resp.status_code
    try:
        return int(resp.json()["statusCode"])
    except (ValueError, KeyError):
        return resp.status_code


def new_path(s: Session, who: str, ext: str = "png") -> str:
    return f"{s.cast[who].id}/{uuid.uuid4()}.{ext}"


def sign_upload(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.post(f"{STORAGE}/object/upload/sign/logos/{path}", headers=s.headers(who), timeout=20)


def put_file(url: str, data: bytes, content_type: str = "image/png") -> httpx.Response:
    """Lo que hará el navegador: solo Content-Type (y su Origin), sin Authorization ni apikey."""
    return httpx.put(url, content=data, headers={"Content-Type": content_type, "Origin": ORIGIN}, timeout=60)


def upload(
    s: Session, who: str, data: bytes, content_type: str = "image/png", ext: str = "png"
) -> tuple[str, httpx.Response]:
    path = new_path(s, who, ext)
    signed = sign_upload(s, who, path)
    assert signed.status_code == 200, signed.text
    s.uploaded.append((who, path))
    return path, put_file(f"{STORAGE}{signed.json()['url']}", data, content_type)


def sign_read(s: Session, who: str, path: str, seconds: int = 60) -> httpx.Response:
    return httpx.post(
        f"{STORAGE}/object/sign/logos/{path}", headers=s.headers(who), json={"expiresIn": seconds}, timeout=20
    )


def head_bytes(s: Session, who: str, path: str, length: int = 12) -> httpx.Response:
    headers = {**s.headers(who), "Range": f"bytes=0-{length - 1}"}
    return httpx.get(f"{STORAGE}/object/authenticated/logos/{path}", headers=headers, timeout=20)


def info(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.get(f"{STORAGE}/object/info/authenticated/logos/{path}", headers=s.headers(who), timeout=20)


def delete(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.delete(f"{STORAGE}/object/logos/{path}", headers=s.headers(who), timeout=20)


# --- firmar la subida -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ext", ["png", "jpg", "webp"])
@pytest.mark.parametrize("who", ["alicia", "beto"])
def test_a_usuario_gets_a_signed_upload_for_their_own_folder(session: Session, who: str, ext: str) -> None:
    signed = sign_upload(session, who, new_path(session, who, ext))
    assert signed.status_code == 200
    assert set(signed.json()) == {"url", "token"}
    assert signed.json()["url"].startswith("/object/upload/sign/logos/"), "la URL es relativa a /storage/v1"


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_even_sign_an_upload_to_their_own_folder(session: Session, who: str) -> None:
    """T5-04, B.1: la política exige el rol `usuario`."""
    assert code(sign_upload(session, who, new_path(session, who))) == 403


def test_nobody_signs_an_upload_to_another_persons_folder_or_to_a_bad_name(session: Session) -> None:
    cast = session.cast
    assert code(sign_upload(session, "alicia", f"{cast.beto.id}/{uuid.uuid4()}.png")) == 403
    for name in (
        "logo.png",
        f"{uuid.uuid4()}.svg",
        f"{uuid.uuid4()}.gif",
        f"x/{uuid.uuid4()}.png",
        f"{str(uuid.uuid4()).upper()}.png",
    ):
        assert code(sign_upload(session, "alicia", f"{cast.alicia.id}/{name}")) == 403, name


# --- subir: los límites del bucket ----------------------------------------------------------------------------------------------------------


def test_one_mebibyte_is_accepted_and_one_byte_more_is_not(session: Session) -> None:
    exact = PNG + b"\x00" * (MIB - len(PNG))
    path, ok = upload(session, "alicia", exact)
    assert ok.status_code == 200 and info(session, "alicia", path).json()["size"] == MIB
    _, too_big = upload(session, "alicia", exact + b"\x00")
    assert code(too_big) == 413


@pytest.mark.parametrize("content_type", ["image/svg+xml", "image/gif", "text/plain", "application/pdf"])
def test_other_types_are_refused_with_415(session: Session, content_type: str) -> None:
    assert code(upload(session, "alicia", b"<svg/>", content_type)[1]) == 415


def test_a_content_type_with_parameters_is_accepted(session: Session) -> None:
    assert upload(session, "alicia", PNG, "image/png; charset=binary")[1].status_code == 200


def test_a_signed_url_admits_one_upload_only(session: Session) -> None:
    path = new_path(session, "alicia")
    url = f"{STORAGE}{sign_upload(session, 'alicia', path).json()['url']}"
    session.uploaded.append(("alicia", path))
    assert put_file(url, PNG).status_code == 200
    assert code(put_file(url, PNG + b"x")) == 409


# --- Storage no mira el contenido: la firma la comprueba la API -----------------------------------------------------------------------------


def test_storage_does_not_look_inside_the_file(session: Session) -> None:
    path, put = upload(session, "alicia", b"esto no es una imagen")
    assert put.status_code == 200
    meta = info(session, "alicia", path).json()
    assert (meta["size"], meta["content_type"]) == (21, "image/png")
    path2, put2 = upload(session, "alicia", PNG, "image/jpeg", "jpg")  # un PNG declarado como JPEG también entra
    assert put2.status_code == 200 and info(session, "alicia", path2).json()["content_type"] == "image/jpeg"


@pytest.mark.parametrize(
    ("data", "content_type", "ext", "head"),
    [
        (PNG, "image/png", "png", PNG[:12]),
        (JPEG, "image/jpeg", "jpg", JPEG[:12]),
        (WEBP, "image/webp", "webp", WEBP[:12]),
    ],
)
def test_range_returns_exactly_the_first_twelve_bytes(
    session: Session, data: bytes, content_type: str, ext: str, head: bytes
) -> None:
    path, put = upload(session, "alicia", data, content_type, ext)
    assert put.status_code == 200
    reply = head_bytes(session, "alicia", path)
    assert reply.status_code == 206 and reply.content == head and len(reply.content) == 12
    assert reply.headers["content-range"] == f"bytes 0-11/{len(data)}"
    meta = info(session, "alicia", path).json()
    assert (meta["size"], meta["content_type"]) == (len(data), content_type)


# --- leer ------------------------------------------------------------------------------------------------------------------------------------


def test_the_owner_signs_a_read_and_the_url_serves_the_image_without_headers(session: Session) -> None:
    path, _ = upload(session, "alicia", PNG)
    signed = sign_read(session, "alicia", path, 60)
    assert signed.status_code == 200
    got = httpx.get(f"{STORAGE}{signed.json()['signedURL']}", timeout=20)
    assert got.status_code == 200 and got.content == PNG
    assert got.headers["content-type"] == "image/png" and got.headers["access-control-allow-origin"] in {"*", ORIGIN}


def test_a_signed_read_expires(session: Session) -> None:
    path, _ = upload(session, "alicia", PNG)
    url = f"{STORAGE}{sign_read(session, 'alicia', path, 2).json()['signedURL']}"
    assert httpx.get(url, timeout=20).status_code == 200
    time.sleep(3.2)
    assert code(httpx.get(url, timeout=20)) == 400


@pytest.mark.parametrize("scenario", ["baseline", "pending", "active", "revoked", "declined"])
def test_signed_reads_follow_the_link_state(app_pool: Pool, session: Session, scenario: str) -> None:
    apply_scenario(app_pool, session.cast, scenario)
    path, _ = upload(session, "alicia", PNG)
    expected = {"alicia": 200, "beto": 404, "gina": 200 if scenario == "active" else 404, "gus": 404, "adan": 404}
    for who, status in expected.items():
        assert code(sign_read(session, who, path)) == status, f"{scenario}: {who}"
    assert code(sign_read(session, "alicia", f"{session.cast.alicia.id}/{uuid.uuid4()}.png")) == 404, (
        "una ruta inexistente"
    )


def test_an_active_gestor_reads_but_neither_deletes_nor_uploads(app_pool: Pool, session: Session) -> None:
    apply_scenario(app_pool, session.cast, "active")
    path, _ = upload(session, "alicia", PNG)
    assert head_bytes(session, "gina", path, 8).status_code == 206
    assert code(delete(session, "gina", path)) == 403
    assert code(sign_upload(session, "gina", new_path(session, "alicia"))) == 403


# --- reemplazar y borrar ------------------------------------------------------------------------------------------------------------------


def test_replacing_a_logo_and_deleting_the_previous_one_with_the_owners_token(
    app_pool: Pool, admin: Connection[DictRow], session: Session
) -> None:
    first, _ = upload(session, "alicia", PNG)
    second, put = upload(session, "alicia", PNG)
    assert put.status_code == 200
    assert call(app_pool, session.cast.alicia, "set_business_logo", first).rows[0]["set_business_logo"] is None
    previous = call(app_pool, session.cast.alicia, "set_business_logo", second).rows[0]["set_business_logo"]
    assert previous == first

    assert code(delete(session, "beto", previous)) == 403, "otro usuario no borra"
    assert code(delete(session, "alicia", previous)) == 200
    assert code(delete(session, "alicia", previous)) == 404, "borrar lo que ya no está"
    assert code(delete(session, "alicia", f"{session.cast.alicia.id}/{uuid.uuid4()}.png")) == 404
    assert code(sign_read(session, "alicia", previous)) == 404
    assert code(sign_read(session, "alicia", second)) == 200


def test_an_upload_nobody_completes_leaves_an_orphan_object(admin: Connection[DictRow], session: Session) -> None:
    """Ya excluido en §4: Storage guarda el objeto aunque la API no llegue a llamar a `set_business_logo`."""
    path, put = upload(session, "alicia", PNG)
    assert put.status_code == 200
    row = admin.execute(
        "select count(*) as n from storage.objects where bucket_id = 'logos' and name = %s", (path,)
    ).fetchone()
    logo = admin.execute(
        "select logo_path from public.business_profiles where owner_id = %s", (session.cast.alicia.id,)
    ).fetchone()
    assert row is not None and row["n"] == 1
    assert logo is not None and logo["logo_path"] is None
