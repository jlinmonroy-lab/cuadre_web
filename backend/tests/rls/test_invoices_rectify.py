"""AC-13 a AC-16 y AC-20 · `app.issue_rectifying_invoice` y `app.ensure_rectifying_series` (SPEC-W-007 §5.1.5, §5.2, D-12, Anexo B.1-D).

La rectificativa resta: su base es la corregida menos la vigente y sus cuotas, las diferencias de valores (B.2). La base RECALCULA lo vigente bajo el
cerrojo y no deja que nadie devuelva más de lo facturado aunque llame a la función a mano. Aquí: la rectificativa simple, la cadena que acaba en
cero, la serie `R-AAAA`, el orden de las comprobaciones y cada código de error. Las carreras están en `test_invoices_concurrency.py`.
"""

import datetime
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.tax import Standing
from tests.rls.invoices_support import (
    D1,
    D2,
    D3,
    ISSUER,
    Ready,
    code_of,
    invoice,
    issue,
    made,
    next_number,
    ready,
    rectification_terms,
    rectify,
    series,
    today,
)
from tests.support import Cast, Pool, call

STANDING = Standing(100_000, 21_000, 15_000)  # la original de las pruebas: base 100.000 al 21 % con retención del 15 %


@pytest.fixture
def r(admin: Connection[DictRow], cast: Cast) -> Ready:
    return ready(admin, cast.alicia)


@pytest.fixture
def original(app_pool: Pool, cast: Cast, r: Ready) -> Any:
    return made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series, when=D1))


def rect_series(admin: Connection[DictRow], cast: Cast) -> list[dict[str, Any]]:
    return admin.execute(
        "select * from public.invoice_series where owner_id = %s and kind = 'rectifying' order by code",
        (cast.alicia.id,),
    ).fetchall()


# --- La rectificativa ---------------------------------------------------------------------------------------------------------------------


def test_a_rectification_subtracts_the_difference_and_is_the_first_of_the_yearly_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    rid = made(rectify(app_pool, cast.alicia, original, corrected=80_000, when=D2))
    row = invoice(admin, rid)
    # base −20.000, IVA −4.200, retención −3.000, total −21.200 (§5.1.5)
    assert (row["kind"], row["base_cents"], row["vat_cents"], row["irpf_cents"], row["total_cents"]) == (
        "rectifying",
        -20_000,
        -4_200,
        -3_000,
        -21_200,
    )
    assert (row["series_code"], row["number"], row["issue_date"], row["rectifies_id"]) == ("R-2026", 1, D2, original)
    assert row["rectification_reason"] == "Importe mal calculado" and row["paid_at"] is None
    (serie,) = rect_series(admin, cast)
    assert (serie["id"], serie["code"], serie["is_default"], serie["next_number"], serie["archived_at"]) == (
        row["series_id"],
        "R-2026",
        False,
        2,
        None,
    )


def test_a_full_cancellation_gives_everything_back(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    rid = made(rectify(app_pool, cast.alicia, original, corrected=0))
    row = invoice(admin, rid)
    assert (row["base_cents"], row["vat_cents"], row["irpf_cents"], row["total_cents"]) == (
        -100_000,
        -21_000,
        -15_000,
        -106_000,
    )


def test_the_rectification_inherits_the_client_the_treatment_the_rates_the_note_and_the_concept(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("eu", "business")]
    eu = made(
        issue(app_pool, cast.alicia, cid, r.series, scope="eu", kind="business", concept="Concepto de la original")
    )
    orig = invoice(admin, eu)
    rid = made(
        rectify(app_pool, cast.alicia, eu, corrected=60_000, vat="0", irpf="0", standing=Standing(100_000, 0, 0))
    )
    row = invoice(admin, rid)
    for column in (
        "client_id",
        "client_name",
        "client_kind",
        "client_country",
        "client_scope",
        "client_tax_id",
        "client_address",
        "concept",
        "tax_treatment",
        "vat_rate",
        "irpf_rate",
        "legal_note",
    ):
        assert row[column] == orig[column], column
    assert row["legal_note"] and (row["vat_cents"], row["irpf_cents"], row["base_cents"], row["total_cents"]) == (
        0,
        0,
        -40_000,
        -40_000,
    )


def test_the_issuer_is_the_current_profile_and_the_client_copy_the_originals(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    before = invoice(admin, original)
    admin.execute(
        "update public.business_profiles set legal_name = 'Nuevo nombre', iban = null where owner_id = %s",
        (cast.alicia.id,),
    )
    admin.execute("update public.clients set name = 'Cliente renombrado' where id = %s", (before["client_id"],))
    row = invoice(admin, made(rectify(app_pool, cast.alicia, original)))
    assert (row["issuer_name"], row["issuer_iban"], row["issuer_tax_id"]) == ("Nuevo nombre", None, ISSUER["tax_id"])
    assert row["client_name"] == before["client_name"]  # la copia de la original, no el cliente de ahora


def test_an_archived_client_does_not_stop_a_rectification(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    admin.execute(
        "update public.clients set archived_at = now() where id = %s", (invoice(admin, original)["client_id"],)
    )
    assert not rectify(app_pool, cast.alicia, original).error


def test_a_paid_invoice_can_be_rectified(app_pool: Pool, cast: Cast, r: Ready, original: Any) -> None:
    assert not call(app_pool, cast.alicia, "set_invoice_paid", original, True).error
    assert not rectify(app_pool, cast.alicia, original).error


def test_the_activity_log_names_the_original_and_nothing_personal(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    rid = made(rectify(app_pool, cast.alicia, original, reason="Motivo secreto 987"))
    row = admin.execute(
        "select action, entity_id, metadata from public.activity_log where action = 'invoice.rectified' and owner_id = %s",
        (cast.alicia.id,),
    ).fetchone()
    assert row is not None
    assert (row["action"], row["entity_id"]) == ("invoice.rectified", str(rid))
    assert row["metadata"] == {
        "invoice_id": str(rid),
        "rectifies_id": str(original),
        "series": "R-2026",
        "number": 1,
        "treatment": "national_vat",
    }
    assert "Motivo secreto" not in str(row)


# --- La cadena ----------------------------------------------------------------------------------------------------------------------------


def test_each_rectification_works_from_what_is_still_standing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    first = made(rectify(app_pool, cast.alicia, original, corrected=80_000, when=D2))
    now = Standing(80_000, 16_800, 12_000)
    second = made(rectify(app_pool, cast.alicia, original, corrected=0, when=D3, standing=now))
    rows = [invoice(admin, i) for i in (first, second)]
    assert [(x["number"], x["base_cents"], x["vat_cents"], x["irpf_cents"]) for x in rows] == [
        (1, -20_000, -4_200, -3_000),
        (2, -80_000, -16_800, -12_000),
    ]
    total = admin.execute(
        "select sum(base_cents) as b, sum(vat_cents) as v, sum(irpf_cents) as i from public.invoices where id = %s or rectifies_id = %s",
        (original, original),
    ).fetchone()
    assert total == {"b": 0, "v": 0, "i": 0}
    assert len(rect_series(admin, cast)) == 1  # las dos van a la misma serie `R-2026`


def test_cancelling_105_at_10_percent_in_two_steps_leaves_nothing_standing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """El caso por el que las cuotas son DIFERENCIAS de valores y no un porcentaje del importe negativo (B.2): −52 y −53 dejaban 1 de cuota."""
    r = ready(admin, cast.alicia)
    cid = r.clients[("national", "individual")]
    original = made(issue(app_pool, cast.alicia, cid, r.series, base=105, vat="10", kind="individual"))
    start = Standing(105, 11, 0)
    made(rectify(app_pool, cast.alicia, original, corrected=53, standing=start, vat="10", irpf="0"))  # base −52
    made(
        rectify(app_pool, cast.alicia, original, corrected=0, standing=Standing(53, 5, 0), vat="10", irpf="0", when=D3)
    )
    total = admin.execute(
        "select sum(base_cents) as b, sum(vat_cents) as v, sum(total_cents) as t from public.invoices where id = %s or rectifies_id = %s",
        (original, original),
    ).fetchone()
    assert total == {"b": 0, "v": 0, "t": 0}


def test_once_at_zero_there_is_nothing_left_to_rectify(app_pool: Pool, cast: Cast, r: Ready, original: Any) -> None:
    made(rectify(app_pool, cast.alicia, original, corrected=0))
    zero = Standing(0, 0, 0)
    out = rectify(
        app_pool,
        cast.alicia,
        original,
        corrected=0,
        standing=zero,
        given={"vat_cents": 0, "irpf_cents": 0, "total_cents": 0},
        when=D3,
    )
    assert (code_of(out), out.detail) == ("invalid_invoice", "corrected_base_cents")
    assert (
        code_of(rectify(app_pool, cast.alicia, original, corrected=1, standing=zero, when=D3))
        == "rectification_exceeds"
    )


def test_a_rectification_cannot_raise_the_invoice(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    assert code_of(rectify(app_pool, cast.alicia, original, corrected=100_001)) == "rectification_exceeds"
    made(rectify(app_pool, cast.alicia, original, corrected=80_000))
    # Ya no vale 90.000, aunque fuera menos que la original: lo vigente es 80.000.
    assert code_of(rectify(app_pool, cast.alicia, original, corrected=90_000, when=D3)) == "rectification_exceeds"
    assert next_number(admin, rect_series(admin, cast)[0]["id"]) == 2


def test_a_rectification_to_the_same_base_has_nothing_to_rectify(
    app_pool: Pool, cast: Cast, r: Ready, original: Any
) -> None:
    out = rectify(
        app_pool, cast.alicia, original, corrected=100_000, given={"vat_cents": 0, "irpf_cents": 0, "total_cents": 0}
    )
    assert (code_of(out), out.detail) == ("invalid_invoice", "corrected_base_cents")


def test_a_rectification_cannot_be_rectified(app_pool: Pool, cast: Cast, r: Ready, original: Any) -> None:
    rid = made(rectify(app_pool, cast.alicia, original))
    assert code_of(rectify(app_pool, cast.alicia, rid, when=D3)) == "invoice_not_rectifiable"


def test_the_original_must_be_mine_and_exist(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    assert code_of(rectify(app_pool, cast.beto, original)) == "invoice_not_found"
    assert code_of(rectify(app_pool, cast.alicia, "00000000-0000-4000-8000-000000000000")) == "invoice_not_found"
    assert code_of(rectify(app_pool, cast.alicia, None)) == "invoice_not_found"


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_rectify(app_pool: Pool, cast: Cast, r: Ready, original: Any, who: str) -> None:
    assert rectify(app_pool, cast[who], original).sqlstate == "42501"


# --- La serie rectificativa del año --------------------------------------------------------------------------------------------------------


def test_the_yearly_series_is_made_once_and_reused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    first = call(app_pool, cast.alicia, "ensure_rectifying_series", 2026)
    again = call(app_pool, cast.alicia, "ensure_rectifying_series", 2026)
    other = call(app_pool, cast.alicia, "ensure_rectifying_series", 2027)
    assert made(first) == made(again) != made(other)
    assert [s["code"] for s in rect_series(admin, cast)] == ["R-2026", "R-2027"]
    assert all(not s["is_default"] and s["description"] for s in rect_series(admin, cast))


def test_a_rectification_goes_to_the_series_of_the_year_of_its_date(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    old_series = series(admin, cast.alicia, "2025")
    old = made(issue(app_pool, cast.alicia, cid, old_series, when=datetime.date(2025, 12, 20)))
    rid = made(rectify(app_pool, cast.alicia, old, when=datetime.date(2025, 12, 31)))
    assert invoice(admin, rid)["series_code"] == "R-2025"
    rid2 = made(
        rectify(app_pool, cast.alicia, old, when=D1, corrected=60_000, standing=Standing(80_000, 16_800, 12_000))
    )
    assert invoice(admin, rid2)["series_code"] == "R-2026"
    assert [s["code"] for s in rect_series(admin, cast)] == ["R-2025", "R-2026"]


@pytest.mark.parametrize("year", [None, 1999, 10_000, -1, 0])
def test_the_year_of_a_rectifying_series_has_four_digits_from_2000(
    app_pool: Pool, cast: Cast, r: Ready, year: int | None
) -> None:
    out = call(app_pool, cast.alicia, "ensure_rectifying_series", year)
    assert (code_of(out), out.detail) == ("invalid_invoice", "issue_date")


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_make_the_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    assert call(app_pool, cast[who], "ensure_rectifying_series", 2026).sqlstate == "42501"
    assert rect_series(admin, cast) == []


def test_the_exhausted_yearly_series_stops_the_rectifications(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    sid = made(call(app_pool, cast.alicia, "ensure_rectifying_series", 2026))
    admin.execute("update public.invoice_series set next_number = 1000000 where id = %s", (sid,))
    assert code_of(rectify(app_pool, cast.alicia, original)) == "series_exhausted"


# --- Fechas -------------------------------------------------------------------------------------------------------------------------------


def test_a_date_before_the_original_is_out_of_order_and_says_which(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    late = made(issue(app_pool, cast.alicia, cid, r.series, when=D3))
    out = rectify(app_pool, cast.alicia, late, when=D2)
    assert (code_of(out), out.detail) == ("invoice_date_out_of_order", D3.isoformat())
    assert not rectify(app_pool, cast.alicia, late, when=D3).error  # la misma fecha vale


def test_a_date_before_the_last_rectification_is_out_of_order_in_the_rectifying_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    one = made(issue(app_pool, cast.alicia, cid, r.series, when=D1))
    two = made(issue(app_pool, cast.alicia, cid, r.series, when=D1))
    made(rectify(app_pool, cast.alicia, one, when=D3))
    out = rectify(app_pool, cast.alicia, two, when=D2)
    assert (code_of(out), out.detail) == ("invoice_date_out_of_order", D3.isoformat())


def test_a_future_or_missing_date_is_a_bad_field_even_before_looking_for_the_original(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    tomorrow = today(admin) + datetime.timedelta(days=1)
    for when in (tomorrow, None, datetime.date(1999, 12, 31)):
        out = rectify(app_pool, cast.alicia, original, when=when)
        assert (code_of(out), out.detail) == ("invalid_invoice", "issue_date")
        out = rectify(app_pool, cast.alicia, "00000000-0000-4000-8000-000000000000", when=when)
        assert (code_of(out), out.detail) == ("invalid_invoice", "issue_date")
    assert rect_series(admin, cast) == []
    assert not rectify(app_pool, cast.alicia, original, when=today(admin)).error


# --- Los campos y las cuotas -----------------------------------------------------------------------------------------------------------------

GOOD = rectification_terms(STANDING, 80_000)


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"reason": None}, "reason"),
        ({"reason": "a"}, "reason"),
        ({"reason": "a" * 301}, "reason"),
        ({"corrected": None, "given": GOOD}, "corrected_base_cents"),
        ({"corrected": -1, "given": GOOD}, "corrected_base_cents"),
        ({"given": None}, "terms"),
        ({"given": {**GOOD, "extra": 1}}, "terms"),
        ({"given": {"vat_cents": -4200, "total_cents": -21200}}, "irpf_cents"),
        ({"given": {**GOOD, "vat_cents": "x"}}, "vat_cents"),
        ({"given": {**GOOD, "vat_cents": -4200.5}}, "vat_cents"),
        ({"given": {**GOOD, "irpf_cents": None}}, "irpf_cents"),
        ({"given": {**GOOD, "total_cents": 1.5}}, "total_cents"),
    ],
)
def test_a_bad_field_is_invalid_invoice_naming_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any, kwargs: dict[str, Any], field: str
) -> None:
    args = {"corrected": 80_000, "given": "default", **kwargs}
    out = rectify(app_pool, cast.alicia, original, **args)
    assert (code_of(out), out.detail) == ("invalid_invoice", field)
    # Nada queda: ni la rectificativa ni la serie `R-AAAA` que la función creó antes de fallar.
    assert not admin.execute("select 1 from public.invoices where rectifies_id = %s", (original,)).fetchall()
    assert rect_series(admin, cast) == []


@pytest.mark.parametrize(
    ("given", "field"),
    [
        # el IVA o la retención no restan, o dejan lo vigente por debajo de cero
        ({"vat_cents": 100, "irpf_cents": -3000, "total_cents": -16_900}, "vat_cents"),
        ({"vat_cents": -21_001, "irpf_cents": -3000, "total_cents": -38_001}, "vat_cents"),
        ({"vat_cents": -4200, "irpf_cents": 100, "total_cents": -24_100}, "irpf_cents"),
        ({"vat_cents": -4200, "irpf_cents": -15_001, "total_cents": -9_199}, "irpf_cents"),
        # la identidad aritmética
        ({"vat_cents": -4200, "irpf_cents": -3000, "total_cents": -21_201}, "total_cents"),
    ],
)
def test_the_amounts_cannot_give_back_more_than_what_stands(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any, given: dict[str, int], field: str
) -> None:
    out = rectify(app_pool, cast.alicia, original, given=given)
    assert (code_of(out), out.detail) == ("invalid_invoice", field)
    assert admin.execute(
        "select count(*) as n from public.invoices where rectifies_id = %s", (original,)
    ).fetchone() == {"n": 0}


def test_a_full_cancellation_must_give_back_the_whole_vat_and_retention(
    app_pool: Pool, cast: Cast, r: Ready, original: Any
) -> None:
    short_vat = {"vat_cents": -20_000, "irpf_cents": -15_000, "total_cents": -105_000}
    short_irpf = {"vat_cents": -21_000, "irpf_cents": -14_000, "total_cents": -107_000}
    assert rectify(app_pool, cast.alicia, original, corrected=0, given=short_vat).detail == "vat_cents"
    assert rectify(app_pool, cast.alicia, original, corrected=0, given=short_irpf).detail == "irpf_cents"


def test_where_the_original_has_no_vat_or_retention_the_rectification_has_none_either(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    eu = made(issue(app_pool, cast.alicia, r.clients[("eu", "business")], r.series, scope="eu", kind="business"))
    out = rectify(
        app_pool, cast.alicia, eu, corrected=60_000, given={"vat_cents": -1, "irpf_cents": 0, "total_cents": -40_001}
    )
    assert out.detail == "vat_cents"
    out = rectify(
        app_pool, cast.alicia, eu, corrected=60_000, given={"vat_cents": 0, "irpf_cents": -1, "total_cents": -39_999}
    )
    assert out.detail == "irpf_cents"


def test_the_profile_must_still_be_complete_to_rectify(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    admin.execute("update public.business_profiles set fiscal_address = null where owner_id = %s", (cast.alicia.id,))
    out = rectify(app_pool, cast.alicia, original)
    assert (code_of(out), out.detail) == ("profile_incomplete", "fiscal_address")


def test_the_checks_run_in_the_documented_order(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    made(rectify(app_pool, cast.alicia, original, corrected=80_000, when=D3))
    rect_id = admin.execute("select id from public.invoices where rectifies_id = %s", (original,)).fetchone()
    assert rect_id is not None
    # 1.º que no sea una rectificativa; 2.º el motivo; 3.º que no suba; 4.º las fechas
    assert (
        code_of(rectify(app_pool, cast.alicia, rect_id["id"], reason=None, when=D1, corrected=999_999))
        == "invoice_not_rectifiable"
    )
    assert rectify(app_pool, cast.alicia, original, reason=None, corrected=999_999, when=D1).detail == "reason"
    assert code_of(rectify(app_pool, cast.alicia, original, corrected=999_999, when=D1)) == "rectification_exceeds"
    assert (
        code_of(
            rectify(
                app_pool, cast.alicia, original, corrected=10_000, when=D2, standing=Standing(80_000, 16_800, 12_000)
            )
        )
        == "invoice_date_out_of_order"
    )
