"""AC-08, AC-09, AC-11 y AC-17 · `app.set_invoice_paid`, `app.attach_invoice_pdf` y lo que SPEC-W-007 cambia en las series de SPEC-W-005.

Cobrar es lo único que cambia en una factura (`paid_at`); el PDF se registra una sola vez, con una ruta y una huella coherentes entre sí; y las
series rectificativas `R-AAAA` no se crean, editan, predeterminan ni archivan por las funciones de series ordinarias (`series_lock_own` solo ve las
ordinarias y el código está reservado). La base no sabe cómo es el PDF: ruta y huella las construye el servicio del hito 3.
"""

import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from tests.rls.invoices_support import Ready, code_of, invoice, issue, made, ready, rectify, series
from tests.support import Cast, Pool, call

SHA = "0123456789abcdef" * 4


@pytest.fixture
def r(admin: Connection[DictRow], cast: Cast) -> Ready:
    return ready(admin, cast.alicia)


@pytest.fixture
def original(app_pool: Pool, cast: Cast, r: Ready) -> Any:
    return made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))


def paid_at(admin: Connection[DictRow], invoice_id: object) -> Any:
    return invoice(admin, invoice_id)["paid_at"]


def payment_log(admin: Connection[DictRow], cast: Cast) -> list[dict[str, Any]]:
    return admin.execute(
        "select metadata from public.activity_log where action = 'invoice.payment_changed' and owner_id = %s order by id",
        (cast.alicia.id,),
    ).fetchall()


# --- Cobrar -----------------------------------------------------------------------------------------------------------------------------


def test_paying_sets_paid_at_and_unpaying_clears_it(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any
) -> None:
    assert paid_at(admin, original) is None
    assert not call(app_pool, cast.alicia, "set_invoice_paid", original, True).error
    assert paid_at(admin, original) is not None
    assert not call(app_pool, cast.alicia, "set_invoice_paid", original, False).error
    assert paid_at(admin, original) is None


def test_paying_twice_keeps_the_first_date_and_only_real_changes_are_logged(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any
) -> None:
    call(app_pool, cast.alicia, "set_invoice_paid", original, False)  # ya estaba sin cobrar: nada
    assert payment_log(admin, cast) == []
    call(app_pool, cast.alicia, "set_invoice_paid", original, True)
    first = paid_at(admin, original)
    call(app_pool, cast.alicia, "set_invoice_paid", original, True)
    assert paid_at(admin, original) == first
    call(app_pool, cast.alicia, "set_invoice_paid", original, False)
    assert [e["metadata"]["paid"] for e in payment_log(admin, cast)] == [True, False]


def test_the_payment_entry_has_only_the_invoice_series_number_and_state(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any
) -> None:
    call(app_pool, cast.alicia, "set_invoice_paid", original, True)
    (entry,) = payment_log(admin, cast)
    assert entry["metadata"] == {"invoice_id": str(original), "series": "2026", "number": 1, "paid": True}


def test_paying_changes_nothing_else_in_the_invoice(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any
) -> None:
    before = invoice(admin, original)
    call(app_pool, cast.alicia, "set_invoice_paid", original, True)
    after = invoice(admin, original)
    assert {k: v for k, v in after.items() if k != "paid_at"} == {k: v for k, v in before.items() if k != "paid_at"}


def test_a_rectification_is_not_payable(app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any) -> None:
    rid = made(rectify(app_pool, cast.alicia, original))
    assert code_of(call(app_pool, cast.alicia, "set_invoice_paid", rid, True)) == "invoice_not_payable"
    assert paid_at(admin, rid) is None


def test_only_my_invoices_are_found_and_the_flag_must_be_a_boolean(app_pool: Pool, cast: Cast, original: Any) -> None:
    assert code_of(call(app_pool, cast.beto, "set_invoice_paid", original, True)) == "invoice_not_found"
    assert code_of(call(app_pool, cast.alicia, "set_invoice_paid", uuid.uuid4(), True)) == "invoice_not_found"
    assert code_of(call(app_pool, cast.alicia, "set_invoice_paid", None, True)) == "invoice_not_found"
    out = call(app_pool, cast.alicia, "set_invoice_paid", original, None)
    assert (code_of(out), out.detail) == ("invalid_invoice", "paid")


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_pay(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any, who: str
) -> None:
    assert call(app_pool, cast[who], "set_invoice_paid", original, True).sqlstate == "42501"
    assert paid_at(admin, original) is None


# --- El PDF ---------------------------------------------------------------------------------------------------------------------------------


def good_path(cast: Cast, invoice_id: object, sha: str = SHA) -> str:
    return f"{cast.alicia.id}/{invoice_id}-{sha[:16]}.pdf"


def attach(pool: Pool, cast: Cast, invoice_id: object, **over: Any) -> Any:
    args = {"path": good_path(cast, invoice_id), "sha": SHA, "size": 12_345, **over}
    return call(pool, cast.alicia, "attach_invoice_pdf", invoice_id, args["path"], args["sha"], args["size"])


def test_the_pdf_is_recorded_once(app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any) -> None:
    assert not attach(app_pool, cast, original).error
    row = admin.execute("select * from public.invoice_files where invoice_id = %s", (original,)).fetchone()
    assert row is not None
    assert (row["owner_id"], row["storage_path"], row["sha256"], row["size_bytes"]) == (
        cast.alicia.id,
        good_path(cast, original),
        SHA,
        12_345,
    )
    assert code_of(attach(app_pool, cast, original)) == "invoice_pdf_exists"
    # incluso con otra huella: una vez subido, el PDF no se sustituye
    other = "f" * 64
    assert (
        code_of(attach(app_pool, cast, original, sha=other, path=good_path(cast, original, other)))
        == "invoice_pdf_exists"
    )
    assert admin.execute("select sha256 from public.invoice_files where invoice_id = %s", (original,)).fetchone() == {
        "sha256": SHA
    }


def test_a_rectification_has_its_own_pdf(app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any) -> None:
    rid = made(rectify(app_pool, cast.alicia, original))
    assert not attach(app_pool, cast, original).error
    assert not attach(app_pool, cast, rid).error
    assert admin.execute(
        "select count(*) as n from public.invoice_files where owner_id = %s", (cast.alicia.id,)
    ).fetchone() == {"n": 2}


@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"sha": None}, "sha256"),
        ({"sha": "A" * 64}, "sha256"),
        ({"sha": "a" * 63}, "sha256"),
        ({"sha": "g" * 64}, "sha256"),
        ({"size": None}, "size_bytes"),
        ({"size": 0}, "size_bytes"),
        ({"size": 1_048_577}, "size_bytes"),
        ({"path": None}, "storage_path"),
        ({"path": "no/es/la/ruta.pdf"}, "storage_path"),
        ({"path": "$beto"}, "storage_path"),
        ({"path": "$other_invoice"}, "storage_path"),
        ({"path": "$upper"}, "storage_path"),
        ({"path": "$short_hash"}, "storage_path"),
        ({"path": "$other_hash"}, "storage_path"),
        ({"path": "$no_extension"}, "storage_path"),
    ],
)
def test_a_bad_pdf_record_is_invalid_invoice_naming_the_field(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any, over: dict[str, Any], field: str
) -> None:
    good = good_path(cast, original)
    shapes = {
        "$beto": good.replace(str(cast.alicia.id), str(cast.beto.id)),
        "$other_invoice": good_path(cast, uuid.uuid4()),
        "$upper": good.upper(),
        "$short_hash": good[:-5] + ".pdf",
        "$other_hash": good_path(cast, original, "e" * 64),
        "$no_extension": good[:-4],
    }
    over = {k: shapes.get(v, v) if isinstance(v, str) else v for k, v in over.items()}
    out = attach(app_pool, cast, original, **over)
    assert (code_of(out), out.detail) == ("invalid_invoice", field)
    assert admin.execute("select count(*) as n from public.invoice_files").fetchone() is not None
    assert not admin.execute("select 1 from public.invoice_files where invoice_id = %s", (original,)).fetchall()


def test_only_my_invoices_take_a_pdf(app_pool: Pool, cast: Cast, original: Any) -> None:
    out = call(
        app_pool, cast.beto, "attach_invoice_pdf", original, f"{cast.beto.id}/{original}-{SHA[:16]}.pdf", SHA, 10
    )
    assert code_of(out) == "invoice_not_found"
    assert code_of(attach(app_pool, cast, uuid.uuid4())) == "invoice_not_found"


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_attach_a_pdf(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, original: Any, who: str
) -> None:
    out = call(app_pool, cast[who], "attach_invoice_pdf", original, good_path(cast, original), SHA, 10)
    assert out.sqlstate == "42501"
    assert not admin.execute("select 1 from public.invoice_files where invoice_id = %s", (original,)).fetchall()


# --- Lo que cambia en las series de SPEC-W-005 ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["R-2026", "R-0000", "R-9999", "R-1234"])
def test_a_rectifying_code_is_reserved_when_creating_a_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, code: str
) -> None:
    out = call(app_pool, cast.alicia, "create_invoice_series", code, None, None, False)
    assert code_of(out) == "series_code_reserved"
    assert not admin.execute(
        "select 1 from public.invoice_series where owner_id = %s and code = %s", (cast.alicia.id, code)
    ).fetchall()


@pytest.mark.parametrize("code", ["R-26", "R-20266", "R-202", "XR-2026", "R2026", "r-2026", "R-ABCD", "R-2026A"])
def test_codes_that_only_look_like_a_rectifying_one_are_free(app_pool: Pool, cast: Cast, code: str) -> None:
    out = call(app_pool, cast.alicia, "create_invoice_series", code, None, None, False)
    # `r-2026` en minúsculas y `R-2026A` (7 caracteres con una letra al final) no son formato válido de serie; los demás sí valen.
    expected = {"r-2026": "invalid_series"}
    if code in expected:
        assert code_of(out) == expected[code]
    else:
        assert not out.error, (code, out.message)


def test_a_rectifying_code_is_reserved_when_renaming_a_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    out = call(app_pool, cast.alicia, "update_invoice_series", r.series, Jsonb({"code": "R-2027"}))
    assert code_of(out) == "series_code_reserved"
    assert admin.execute("select code from public.invoice_series where id = %s", (r.series,)).fetchone() == {
        "code": "2026"
    }


@pytest.mark.parametrize("code", ["R-26", "R-20266", "XR-2026", "R2026", "R-ABCD"])
def test_codes_that_only_look_like_a_rectifying_one_are_free_when_renaming_too(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, code: str
) -> None:
    other = made(call(app_pool, cast.alicia, "create_invoice_series", "TMP", None, None, False))
    out = call(app_pool, cast.alicia, "update_invoice_series", other, Jsonb({"code": code}))
    assert not out.error, (code, out.message)
    assert admin.execute("select code from public.invoice_series where id = %s", (other,)).fetchone() == {"code": code}


def test_the_check_of_the_series_table_keeps_the_codes_apart_even_for_the_database_owner(
    admin: Connection[DictRow], cast: Cast
) -> None:
    def violates(code: str, kind: str, default: bool = False) -> str:
        try:
            series(admin, cast.alicia, code, kind=kind, default=default)
        except psycopg.errors.CheckViolation as exc:
            return exc.diag.constraint_name or "?"
        return "ok"

    assert violates("R-2026", "standard") == "invoice_series_kind_matches_code"
    assert violates("AB", "rectifying") == "invoice_series_kind_matches_code"
    assert violates("R-2027", "rectifying", default=True) == "invoice_series_rectifying_not_default"
    assert violates("R-2028", "rectifying") == "ok"
    assert violates("2028", "standard", default=True) == "ok"


def test_the_ordinary_series_functions_do_not_see_a_rectifying_series(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    rect = made(call(app_pool, cast.alicia, "ensure_rectifying_series", 2026))
    for function, args in (
        ("update_invoice_series", (rect, Jsonb({"description": "otra"}))),
        ("set_default_invoice_series", (rect,)),
        ("set_invoice_series_archived", (rect, True)),
    ):
        assert code_of(call(app_pool, cast.alicia, function, *args)) == "series_not_found", function
    row = admin.execute(
        "select description, is_default, archived_at from public.invoice_series where id = %s", (rect,)
    ).fetchone()
    assert row is not None and row["is_default"] is False and row["archived_at"] is None


def test_the_kind_of_a_series_never_changes(admin: Connection[DictRow], cast: Cast, r: Ready) -> None:
    rect = series(admin, cast.alicia, "R-2029", kind="rectifying")
    for target, kind in ((r.series, "rectifying"), (rect, "standard")):
        with pytest.raises(psycopg.errors.RaiseException, match="series_immutable_column"):
            admin.execute("update public.invoice_series set kind = %s where id = %s", (kind, target))


def test_issuing_advances_the_series_counter_which_the_guard_allows_and_never_lets_go_down(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    assert admin.execute("select next_number from public.invoice_series where id = %s", (r.series,)).fetchone() == {
        "next_number": 2
    }
    with pytest.raises(psycopg.errors.RaiseException, match="series_number_regression"):
        admin.execute("update public.invoice_series set next_number = 1 where id = %s", (r.series,))
    # y una serie con facturas ya no cambia de código ni de número inicial
    out = call(app_pool, cast.alicia, "update_invoice_series", r.series, Jsonb({"code": "NUEVO"}))
    assert code_of(out) == "series_in_use"


def test_the_series_of_an_invoice_cannot_be_deleted_or_renamed_under_it(
    admin: Connection[DictRow], cast: Cast, r: Ready, original: Any
) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="series_in_use"):
        admin.execute("update public.invoice_series set code = 'OTRO' where id = %s", (r.series,))
    with pytest.raises(psycopg.errors.Error):
        admin.execute("delete from public.invoice_series where id = %s", (r.series,))
    assert series(admin, cast.alicia, "LIBRE")
