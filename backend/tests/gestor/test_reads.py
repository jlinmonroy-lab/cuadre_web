"""AC-11, AC-12, AC-13 · Lo que lee el gestor es lo que ve el autónomo: facturas, gastos, documentos, perfil, clientes y los borradores del 303 y del 130 (SPEC-W-010 hito 2).

Se siembran los ejercicios de B.1 de SPEC-W-008 (303) y SPEC-W-009 (130) en una cuenta con un gestor vinculado y se comparan, cuerpo a cuerpo, las respuestas del gestor con las del
propio autónomo: son las MISMAS consultas y los mismos presentadores. Los archivos no pasan por la API: el PDF y el original salen por URL firmada (aquí, un Storage de mentira que
apunta lo que se le pide).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.documents.storage import StorageNotFound, StorageUnavailable
from tests.gestor.conftest import Api
from tests.gestor.support import FakeStorage, documents, link
from tests.quarters.conftest import Seeded, seed, seed_130
from tests.support import Pool
from tests.tax.test_modelo_130_cases import EVERY_CASE as CASES_130
from tests.tax.test_modelo_303_cases import CASES as CASES_303

IBAN = "ES3600000000050000000001"


@pytest.fixture(scope="module")
def s303(admin: Connection[DictRow], app_pool: Pool) -> Iterator[Seeded]:
    seeded = seed(admin, app_pool)
    link(app_pool, seeded.cast.alicia, seeded.cast.gina)
    yield seeded


@pytest.fixture(scope="module")
def s130(admin: Connection[DictRow], app_pool: Pool) -> Iterator[Seeded]:
    seeded = seed_130(admin, app_pool)
    link(app_pool, seeded.cast.alicia, seeded.cast.gina)
    yield seeded


def base(seeded: Seeded) -> str:
    return f"/api/gestor/autonomos/{seeded.cast.alicia.id}"


def both(api: Api, seeded: Seeded, own: str, theirs: str, **params: Any) -> tuple[Any, Any]:
    """La respuesta del propio autónomo y la del gestor a lo mismo."""
    mine = api.request("GET", own, seeded.cast.alicia, params=params or None)
    gestor = api.request("GET", f"{base(seeded)}{theirs}", seeded.cast.gina, params=params or None)
    assert mine.status_code == 200, mine.text
    assert gestor.status_code == 200, gestor.text
    assert gestor.headers["cache-control"] == "private, no-store"
    return mine.json(), gestor.json()


# --- Facturas ---------------------------------------------------------------------------------------------------------------------------


def test_the_invoice_list_is_what_the_owner_sees_with_the_rectifications_in_it(api: Api, s303: Seeded) -> None:  # AC-11
    mine, theirs = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200)
    assert len(theirs) == 23 and theirs == mine  # 17 ordinarias y 6 rectificativas de 2025
    assert {i["kind"] for i in theirs} == {"standard", "rectifying"}


def test_the_list_comes_by_pages_that_add_up_to_the_whole(api: Api, s303: Seeded) -> None:  # AC-23
    _, whole = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200)
    pages: list[dict[str, Any]] = []
    for offset in range(0, 30, 10):
        response = api.request(
            "GET", f"{base(s303)}/facturas", s303.cast.gina, params={"year": 2025, "limit": 10, "offset": offset}
        )
        assert response.status_code == 200 and len(response.json()) <= 10
        pages.extend(response.json())
    assert pages == whole


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"year": 1999}, {"scope": "mars"}])
def test_a_bad_page_or_filter_is_a_validation_error(api: Api, s303: Seeded, params: dict[str, Any]) -> None:
    response = api.request("GET", f"{base(s303)}/facturas", s303.cast.gina, params=params)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_the_filters_of_the_list_are_the_ones_of_the_owner(api: Api, s303: Seeded) -> None:
    for params in ({"scope": "eu"}, {"paid": "false"}, {"scope": "national", "paid": "false"}):
        mine, theirs = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200, **params)
        assert theirs == mine and len(theirs) > 0, params


def test_one_invoice_and_its_rectification_are_what_the_owner_sees(api: Api, s303: Seeded) -> None:  # AC-11
    _, listing = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200)
    original = next(i for i in listing if i["rectified_by"])
    rectification = next(i for i in listing if i["kind"] == "rectifying")
    for invoice in (original, rectification):
        mine, theirs = both(api, s303, f"/api/invoices/{invoice['id']}", f"/facturas/{invoice['id']}")
        assert theirs == mine
    assert theirs["rectifies"] is not None  # la rectificativa dice a quién rectifica


def test_an_invoice_that_is_not_the_clients_is_not_found_even_if_the_gestor_has_another_client(
    api: Api, s303: Seeded, app_pool: Pool
) -> None:
    _, listing = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200)
    other = api.cast  # otro reparto: Beto es otro autónomo y también de Gina
    link(app_pool, other.beto, s303.cast.gina)
    response = api.request("GET", f"/api/gestor/autonomos/{other.beto.id}/facturas/{listing[0]['id']}", s303.cast.gina)
    assert (response.status_code, response.json()["code"]) == (404, "invoice_not_found")


def with_pdf(admin: Connection[DictRow], seeded: Seeded, invoice_id: str) -> str:
    sha = "ab" * 32
    path = f"{seeded.cast.alicia.id}/{invoice_id}-{sha[:16]}.pdf"
    admin.execute(
        "insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes) values (%s, %s, %s, %s, 1234) "
        "on conflict (invoice_id) do nothing",
        (invoice_id, seeded.cast.alicia.id, path, sha),
    )
    return path


def test_the_pdf_is_a_signed_url_made_with_the_gestors_own_token_and_never_the_bytes(
    api: Api, s303: Seeded, admin: Connection[DictRow]
) -> None:  # AC-11
    _, listing = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200)
    invoice_id = listing[0]["id"]
    url = f"{base(s303)}/facturas/{invoice_id}/pdf"
    pending = api.request("GET", url, s303.cast.gina)
    assert (pending.status_code, pending.json()["code"]) == (409, "invoice_pdf_pending")

    path = with_pdf(admin, s303, invoice_id)
    storage = FakeStorage()
    api.app.state.invoice_storage = storage
    token = api.signer.token(s303.cast.gina)
    response = api.client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert (
        response.headers["content-type"].startswith("application/json")
        and response.headers["cache-control"] == "private, no-store"
    )
    assert response.json() == {"url": f"https://storage.example.test/{path}?sig=fake", "expires_in": 60}
    assert storage.signed == [(path, token, 60)]  # con el JWT del GESTOR, no el del autónomo ni la service key


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [(StorageNotFound(), 409, "invoice_pdf_corrupt"), (StorageUnavailable(), 503, "storage_unavailable")],
)
def test_a_missing_or_unavailable_file_is_a_clear_error(
    api: Api, s303: Seeded, admin: Connection[DictRow], failure: Exception, status: int, code: str
) -> None:
    _, listing = both(api, s303, "/api/invoices", "/facturas", year=2025, limit=200)
    with_pdf(admin, s303, listing[0]["id"])
    api.app.state.invoice_storage = FakeStorage(fail=failure)
    response = api.request("GET", f"{base(s303)}/facturas/{listing[0]['id']}/pdf", s303.cast.gina)
    assert (response.status_code, response.json()["code"]) == (status, code)


# --- Gastos ----------------------------------------------------------------------------------------------------------------------------


def all_pages(api: Api, seeded: Seeded, who: object, url: str, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page: str | None = None
    for _ in range(30):
        response = api.request("GET", url, who, params={**params, **({"page": page} if page else {})})  # type: ignore[arg-type]
        assert response.status_code == 200, response.text
        body = response.json()
        items.extend(body["items"])
        page = body["next_cursor"]
        if page is None:
            return items
    raise AssertionError("demasiadas páginas")


def test_the_gestor_sees_every_expense_with_the_voided_ones_marked_and_the_owner_does_not(
    api: Api, s303: Seeded
) -> None:  # AC-12
    mine = all_pages(api, s303, s303.cast.alicia, "/api/expenses", limit=100)
    theirs = all_pages(api, s303, s303.cast.gina, f"{base(s303)}/gastos", limit=100)
    voided = [e for e in theirs if e["voided_at"] is not None]
    assert voided, "la siembra de B.1 trae gastos anulados"
    assert {e["id"] for e in voided}.isdisjoint({e["id"] for e in mine})
    assert [e["id"] for e in theirs if e["voided_at"] is None] == [e["id"] for e in mine]
    assert set(theirs[0]) >= {"id", "supplier_name", "total_cents", "voided_at", "tax_breakdown"}


def test_the_expense_pages_add_up_and_the_cursor_is_checked(api: Api, s303: Seeded) -> None:
    whole = all_pages(api, s303, s303.cast.gina, f"{base(s303)}/gastos", limit=100)
    paged = all_pages(api, s303, s303.cast.gina, f"{base(s303)}/gastos", limit=3)
    assert paged == whole and len(whole) > 3
    for params in ({"page": "no-vale"}, {"limit": 0}, {"limit": 101}, {"month": 3}, {"month": 13, "year": 2025}):
        response = api.request("GET", f"{base(s303)}/gastos", s303.cast.gina, params=params)
        assert response.status_code == 422, params
    assert (
        api.request("GET", f"{base(s303)}/gastos", s303.cast.gina, params={"page": "no-vale"}).json()["code"]
        == "invalid_cursor"
    )
    assert (
        api.request("GET", f"{base(s303)}/gastos", s303.cast.gina, params={"month": 3}).json()["code"]
        == "validation_error"  # el mes sin año: el mismo error que da la lista del autónomo
    )


def test_the_expense_filters_are_the_owners(api: Api, s303: Seeded) -> None:
    mine = all_pages(api, s303, s303.cast.alicia, "/api/expenses", limit=100, year=2025, month=11)
    theirs = [
        e
        for e in all_pages(api, s303, s303.cast.gina, f"{base(s303)}/gastos", limit=100, year=2025, month=11)
        if e["voided_at"] is None
    ]
    # La lista del autónomo es el resumen; la del gestor, el gasto completo: se comparan los campos del resumen.
    assert [{k: e[k] for k in mine[0]} for e in theirs] == mine and len(mine) > 0


# --- Documentos --------------------------------------------------------------------------------------------------------------------------


def test_the_documents_are_only_those_to_review_or_that_could_not_be_read_and_the_original_is_a_signed_url(
    api: Api, s303: Seeded, app_pool: Pool
) -> None:  # AC-12
    review = documents(app_pool, s303.cast.alicia, "review", 2)
    failed = documents(app_pool, s303.cast.alicia, "extraction_failed", 1)
    processing = documents(app_pool, s303.cast.alicia, "processing", 1)
    discarded = documents(app_pool, s303.cast.alicia, "discarded", 1)
    response = api.request("GET", f"{base(s303)}/documentos", s303.cast.gina)
    assert response.status_code == 200, response.text
    shown = {d["id"]: d["status"] for d in response.json()}
    assert {str(d.id) for d in review + failed} <= set(shown)
    assert not ({str(d.id) for d in processing + discarded} & set(shown))
    assert set(shown.values()) <= {"review", "extraction_failed"}

    storage = FakeStorage()
    api.app.state.storage = storage
    token = api.signer.token(s303.cast.gina)
    ok = api.client.get(
        f"{base(s303)}/documentos/{review[0].id}/original", headers={"Authorization": f"Bearer {token}"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"url": f"https://storage.example.test/{review[0].path}?sig=fake", "expires_in": 60}
    assert storage.signed == [(review[0].path, token, 60)]
    for gone in discarded:
        assert api.request("GET", f"{base(s303)}/documentos/{gone.id}/original", s303.cast.gina).status_code == 404


# --- Perfil y clientes -------------------------------------------------------------------------------------------------------------------


def test_the_profile_and_the_series_are_the_owners_and_the_iban_is_visible(
    api: Api, s303: Seeded
) -> None:  # AC-12, P-01
    profile = api.request("GET", "/api/profile", s303.cast.alicia).json()
    series = api.request("GET", "/api/invoice-series", s303.cast.alicia).json()
    response = api.request("GET", f"{base(s303)}/perfil", s303.cast.gina)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"] == profile and body["series"] == series
    assert body["profile"]["iban"] == IBAN and len(series) >= 1


def test_the_clients_are_the_owners_archived_included(api: Api, s303: Seeded) -> None:  # AC-12
    mine, theirs = both(api, s303, "/api/clients", "/clientes", include_archived="true")
    assert theirs == mine and len(theirs) >= 6


# --- Borradores 303 y 130 ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES_303["trimestres"], ids=[t["caso"] for t in CASES_303["trimestres"]])
def test_the_303_is_to_the_cent_the_one_the_owner_sees(api: Api, s303: Seeded, case: dict[str, Any]) -> None:  # AC-13
    params = {"year": case["anio"], "quarter": case["trimestre"]}
    mine, theirs = both(api, s303, "/api/tax/303", "/trimestres/303", **params)
    assert theirs == mine
    assert {b["code"]: b["amount_cents"] for b in theirs["boxes"]} == case["casillas"]


@pytest.mark.parametrize("case", CASES_130, ids=[c["caso"] for c in CASES_130])
def test_the_130_is_to_the_cent_the_one_the_owner_sees(api: Api, s130: Seeded, case: dict[str, Any]) -> None:  # AC-13
    params = {"year": case["anio"], "quarter": case["trimestre"]}
    mine, theirs = both(api, s130, "/api/tax/130", "/trimestres/130", **params)
    assert theirs == mine
    assert {b["code"]: b["amount_cents"] for b in theirs["boxes"]} == case["casillas"]


def test_the_period_errors_are_the_same_and_leave_no_trace(api: Api, s303: Seeded, admin: Connection[DictRow]) -> None:
    from tests.gestor.support import reads

    before = len(reads(admin, s303.cast.alicia))
    for model in ("303", "130"):
        for params, code in (
            ({"year": 2025, "quarter": 5}, "invalid_period"),
            ({"year": 2999, "quarter": 1}, "period_in_future"),
        ):
            mine = api.request("GET", f"/api/tax/{model}", s303.cast.alicia, params=params)
            theirs = api.request("GET", f"{base(s303)}/trimestres/{model}", s303.cast.gina, params=params)
            assert (mine.status_code, theirs.status_code) == (422, 422)
            assert mine.json()["code"] == theirs.json()["code"] == code
    assert len(reads(admin, s303.cast.alicia)) == before  # un periodo rechazado no abre nada ni registra nada
