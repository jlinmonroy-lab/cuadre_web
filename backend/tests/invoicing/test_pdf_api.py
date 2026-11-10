"""AC-16 · El PDF por la API: se genera al emitir, se guarda con su huella y se descarga comprobándola (SPEC-W-007 §5.3 y §5.4, D-03, D-10).

Storage es un doble en memoria que se comporta como el real (409 al repetir, objeto ajeno = inexistente) y anota el JWT de cada llamada. Lo esencial
contra el Storage real está en `test_storage_live.py`.
"""

import hashlib
import io
import threading
import uuid
from collections.abc import Callable
from typing import Any

import httpx2 as httpx
import pytest
from pypdf import PdfReader

from cuadre.documents.storage import StorageUnavailable
from cuadre.invoicing import repository
from tests.invoicing.conftest import Api
from tests.invoicing.pdf_support import image, images_of, text_of
from tests.rls.invoices_support import D1, D3


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_row(api: Api, invoice_id: object) -> dict[str, Any] | None:
    return api.admin.execute("select * from public.invoice_files where invoice_id = %s", (invoice_id,)).fetchone()


def token_of(api: Api, person: Any) -> str:
    return api.headers(person)["Authorization"].removeprefix("Bearer ")


def run_all(jobs: list[Callable[[], httpx.Response]]) -> list[httpx.Response]:
    barrier = threading.Barrier(len(jobs))
    results: list[httpx.Response | None] = [None] * len(jobs)

    def work(index: int) -> None:
        barrier.wait()
        results[index] = jobs[index]()

    threads = [threading.Thread(target=work, args=(i,)) for i in range(len(jobs))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return [r for r in results if r is not None]


def issue_without_pdf(api: Api, **fields: Any) -> dict[str, Any]:
    """Una factura emitida mientras Storage no responde: queda `pending` (la emisión no depende del PDF)."""
    api.storage.fail["upload"] = StorageUnavailable()
    invoice = api.made(api.cast.alicia, **fields)
    del api.storage.fail["upload"]
    assert invoice["pdf_status"] == "pending"
    return invoice


# --- Al emitir ------------------------------------------------------------------------------------------------------------------


def test_issuing_stores_the_pdf_registers_its_hash_and_marks_it_ready(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    assert invoice["pdf_status"] == "ready"
    ((path, data),) = api.storage.objects.items()
    row = file_row(api, invoice["id"])
    assert row is not None
    assert path == f"{api.cast.alicia.id}/{invoice['id']}-{sha(data)[:16]}.pdf"  # la ruta lleva el prefijo de la huella
    assert (row["storage_path"], row["sha256"], row["size_bytes"], row["owner_id"]) == (
        path,
        sha(data),
        len(data),
        api.cast.alicia.id,
    )
    assert data.startswith(b"%PDF-") and len(data) < 1_048_576
    assert api.get(api.cast.alicia, invoice["id"]).json()["pdf_status"] == "ready"


def test_the_pdf_is_the_invoice(api: Api) -> None:
    invoice = api.made(api.cast.alicia, "eu", "business", base_cents=150_000)
    (data,) = api.storage.objects.values()
    text = " ".join(text_of(data).split())
    for expected in (
        "FACTURA",
        f"Número {invoice['display_number']}",
        invoice["client"]["name"],
        "Inversión del sujeto pasivo.",
        "1.500,00 €",
        "Sin IVA",
    ):
        assert expected in text, expected
    assert "TOTAL 1.500,00 €" in text or "1.500,00 €" in text


def test_every_storage_call_goes_with_the_users_jwt_and_never_the_service_key(api: Api) -> None:
    api.made(api.cast.alicia)
    token = token_of(api, api.cast.alicia)
    assert api.storage.calls and {c.token for c in api.storage.calls} == {token}
    assert {c.operation for c in api.storage.calls} == {"upload"}


def test_the_same_invoice_data_gives_the_same_path_so_a_retry_is_idempotent(api: Api) -> None:
    first = api.made(api.cast.alicia)
    (path,) = api.storage.objects
    assert first["pdf_status"] == "ready"
    # el mismo PDF de la misma factura: la ruta no cambia aunque se pida otra vez
    assert api.create_pdf(api.cast.alicia, first["id"]).status_code == 200
    assert list(api.storage.objects) == [path]
    assert len(api.storage.operations("upload")) == 1  # la segunda petición ni sube ni dibuja: ya estaba registrado


def test_a_failing_storage_does_not_stop_the_invoice(api: Api) -> None:
    api.storage.fail["upload"] = StorageUnavailable()
    response = api.issue(
        api.cast.alicia,
        {"client_id": str(api.cid()), "issue_date": D1.isoformat(), "concept": "Servicios", "base_cents": 100_000},
    )
    assert response.status_code == 201
    invoice = response.json()
    assert (invoice["pdf_status"], invoice["number"]) == ("pending", 1)
    assert file_row(api, invoice["id"]) is None and api.storage.objects == {}
    assert api.get(api.cast.alicia, invoice["id"]).json()["pdf_status"] == "pending"


def test_a_failing_registration_leaves_the_invoice_pending_and_the_uploaded_object_reusable(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = repository.attach_pdf
    attempts: list[int] = []

    def flaky(conn: Any, invoice_id: object, path: str, sha256: str, size: int) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("la base no responde")
        real(conn, invoice_id, path, sha256, size)

    monkeypatch.setattr(repository, "attach_pdf", flaky)
    invoice = api.made(api.cast.alicia)
    assert invoice["pdf_status"] == "pending"
    (path,) = api.storage.objects  # el PDF ya estaba subido: un huérfano sin fila
    done = api.create_pdf(api.cast.alicia, invoice["id"])
    assert done.status_code == 200 and done.json()["pdf_status"] == "ready"
    assert list(api.storage.objects) == [path]  # el 409 de Storage no es un error y no se duplica
    row = file_row(api, invoice["id"])
    assert row is not None and row["storage_path"] == path


def test_a_rectification_has_its_own_pdf(api: Api) -> None:
    original = api.made(api.cast.alicia)
    rect = api.rectify(api.cast.alicia, original["id"]).json()
    assert rect["pdf_status"] == "ready" and len(api.storage.objects) == 2
    response = api.pdf(api.cast.alicia, rect["id"])
    text = " ".join(text_of(response.content).split())
    assert (
        "FACTURA RECTIFICATIVA" in text
        and "Factura rectificativa de la 2026-001" in text
        and "Motivo: Importe mal calculado" in text
    )
    for amount in (
        "-200,00 €",
        "-42,00 €",
        "30,00 €",
        "-212,00 €",
    ):  # base, IVA, retención devuelta y total de ESTA rectificativa
        assert amount in text, amount


# --- El logo --------------------------------------------------------------------------------------------------------------------


def set_logo(api: Api, data: bytes | None) -> str:
    path = f"{api.cast.alicia.id}/{uuid.uuid4()}.png"
    api.admin.execute(
        "update public.business_profiles set logo_path = %s where owner_id = %s", (path, api.cast.alicia.id)
    )
    if data is not None:
        api.logos.objects[path] = data
    return path


def test_the_profile_logo_is_read_with_the_users_jwt_and_drawn(api: Api) -> None:
    path = set_logo(api, image("PNG"))
    invoice = api.made(api.cast.alicia)
    (pdf,) = api.storage.objects.values()
    assert invoice["pdf_status"] == "ready" and images_of(pdf) == 1
    assert [(c.path, c.token) for c in api.logos.calls] == [(path, token_of(api, api.cast.alicia))]


def test_without_a_logo_in_the_profile_nothing_is_read_and_nothing_is_drawn(api: Api) -> None:
    api.made(api.cast.alicia)
    (pdf,) = api.storage.objects.values()
    assert images_of(pdf) == 0 and api.logos.calls == []


@pytest.mark.parametrize("what", ["missing", "huge", "garbage", "storage_down"])
def test_a_logo_that_cannot_be_used_means_an_invoice_without_logo(api: Api, what: str) -> None:
    if what == "missing":
        set_logo(api, None)
    elif what == "huge":
        set_logo(api, image("PNG", 3000, 2000))
    elif what == "garbage":
        set_logo(api, b"esto no es una imagen")
    else:
        set_logo(api, image("PNG"))
        api.logos.fail = StorageUnavailable()
    invoice = api.made(api.cast.alicia)
    assert invoice["pdf_status"] == "ready"
    (pdf,) = api.storage.objects.values()
    assert images_of(pdf) == 0


# --- POST /pdf ------------------------------------------------------------------------------------------------------------------


def test_create_pdf_completes_a_pending_invoice_once(api: Api) -> None:
    invoice = issue_without_pdf(api)
    done = api.create_pdf(api.cast.alicia, invoice["id"])
    assert done.status_code == 200
    assert done.json() == {**invoice, "pdf_status": "ready"}
    assert len(api.storage.objects) == 1 and file_row(api, invoice["id"]) is not None
    again = api.create_pdf(api.cast.alicia, invoice["id"])
    assert again.status_code == 200 and again.json() == done.json()
    assert (
        len(api.storage.operations("upload")) == 2
    )  # la del intento fallido de emitir y la de ahora; la tercera petición no hizo nada


def test_create_pdf_failing_is_an_error_here(api: Api) -> None:
    invoice = issue_without_pdf(api)
    api.storage.fail["upload"] = StorageUnavailable()
    response = api.create_pdf(api.cast.alicia, invoice["id"])
    assert response.status_code == 503 and response.json()["code"] == "storage_unavailable"
    assert "Retry-After" in response.headers
    assert file_row(api, invoice["id"]) is None


def test_two_simultaneous_create_pdf_leave_one_record(api: Api) -> None:
    invoice = issue_without_pdf(api)
    responses = run_all([lambda: api.create_pdf(api.cast.alicia, invoice["id"]) for _ in range(5)])
    assert [r.status_code for r in responses] == [200] * 5, [r.text for r in responses]
    assert {r.json()["pdf_status"] for r in responses} == {"ready"}
    count = api.admin.execute(
        "select count(*) as n from public.invoice_files where invoice_id = %s", (invoice["id"],)
    ).fetchone()
    assert count == {"n": 1}
    assert len(api.storage.objects) == 1


def test_an_object_in_the_path_with_other_content_is_corrupt_not_overwritten(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = repository.attach_pdf
    monkeypatch.setattr(repository, "attach_pdf", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    invoice = api.made(api.cast.alicia)
    (path,) = api.storage.objects
    monkeypatch.setattr(repository, "attach_pdf", real)
    api.storage.objects[path] = b"%PDF-1.4 otra cosa"
    response = api.create_pdf(api.cast.alicia, invoice["id"])
    assert response.status_code == 409 and response.json()["code"] == "invoice_pdf_corrupt"
    assert file_row(api, invoice["id"]) is None and api.storage.objects[path] == b"%PDF-1.4 otra cosa"


def test_create_pdf_of_anothers_or_a_missing_invoice_is_not_found(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    for person, target in ((api.cast.beto, invoice["id"]), (api.cast.alicia, str(uuid.uuid4()))):
        response = api.create_pdf(person, target)
        assert (response.status_code, response.json()["code"]) == (404, "invoice_not_found")
    assert api.create_pdf(api.cast.alicia, "no-uuid").status_code == 422


# --- GET /pdf -------------------------------------------------------------------------------------------------------------------


def test_the_download_returns_exactly_the_stored_bytes_with_its_headers(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    (stored,) = api.storage.objects.values()
    response = api.pdf(api.cast.alicia, invoice["id"])
    assert response.status_code == 200
    assert response.content == stored and sha(response.content) == file_row(api, invoice["id"])["sha256"]  # type: ignore[index]
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="2026-001.pdf"'
    assert response.headers["cache-control"] == "private, no-store"
    assert len(PdfReader(io.BytesIO(response.content)).pages) == 1


def test_the_rectification_download_is_named_after_its_number(api: Api) -> None:
    original = api.made(api.cast.alicia)
    rect = api.rectify(api.cast.alicia, original["id"]).json()
    assert (
        api.pdf(api.cast.alicia, rect["id"]).headers["content-disposition"] == 'attachment; filename="R-2026-001.pdf"'
    )


def test_a_pdf_that_was_altered_is_not_delivered(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    (path,) = api.storage.objects
    original = api.storage.objects[path]
    for altered in (
        original + b"\n",
        original[:-10],
        b"x" * len(original),
        original.replace(b"2026-001", b"2026-002", 1),
    ):
        api.storage.objects[path] = altered
        response = api.pdf(api.cast.alicia, invoice["id"])
        assert (response.status_code, response.json()["code"]) == (409, "invoice_pdf_corrupt")
    api.storage.objects[path] = original
    assert api.pdf(api.cast.alicia, invoice["id"]).status_code == 200


def test_a_pdf_that_disappeared_is_corrupt(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    api.storage.objects.clear()
    response = api.pdf(api.cast.alicia, invoice["id"])
    assert (response.status_code, response.json()["code"]) == (409, "invoice_pdf_corrupt")


def test_an_invoice_without_pdf_is_pending(api: Api) -> None:
    invoice = issue_without_pdf(api)
    response = api.pdf(api.cast.alicia, invoice["id"])
    assert (response.status_code, response.json()["code"]) == (409, "invoice_pdf_pending")
    api.create_pdf(api.cast.alicia, invoice["id"])
    assert api.pdf(api.cast.alicia, invoice["id"]).status_code == 200


def test_storage_down_at_download_is_a_503_not_a_corrupt_pdf(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    api.storage.fail["download"] = StorageUnavailable()
    response = api.pdf(api.cast.alicia, invoice["id"])
    assert (response.status_code, response.json()["code"]) == (503, "storage_unavailable")


def test_the_download_uses_the_users_jwt(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    api.pdf(api.cast.alicia, invoice["id"])
    downloads = api.storage.operations("download")
    assert downloads and {c.token for c in downloads} == {token_of(api, api.cast.alicia)}


def test_download_of_anothers_or_a_missing_invoice_is_not_found(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    for person, target in ((api.cast.beto, invoice["id"]), (api.cast.alicia, str(uuid.uuid4()))):
        response = api.pdf(person, target)
        assert (response.status_code, response.json()["code"]) == (404, "invoice_not_found")
    assert D3 > D1  # (las fechas de las pruebas son fijas y pasadas)


def test_the_pdf_carries_the_issuer_copy_of_the_invoice_not_the_profile_of_now(api: Api) -> None:
    """D-09: el emisor y el cliente del PDF son las copias de la fila. Si cambian después, un PDF generado más tarde (`POST /pdf`) dice lo de entonces."""
    invoice = issue_without_pdf(api)
    before = api.admin.execute(
        "select issuer_name, issuer_tax_id, issuer_address, client_name from public.invoices where id = %s",
        (invoice["id"],),
    ).fetchone()
    assert before is not None
    api.admin.execute(
        "update public.business_profiles set legal_name = 'Nombre Nuevo del Emisor', tax_id = '01230956L', fiscal_address = 'Calle Nueva 99, Otra Ciudad' where owner_id = %s",
        (api.cast.alicia.id,),
    )
    api.admin.execute("update public.clients set name = 'Cliente Renombrado S.L.' where id = %s", (api.cid(),))
    api.create_pdf(api.cast.alicia, invoice["id"])
    (pdf,) = api.storage.objects.values()
    text = " ".join(text_of(pdf).split())
    for frozen in (before["issuer_name"], before["issuer_tax_id"], before["issuer_address"], before["client_name"]):
        assert frozen in text, frozen
    for current in ("Nombre Nuevo del Emisor", "01230956L", "Calle Nueva 99", "Cliente Renombrado"):
        assert current not in text, current
