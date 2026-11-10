"""`HttpStorage.upload` y `HttpStorage.download` contra un servidor local guionado (SPEC-W-007 §5.4, B.1-C): lo que sale por el cable y cómo se interpretan
las respuestas de Storage.

Las respuestas simuladas copian lo que midió el spike del hito 0 contra el Storage real: 200 al subir, **409 `Duplicate`** al repetir, 403 al reemplazar o
borrar (no hay política), 413 y 415 como HTTP 400 con el estado real en el cuerpo, y un objeto ajeno igual que uno inexistente.
"""

import pytest

from cuadre.documents.storage import HttpStorage, StorageDenied, StorageNotFound, StorageUnavailable
from cuadre.invoicing.limits import PDF_PATH
from cuadre.invoicing.storage import invoice_storage
from tests.agents.conftest import server  # noqa: F401 - fixture de otro conftest
from tests.agents.server import Reply, ScriptedServer
from tests.agents.support import captured_logs, rendered

TOKEN = "JWT-DE-PRUEBA-NO-DEBE-SALIR.abc.def"
OWNER = "11111111-1111-4111-8111-111111111111"
INVOICE = "22222222-2222-4222-8222-222222222222"
PATH = f"{OWNER}/{INVOICE}-0123456789abcdef.pdf"
PDF = b"%PDF-1.4\n" + b"contenido de prueba " * 20


def wrapped(status: int, message: str = "x") -> Reply:
    """Cómo responde Storage a casi todo error: HTTP 400 con el estado real en el cuerpo."""
    return Reply(400, {"statusCode": str(status), "error": "x", "message": message, "code": "X"})


def make(server: ScriptedServer) -> HttpStorage:  # noqa: F811
    return HttpStorage(server.url, bucket="invoices", path=PDF_PATH)


# --- Subir ----------------------------------------------------------------------------------------------------------------------


def test_upload_posts_the_raw_bytes_with_the_pdf_type_and_only_the_users_jwt(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(Reply(200, {"Id": "x", "Key": f"invoices/{PATH}"}))
    assert make(server).upload(PATH, PDF, "application/pdf", token=TOKEN) == "created"
    (seen,) = server.seen
    assert (seen.method, seen.path) == ("POST", f"/storage/v1/object/invoices/{PATH}")
    assert seen.body == PDF
    assert seen.headers["content-type"] == "application/pdf"
    assert seen.headers["authorization"] == f"Bearer {TOKEN}"
    assert "apikey" not in seen.headers and "x-upsert" not in seen.headers  # nunca reemplaza: no hay política de UPDATE


def test_a_second_upload_to_the_same_path_is_already_there_not_an_error(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(wrapped(409, "The resource already exists"))
    assert make(server).upload(PATH, PDF, "application/pdf", token=TOKEN) == "exists"


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (wrapped(403), StorageDenied),
        (wrapped(413), StorageUnavailable),
        (wrapped(415), StorageUnavailable),
        (Reply(500, ""), StorageUnavailable),
        (Reply(503, ""), StorageUnavailable),
        (Reply(401, ""), StorageUnavailable),
    ],
    ids=["403", "413", "415", "500", "503", "401"],
)
def test_upload_failures(server: ScriptedServer, reply: Reply, error: type[Exception]) -> None:  # noqa: F811
    server.serve(reply)
    with pytest.raises(error):
        make(server).upload(PATH, PDF, "application/pdf", token=TOKEN)


# --- Descargar ------------------------------------------------------------------------------------------------------------------


def test_download_gets_the_whole_object_with_the_users_jwt(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(Reply(200, PDF, headers={"Content-Type": "application/pdf"}))
    assert make(server).download(PATH, token=TOKEN, max_bytes=1_048_576) == PDF
    (seen,) = server.seen
    assert (seen.method, seen.path) == ("GET", f"/storage/v1/object/authenticated/invoices/{PATH}")
    assert seen.headers["authorization"] == f"Bearer {TOKEN}"


def test_download_never_reads_more_than_the_limit_plus_one_byte(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(Reply(200, b"x" * 5000, chunk_size=500))
    data = make(server).download(PATH, token=TOKEN, max_bytes=1000)
    assert len(data) == 1001  # el byte de más delata un objeto demasiado grande y no se lee nada más


def test_download_of_exactly_the_limit_is_returned_whole(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(Reply(200, b"y" * 1000))
    assert make(server).download(PATH, token=TOKEN, max_bytes=1000) == b"y" * 1000


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
def test_download_failures(server: ScriptedServer, reply: Reply, error: type[Exception]) -> None:  # noqa: F811
    server.serve(reply)
    with pytest.raises(error):
        make(server).download(PATH, token=TOKEN, max_bytes=1000)


# --- Rutas y registros ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "factura.pdf",
        f"{OWNER}/{INVOICE}.pdf",
        f"{OWNER}/{INVOICE}-0123456789abcdef.png",
        f"{OWNER}/{INVOICE}-0123456789ABCDEF.pdf",
        f"{OWNER}/{INVOICE}-0123456789abcde.pdf",
        f"{OWNER}/../{INVOICE}-0123456789abcdef.pdf",
        f"x/{OWNER}/{INVOICE}-0123456789abcdef.pdf",
    ],
)
def test_only_paths_of_the_exact_pdf_form_are_ever_requested(server: ScriptedServer, path: str) -> None:  # noqa: F811
    for call in (
        lambda: make(server).upload(path, PDF, "application/pdf", token=TOKEN),
        lambda: make(server).download(path, token=TOKEN, max_bytes=1000),
    ):
        with pytest.raises(ValueError):
            call()
    assert server.seen == []


def test_the_factory_builds_the_invoices_bucket_with_the_pdf_path_rule(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(Reply(200, {"Key": "x"}))
    assert invoice_storage(server.url).upload(PATH, PDF, "application/pdf", token=TOKEN) == "created"
    assert server.seen[0].path == f"/storage/v1/object/invoices/{PATH}"
    with pytest.raises(ValueError):
        invoice_storage(server.url).upload(f"{OWNER}/{INVOICE}.pdf", PDF, "application/pdf", token=TOKEN)


def test_logs_have_the_operation_and_the_status_but_never_the_jwt_the_path_or_the_bytes(server: ScriptedServer) -> None:  # noqa: F811
    server.serve(Reply(200, {"Key": "x"}), Reply(200, PDF))
    with captured_logs("cuadre") as records:
        make(server).upload(PATH, PDF, "application/pdf", token=TOKEN)
        make(server).download(PATH, token=TOKEN, max_bytes=1000)
    text = rendered(records)
    assert "upload" in text and "download" in text
    for secret in (TOKEN, PATH, OWNER, INVOICE, "contenido de prueba"):
        assert secret not in text, secret
