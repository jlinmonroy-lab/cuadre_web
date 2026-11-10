"""AC-01 a AC-03, AC-06, AC-07, AC-10 y AC-18 · `app.issue_invoice` (SPEC-W-007 §5.2, §5.1.1 a §5.1.4, Anexo B.1-D).

Las condiciones que recibe la función las calcula `cuadre.tax` de verdad (ver `invoices_support`): la base comprueba que son COHERENTES con el
cliente y el perfil, no recalcula un porcentaje. Se prueba cada tratamiento, cada código de error con su `DETAIL`, el ORDEN de las comprobaciones
y que un fallo no consume el número. Las rectificativas, el cobro y el PDF están en `test_invoices_rectify.py` y `test_invoices_pay_and_pdf.py`.
"""

import datetime
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.tax import NOTE_NON_EU, NOTE_REVERSE_CHARGE
from tests.rls.invoices_support import (
    D1,
    D2,
    ISSUER,
    Ready,
    client,
    code_of,
    invoice,
    issue,
    made,
    next_number,
    ready,
    series,
    terms,
    today,
)
from tests.support import Cast, Pool, attempt, call

ALICIA_TOTALS = {
    # (ámbito, tipo): (tratamiento, tipo de IVA, IVA, retención, total, mención) con base 100.000 y retención del 15 % en el perfil
    ("national", "business"): ("national_vat", 21, 21_000, 15_000, 106_000, None),
    ("national", "individual"): ("national_vat", 21, 21_000, 0, 121_000, None),
    ("eu", "business"): ("eu_reverse_charge", 0, 0, 0, 100_000, NOTE_REVERSE_CHARGE),
    ("eu", "individual"): ("eu_consumer_vat", 21, 21_000, 0, 121_000, None),
    ("non_eu", "business"): ("non_eu_not_subject", 0, 0, 0, 100_000, NOTE_NON_EU),
    ("non_eu", "individual"): ("non_eu_consumer_vat", 21, 21_000, 0, 121_000, None),
}


@pytest.fixture
def r(admin: Connection[DictRow], cast: Cast) -> Ready:
    return ready(admin, cast.alicia)


# --- Emitir -----------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("scope", "kind"), list(ALICIA_TOTALS))
def test_each_treatment_is_stored_with_its_amounts_and_note(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, scope: str, kind: str
) -> None:
    treatment, vat_rate, vat, irpf, total, note = ALICIA_TOTALS[(scope, kind)]
    iid = made(issue(app_pool, cast.alicia, r.clients[(scope, kind)], r.series, scope=scope, kind=kind))
    row = invoice(admin, iid)
    assert (
        row["tax_treatment"],
        row["vat_rate"],
        row["vat_cents"],
        row["irpf_cents"],
        row["total_cents"],
        row["legal_note"],
    ) == (
        treatment,
        vat_rate,
        vat,
        irpf,
        total,
        note,
    )
    assert row["irpf_rate"] == (15 if irpf else 0)
    assert (
        row["owner_id"],
        row["kind"],
        row["base_cents"],
        row["rectifies_id"],
        row["rectification_reason"],
        row["paid_at"],
    ) == (
        cast.alicia.id,
        "standard",
        100_000,
        None,
        None,
        None,
    )


def test_the_number_is_the_next_of_the_series_and_advances_with_no_gaps(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    ids = [made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, when=D1)) for _ in range(3)]
    assert [(invoice(admin, i)["series_code"], invoice(admin, i)["number"]) for i in ids] == [
        ("2026", 1),
        ("2026", 2),
        ("2026", 3),
    ]
    assert next_number(admin, r.series) == 4


def test_a_series_that_starts_at_another_number_numbers_from_there(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    other = series(admin, cast.alicia, "B", first=500)
    iid = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], other))
    assert (invoice(admin, iid)["series_code"], invoice(admin, iid)["number"]) == ("B", 500)
    assert next_number(admin, other) == 501
    assert next_number(admin, r.series) == 1  # la otra serie no se toca


def test_the_issuer_and_the_client_are_frozen_copies(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("eu", "business")]
    iid = made(issue(app_pool, cast.alicia, cid, r.series, scope="eu", kind="business"))
    row = invoice(admin, iid)
    original = admin.execute("select * from public.clients where id = %s", (cid,)).fetchone()
    assert original is not None
    assert (
        row["client_name"],
        row["client_kind"],
        row["client_country"],
        row["client_scope"],
        row["client_tax_id"],
    ) == (
        original["name"],
        "business",
        "DE",
        "eu",
        original["tax_id"],
    )
    assert row["client_address"] == original["address"] and row["client_id"] == cid
    assert (row["issuer_name"], row["issuer_tax_id"], row["issuer_address"], row["issuer_iban"]) == (
        ISSUER["legal_name"],
        ISSUER["tax_id"],
        ISSUER["fiscal_address"],
        ISSUER["iban"],
    )
    # Cambiar al cliente o al perfil después NO cambia la factura (D-09).
    admin.execute("update public.clients set name = 'Otro nombre', address = 'Otra calle 9' where id = %s", (cid,))
    admin.execute(
        "update public.business_profiles set legal_name = 'Otro emisor', iban = null where owner_id = %s",
        (cast.alicia.id,),
    )
    assert invoice(admin, iid) == row


def test_the_client_address_is_stored_trimmed_and_the_issuer_iban_may_be_missing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia, iban=None)
    cid = client(admin, cast.alicia, address="  Calle con espacios 4  ")
    row = invoice(admin, made(issue(app_pool, cast.alicia, cid, r.series)))
    assert row["client_address"] == "Calle con espacios 4" and row["issuer_iban"] is None


def test_the_date_may_be_today_and_the_same_as_the_last_invoice_of_the_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    assert not issue(app_pool, cast.alicia, cid, r.series, when=today(admin)).error
    assert not issue(app_pool, cast.alicia, cid, r.series, when=today(admin)).error


def test_the_activity_log_has_only_ids_series_number_and_treatment(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    iid = made(
        issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, concept="Concepto secreto 123")
    )
    rows = admin.execute(
        "select category, actor_id, actor_role, owner_id, action, entity_type, entity_id, metadata from public.activity_log "
        "where action like 'invoice.%%' and owner_id = %s",
        (cast.alicia.id,),
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert (
        row["category"],
        row["actor_id"],
        row["actor_role"],
        row["action"],
        row["entity_type"],
        row["entity_id"],
    ) == (
        "data",
        cast.alicia.id,
        "usuario",
        "invoice.issued",
        "invoice",
        str(iid),
    )
    assert row["metadata"] == {"invoice_id": str(iid), "series": "2026", "number": 1, "treatment": "national_vat"}
    text = str(row)
    for secret in ("Concepto secreto", ISSUER["legal_name"], ISSUER["tax_id"], ISSUER["iban"], "Calle del Cliente"):
        assert secret not in text


# --- Quién puede ------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_issue(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, who: str
) -> None:
    out = issue(app_pool, cast[who], r.clients[("national", "business")], r.series)
    assert out.sqlstate == "42501"
    assert admin.execute("select count(*) as n from public.invoices").fetchone() is not None
    assert next_number(admin, r.series) == 1


def test_a_suspended_account_cannot_issue(app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series).sqlstate == "42501"


def test_another_persons_series_and_client_answer_like_missing_ones(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    beto = ready(admin, cast.beto)
    mine = r.clients[("national", "business")]
    assert code_of(issue(app_pool, cast.alicia, mine, beto.series)) == "series_not_found"
    assert code_of(issue(app_pool, cast.alicia, beto.clients[("national", "business")], r.series)) == "client_not_found"
    assert next_number(admin, beto.series) == 1 and next_number(admin, r.series) == 1


def test_unknown_null_archived_and_rectifying_series_are_all_series_not_found(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    mine = r.clients[("national", "business")]
    archived = series(admin, cast.alicia, "OLD")
    admin.execute("update public.invoice_series set archived_at = now() where id = %s", (archived,))
    rectifying = series(admin, cast.alicia, "R-2026", kind="rectifying")
    unknown = "00000000-0000-4000-8000-000000000000"
    for bad in (unknown, None, archived, rectifying):
        assert code_of(issue(app_pool, cast.alicia, mine, bad)) == "series_not_found", bad


def test_unknown_and_null_clients_are_client_not_found(app_pool: Pool, cast: Cast, r: Ready) -> None:
    for bad in ("00000000-0000-4000-8000-000000000000", None):
        assert code_of(issue(app_pool, cast.alicia, bad, r.series)) == "client_not_found"


# --- El cliente y el perfil ---------------------------------------------------------------------------------------------------------------


def test_an_archived_client_is_not_billable(app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready) -> None:
    cid = client(admin, cast.alicia, archived=True)
    out = issue(app_pool, cast.alicia, cid, r.series)
    assert (code_of(out), out.detail) == ("client_not_billable", "archived")


@pytest.mark.parametrize("address", [None, "", "   "])
def test_a_client_without_an_address_is_not_billable(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, address: str | None
) -> None:
    cid = client(admin, cast.alicia, address=address)
    out = issue(app_pool, cast.alicia, cid, r.series)
    assert (code_of(out), out.detail) == ("client_not_billable", "address")


def test_archived_is_reported_before_the_address(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = client(admin, cast.alicia, address=None, archived=True)
    assert issue(app_pool, cast.alicia, cid, r.series).detail == "archived"


@pytest.mark.parametrize(
    ("blank", "missing"),
    [
        ({"legal_name": None}, "legal_name"),
        ({"tax_id": None}, "tax_id"),
        ({"fiscal_address": None}, "fiscal_address"),
        ({"legal_name": None, "fiscal_address": None}, "legal_name,fiscal_address"),
        ({"legal_name": None, "tax_id": None, "fiscal_address": None}, "legal_name,tax_id,fiscal_address"),
    ],
)
def test_an_incomplete_profile_says_what_is_missing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, blank: dict[str, None], missing: str
) -> None:
    sets = ", ".join(f"{column} = null" for column in blank)
    admin.execute(f"update public.business_profiles set {sets} where owner_id = %s", (cast.alicia.id,))
    out = issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series)
    assert (code_of(out), out.detail) == ("profile_incomplete", missing)
    assert next_number(admin, r.series) == 1


def test_a_person_without_a_profile_row_is_incomplete(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    admin.execute("delete from public.business_profiles where owner_id = %s", (cast.alicia.id,))
    out = issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series)
    assert (code_of(out), out.detail) == ("profile_incomplete", "legal_name,tax_id,fiscal_address")


def test_the_client_is_checked_before_the_profile(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    admin.execute("update public.business_profiles set tax_id = null where owner_id = %s", (cast.alicia.id,))
    cid = client(admin, cast.alicia, archived=True)
    assert issue(app_pool, cast.alicia, cid, r.series).detail == "archived"


def test_a_national_company_needs_the_retention_chosen_but_nobody_else_does(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia, irpf=None)
    out = issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series)
    assert code_of(out) == "irpf_rate_missing"
    assert next_number(admin, r.series) == 1
    for scope, kind in (
        ("national", "individual"),
        ("eu", "business"),
        ("eu", "individual"),
        ("non_eu", "business"),
        ("non_eu", "individual"),
    ):
        assert not issue(app_pool, cast.alicia, r.clients[(scope, kind)], r.series, scope=scope, kind=kind).error


@pytest.mark.parametrize("irpf", ["7.00", "15.00"])
def test_the_retention_of_the_profile_is_the_one_that_must_come(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, irpf: str
) -> None:
    r = ready(admin, cast.alicia, irpf=irpf)
    cid = r.clients[("national", "business")]
    right = int(float(irpf))
    wrong = 7 if right == 15 else 15
    assert not issue(app_pool, cast.alicia, cid, r.series, irpf=str(right)).error
    out = issue(app_pool, cast.alicia, cid, r.series, irpf=str(wrong))
    assert (code_of(out), out.detail) == ("invalid_invoice", "irpf_rate")


# --- Los campos ---------------------------------------------------------------------------------------------------------------------------

GOOD_TERMS = terms()


def changed(**fields: Any) -> dict[str, Any]:
    return {**GOOD_TERMS, **fields}


def without(key: str) -> dict[str, Any]:
    return {k: v for k, v in GOOD_TERMS.items() if k != key}


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"when": None}, "issue_date"),
        ({"when": datetime.date(1999, 12, 31)}, "issue_date"),
        ({"concept": None}, "concept"),
        ({"concept": "a"}, "concept"),
        ({"concept": "a" * 301}, "concept"),
        ({"base": None, "given": GOOD_TERMS}, "base_cents"),
        ({"base": 0, "given": GOOD_TERMS}, "base_cents"),
        ({"base": -1, "given": GOOD_TERMS}, "base_cents"),
        ({"base": 10_000_000_000, "given": GOOD_TERMS}, "base_cents"),
        ({"given": None}, "terms"),
        ({"given": []}, "terms"),
        ({"given": "texto"}, "terms"),
        ({"given": {**GOOD_TERMS, "extra": 1}}, "terms"),
        ({"given": without("tax_treatment")}, "tax_treatment"),
        ({"given": without("vat_rate")}, "vat_rate"),
        ({"given": without("legal_note")}, "legal_note"),
        ({"given": changed(tax_treatment="inventado")}, "tax_treatment"),
        ({"given": changed(tax_treatment=1)}, "tax_treatment"),
        ({"given": changed(vat_rate="21")}, "vat_rate"),
        ({"given": changed(vat_rate=21.5)}, "vat_rate"),
        ({"given": changed(vat_rate=-21)}, "vat_rate"),
        ({"given": changed(irpf_rate="15")}, "irpf_rate"),
        ({"given": changed(vat_cents=21000.5)}, "vat_cents"),
        ({"given": changed(vat_cents="21000")}, "vat_cents"),
        ({"given": changed(vat_cents=-1)}, "vat_cents"),
        ({"given": changed(vat_cents=10**15)}, "vat_cents"),
        ({"given": changed(irpf_cents=-1)}, "irpf_cents"),
        ({"given": changed(total_cents=None)}, "total_cents"),
        ({"given": changed(legal_note=5)}, "legal_note"),
        ({"given": changed(legal_note="a" * 301)}, "legal_note"),
    ],
)
def test_a_bad_field_is_invalid_invoice_naming_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, kwargs: dict[str, Any], field: str
) -> None:
    args = {"when": D1, "concept": "Servicios", "base": 100_000, "given": "default", **kwargs}
    out = issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, **args)
    assert (code_of(out), out.detail) == ("invalid_invoice", field)
    assert next_number(admin, r.series) == 1  # un fallo no consume el número


def test_a_future_date_is_refused_but_tomorrow_in_madrid_is_the_first_future_day(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    tomorrow = today(admin) + datetime.timedelta(days=1)
    out = issue(app_pool, cast.alicia, cid, r.series, when=tomorrow)
    assert (code_of(out), out.detail) == ("invalid_invoice", "issue_date")
    assert not issue(app_pool, cast.alicia, cid, r.series, when=today(admin)).error


def test_the_earliest_date_that_can_be_issued_is_the_first_of_january_2000(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    out = issue(app_pool, cast.alicia, cid, r.series, when=datetime.date(1999, 12, 31))
    assert (code_of(out), out.detail) == ("invalid_invoice", "issue_date")
    assert not issue(app_pool, cast.alicia, cid, r.series, when=datetime.date(2000, 1, 1)).error


@pytest.mark.parametrize("zone", ["Pacific/Kiritimati", "Pacific/Pago_Pago"])
def test_today_is_the_day_in_madrid_whatever_the_clock_of_the_session_says(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, zone: str
) -> None:
    """Kiritimati va 12 o 13 horas por delante de Madrid y Pago Pago 10 u 11 por detrás: por la mañana o por la tarde de Madrid, una de las dos
    está en otro día. `current_date` daría un resultado distinto según la hora; `private.today_madrid()`, no."""
    cid = r.clients[("national", "business")]
    madrid = today(admin)
    sql = "select set_config('TimeZone', %s, true), app.issue_invoice(%s, %s, %s, 'Servicios', 100000, %s)"

    def attempt_on(day: datetime.date) -> Any:
        return attempt(app_pool, cast.alicia, sql, (zone, cid, r.series, day, Jsonb(terms())))

    assert not attempt_on(madrid).error
    out = attempt_on(madrid + datetime.timedelta(days=1))
    assert (out.sqlstate, out.message, out.detail) == ("P0001", "invalid_invoice", "issue_date")


def test_the_first_bad_field_is_the_one_reported(app_pool: Pool, cast: Cast, r: Ready) -> None:
    cid = r.clients[("national", "business")]
    assert (
        issue(app_pool, cast.alicia, cid, r.series, when=None, concept=None, base=0, given=None).detail == "issue_date"
    )
    assert issue(app_pool, cast.alicia, cid, r.series, concept=None, base=0, given=None).detail == "concept"
    assert issue(app_pool, cast.alicia, cid, r.series, base=0, given=None).detail == "base_cents"


# --- Las condiciones, coherentes con el cliente --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scope", "kind", "given", "field"),
    [
        # tratamiento que no es el del cliente
        ("national", "business", changed(tax_treatment="eu_reverse_charge"), "tax_treatment"),
        ("eu", "business", terms("national", "business"), "tax_treatment"),
        ("eu", "individual", terms("eu", "business"), "tax_treatment"),
        ("non_eu", "business", terms("non_eu", "individual"), "tax_treatment"),
        ("non_eu", "individual", terms("non_eu", "business"), "tax_treatment"),
        # sin IVA con tipo o cuota; con IVA, un tipo que no existe o sin tipo
        ("eu", "business", {**terms("eu", "business"), "vat_rate": 21}, "vat_rate"),
        ("eu", "business", {**terms("eu", "business"), "vat_cents": 5, "total_cents": 100_005}, "vat_cents"),
        ("non_eu", "business", {**terms("non_eu", "business"), "vat_rate": 4}, "vat_rate"),
        ("national", "business", changed(vat_rate=0, vat_cents=0, total_cents=85_000), "vat_rate"),
        ("national", "business", changed(vat_rate=5), "vat_rate"),
        ("eu", "individual", {**terms("eu", "individual"), "vat_rate": 0}, "vat_rate"),
        # la retención solo la lleva una empresa nacional, y es la del perfil
        ("national", "individual", {**terms("national", "individual"), "irpf_rate": 15}, "irpf_rate"),
        ("eu", "business", {**terms("eu", "business"), "irpf_rate": 7}, "irpf_rate"),
        ("national", "business", changed(irpf_rate=0), "irpf_rate"),
        ("national", "business", changed(irpf_rate=7), "irpf_rate"),
        (
            "national",
            "individual",
            {**terms("national", "individual"), "irpf_cents": 3, "total_cents": 120_997},
            "irpf_cents",
        ),
        # la identidad aritmética
        ("national", "business", changed(total_cents=106_001), "total_cents"),
        ("national", "business", changed(total_cents=127_000), "total_cents"),
        ("eu", "business", {**terms("eu", "business"), "total_cents": 99_999}, "total_cents"),
        # la mención: solo los dos tratamientos sin IVA llevan una
        ("eu", "business", {**terms("eu", "business"), "legal_note": None}, "legal_note"),
        ("non_eu", "business", {**terms("non_eu", "business"), "legal_note": None}, "legal_note"),
        ("national", "business", changed(legal_note=NOTE_REVERSE_CHARGE), "legal_note"),
        ("eu", "individual", {**terms("eu", "individual"), "legal_note": NOTE_NON_EU}, "legal_note"),
    ],
)
def test_the_terms_must_fit_the_client_and_the_profile(
    app_pool: Pool,
    admin: Connection[DictRow],
    cast: Cast,
    r: Ready,
    scope: str,
    kind: str,
    given: dict[str, Any],
    field: str,
) -> None:
    out = issue(app_pool, cast.alicia, r.clients[(scope, kind)], r.series, given=given)
    assert (code_of(out), out.detail) == ("invalid_invoice", field)
    assert next_number(admin, r.series) == 1


def test_a_legal_note_of_301_characters_is_refused_where_a_note_is_expected_and_300_are_not(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("eu", "business")]
    long_note = {**terms("eu", "business"), "legal_note": "a" * 301}
    out = issue(app_pool, cast.alicia, cid, r.series, given=long_note)
    assert (code_of(out), out.detail) == ("invalid_invoice", "legal_note")
    assert not issue(app_pool, cast.alicia, cid, r.series, given={**long_note, "legal_note": "a" * 300}).error


@pytest.mark.parametrize("vat", ["21", "10", "4"])
def test_the_three_vat_rates_are_accepted_where_there_is_vat(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, vat: str
) -> None:
    for scope, kind in (
        ("national", "business"),
        ("national", "individual"),
        ("eu", "individual"),
        ("non_eu", "individual"),
    ):
        iid = made(issue(app_pool, cast.alicia, r.clients[(scope, kind)], r.series, scope=scope, kind=kind, vat=vat))
        assert invoice(admin, iid)["vat_rate"] == int(vat)


@pytest.mark.parametrize("rate", [21, 21.0, 21.00])
def test_a_rate_written_as_21_21_0_or_21_00_is_the_same_rate(app_pool: Pool, cast: Cast, r: Ready, rate: float) -> None:
    given = Jsonb(changed(vat_rate=rate))
    out = call(
        app_pool,
        cast.alicia,
        "issue_invoice",
        r.clients[("national", "business")],
        r.series,
        D1,
        "Servicios",
        100_000,
        given,
    )
    assert not out.error, out.message


# --- Fechas y numeración -------------------------------------------------------------------------------------------------------------------


def test_a_date_before_the_last_invoice_of_the_series_is_out_of_order_and_says_which(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    made(issue(app_pool, cast.alicia, cid, r.series, when=D2))
    out = issue(app_pool, cast.alicia, cid, r.series, when=D1)
    assert (code_of(out), out.detail) == ("invoice_date_out_of_order", D2.isoformat())
    assert next_number(admin, r.series) == 2
    other = series(admin, cast.alicia, "B")  # en OTRA serie la fecha anterior sí vale
    assert not issue(app_pool, cast.alicia, cid, other, when=D1).error


def test_the_last_date_is_the_latest_one_even_with_gaps_in_the_numbers_of_other_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    other = series(admin, cast.alicia, "B")
    made(issue(app_pool, cast.alicia, cid, other, when=D2))  # otra serie con una fecha posterior
    assert not issue(app_pool, cast.alicia, cid, r.series, when=D1).error


def test_a_series_that_reaches_the_last_number_is_exhausted(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    last = series(admin, cast.alicia, "FIN", first=999_999)
    cid = r.clients[("national", "business")]
    iid = made(issue(app_pool, cast.alicia, cid, last))
    assert invoice(admin, iid)["number"] == 999_999 and next_number(admin, last) == 1_000_000
    assert code_of(issue(app_pool, cast.alicia, cid, last)) == "series_exhausted"
    assert next_number(admin, last) == 1_000_000


def test_a_failure_inside_the_insert_does_not_consume_the_number(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    """El número se avanza ANTES de insertar: si el INSERT falla, la transacción entera se deshace y el número sigue libre."""
    admin.execute("alter table public.invoices add constraint invoices_test_boom check (concept <> 'BOOM')")
    try:
        out = issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, concept="BOOM")
        assert out.sqlstate == "23514" and out.constraint == "invoices_test_boom"
    finally:
        admin.execute("alter table public.invoices drop constraint invoices_test_boom")
    assert next_number(admin, r.series) == 1
    iid = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    assert invoice(admin, iid)["number"] == 1


def test_a_failed_issue_leaves_no_trace_in_the_activity_log(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, concept="a")
    row = admin.execute(
        "select count(*) as n from public.activity_log where action like 'invoice.%%' and owner_id = %s",
        (cast.alicia.id,),
    ).fetchone()
    assert row == {"n": 0}
