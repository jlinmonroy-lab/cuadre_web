"""AC-18 · La vista previa (SPEC-W-007 §5.3, T7-07): ámbito, importes y mención sin número y sin escribir nada.

Es la misma validación que emitir (mismos errores y mismos importes), pero no crea la serie del año, no avanza ningún número y no deja rastro en el
registro de actividad. El navegador la enseña y no calcula impuestos.
"""

from typing import Any

import pytest

from cuadre.tax import NOTE_NON_EU, NOTE_REVERSE_CHARGE
from tests.invoicing.conftest import Api, invoice_body
from tests.rls.invoices_support import series

EXPECTED = {
    ("national", "business"): ("national_vat", "21.00", 21_000, "15.00", 15_000, 106_000, None, True),
    ("national", "individual"): ("national_vat", "21.00", 21_000, "0.00", 0, 121_000, None, True),
    ("eu", "business"): ("eu_reverse_charge", "0.00", 0, "0.00", 0, 100_000, NOTE_REVERSE_CHARGE, False),
    ("eu", "individual"): ("eu_consumer_vat", "21.00", 21_000, "0.00", 0, 121_000, None, True),
    ("non_eu", "business"): ("non_eu_not_subject", "0.00", 0, "0.00", 0, 100_000, NOTE_NON_EU, False),
    ("non_eu", "individual"): ("non_eu_consumer_vat", "21.00", 21_000, "0.00", 0, 121_000, None, True),
}


def snapshot(api: Api) -> dict[str, Any]:
    """Todo lo que emitir tocaría: facturas, contadores de serie, series y registro de actividad de Alicia."""
    owner = api.cast.alicia.id
    return {
        "invoices": api.admin.execute(
            "select count(*) as n from public.invoices where owner_id = %s", (owner,)
        ).fetchone(),
        "series": api.admin.execute(
            "select code, next_number from public.invoice_series where owner_id = %s order by code", (owner,)
        ).fetchall(),
        "log": api.admin.execute(
            "select count(*) as n from public.activity_log where owner_id = %s", (owner,)
        ).fetchone(),
    }


@pytest.mark.parametrize(("scope", "kind"), list(EXPECTED))
def test_the_preview_shows_scope_amounts_and_note(api: Api, scope: str, kind: str) -> None:
    treatment, rate, vat, irpf_rate, irpf, total, note, editable = EXPECTED[(scope, kind)]
    response = api.preview(api.cast.alicia, invoice_body(api.cid(scope, kind)))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "scope": scope,
        "kind": kind,
        "tax_treatment": treatment,
        "base_cents": 100_000,
        "vat_rate": rate,
        "vat_cents": vat,
        "irpf_rate": irpf_rate,
        "irpf_cents": irpf,
        "total_cents": total,
        "legal_note": note,
        "vat_editable": editable,
    }


def test_the_preview_follows_the_vat_rate_chosen(api: Api) -> None:
    response = api.preview(api.cast.alicia, invoice_body(api.cid("national", "individual"), vat_rate="10.00"))
    assert (response.json()["vat_rate"], response.json()["vat_cents"], response.json()["total_cents"]) == (
        "10.00",
        10_000,
        110_000,
    )


def test_the_preview_is_what_issuing_then_stores(api: Api) -> None:
    body = invoice_body(api.cid("national", "business"), base_cents=123_457)
    preview = api.preview(api.cast.alicia, body).json()
    invoice = api.issue(api.cast.alicia, body).json()
    for key in (
        "tax_treatment",
        "base_cents",
        "vat_rate",
        "vat_cents",
        "irpf_rate",
        "irpf_cents",
        "total_cents",
        "legal_note",
    ):
        assert preview[key] == invoice[key], key


def test_the_preview_writes_nothing(api: Api) -> None:
    api.admin.execute("delete from public.invoice_series where owner_id = %s", (api.cast.alicia.id,))
    before = snapshot(api)
    assert (
        api.preview(api.cast.alicia, invoice_body(api.cid())).status_code == 422
    )  # sin serie no hay vista previa y tampoco se crea
    assert snapshot(api) == before
    other = series(api.admin, api.cast.alicia, "B")
    before = snapshot(api)
    for _ in range(3):
        assert api.preview(api.cast.alicia, invoice_body(api.cid(), series_id=str(other))).status_code == 200
    assert snapshot(api) == before


def test_the_preview_needs_no_number_and_so_not_even_a_free_one(api: Api) -> None:
    last = series(api.admin, api.cast.alicia, "FIN", first=999_999)
    api.made(api.cast.alicia, series_id=str(last))  # la serie queda agotada
    assert api.preview(api.cast.alicia, invoice_body(api.cid(), series_id=str(last))).status_code == 200


def test_the_preview_reports_every_field_error_at_once(api: Api) -> None:
    response = api.preview(
        api.cast.alicia, {"client_id": "no-uuid", "issue_date": "2026-02-30", "concept": "a", "base_cents": 0}
    )
    assert response.status_code == 422
    assert {f["field"] for f in response.json()["fields"]} == {"client_id", "issue_date", "concept", "base_cents"}


def test_the_preview_has_the_same_problems_as_issuing(api: Api) -> None:
    api.admin.execute("update public.clients set archived_at = now() where id = %s", (api.cid(),))
    response = api.preview(api.cast.alicia, invoice_body(api.cid()))
    assert (response.status_code, response.json()["code"], response.json()["field"]) == (
        409,
        "client_not_billable",
        "client_id",
    )
    api.admin.execute("update public.business_profiles set tax_id = null where owner_id = %s", (api.cast.alicia.id,))
    response = api.preview(api.cast.alicia, invoice_body(api.cid("eu", "business")))
    assert (response.status_code, response.json()["code"]) == (422, "profile_incomplete")
    assert response.json()["missing"] == [{"field": "tax_id", "label": "NIF"}]


def test_the_preview_refuses_a_date_before_the_last_invoice_of_the_series(api: Api) -> None:
    api.made(api.cast.alicia, issue_date="2026-03-09")
    response = api.preview(api.cast.alicia, invoice_body(api.cid(), issue_date="2026-03-02"))
    assert (response.status_code, response.json()["code"]) == (409, "invoice_date_out_of_order")


def test_the_preview_with_a_missing_retention_is_the_same_422(api: Api) -> None:
    api.admin.execute("update public.business_profiles set irpf_rate = null where owner_id = %s", (api.cast.alicia.id,))
    response = api.preview(api.cast.alicia, invoice_body(api.cid()))
    assert (response.status_code, response.json()["code"]) == (422, "irpf_rate_missing")
