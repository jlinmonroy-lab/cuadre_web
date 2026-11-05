"""AC-07 · Las políticas de Storage contra la API REAL de Storage, con tokens ES256 de GoTrue (SPEC-W-002 §5.2, Anexo B).

`test_storage_policies.py` prueba la lógica por SQL. Esto prueba el cableado: que Storage valide el JWT por JWKS, evalúe nuestras
políticas con la identidad del usuario y se comporte como descubrió el spike del hito 0 (URL relativa, 2 h de validez, una sola
subida, errores con HTTP 400 y el código real en el cuerpo, objeto ajeno = inexistente). Si una versión nueva de Storage cambia algo
de esto, falla aquí y no en producción.

Requiere `npx supabase start` y `TEST_SUPABASE_ANON_KEY`. Crea usuarios nuevos con contraseña propia (no usa los del seed).
"""

import base64
import json
import os
import secrets
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import httpx2 as httpx
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import (
    Cast,
    Doc,
    Pool,
    advance,
    apply_scenario,
    attempt,
    call,
    make_cast,
    new_document,
    password_grant,
)

pytestmark = pytest.mark.live

STORAGE = f"{os.environ['SUPABASE_URL'].rstrip('/')}/storage/v1"
ORIGIN = "http://localhost:3000"  # el origen del navegador (D-01)
PDF = b"%PDF-1.4\n% fichero sintetico de la prueba\n" + b"0" * 200 + b"\n%%EOF\n"


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
        httpx.request("DELETE", f"{STORAGE}/object/documents/{path}", headers=current.headers(owner), timeout=20)


def code(resp: httpx.Response) -> int:
    """Storage responde casi todo con HTTP 400 y el estado real en el cuerpo (`statusCode`)."""
    if resp.status_code < 400:
        return resp.status_code
    try:
        return int(resp.json()["statusCode"])
    except (ValueError, KeyError):
        return resp.status_code


def sign_upload(s: Session, who: str, path: str) -> httpx.Response:
    return httpx.post(f"{STORAGE}/object/upload/sign/documents/{path}", headers=s.headers(who), timeout=20)


def put_file(url: str, data: bytes, content_type: str = "application/pdf") -> httpx.Response:
    """Lo que hará el navegador: solo Content-Type (y su Origin), sin Authorization ni apikey."""
    return httpx.put(url, content=data, headers={"Content-Type": content_type, "Origin": ORIGIN}, timeout=30)


def sign_read(s: Session, who: str, path: str, seconds: int = 60) -> httpx.Response:
    return httpx.post(
        f"{STORAGE}/object/sign/documents/{path}", headers=s.headers(who), json={"expiresIn": seconds}, timeout=20
    )


def stored(admin: Connection[DictRow], path: str) -> dict | None:
    return admin.execute(
        "select metadata->>'size' as size, metadata->>'mimetype' as mimetype from storage.objects "
        "where bucket_id = 'documents' and name = %s",
        (path,),
    ).fetchone()


def jwt_lifetime(token: str) -> int:
    part = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    return claims["exp"] - claims["iat"]


def upload(s: Session, app_pool: Pool, who: str = "alicia") -> Doc:
    """Reserva un documento y sube PDF por la URL firmada, como el navegador."""
    doc = new_document(app_pool, s.cast[who])
    signed = sign_upload(s, who, doc.path)
    assert signed.status_code == 200, signed.text
    s.uploaded.append((who, doc.path))
    assert put_file(f"{STORAGE}{signed.json()['url']}", PDF).status_code == 200
    return doc


# --- subir ---------------------------------------------------------------------------------------------------------------------


def test_only_the_owner_gets_a_signed_upload_for_the_reserved_path(
    app_pool: Pool, admin: Connection[DictRow], session: Session
) -> None:
    cast = session.cast
    doc = new_document(app_pool, cast.alicia)

    signed = sign_upload(session, "alicia", doc.path)
    assert signed.status_code == 200
    body = signed.json()
    assert set(body) == {"url", "token"}
    assert body["url"].startswith("/object/upload/sign/documents/"), "la URL es relativa a /storage/v1"
    assert jwt_lifetime(body["token"]) == 7200, "la URL de subida vale 2 h y no se puede acortar"

    for who in ("beto", "gina", "gus", "adan"):
        assert code(sign_upload(session, who, doc.path)) == 403, who
    assert code(sign_upload(session, "alicia", f"{cast.alicia.id}/{cast.beto.id}.pdf")) == 403, "sin fila reservada"
    other = new_document(app_pool, cast.beto)
    assert code(sign_upload(session, "alicia", other.path)) == 403, "ruta reservada por otra persona"
    assert stored(admin, doc.path) is None


def test_the_browser_upload_works_once_and_only_within_the_bucket_limits(
    app_pool: Pool, admin: Connection[DictRow], session: Session
) -> None:
    doc = new_document(app_pool, session.cast.alicia)
    url = f"{STORAGE}{sign_upload(session, 'alicia', doc.path).json()['url']}"
    session.uploaded.append(("alicia", doc.path))

    preflight = httpx.options(
        url,
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert preflight.status_code == 200
    assert "PUT" in preflight.headers["access-control-allow-methods"]
    assert preflight.headers["access-control-allow-origin"] in {"*", ORIGIN}

    first = put_file(url, PDF)
    assert first.status_code == 200 and first.headers["access-control-allow-origin"] in {"*", ORIGIN}
    assert stored(admin, doc.path) == {"size": str(len(PDF)), "mimetype": "application/pdf"}

    again = put_file(url, PDF + b"x")
    assert code(again) == 409, "una URL firmada admite una sola subida"
    assert stored(admin, doc.path) == {"size": str(len(PDF)), "mimetype": "application/pdf"}, (
        "el archivo no se sobrescribe"
    )

    assert not call(app_pool, session.cast.alicia, "mark_document_uploaded", doc.id).error
    assert code(sign_upload(session, "alicia", doc.path)) == 403, "empezada la lectura, ya no se firma otra subida"

    wrong_type = new_document(app_pool, session.cast.alicia)
    wrong_url = f"{STORAGE}{sign_upload(session, 'alicia', wrong_type.path).json()['url']}"
    session.uploaded.append(("alicia", wrong_type.path))
    assert code(put_file(wrong_url, b"texto", "text/plain")) == 415
    assert stored(admin, wrong_type.path) is None


def test_storage_does_not_look_inside_the_file(app_pool: Pool, admin: Connection[DictRow], session: Session) -> None:
    """Por eso la API comprueba la firma del archivo (T2-08): Storage acepta cualquier contenido con un tipo permitido."""
    doc = new_document(app_pool, session.cast.alicia)
    url = f"{STORAGE}{sign_upload(session, 'alicia', doc.path).json()['url']}"
    session.uploaded.append(("alicia", doc.path))
    assert put_file(url, b"esto no es un pdf").status_code == 200
    assert stored(admin, doc.path) == {"size": "17", "mimetype": "application/pdf"}


# --- leer ----------------------------------------------------------------------------------------------------------------------


def test_signed_reads_follow_the_link_state_and_expire(app_pool: Pool, session: Session) -> None:
    cast = session.cast
    doc = upload(session, app_pool)

    own = sign_read(session, "alicia", doc.path, 120)
    assert own.status_code == 200
    relative = own.json()["signedURL"]
    assert relative.startswith("/object/sign/documents/")
    assert jwt_lifetime(relative.split("token=")[1]) == 120

    whole = httpx.get(f"{STORAGE}{relative}", timeout=20)  # sin ninguna cabecera: es lo único que tiene el agente
    assert whole.status_code == 200 and whole.content == PDF and whole.headers["content-type"] == "application/pdf"
    head = httpx.get(f"{STORAGE}{relative}", headers={"Range": "bytes=0-7"}, timeout=20)
    assert head.status_code == 206 and head.content == b"%PDF-1.4"
    assert head.headers["content-range"] == f"bytes 0-7/{len(PDF)}"

    for who in ("beto", "gus", "adan", "gina"):
        assert code(sign_read(session, who, doc.path)) == 404, f"{who} sin vínculo"
    ghost = sign_read(session, "alicia", f"{cast.alicia.id}/{cast.beto.id}.pdf")
    assert code(ghost) == 404 and ghost.json() == sign_read(session, "beto", doc.path).json(), (
        "un archivo ajeno responde igual que uno inexistente"
    )

    link = apply_scenario(app_pool, cast, "pending")
    assert code(sign_read(session, "gina", doc.path)) == 404, "vínculo pendiente"
    assert not call(app_pool, cast.gina, "accept_gestor_access", link).error
    assert sign_read(session, "gina", doc.path).status_code == 200, "vínculo activo"
    assert not call(app_pool, cast.alicia, "revoke_gestor_access", link).error
    assert code(sign_read(session, "gina", doc.path)) == 404, "vínculo revocado"

    brief = sign_read(session, "alicia", doc.path, 2).json()["signedURL"]
    assert httpx.get(f"{STORAGE}{brief}", timeout=20).status_code == 200
    time.sleep(3)
    expired = httpx.get(f"{STORAGE}{brief}", timeout=20)
    assert expired.status_code == 400 and expired.json()["error"] == "InvalidJWT"


def test_the_backend_can_check_size_and_signature_without_downloading_the_file(
    app_pool: Pool, session: Session
) -> None:
    doc = upload(session, app_pool)
    headers = session.headers("alicia")  # basta el JWT del usuario: no hace falta apikey

    first_bytes = httpx.get(
        f"{STORAGE}/object/authenticated/documents/{doc.path}", headers={**headers, "Range": "bytes=0-31"}, timeout=20
    )
    assert first_bytes.status_code == 206 and first_bytes.content == PDF[:32]
    assert first_bytes.headers["content-range"] == f"bytes 0-31/{len(PDF)}"

    info = httpx.get(f"{STORAGE}/object/info/authenticated/documents/{doc.path}", headers=headers, timeout=20)
    assert info.status_code == 200
    assert info.json()["size"] == len(PDF) and info.json()["content_type"] == "application/pdf"

    other = httpx.get(
        f"{STORAGE}/object/info/authenticated/documents/{doc.path}", headers=session.headers("beto"), timeout=20
    )
    assert code(other) == 404


# --- borrar --------------------------------------------------------------------------------------------------------------------


def set_status_bypassing_the_trigger(admin: Connection[DictRow], doc: Doc, status: str) -> None:
    """Solo para preparar un caso que ninguna ruta de esta spec produce (`registered` lo introduce SPEC-W-003)."""
    with admin.transaction():
        admin.execute("alter table public.documents disable trigger documents_guard")
        admin.execute("update public.documents set status = %s where id = %s", (status, doc.id))
        admin.execute("alter table public.documents enable trigger documents_guard")


def test_only_the_owner_deletes_and_never_a_registered_document(
    app_pool: Pool, admin: Connection[DictRow], session: Session
) -> None:
    doc = upload(session, app_pool)
    apply_scenario(app_pool, session.cast, "active")

    def delete(who: str) -> int:
        return code(
            httpx.request("DELETE", f"{STORAGE}/object/documents/{doc.path}", headers=session.headers(who), timeout=20)
        )

    for who in ("beto", "gina", "gus", "adan"):
        assert delete(who) == 403, who
        assert stored(admin, doc.path) is not None, f"{who} borró el archivo"

    set_status_bypassing_the_trigger(admin, doc, "registered")
    assert delete("alicia") == 403, "un documento registrado conserva su archivo (CONF-004)"
    assert stored(admin, doc.path) is not None

    set_status_bypassing_the_trigger(admin, doc, "discarded")
    assert delete("alicia") == 200
    assert stored(admin, doc.path) is None


def test_the_discard_flow_removes_the_file(app_pool: Pool, admin: Connection[DictRow], session: Session) -> None:
    """AC-13, el trozo de Storage: descartar y borrar con el JWT del dueño."""
    doc = advance(app_pool, session.cast.alicia, upload(session, app_pool), "uploading")
    assert not call(app_pool, session.cast.alicia, "discard_document", doc.id).error
    gone: Callable[[], bool] = lambda: stored(admin, doc.path) is None  # noqa: E731
    assert not gone()
    deleted = httpx.request(
        "DELETE", f"{STORAGE}/object/documents/{doc.path}", headers=session.headers("alicia"), timeout=20
    )
    assert deleted.status_code == 200 and gone()
    assert attempt(
        app_pool, session.cast.alicia, "select status from public.documents where id = %s", (doc.id,)
    ).rows == [{"status": "discarded"}]
