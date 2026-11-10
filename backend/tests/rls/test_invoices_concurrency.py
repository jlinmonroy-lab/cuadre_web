"""AC-19 · Los cerrojos de la emisión, con hilos de verdad (SPEC-W-007 §5.2, Anexo B.1-D) y los permisos de las funciones.

El spike del hito 0 midió que SIN cerrojo 20 hilos × 5 emisiones emitían 18 de 100 (el resto caía en el UNIQUE con un error sin código útil) y que
cinco anulaciones simultáneas de una misma factura admitían dos (se devolvía dos veces). Con el cerrojo asesor por persona y los de fila, 100 de 100
sin huecos ni repetidos y exactamente una anulación. Aquí se vuelve a medir, y se comprueba que cada comprobación de fecha y de estado ocurre
DENTRO del cerrojo.
"""

import os
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.db import open_pool, user_transaction
from cuadre.tax import Standing
from tests.rls.invoices_support import (
    D1,
    D2,
    Ready,
    code_of,
    invoice,
    issue,
    made,
    next_number,
    ready,
    rectification_terms,
    rectify,
    terms,
)
from tests.support import Cast, Outcome, Person, Pool, attempt, call

THREADS, EACH = 20, 5


@pytest.fixture
def r(admin: Connection[DictRow], cast: Cast) -> Ready:
    return ready(admin, cast.alicia)


@pytest.fixture
def wide_pool() -> Any:
    """Un pool de 20 conexiones: el de las pruebas tiene 4 y no llegaría a 20 hilos de verdad."""
    pool = open_pool(os.environ["DATABASE_URL"], name="tests-invoices", max_size=THREADS)
    yield pool
    pool.close()


def run_all(jobs: list[Callable[[], Outcome]]) -> list[Outcome]:
    """Lanza todos los trabajos a la vez (con una barrera) y devuelve sus resultados."""
    barrier = threading.Barrier(len(jobs))
    results: list[Outcome | None] = [None] * len(jobs)

    def work(index: int) -> None:
        barrier.wait()
        results[index] = jobs[index]()

    threads = [threading.Thread(target=work, args=(i,)) for i in range(len(jobs))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert all(not t.is_alive() for t in threads), "algún hilo no terminó"
    return [out for out in results if out is not None]


def run_while_holding(
    pool: Pool, person: Person, hold: Callable[[Any], object], then: Callable[[], Outcome]
) -> tuple[bool, Outcome]:
    """Ejecuta `hold(conn)` sin confirmar y, desde otro hilo, `then`. Devuelve (¿esperó?, resultado del segundo)."""
    outcome: dict[str, Outcome] = {}
    waiter = threading.Thread(target=lambda: outcome.update(second=then()))
    with user_transaction(pool, person.id) as conn:
        hold(conn)  # aún sin confirmar
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()
    waiter.join(timeout=15)
    assert not waiter.is_alive(), "el segundo hilo no terminó"
    return still_waiting, outcome["second"]


# --- Muchos a la vez ----------------------------------------------------------------------------------------------------------------------


def test_twenty_threads_issue_a_hundred_invoices_with_no_gaps_and_no_repeats(
    wide_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    jobs = [lambda: issue(wide_pool, cast.alicia, cid, r.series) for _ in range(THREADS * EACH)]
    results = run_all(jobs)
    assert [o.message for o in results if o.error] == []
    numbers = sorted(
        x["number"]
        for x in admin.execute("select number from public.invoices where series_id = %s", (r.series,)).fetchall()
    )
    assert numbers == list(range(1, THREADS * EACH + 1))
    assert next_number(admin, r.series) == THREADS * EACH + 1
    assert len({o.rows[0]["issue_invoice"] for o in results}) == THREADS * EACH


def test_two_people_issue_at_the_same_time_each_with_their_own_numbering(
    wide_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    other = ready(admin, cast.beto)
    jobs: list[Callable[[], Outcome]] = []
    for _ in range(10):
        jobs.append(lambda: issue(wide_pool, cast.alicia, r.clients[("national", "business")], r.series))
        jobs.append(lambda: issue(wide_pool, cast.beto, other.clients[("national", "business")], other.series))
    assert [o.message for o in run_all(jobs) if o.error] == []
    for person, serie in ((cast.alicia, r.series), (cast.beto, other.series)):
        numbers = sorted(
            x["number"]
            for x in admin.execute("select number from public.invoices where series_id = %s", (serie,)).fetchall()
        )
        assert numbers == list(range(1, 11)), person.key


def test_five_full_cancellations_at_once_give_back_the_invoice_exactly_once(
    wide_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    original = made(issue(wide_pool, cast.alicia, r.clients[("national", "business")], r.series))
    jobs = [lambda: rectify(wide_pool, cast.alicia, original, corrected=0, when=D2) for _ in range(5)]
    results = run_all(jobs)
    assert sum(1 for o in results if not o.error) == 1, [o.message for o in results]
    assert Counter(code_of(o) for o in results if o.error) == {"invalid_invoice": 4}
    assert {o.detail for o in results if o.error} == {
        "corrected_base_cents"
    }  # los demás ven lo vigente en 0: nada que rectificar
    total = admin.execute(
        "select sum(base_cents) as b, sum(vat_cents) as v, sum(irpf_cents) as i, count(*) as n "
        "from public.invoices where id = %s or rectifies_id = %s",
        (original, original),
    ).fetchone()
    assert total == {"b": 0, "v": 0, "i": 0, "n": 2}


def test_partial_rectifications_at_once_never_give_back_more_than_the_invoice(
    wide_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    """Cada hilo pide rebajar a 60.000 desde lo que ve; solo la primera ve 100.000, las demás ven 60.000 y no hay nada que rectificar."""
    original = made(issue(wide_pool, cast.alicia, r.clients[("national", "business")], r.series))
    jobs = [lambda: rectify(wide_pool, cast.alicia, original, corrected=60_000, when=D2) for _ in range(5)]
    results = run_all(jobs)
    assert sum(1 for o in results if not o.error) == 1
    base = admin.execute(
        "select sum(base_cents) as b from public.invoices where id = %s or rectifies_id = %s", (original, original)
    ).fetchone()
    assert base == {"b": 60_000}


def test_a_rectification_and_an_issue_at_once_number_their_own_series(
    wide_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    base = [made(issue(wide_pool, cast.alicia, cid, r.series)) for _ in range(3)]
    jobs: list[Callable[[], Outcome]] = [lambda: issue(wide_pool, cast.alicia, cid, r.series) for _ in range(5)]
    jobs += [lambda o=o: rectify(wide_pool, cast.alicia, o, when=D2) for o in base]
    assert [o.message for o in run_all(jobs) if o.error] == []
    rect_numbers = sorted(
        x["number"]
        for x in admin.execute(
            "select number from public.invoices where kind = 'rectifying' and owner_id = %s", (cast.alicia.id,)
        ).fetchall()
    )
    assert rect_numbers == [1, 2, 3]
    assert next_number(admin, r.series) == 9


# --- Los cerrojos, uno a uno --------------------------------------------------------------------------------------------------------------


def hold_issue(person: Person, cid: object, sid: object, when: Any = D1) -> Callable[[Any], object]:
    return lambda conn: conn.execute(
        "select app.issue_invoice(%s, %s, %s, 'Servicios', 100000, %s)", (cid, sid, when, Jsonb(terms()))
    )


def test_the_date_is_checked_inside_the_lock(app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready) -> None:
    """Una emisión con fecha posterior espera sin confirmar; la de fecha anterior que llega después la ve al despertar y se niega."""
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        hold_issue(cast.alicia, cid, r.series, D2),
        lambda: issue(app_pool, cast.alicia, cid, r.series, when=D1),
    )
    assert waited, "la segunda emisión no esperó a la primera"
    assert (code_of(second), second.detail) == ("invoice_date_out_of_order", D2.isoformat())
    assert next_number(admin, r.series) == 2


def test_the_number_is_taken_inside_the_lock(app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready) -> None:
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        hold_issue(cast.alicia, cid, r.series),
        lambda: issue(app_pool, cast.alicia, cid, r.series),
    )
    assert waited
    assert not second.error
    assert sorted(
        x["number"]
        for x in admin.execute("select number from public.invoices where series_id = %s", (r.series,)).fetchall()
    ) == [1, 2]


def test_the_lock_is_per_person_not_global(app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready) -> None:
    other = ready(admin, cast.beto)
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        hold_issue(cast.alicia, cid, r.series),
        lambda: issue(app_pool, cast.beto, other.clients[("national", "business")], other.series),
    )
    assert not waited, "Beto esperó a Alicia"
    assert not second.error


def test_archiving_the_client_waits_for_an_issue_in_progress(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        hold_issue(cast.alicia, cid, r.series),
        lambda: call(app_pool, cast.alicia, "set_client_archived", cid, True),
    )
    assert waited, "archivar al cliente no esperó a la emisión"
    assert not second.error
    assert admin.execute("select count(*) as n from public.invoices where client_id = %s", (cid,)).fetchone() == {
        "n": 1
    }


def test_an_issue_waits_for_a_client_being_archived_and_then_refuses(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        lambda conn: conn.execute("select app.set_client_archived(%s, true)", (cid,)),
        lambda: issue(app_pool, cast.alicia, cid, r.series),
    )
    assert waited, "la emisión no esperó al archivado"
    assert (code_of(second), second.detail) == ("client_not_billable", "archived")
    assert next_number(admin, r.series) == 1


def test_editing_the_client_waits_for_an_issue_in_progress(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    """El cliente se bloquea con FOR SHARE mientras se factura: no se le quita el domicilio entre la comprobación y la copia."""
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        hold_issue(cast.alicia, cid, r.series),
        lambda: call(
            app_pool,
            cast.alicia,
            "update_client",
            cid,
            "Nombre nuevo S.L.",
            "business",
            "ES",
            "national",
            None,
            None,
            "not_applicable",
        ),
    )
    assert waited
    assert not second.error
    row = admin.execute(
        "select client_name, client_address from public.invoices where client_id = %s", (cid,)
    ).fetchone()
    assert row is not None and row["client_name"] != "Nombre nuevo S.L." and row["client_address"]


def test_the_original_is_locked_while_it_is_being_rectified(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    original = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    start = Standing(100_000, 21_000, 15_000)

    def hold(conn: Any) -> object:
        return conn.execute(
            "select app.issue_rectifying_invoice(%s, 'Primera', 0, %s, %s)",
            (original, D2, Jsonb(rectification_terms(start, 0))),
        )

    waited, second = run_while_holding(
        app_pool, cast.alicia, hold, lambda: rectify(app_pool, cast.alicia, original, corrected=50_000, when=D2)
    )
    assert waited
    assert (code_of(second), second.detail) == ("rectification_exceeds", None)


def test_paying_waits_for_a_rectification_of_the_same_invoice(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    original = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    start = Standing(100_000, 21_000, 15_000)

    def hold(conn: Any) -> object:
        return conn.execute(
            "select app.issue_rectifying_invoice(%s, 'Primera', 0, %s, %s)",
            (original, D2, Jsonb(rectification_terms(start, 0))),
        )

    waited, second = run_while_holding(
        app_pool, cast.alicia, hold, lambda: call(app_pool, cast.alicia, "set_invoice_paid", original, True)
    )
    assert waited
    assert not second.error  # cobrar una factura anulada es posible: la original sigue siendo una factura emitida
    assert invoice(admin, original)["paid_at"] is not None


def test_two_pdf_records_at_once_give_exists_to_the_second(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    original = made(issue(app_pool, cast.alicia, r.clients[("national", "business")], r.series))
    sha = "ab" * 32
    path = f"{cast.alicia.id}/{original}-{sha[:16]}.pdf"
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        lambda conn: conn.execute("select app.attach_invoice_pdf(%s, %s, %s, 10)", (original, path, sha)),
        lambda: call(app_pool, cast.alicia, "attach_invoice_pdf", original, path, sha, 10),
    )
    assert waited
    assert code_of(second) == "invoice_pdf_exists"


def test_the_series_functions_wait_for_an_issue_in_progress(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, r: Ready
) -> None:
    """Renombrar o archivar la serie no puede colarse entre el número y la inserción."""
    cid = r.clients[("national", "business")]
    waited, second = run_while_holding(
        app_pool,
        cast.alicia,
        hold_issue(cast.alicia, cid, r.series),
        lambda: call(app_pool, cast.alicia, "update_invoice_series", r.series, Jsonb({"code": "NUEVO"})),
    )
    assert waited
    assert code_of(second) == "series_in_use"  # esperó, vio la factura emitida y se negó


# --- Permisos de las funciones --------------------------------------------------------------------------------------------------------------

APP_FUNCTIONS = {
    "issue_invoice",
    "issue_rectifying_invoice",
    "set_invoice_paid",
    "attach_invoice_pdf",
    "ensure_rectifying_series",
}
PRIVATE_FUNCTIONS = {
    "invoice_expected_treatment",
    "invoice_terms_problem",
    "series_last_issue_date",
    "invoice_date_problem",
    "invoice_insert",
    "series_lock_for_issue",
    "invoices_immutable",
    "invoice_files_append_only",
    "invoice_file_folder_owner",
    "invoice_file_can_upload",
    "invoice_file_can_read",
}


def test_the_functions_are_security_definer_with_an_empty_search_path_and_only_the_app_ones_reach_authenticated(
    admin: Connection[DictRow],
) -> None:
    found = admin.execute(
        "select n.nspname, p.proname, p.prosecdef, p.proconfig, has_function_privilege('authenticated', p.oid, 'EXECUTE') as auth, "
        "has_function_privilege('anon', p.oid, 'EXECUTE') as anon from pg_proc p join pg_namespace n on n.oid = p.pronamespace "
        "where n.nspname in ('app', 'private') and p.proname = any(%s) order by 1, 2",
        (sorted(APP_FUNCTIONS | PRIVATE_FUNCTIONS),),
    ).fetchall()
    assert {(r["nspname"], r["proname"]) for r in found} == {("app", n) for n in APP_FUNCTIONS} | {
        ("private", n) for n in PRIVATE_FUNCTIONS
    }
    for r in found:
        assert r["anon"] is False, r["proname"]
        assert r["auth"] is (
            r["nspname"] == "app" or r["proname"] in {"invoice_file_can_upload", "invoice_file_can_read"}
        ), r["proname"]
        assert r["proconfig"] and any(
            c.replace(" ", "") in ('search_path=""', "search_path=") for c in r["proconfig"]
        ), r["proname"]
        if r["nspname"] == "app":
            assert r["prosecdef"] is True, r["proname"]


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_calls_the_private_helpers(app_pool: Pool, cast: Cast, who: str) -> None:
    for name, args in (
        ("invoice_insert", "null, null"),
        ("series_last_issue_date", f"'{uuid.uuid4()}', '{uuid.uuid4()}'"),
        ("series_lock_for_issue", f"'{uuid.uuid4()}', 'standard'"),
    ):
        out = attempt(app_pool, cast[who], f"select private.{name}({args})")
        assert out.sqlstate == "42501", (name, out.sqlstate)
