"""AC-01 a AC-03, AC-05, AC-06, AC-10 a AC-13 · Emitir, leer y cobrar facturas por la API (SPEC-W-007 §5.3).

La API valida con `cuadre.invoicing` ANTES de llamar a la base, devuelve todos los errores de campo a la vez y no emite nada si algo falla. Las
condiciones (ámbito, IVA, retención, mención) las calcula el servidor. Las rectificativas están en `test_rectifications_api.py` y el listado en
`test_listing.py`.
"""

import uuid
from datetime import timedelta
from typing import Any

import pytest

from cuadre.tax import NOTE_NON_EU, NOTE_REVERSE_CHARGE
from tests.invoicing.conftest import CONCEPT, Api, invoice_body
from tests.rls.invoices_support import D1, D2, ISSUER, ready, series

EXPECTED = {
    # (ámbito, tipo): (tratamiento, tipo de IVA, IVA, retención, total, mención) con base 100.000 y retención del 15 % en el perfil
    ("national", "business"): ("national_vat", "21.00", 21_000, 15_000, 106_000, None),
    ("national", "individual"): ("national_vat", "21.00", 21_000, 0, 121_000, None),
    ("eu", "business"): ("eu_reverse_charge", "0.00", 0, 0, 100_000, NOTE_REVERSE_CHARGE),
    ("eu", "individual"): ("eu_consumer_vat", "21.00", 21_000, 0, 121_000, None),
    ("non_eu", "business"): ("non_eu_not_subject", "0.00", 0, 0, 100_000, NOTE_NON_EU),
    ("non_eu", "individual"): ("non_eu_consumer_vat", "21.00", 21_000, 0, 121_000, None),
}


# --- Emitir -----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("scope", "kind"), list(EXPECTED))
def test_each_treatment_is_issued_with_its_amounts_and_note(api: Api, scope: str, kind: str) -> None:
    treatment, rate, vat, irpf, total, note = EXPECTED[(scope, kind)]
    invoice = api.made(api.cast.alicia, scope, kind)
    assert (invoice["tax_treatment"], invoice["vat_rate"], invoice["vat_cents"], invoice["irpf_cents"]) == (
        treatment,
        rate,
        vat,
        irpf,
    )
    assert (invoice["base_cents"], invoice["total_cents"], invoice["legal_note"]) == (100_000, total, note)
    assert invoice["irpf_rate"] == ("15.00" if irpf else "0.00")
    assert (invoice["kind"], invoice["rectifies"], invoice["rectification_reason"], invoice["rectified_by"]) == (
        "standard",
        None,
        None,
        [],
    )
    assert (invoice["paid_at"], invoice["pdf_status"]) == (None, "pending")


def test_the_response_has_the_documented_shape(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    assert set(invoice) == {
        "id",
        "series_code",
        "number",
        "display_number",
        "kind",
        "issue_date",
        "client",
        "concept",
        "tax_treatment",
        "base_cents",
        "vat_rate",
        "vat_cents",
        "irpf_rate",
        "irpf_cents",
        "total_cents",
        "legal_note",
        "rectifies",
        "rectification_reason",
        "rectified_by",
        "standing",
        "paid_at",
        "pdf_status",
        "created_at",
    }
    assert set(invoice["client"]) == {"id", "name", "kind", "country", "scope", "tax_id", "address"}
    assert (invoice["series_code"], invoice["number"], invoice["display_number"]) == ("2026", 1, "2026-001")
    assert invoice["issue_date"] == D1.isoformat() and invoice["concept"] == CONCEPT
    assert invoice["standing"] == {"base_cents": 100_000, "vat_cents": 21_000, "irpf_cents": 15_000}
    assert invoice["client"]["id"] == str(api.cid())


def test_the_numbers_are_correlative_and_the_display_number_has_three_digits(api: Api) -> None:
    numbers = [api.made(api.cast.alicia)["display_number"] for _ in range(3)]
    assert numbers == ["2026-001", "2026-002", "2026-003"]


def test_the_vat_rate_can_be_chosen_where_there_is_vat(api: Api) -> None:
    for rate, vat in (("10.00", 10_000), ("4.00", 4_000), ("21.00", 21_000), ("21", 21_000)):
        invoice = api.made(api.cast.alicia, "national", "individual", vat_rate=rate)
        assert invoice["vat_cents"] == vat


def test_the_series_may_be_chosen_or_left_to_the_default(api: Api) -> None:
    other = series(api.admin, api.cast.alicia, "B", first=40)
    chosen = api.made(api.cast.alicia, series_id=str(other))
    assert chosen["display_number"] == "B-040"
    assert api.made(api.cast.alicia, series_id="")["display_number"] == "2026-001"
    assert api.made(api.cast.alicia, series_id=str(api.world.series))["display_number"] == "2026-002"


def test_the_client_and_the_issuer_are_frozen_copies(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    row = api.admin.execute(
        "select issuer_name, issuer_tax_id, issuer_iban from public.invoices where id = %s", (invoice["id"],)
    ).fetchone()
    assert row == {
        "issuer_name": ISSUER["legal_name"],
        "issuer_tax_id": ISSUER["tax_id"],
        "issuer_iban": ISSUER["iban"],
    }
    api.admin.execute("update public.clients set name = 'Otro nombre' where id = %s", (api.cid(),))
    assert api.get(api.cast.alicia, invoice["id"]).json()["client"]["name"] == invoice["client"]["name"]


def test_the_current_year_series_is_created_when_the_person_has_none(api: Api) -> None:
    api.admin.execute("delete from public.invoice_series where owner_id = %s", (api.cast.alicia.id,))
    invoice = api.made(api.cast.alicia)
    year = str(api.today().year)
    assert (invoice["series_code"], invoice["number"]) == (year, 1)
    rows = api.admin.execute(
        "select code, is_default from public.invoice_series where owner_id = %s", (api.cast.alicia.id,)
    ).fetchall()
    assert rows == [{"code": year, "is_default": True}]


# --- Errores de campo: todos a la vez y nada se emite -----------------------------------------------------------------------------------


def fields_of(response: Any) -> dict[str, str]:
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "invalid_invoice"
    return {f["field"]: f["message"] for f in body["fields"]}


def issued_count(api: Api) -> int:
    row = api.admin.execute(
        "select count(*) as n from public.invoices where owner_id = %s", (api.cast.alicia.id,)
    ).fetchone()
    assert row is not None
    return row["n"]


def test_every_bad_field_is_reported_at_once_and_nothing_is_issued(api: Api) -> None:
    body = {
        "client_id": "no-uuid",
        "series_id": "tampoco",
        "issue_date": "2026-02-30",
        "concept": "a",
        "base_cents": 0,
        "vat_rate": "5",
    }
    errors = fields_of(api.issue(api.cast.alicia, body))
    assert set(errors) == {"client_id", "series_id", "issue_date", "concept", "base_cents", "vat_rate"}
    assert issued_count(api) == 0


def test_a_missing_body_reports_the_required_fields(api: Api) -> None:
    errors = fields_of(api.issue(api.cast.alicia, {}))
    assert set(errors) == {"client_id", "issue_date", "concept", "base_cents"}  # la serie vacía es la predeterminada


@pytest.mark.parametrize("base", [True, False, "120", 120.0, 1.5, [1], {"a": 1}])
def test_base_cents_must_be_a_real_integer(api: Api, base: object) -> None:
    response = api.issue(api.cast.alicia, invoice_body(api.cid(), base_cents=base))
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
    assert issued_count(api) == 0


def test_an_unknown_field_is_a_validation_error(api: Api) -> None:
    response = api.issue(api.cast.alicia, {**invoice_body(api.cid()), "total_cents": 1})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"issue_date": "2026-13-01"}, "issue_date"),
        ({"issue_date": None}, "issue_date"),
        ({"concept": "x" * 301}, "concept"),
        ({"concept": None}, "concept"),
        ({"base_cents": -5}, "base_cents"),
        ({"base_cents": 10_000_000_000}, "base_cents"),
        ({"vat_rate": "abc"}, "vat_rate"),
        ({"vat_rate": "5.00"}, "vat_rate"),
        ({"client_id": str(uuid.uuid4())}, "client_id"),
        ({"series_id": str(uuid.uuid4())}, "series_id"),
    ],
)
def test_each_bad_field_names_itself(api: Api, changes: dict[str, Any], field: str) -> None:
    assert field in fields_of(api.issue(api.cast.alicia, {**invoice_body(api.cid()), **changes}))


def test_a_future_date_is_a_field_error(api: Api) -> None:
    tomorrow = (api.today() + timedelta(days=1)).isoformat()
    assert "issue_date" in fields_of(api.issue(api.cast.alicia, invoice_body(api.cid(), issue_date=tomorrow)))


def test_a_client_without_vat_refuses_a_vat_rate(api: Api) -> None:
    errors = fields_of(api.issue(api.cast.alicia, invoice_body(api.cid("eu", "business"), vat_rate="21.00")))
    assert list(errors) == ["vat_rate"]


def test_another_persons_client_or_series_is_a_field_error(api: Api) -> None:
    beto = ready(api.admin, api.cast.beto)
    assert "client_id" in fields_of(api.issue(api.cast.alicia, invoice_body(beto.clients[("national", "business")])))
    assert "series_id" in fields_of(api.issue(api.cast.alicia, invoice_body(api.cid(), series_id=str(beto.series))))
    assert issued_count(api) == 0


def test_an_archived_or_rectifying_series_is_a_field_error(api: Api) -> None:
    archived = series(api.admin, api.cast.alicia, "OLD")
    api.admin.execute("update public.invoice_series set archived_at = now() where id = %s", (archived,))
    rectifying = series(api.admin, api.cast.alicia, "R-2026", kind="rectifying")
    for bad in (archived, rectifying):
        assert "series_id" in fields_of(api.issue(api.cast.alicia, invoice_body(api.cid(), series_id=str(bad))))


# --- Problemas: un solo motivo, con su código ---------------------------------------------------------------------------------------------


def test_an_incomplete_profile_says_what_is_missing_before_looking_at_the_body(api: Api) -> None:
    api.admin.execute(
        "update public.business_profiles set legal_name = null, fiscal_address = null where owner_id = %s",
        (api.cast.alicia.id,),
    )
    response = api.issue(api.cast.alicia, {"client_id": "no-uuid"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "profile_incomplete"
    assert body["missing"] == [
        {"field": "legal_name", "label": "Nombre o razón social"},
        {"field": "fiscal_address", "label": "Domicilio fiscal"},
    ]
    assert issued_count(api) == 0


def test_a_missing_retention_blocks_only_a_national_company(api: Api) -> None:
    api.admin.execute("update public.business_profiles set irpf_rate = null where owner_id = %s", (api.cast.alicia.id,))
    blocked = api.issue(api.cast.alicia, invoice_body(api.cid("national", "business")))
    assert blocked.status_code == 422 and blocked.json()["code"] == "irpf_rate_missing"
    for scope, kind in (("national", "individual"), ("eu", "business"), ("non_eu", "individual")):
        assert api.issue(api.cast.alicia, invoice_body(api.cid(scope, kind))).status_code == 201


def test_an_archived_client_is_not_billable(api: Api) -> None:
    api.admin.execute("update public.clients set archived_at = now() where id = %s", (api.cid(),))
    response = api.issue(api.cast.alicia, invoice_body(api.cid()))
    assert response.status_code == 409
    assert (response.json()["code"], response.json()["field"]) == ("client_not_billable", "client_id")


def test_a_client_without_an_address_is_not_billable(api: Api) -> None:
    api.admin.execute("update public.clients set address = null where id = %s", (api.cid(),))
    response = api.issue(api.cast.alicia, invoice_body(api.cid()))
    assert response.status_code == 409
    assert (response.json()["code"], response.json()["field"]) == ("client_not_billable", "address")


def test_a_date_before_the_last_invoice_of_the_series_is_out_of_order(api: Api) -> None:
    api.made(api.cast.alicia, issue_date=D2.isoformat())
    response = api.issue(api.cast.alicia, invoice_body(api.cid(), issue_date=D1.isoformat()))
    assert response.status_code == 409
    body = response.json()
    assert (body["code"], body["field"]) == ("invoice_date_out_of_order", "issue_date")
    assert "09/03/2026" in body["detail"]  # la fecha de la última factura de la serie
    assert issued_count(api) == 1
    assert api.made(api.cast.alicia, issue_date=D2.isoformat())["display_number"] == "2026-002"  # la misma fecha vale


def test_the_first_problem_in_order_is_the_one_reported(api: Api) -> None:
    api.admin.execute("update public.clients set archived_at = now(), address = null where id = %s", (api.cid(),))
    api.admin.execute("update public.business_profiles set irpf_rate = null where owner_id = %s", (api.cast.alicia.id,))
    assert api.issue(api.cast.alicia, invoice_body(api.cid())).json()["field"] == "client_id"


def test_a_failed_issue_leaves_no_serie_and_no_log(api: Api) -> None:
    api.admin.execute("delete from public.invoice_series where owner_id = %s", (api.cast.alicia.id,))
    assert api.issue(api.cast.alicia, invoice_body(api.cid(), concept="a")).status_code == 422
    series_rows = api.admin.execute(
        "select count(*) as n from public.invoice_series where owner_id = %s", (api.cast.alicia.id,)
    ).fetchone()
    log = api.admin.execute(
        "select count(*) as n from public.activity_log where owner_id = %s and action like 'invoice.%%'",
        (api.cast.alicia.id,),
    ).fetchone()
    assert series_rows == {"n": 0} and log == {"n": 0}


def test_a_serie_that_has_reached_the_last_number_is_exhausted(api: Api) -> None:
    last = series(api.admin, api.cast.alicia, "FIN", first=999_999)
    assert api.issue(api.cast.alicia, invoice_body(api.cid(), series_id=str(last))).status_code == 201
    response = api.issue(api.cast.alicia, invoice_body(api.cid(), series_id=str(last)))
    assert response.status_code == 409 and response.json()["code"] == "series_exhausted"


# --- Leer ------------------------------------------------------------------------------------------------------------------------------


def test_get_returns_the_invoice_and_another_persons_is_not_found(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    assert api.get(api.cast.alicia, invoice["id"]).json() == invoice
    other = api.get(api.cast.beto, invoice["id"])
    missing = api.get(api.cast.alicia, uuid.uuid4())
    assert other.status_code == missing.status_code == 404
    assert other.json()["code"] == missing.json()["code"] == "invoice_not_found"
    assert api.get(api.cast.alicia, "no-uuid").status_code == 422


# --- Cobrar ----------------------------------------------------------------------------------------------------------------------------


def test_an_invoice_can_be_paid_and_unpaid(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    paid = api.pay(api.cast.alicia, invoice["id"], True)
    assert paid.status_code == 200 and paid.json()["paid_at"] is not None
    assert {k: v for k, v in paid.json().items() if k != "paid_at"} == {
        k: v for k, v in invoice.items() if k != "paid_at"
    }
    again = api.pay(api.cast.alicia, invoice["id"], True)
    assert again.json()["paid_at"] == paid.json()["paid_at"]
    assert api.pay(api.cast.alicia, invoice["id"], False).json()["paid_at"] is None


@pytest.mark.parametrize("flag", ["yes", 1, "true", None, 0])
def test_paid_must_be_a_real_boolean(api: Api, flag: object) -> None:
    invoice = api.made(api.cast.alicia)
    response = api.pay(api.cast.alicia, invoice["id"], flag)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_paying_another_persons_or_a_missing_invoice_is_not_found(api: Api) -> None:
    invoice = api.made(api.cast.alicia)
    assert api.pay(api.cast.beto, invoice["id"], True).status_code == 404
    assert api.pay(api.cast.alicia, uuid.uuid4(), True).status_code == 404
