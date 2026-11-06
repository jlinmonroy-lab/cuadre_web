"""HttpStorage contra un servidor local guionado: lo que sale por el cable y cómo se interpretan las respuestas de Storage (Anexo B.1).

Las respuestas simuladas copian lo que observó el spike del hito 0 contra el Storage real: URL relativas a `/storage/v1`, errores con
HTTP 400 y el estado real en `statusCode` del cuerpo, un objeto ajeno igual que uno inexistente.
"""

import json
import time
from collections.abc import Callable
from typing import Any

import pytest

from cuadre.documents import storage as storage_module
from cuadre.documents.storage import (
    HttpStorage,
    ObjectInfo,
    StorageDenied,
    StorageNotFound,
    StorageUnavailable,
)
from tests.agents.server import Reply, ScriptedServer, closed_port_url
from tests.agents.support import captured_logs, rendered

TOKEN = "JWT-DE-PRUEBA-NO-DEBE-SALIR.abc.def"
PATH = "11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222.pdf"
PDF_HEAD = b"%PDF-1.4\n" + b"0" * 40


def wrapped(status: int, message: str = "x") -> Reply:
    """Cómo responde Storage a casi todo error: HTTP 400 con el estado real en el cuerpo."""
    return Reply(400, {"statusCode": str(status), "error": "x", "message": message, "code": "X"})


def make(server: ScriptedServer) -> HttpStorage:
    return HttpStorage(server.url)


# --- Firma de subida ----------------------------------------------------------------------------------------------------------


def test_sign_upload_composes_the_full_url_and_authenticates_only_with_the_users_jwt(server: ScriptedServer) -> None:
    relative = f"/object/upload/sign/documents/{PATH}?token=UPLOAD-TOKEN"
    server.serve(Reply(200, {"url": relative, "token": "UPLOAD-TOKEN"}))
    url = make(server).sign_upload(PATH, token=TOKEN)

    assert url == f"{server.url}/storage/v1{relative}"
    (seen,) = server.seen
    assert (seen.method, seen.path) == ("POST", f"/storage/v1/object/upload/sign/documents/{PATH}")
    assert seen.headers["authorization"] == f"Bearer {TOKEN}"
    assert "apikey" not in seen.headers, "basta el JWT del usuario: la clave publicable sola actuaría como anon"


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (wrapped(403), StorageDenied),
        (wrapped(404), StorageUnavailable),  # firmar una ruta que acabamos de reservar y no existe: algo va mal
        (Reply(500, ""), StorageUnavailable),
        (Reply(200, "no es json"), StorageUnavailable),
        (Reply(200, []), StorageUnavailable),
        (Reply(200, {}), StorageUnavailable),
        (Reply(200, {"url": 5}), StorageUnavailable),
        (Reply(200, {"url": "https://evil.test/robar"}), StorageUnavailable),
        (Reply(200, {"url": "/object/sign/documents/x?token=t"}), StorageUnavailable),  # no es una URL de subida
        (Reply(200, {"url": "/object/upload/sign/otro-bucket/x?token=t"}), StorageUnavailable),
    ],
    ids=lambda v: getattr(v, "__name__", None) or f"{v.status}-{str(v.body)[:30]}",
)
def test_sign_upload_failures(server: ScriptedServer, reply: Reply, error: type[Exception]) -> None:
    server.serve(reply)
    with pytest.raises(error):
        make(server).sign_upload(PATH, token=TOKEN)


# --- Tamaño y tipo registrados ---------------------------------------------------------------------------------------------------


def test_object_info_returns_what_storage_registered(server: ScriptedServer) -> None:
    server.serve(
        Reply(
            200, {"id": "x", "name": PATH, "size": 246, "content_type": "application/pdf", "cache_control": "no-cache"}
        )
    )
    assert make(server).object_info(PATH, token=TOKEN) == ObjectInfo(246, "application/pdf")
    assert server.seen[0].path == f"/storage/v1/object/info/authenticated/documents/{PATH}"


@pytest.mark.parametrize("reply", [wrapped(404), Reply(404, {"message": "no"})], ids=["400+404", "404"])
def test_object_info_of_a_missing_or_foreign_object_is_none(server: ScriptedServer, reply: Reply) -> None:
    server.serve(reply)
    assert make(server).object_info(PATH, token=TOKEN) is None


@pytest.mark.parametrize(
    "body",
    [
        {"size": "246", "content_type": "application/pdf"},
        {"size": True, "content_type": "application/pdf"},
        {"size": -1, "content_type": "application/pdf"},
        {"size": 12.5, "content_type": "application/pdf"},
        {"size": 246},
        {"content_type": "application/pdf"},
        {"size": 246, "content_type": 7},
        [],
    ],
)
def test_object_info_with_an_unexpected_shape_is_unavailable(server: ScriptedServer, body: Any) -> None:
    server.serve(Reply(200, body))
    with pytest.raises(StorageUnavailable):
        make(server).object_info(PATH, token=TOKEN)


def test_object_info_forbidden_and_server_error(server: ScriptedServer) -> None:
    server.serve(wrapped(403))
    with pytest.raises(StorageDenied):
        make(server).object_info(PATH, token=TOKEN)
    server.serve(Reply(500, ""))
    with pytest.raises(StorageUnavailable):
        make(server).object_info(PATH, token=TOKEN)


# --- Primeros bytes ------------------------------------------------------------------------------------------------------------


def test_read_head_asks_for_a_range_and_returns_those_bytes(server: ScriptedServer) -> None:
    server.serve(Reply(206, PDF_HEAD[:32], {"Content-Range": f"bytes 0-31/{len(PDF_HEAD)}"}))
    assert make(server).read_head(PATH, token=TOKEN, length=32) == PDF_HEAD[:32]
    (seen,) = server.seen
    assert seen.method == "GET" and seen.path == f"/storage/v1/object/authenticated/documents/{PATH}"
    assert seen.headers["range"] == "bytes=0-31"


def test_read_head_never_downloads_the_whole_file_even_if_storage_ignores_range(server: ScriptedServer) -> None:
    big = b"%PDF-" + b"0" * (5 * 1024 * 1024)
    # Storage ignora `Range` y devuelve 5 MB, en trozos de 64 KiB: el cliente debe cortar al tener los 32 bytes.
    server.serve(Reply(200, big, chunk_size=65536, chunk_delay_ms=5))
    head = make(server).read_head(PATH, token=TOKEN, length=32)
    assert head == big[:32]
    time.sleep(0.3)  # deja al servidor intentar seguir escribiendo
    assert server.written < len(big) // 2, f"el servidor llegó a escribir {server.written} de {len(big)} bytes"


def test_read_head_of_a_file_shorter_than_asked(server: ScriptedServer) -> None:
    server.serve(Reply(206, b"%PDF-"))
    assert make(server).read_head(PATH, token=TOKEN, length=32) == b"%PDF-"


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (wrapped(404), StorageNotFound),
        (wrapped(403), StorageDenied),
        (Reply(500, ""), StorageUnavailable),
        (Reply(416, ""), StorageUnavailable),
    ],
    ids=["404", "403", "500", "416"],
)
def test_read_head_failures(server: ScriptedServer, reply: Reply, error: type[Exception]) -> None:
    server.serve(reply)
    with pytest.raises(error):
        make(server).read_head(PATH, token=TOKEN, length=32)


# --- Firma de lectura -----------------------------------------------------------------------------------------------------------


def test_sign_read_sends_the_expiry_and_composes_the_full_url(server: ScriptedServer) -> None:
    relative = f"/object/sign/documents/{PATH}?token=READ-TOKEN"
    server.serve(Reply(200, {"signedURL": relative}))
    assert make(server).sign_read(PATH, token=TOKEN, expires_in=120) == f"{server.url}/storage/v1{relative}"
    (seen,) = server.seen
    assert (seen.method, seen.path) == ("POST", f"/storage/v1/object/sign/documents/{PATH}")
    assert json.loads(seen.body) == {"expiresIn": 120}


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (wrapped(404), StorageNotFound),
        (wrapped(403), StorageDenied),
        (Reply(200, {"signedURL": "https://evil.test/x"}), StorageUnavailable),
        (Reply(200, {"signedURL": f"/object/upload/sign/documents/{PATH}?token=t"}), StorageUnavailable),
        (Reply(200, {}), StorageUnavailable),
        (Reply(503, ""), StorageUnavailable),
    ],
    ids=["404", "403", "absoluta", "de subida", "vacía", "503"],
)
def test_sign_read_failures(server: ScriptedServer, reply: Reply, error: type[Exception]) -> None:
    server.serve(reply)
    with pytest.raises(error):
        make(server).sign_read(PATH, token=TOKEN, expires_in=60)


# --- Borrado ------------------------------------------------------------------------------------------------------------------


def test_delete_uses_delete_on_the_object_path(server: ScriptedServer) -> None:
    server.serve(Reply(200, {"message": "Successfully deleted"}))
    make(server).delete(PATH, token=TOKEN)
    (seen,) = server.seen
    assert (seen.method, seen.path) == ("DELETE", f"/storage/v1/object/documents/{PATH}")


@pytest.mark.parametrize("reply", [wrapped(404), Reply(404, "")], ids=["400+404", "404"])
def test_deleting_something_already_gone_is_fine(server: ScriptedServer, reply: Reply) -> None:
    server.serve(reply)
    make(server).delete(PATH, token=TOKEN)


@pytest.mark.parametrize(
    "reply, error", [(wrapped(403), StorageDenied), (Reply(500, ""), StorageUnavailable)], ids=["403", "500"]
)
def test_delete_failures(server: ScriptedServer, reply: Reply, error: type[Exception]) -> None:
    server.serve(reply)
    with pytest.raises(error):
        make(server).delete(PATH, token=TOKEN)


# --- Red -----------------------------------------------------------------------------------------------------------------------


def test_a_refused_connection_is_unavailable() -> None:
    with pytest.raises(StorageUnavailable):
        HttpStorage(closed_port_url()).object_info(PATH, token=TOKEN)


def test_a_timeout_is_unavailable_and_ends_in_time(server: ScriptedServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_module, "TIMEOUT_SECONDS", 1)
    server.serve(Reply(200, {"size": 1, "content_type": "application/pdf"}, delay_ms=2500))
    began = time.monotonic()
    with pytest.raises(StorageUnavailable):
        make(server).object_info(PATH, token=TOKEN)
    assert time.monotonic() - began < 2.4


def test_a_redirect_is_not_followed(server: ScriptedServer) -> None:
    server.serve(
        Reply(302, "", {"Location": f"{server.url}/robar"}), Reply(200, {"size": 1, "content_type": "application/pdf"})
    )
    with pytest.raises(StorageUnavailable):
        make(server).object_info(PATH, token=TOKEN)
    assert [seen.path for seen in server.seen] == [f"/storage/v1/object/info/authenticated/documents/{PATH}"]


def test_proxies_from_the_environment_are_ignored(server: ScriptedServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """El JWT de la persona solo va a la URL de Storage configurada, no a un proxy que sugiera el entorno."""
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, closed_port_url())
    server.serve(Reply(200, {"size": 1, "content_type": "application/pdf"}))
    assert make(server).object_info(PATH, token=TOKEN) == ObjectInfo(1, "application/pdf")


@pytest.mark.parametrize(
    "path", ["factura.pdf", "../etc/passwd", "a/b.pdf", f"{PATH}/x", "", PATH.upper(), PATH + "?x=1"]
)
def test_only_paths_made_of_identifiers_are_ever_requested(server: ScriptedServer, path: str) -> None:
    server.serve(Reply(200, {"size": 1, "content_type": "application/pdf"}))
    calls: list[Callable[[], Any]] = [
        lambda: make(server).sign_upload(path, token=TOKEN),
        lambda: make(server).object_info(path, token=TOKEN),
        lambda: make(server).read_head(path, token=TOKEN, length=32),
        lambda: make(server).sign_read(path, token=TOKEN, expires_in=60),
        lambda: make(server).delete(path, token=TOKEN),
    ]
    for call in calls:
        with pytest.raises(ValueError):
            call()
    assert server.seen == [], "ni siquiera se llegó a hacer la petición"


# --- Registros ------------------------------------------------------------------------------------------------------------------


def test_logs_have_the_operation_and_the_status_but_never_the_jwt_or_a_signed_url(server: ScriptedServer) -> None:
    server.serve(
        Reply(
            200, {"url": f"/object/upload/sign/documents/{PATH}?token=SECRETO-DE-SUBIDA", "token": "SECRETO-DE-SUBIDA"}
        ),
        Reply(200, {"size": 1, "content_type": "application/pdf"}),
        Reply(200, {"signedURL": f"/object/sign/documents/{PATH}?token=SECRETO-DE-LECTURA"}),
        wrapped(403, message=f"policy violation on {PATH}"),
        Reply(500, "cuerpo con TOKEN-EN-EL-CUERPO"),
    )
    store = make(server)
    with captured_logs("cuadre") as records:
        store.sign_upload(PATH, token=TOKEN)
        store.object_info(PATH, token=TOKEN)
        store.sign_read(PATH, token=TOKEN, expires_in=120)
        with pytest.raises(StorageDenied):
            store.delete(PATH, token=TOKEN)
        with pytest.raises(StorageUnavailable):
            store.delete(PATH, token=TOKEN)

    text = rendered(records)
    for secret in (
        TOKEN,
        "SECRETO-DE-SUBIDA",
        "SECRETO-DE-LECTURA",
        "token=",
        "TOKEN-EN-EL-CUERPO",
        "policy violation",
        PATH,
    ):
        assert secret not in text, f"el registro contiene {secret!r}"
    assert [(r.operation, r.status) for r in records if hasattr(r, "operation")] == [  # type: ignore[attr-defined]
        ("sign_upload", 200),
        ("object_info", 200),
        ("sign_read", 200),
        ("delete", 403),
        ("delete", 500),
    ]
