"""AC-01 a AC-06, AC-09, AC-10 · Validar una factura: campos, todos los errores a la vez y los problemas que impiden emitir (SPEC-W-007 §5.1.1)."""

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from cuadre.invoicing import MESSAGES, RawInvoice, parse_uuid, validate_invoice
from tests.invoicing.support import (
    CLIENT_ID,
    FULLWIDTH_DATE,
    IRPF,
    LF,
    LINE_SEP,
    NBSP,
    RLO,
    SERIES_ID,
    TAB,
    TODAY,
    ZERO_WIDTH,
    client,
    issue,
    issue_no_client,
    issue_no_series,
    series,
)

# Cada mensaje de §5.1.1, tal cual está escrito en la spec.
TEXT = {
    "client": "Elige un cliente.",
    "client_archived": "Ese cliente está archivado: reactívalo para facturarle.",
    "client_address": "Falta el domicilio del cliente: añádelo para emitir la factura.",
    "series": "Elige una serie activa.",
    "date": "Elige la fecha de expedición.",
    "date_future": "La fecha no puede ser futura.",
    "concept": "Describe el servicio facturado.",
    "concept_length": "El concepto admite entre 2 y 300 caracteres, sin saltos de línea.",
    "base": "Escribe un importe mayor que cero, por ejemplo 1.200,00.",
    "base_max": "El importe no puede superar 99.999.999,99 €.",
    "vat_rate": "El tipo de IVA no es válido: elige 21, 10 o 4 %.",
    "vat_not_applicable": "Este cliente no lleva IVA: no envíes tipo de IVA.",
    "irpf_rate_missing": "Elige tu retención de IRPF en el perfil para facturar a una empresa.",
}


def errors(result) -> dict[str, str]:
    return {e.field: e.message for e in result.errors}


def test_the_messages_are_the_ones_of_the_spec() -> None:
    for key, text in TEXT.items():
        assert MESSAGES[key] == text, key


def test_a_result_is_exactly_one_of_values_errors_or_problem() -> None:
    cases = [issue(), issue(concept=None), issue(cl=client(archived=True))]
    for result in cases:
        assert (result.values is not None) + bool(result.errors) + (result.problem is not None) == 1


# --- La factura válida ---------------------------------------------------------------------------------------------------------


def test_ac_01_a_national_company_with_vat_and_withholding() -> None:
    result = issue()
    assert result.values is not None and result.errors == () and result.problem is None
    v = result.values
    assert (v.client_id, v.series_id, v.issue_date, v.concept) == (
        CLIENT_ID,
        SERIES_ID,
        date(2026, 11, 10),
        "Diseño de identidad visual",
    )
    a = v.amounts
    assert (a.base_cents, a.vat_cents, a.irpf_cents, a.total_cents) == (120_000, 25_200, 18_000, 127_200)
    assert v.terms.treatment == "national_vat" and v.terms.legal_note is None


def test_ac_02_a_company_in_the_eu_has_no_vat_and_the_reverse_charge_note() -> None:
    v = issue(cl=client("eu", "business", country="DE", tax_id="DE534861408"), base_cents=150_000).values
    assert v is not None
    assert (v.amounts.base_cents, v.amounts.vat_cents, v.amounts.irpf_cents, v.amounts.total_cents) == (
        150_000,
        0,
        0,
        150_000,
    )
    assert (v.terms.treatment, v.terms.legal_note) == ("eu_reverse_charge", "Inversión del sujeto pasivo.")


@pytest.mark.parametrize(
    ("scope", "kind", "treatment", "vat", "total"),
    [
        ("eu", "individual", "eu_consumer_vat", 21_000, 121_000),
        ("national", "individual", "national_vat", 21_000, 121_000),
        ("non_eu", "individual", "non_eu_consumer_vat", 21_000, 121_000),
        ("non_eu", "business", "non_eu_not_subject", 0, 100_000),
    ],
)
def test_ac_03_the_other_scopes(scope, kind, treatment, vat, total) -> None:
    v = issue(cl=client(scope, kind), base_cents=100_000).values
    assert v is not None
    assert (v.terms.treatment, v.amounts.vat_cents, v.amounts.irpf_cents, v.amounts.total_cents) == (
        treatment,
        vat,
        0,
        total,
    )


def test_ac_03_a_company_outside_the_eu_carries_the_article_69_note() -> None:
    v = issue(cl=client("non_eu", "business")).values
    assert (
        v is not None
        and v.terms.legal_note == "Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA)."
    )


@pytest.mark.parametrize(
    ("vat", "expected"),
    [
        (None, 25_200),
        ("21", 25_200),
        ("21.0", 25_200),
        ("21.00", 25_200),
        ("10", 12_000),
        ("10.00", 12_000),
        ("4", 4_800),
        (" 4.00 ", 4_800),
        ("", 25_200),
        ("  ", 25_200),
    ],
)
def test_ac_04_the_vat_rates_a_national_client_accepts(vat, expected) -> None:
    v = issue(vat_rate=vat).values
    assert v is not None and v.amounts.vat_cents == expected
    assert str(v.amounts.vat_rate) == {25_200: "21.00", 12_000: "10.00", 4_800: "4.00"}[expected]


@pytest.mark.parametrize(
    "vat",
    ["0", "7", "5", "22", "21,00", "21 %", "abc", "-21", "1e1", "٢١", "21.001", 21, 21.0, Decimal(21), True, ["21"]],
)
def test_ac_04_a_vat_rate_that_is_not_21_10_or_4_is_refused(vat) -> None:
    assert errors(issue(vat_rate=vat)) == {"vat_rate": TEXT["vat_rate"]}


@pytest.mark.parametrize(("scope", "kind"), [("eu", "business"), ("non_eu", "business")])
def test_ac_04_a_client_without_vat_is_not_sent_a_rate(scope, kind) -> None:
    assert errors(issue(cl=client(scope, kind), vat_rate="21.00")) == {"vat_rate": TEXT["vat_not_applicable"]}
    assert issue(cl=client(scope, kind), vat_rate=None).values is not None
    assert issue(cl=client(scope, kind), vat_rate="  ").values is not None
    # Un tipo que ni siquiera es un tipo se dice igual, venga a quien venga.
    assert errors(issue(cl=client(scope, kind), vat_rate="7")) == {"vat_rate": TEXT["vat_rate"]}


def test_the_concept_is_trimmed_and_kept() -> None:
    v = issue(concept="  Diseño ñandú — niño  ").values
    assert v is not None and v.concept == "Diseño ñandú — niño"


# --- Campos, uno a uno -----------------------------------------------------------------------------------------------------------


def test_the_client_is_required() -> None:
    assert errors(issue_no_client()) == {"client_id": TEXT["client"]}


@pytest.mark.parametrize("bad", [None, "no-hay-serie"])
def test_the_series_must_exist(bad) -> None:
    assert errors(issue_no_series(series_id=bad)) == {"series_id": TEXT["series"]}


def test_an_archived_or_rectifying_series_is_not_offered_for_invoices() -> None:
    assert errors(issue(se=series(archived=True))) == {"series_id": TEXT["series"]}
    assert errors(issue(se=series(kind="rectifying"))) == {"series_id": TEXT["series"]}


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "   ",
        "2026-02-30",
        "2026-13-01",
        "2026-00-10",
        "2026-11-00",
        "2026-11-31",
        "20261110",
        "2026/11/10",
        "10-11-2026",
        "2026-11-10T00:00",
        "2026-1-5",
        FULLWIDTH_DATE,
        "1999-12-31",
        "0001-01-01",
        "hoy",
        20261110,
        3.5,
        True,
        datetime(2026, 11, 10),
    ],
)
def test_ac_09_a_date_that_does_not_exist_or_is_not_a_date(bad) -> None:
    assert errors(issue(issue_date=bad)) == {"issue_date": TEXT["date"]}


@pytest.mark.parametrize(
    "good", ["2026-11-10", " 2026-11-10 ", "2026-03-10", "2000-01-01", "2024-02-29", date(2026, 11, 10)]
)
def test_a_real_date_up_to_today_is_accepted(good) -> None:
    result = issue(issue_date=good)
    assert result.values is not None, errors(result)


@pytest.mark.parametrize("future", ["2026-11-11", "2027-01-01", date(2026, 12, 31)])
def test_ac_09_a_future_date_is_a_field_error(future) -> None:
    assert errors(issue(issue_date=future)) == {"issue_date": TEXT["date_future"]}


def test_today_is_the_injected_day_not_the_system_clock() -> None:
    assert issue(issue_date="2026-11-10", today=date(2026, 11, 10)).values is not None
    assert errors(issue(issue_date="2026-11-10", today=date(2026, 11, 9))) == {"issue_date": TEXT["date_future"]}


@pytest.mark.parametrize("bad", [None, "", "   ", 5, 5.5, True, ["Diseño"]])
def test_the_concept_is_required(bad) -> None:
    assert errors(issue(concept=bad)) == {"concept": TEXT["concept"]}


@pytest.mark.parametrize(
    "bad",
    [
        "a",
        "  a  ",
        "x" * 301,
        "Diseño" + LF + "logo",
        "Diseño" + TAB + "logo",
        "Diseño" + ZERO_WIDTH,
        RLO + "Diseño",
        "Diseño" + LINE_SEP + "x",
        "Dis" + chr(0) + "eño",
    ],
)
def test_the_concept_is_two_to_300_characters_on_one_line(bad) -> None:
    assert errors(issue(concept=bad)) == {"concept": TEXT["concept_length"]}


@pytest.mark.parametrize(
    "good",
    [
        "ab",
        "x" * 300,
        "Diseño de logo",
        "Diseño" + NBSP + "gráfico — ñ",
        "  " + "x" * 300 + "  ",
    ],
)
def test_the_concept_bounds_are_inclusive(good) -> None:
    assert issue(concept=good).values is not None


@pytest.mark.parametrize(
    "bad", [None, True, False, "120", "120.5", 120.0, 120.5, Decimal(120), 0, -1, -120_000, [1], {}]
)
def test_the_base_is_a_positive_integer_number_of_cents(bad) -> None:
    assert errors(issue(base_cents=bad)) == {"base_cents": TEXT["base"]}


def test_the_base_goes_from_one_cent_to_99_999_999_99() -> None:
    assert issue(base_cents=1).values is not None
    assert issue(base_cents=9_999_999_999).values is not None
    assert errors(issue(base_cents=10_000_000_000)) == {"base_cents": TEXT["base_max"]}
    assert errors(issue(base_cents=10**30)) == {"base_cents": TEXT["base_max"]}


# --- Todos los errores a la vez ----------------------------------------------------------------------------------------------------


def test_ac_10_all_the_field_errors_come_at_once_in_the_order_of_the_screen() -> None:
    result = validate_invoice(RawInvoice(), client=None, series=None, irpf_rate=IRPF, today=TODAY)
    assert [(e.field, e.message) for e in result.errors] == [
        ("client_id", TEXT["client"]),
        ("series_id", TEXT["series"]),
        ("issue_date", TEXT["date"]),
        ("concept", TEXT["concept"]),
        ("base_cents", TEXT["base"]),
    ]
    assert result.values is None and result.problem is None


def test_ac_10_with_a_client_the_vat_rate_joins_the_list_in_its_place() -> None:
    result = validate_invoice(
        RawInvoice(
            client_id=CLIENT_ID, series_id=SERIES_ID, issue_date="2026-02-30", concept="", base_cents=0, vat_rate="99"
        ),
        client=client(),
        series=series(),
        irpf_rate=IRPF,
        today=TODAY,
    )
    assert [e.field for e in result.errors] == ["issue_date", "concept", "base_cents", "vat_rate"]


def test_field_errors_hide_the_problems_that_would_come_after() -> None:
    result = issue(
        cl=client(archived=True, address=None), concept="", irpf=None, se=series(last_issue_date=date(2026, 12, 1))
    )
    assert [e.field for e in result.errors] == ["concept"] and result.problem is None


def test_the_messages_never_repeat_what_was_typed() -> None:
    secret = "SECRETO-9Z"
    result = validate_invoice(
        RawInvoice(
            client_id=secret,
            series_id=secret,
            issue_date=secret,
            concept=secret + LF,
            base_cents=secret,
            vat_rate=secret,
        ),
        client=None,
        series=None,
        irpf_rate=IRPF,
        today=TODAY,
    )
    assert result.errors
    assert all(secret not in e.message for e in result.errors)


# --- Problemas: lo que impide emitir aunque los datos estén bien ------------------------------------------------------------------


def test_ac_06_an_archived_client_cannot_be_invoiced() -> None:
    p = issue(cl=client(archived=True)).problem
    assert p is not None and (p.code, p.status, p.field, p.message) == (
        "client_not_billable",
        409,
        "client_id",
        TEXT["client_archived"],
    )


@pytest.mark.parametrize("address", [None, "", "   ", TAB])
def test_ac_06_a_client_without_address_cannot_be_invoiced(address) -> None:
    p = issue(cl=client(address=address)).problem
    assert p is not None and (p.code, p.status, p.field, p.message) == (
        "client_not_billable",
        409,
        "address",
        TEXT["client_address"],
    )


def test_ac_05_a_company_that_withholds_needs_the_retention_of_the_profile() -> None:
    p = issue(irpf=None).problem
    assert p is not None and (p.code, p.status, p.field, p.message) == (
        "irpf_rate_missing",
        422,
        None,
        TEXT["irpf_rate_missing"],
    )


@pytest.mark.parametrize(
    ("scope", "kind"),
    [
        ("national", "individual"),
        ("eu", "business"),
        ("eu", "individual"),
        ("non_eu", "business"),
        ("non_eu", "individual"),
    ],
)
def test_only_a_spanish_company_needs_the_retention(scope, kind) -> None:
    assert issue(cl=client(scope, kind), irpf=None).values is not None


def test_ac_09_a_date_before_the_last_of_the_series_is_a_problem_and_the_same_date_is_fine() -> None:
    last = series(last_issue_date=date(2026, 3, 10))
    p = issue(se=last, issue_date="2026-03-09").problem
    assert p is not None and (p.code, p.status, p.field) == ("invoice_date_out_of_order", 409, "issue_date")
    assert p.message == "La fecha no puede ser anterior a la de la última factura de la serie (10/03/2026)."
    assert issue(se=last, issue_date="2026-03-10").values is not None
    assert issue(se=last, issue_date="2026-03-11").values is not None
    assert issue(se=series(last_issue_date=None), issue_date="2000-01-01").values is not None


def test_the_order_of_the_problems_is_archived_then_address_then_retention_then_date() -> None:
    everything = dict(cl=client(archived=True, address=None), irpf=None, se=series(last_issue_date=date(2026, 12, 1)))
    assert (
        issue(**everything).problem.code == "client_not_billable" and issue(**everything).problem.field == "client_id"
    )  # type: ignore[union-attr]
    no_address = dict(cl=client(address=None), irpf=None, se=series(last_issue_date=date(2026, 12, 1)))
    assert issue(**no_address).problem.field == "address"  # type: ignore[union-attr]
    no_irpf = dict(irpf=None, se=series(last_issue_date=date(2026, 12, 1)))
    assert issue(**no_irpf).problem.code == "irpf_rate_missing"  # type: ignore[union-attr]
    only_date = dict(se=series(last_issue_date=date(2026, 12, 1)))
    assert issue(**only_date).problem.code == "invoice_date_out_of_order"  # type: ignore[union-attr]


def test_a_problem_is_never_reported_together_with_values() -> None:
    result = issue(cl=client(archived=True))
    assert result.values is None and result.errors == ()


# --- Normalización de ids -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("good", [CLIENT_ID, " " + CLIENT_ID + " ", CLIENT_ID.upper()])
def test_parse_uuid_accepts_a_uuid_in_any_case_and_returns_it_lower(good) -> None:
    assert parse_uuid(good) == CLIENT_ID


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "no-uuid",
        CLIENT_ID[:-1],
        CLIENT_ID + "0",
        CLIENT_ID.replace("-", ""),
        "{" + CLIENT_ID + "}",
        5,
        [CLIENT_ID],
        "g" + CLIENT_ID[1:],
    ],
)
def test_parse_uuid_refuses_anything_else(bad) -> None:
    assert parse_uuid(bad) is None


def test_the_values_are_immutable() -> None:
    v = issue().values
    assert v is not None
    with pytest.raises(AttributeError):
        v.concept = "otro"  # type: ignore[misc]
    assert replace(v, concept="otro").concept == "otro"


# --- El año de la fecha (la serie rectificativa es la de ese año) -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "year"),
    [
        ("2026-11-10", 2026),
        (" 2025-12-31 ", 2025),
        ("2000-01-01", 2000),
        (date(2027, 3, 4), 2027),
        ("1999-12-31", None),  # antes del 2000 no se admite
        ("2026-02-30", None),
        ("2026-13-01", None),
        (FULLWIDTH_DATE, None),
        ("26-11-10", None),
        ("", None),
        (None, None),
        (20261110, None),
        (datetime(2026, 11, 10, 12, 0), None),
    ],
)
def test_issue_year(raw: object, year: int | None) -> None:
    from cuadre.invoicing.rules import issue_year

    assert issue_year(raw) == year
