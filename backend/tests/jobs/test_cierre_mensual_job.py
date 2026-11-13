"""AC-01 a AC-14 · El job del cierre mensual con la base de datos real (SPEC-W-012 §5.4, D-04, D-05).

Las cuentas sembradas y las de otras pruebas también existen en la base: cada prueba limita el job a las suyas con `only_owners`. Los datos son sintéticos y
reconocibles; las facturas se emiten por la función de la base (la misma que la API) y los gastos se insertan como dueño de la base de datos.
"""

import threading
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.closing import ClosingTooLarge, InvalidMonth, YearMonth
from cuadre.core.auth import CurrentUser
from cuadre.jobs.closing_job import ClosingResult, run_monthly_closing
from cuadre.quarters.service import QuarterService
from cuadre.tax.periods import PeriodInFuture
from tests.agents.support import captured_logs
from tests.clocks import FixedClock
from tests.jobs.closing_support import SHIFTS, apply_shift, day_of, now_to_close, signup_month
from tests.quarters.conftest import standing_of
from tests.rls.expenses_support import insert, params
from tests.rls.invoices_support import Ready, issue, made, ready, rectify, series
from tests.support import Cast, Person, Pool, new_document


def at(year: int, month: int, day: int = 1, hour: int = 8) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=UTC)


OCT_1 = at(2026, 10, 1)  # 10:00 en Madrid: ya es 1 de octubre


def run(
    service_pool: Pool,
    app_pool: Pool,
    now: datetime,
    owners: list[Person] | None,
    month: YearMonth | None = None,
) -> ClosingResult:
    return run_monthly_closing(
        service_pool=service_pool,
        app_pool=app_pool,
        now=now,
        only_owners=[p.id for p in owners] if owners is not None else None,
        month=month,
    )


def rows_of(admin: Connection[DictRow], person: Person) -> dict[tuple[int, int], dict[str, Any]]:
    found = admin.execute(
        "select * from public.monthly_closings where owner_id = %s order by year, month", (person.id,)
    ).fetchall()
    return {(r["year"], r["month"]): r for r in found}


def row(admin: Connection[DictRow], person: Person, year: int, month: int) -> dict[str, Any]:
    found = rows_of(admin, person).get((year, month))
    assert found is not None, f"no hay cierre de {year}-{month:02d}"
    return found


def bill(
    app_pool: Pool,
    admin: Connection[DictRow],
    person: Person,
    r: Ready,
    scope: str,
    when: date,
    base: int,
    *,
    series_id: Any = None,
) -> Any:
    kind = "business"
    out = issue(
        app_pool,
        person,
        r.clients[(scope, kind)],
        series_id or r.series,
        when=when,
        base=base,
        scope=scope,
        kind=kind,
        vat="21" if scope == "national" else None,
    )
    return made(out)


def spend(admin: Connection[DictRow], app_pool: Pool, person: Person, when: date, **over: Any) -> Any:
    over.setdefault(
        "number", f"A-{uuid.uuid4().hex[:10]}"
    )  # el índice impide dos gastos con el mismo proveedor y número
    return insert(admin, params(person, new_document(app_pool, person), date=when, **over))


def figures(admin: Connection[DictRow], app_pool: Pool, person: Person) -> Ready:
    """Septiembre de 2026 con un cliente de cada ámbito y dos gastos."""
    r = ready(admin, person)
    bill(app_pool, admin, person, r, "national", date(2026, 9, 3), 150_000)
    bill(app_pool, admin, person, r, "eu", date(2026, 9, 10), 50_000)
    bill(app_pool, admin, person, r, "non_eu", date(2026, 9, 20), 20_000)
    bill(app_pool, admin, person, r, "national", date(2026, 9, 25), 30_000)
    spend(admin, app_pool, person, date(2026, 9, 5))  # 100 € de base + 21 € de IVA, deducible
    spend(admin, app_pool, person, date(2026, 9, 6), deductible=False)  # el IVA no deducible suma al coste
    return r


# --- AC-01 a AC-04 · Cerrar, a cero, repetir y a la vez ------------------------------------------------------------------------------------


def test_the_first_of_october_closes_september_by_scope_and_client(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    figures(admin, app_pool, cast.alicia)
    result = run(service_pool, app_pool, OCT_1, [cast.alicia])
    assert result == ClosingResult(closed=1, reopened=0, unchanged=0, failed=0)
    sep = row(admin, cast.alicia, 2026, 9)
    assert (sep["invoice_count"], sep["national_cents"], sep["eu_cents"], sep["non_eu_cents"]) == (
        4,
        180_000,
        50_000,
        20_000,
    )
    assert (sep["total_cents"], sep["revision"]) == (250_000, 1)
    assert (
        sep["expenses_cents"] == 10_000 + 10_000 + 2_100
    )  # la base de los dos gastos y el IVA del que no es deducible
    by_client = sep["by_client"]
    assert [(c["scope"], c["base_cents"], c["invoice_count"]) for c in by_client] == [
        ("national", 180_000, 2),
        ("eu", 50_000, 1),
        ("non_eu", 20_000, 1),
    ]
    assert all(set(c) == {"client_id", "name", "scope", "base_cents", "invoice_count"} for c in by_client)


def test_a_month_without_activity_between_two_with_activity_closes_at_zero(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 8, 12), 10_000)
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 10, 12), 20_000)
    run(service_pool, app_pool, at(2026, 11, 1), [cast.alicia])
    sep = row(admin, cast.alicia, 2026, 9)
    assert (sep["invoice_count"], sep["total_cents"], sep["expenses_cents"], sep["by_client"]) == (0, 0, 0, [])
    assert [m for _, m in rows_of(admin, cast.alicia)] == [8, 9, 10]


def test_repeating_the_job_changes_nothing(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    figures(admin, app_pool, cast.alicia)
    run(service_pool, app_pool, OCT_1, [cast.alicia])
    before = rows_of(admin, cast.alicia)
    for now in (OCT_1, at(2026, 10, 1, 18), at(2026, 10, 2)):
        result = run(service_pool, app_pool, now, [cast.alicia])
        assert result == ClosingResult(closed=0, reopened=0, unchanged=1, failed=0)
    assert rows_of(admin, cast.alicia) == before  # ni `revision`, ni `closed_at`, ni `first_closed_at`


def test_two_simultaneous_runs_leave_one_row_per_month(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    figures(admin, app_pool, cast.alicia)
    results: list[ClosingResult] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait()
        results.append(run(service_pool, app_pool, at(2026, 11, 1), [cast.alicia]))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    months = rows_of(admin, cast.alicia)
    assert sorted(m for _, m in months) == [9, 10]
    assert all(r["revision"] == 1 for r in months.values())
    assert (
        sum(r.closed for r in results) == 2
        and sum(r.unchanged for r in results) == 2
        and sum(r.failed for r in results) == 0
    )


# --- AC-05 a AC-07 · Reapertura -----------------------------------------------------------------------------------------------------------


def test_a_late_expense_reopens_the_month(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    figures(admin, app_pool, cast.alicia)
    run(service_pool, app_pool, OCT_1, [cast.alicia])
    first = row(admin, cast.alicia, 2026, 9)
    spend(admin, app_pool, cast.alicia, date(2026, 9, 28))  # llega tarde: gasto con fecha de septiembre
    result = run(service_pool, app_pool, at(2026, 10, 2), [cast.alicia])
    assert result == ClosingResult(closed=0, reopened=1, unchanged=0, failed=0)
    second = row(admin, cast.alicia, 2026, 9)
    assert (second["revision"], second["expenses_cents"]) == (2, first["expenses_cents"] + 10_000)
    assert second["first_closed_at"] == first["first_closed_at"] and second["closed_at"] > first["closed_at"]


def test_a_late_invoice_in_another_series_reopens_the_month(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = figures(admin, app_pool, cast.alicia)
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 10, 5), 1_000)
    run(service_pool, app_pool, at(2026, 11, 1), [cast.alicia])
    other = series(admin, cast.alicia, "TARDE")
    bill(app_pool, admin, cast.alicia, r, "eu", date(2026, 9, 14), 7_000, series_id=other)
    result = run(service_pool, app_pool, at(2026, 11, 2), [cast.alicia])
    assert (result.reopened, result.unchanged, result.closed) == (1, 1, 0)  # septiembre se reabre; octubre no cambia
    sep = row(admin, cast.alicia, 2026, 9)
    assert (sep["revision"], sep["eu_cents"], sep["invoice_count"]) == (2, 57_000, 5)
    assert row(admin, cast.alicia, 2026, 10)["revision"] == 1


def test_voiding_an_expense_after_the_close_reopens_the_month(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 9, 3), 10_000)
    expense = spend(admin, app_pool, cast.alicia, date(2026, 9, 5))
    run(service_pool, app_pool, OCT_1, [cast.alicia])
    assert row(admin, cast.alicia, 2026, 9)["expenses_cents"] == 10_000
    admin.execute("update public.expenses set voided_at = now() where id = %s", (expense,))
    assert run(service_pool, app_pool, at(2026, 10, 2), [cast.alicia]).reopened == 1
    sep = row(admin, cast.alicia, 2026, 9)
    assert (sep["expenses_cents"], sep["revision"]) == (0, 2)


def test_a_rectification_counts_in_its_own_month_and_leaves_the_original_month_alone(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    original = bill(app_pool, admin, cast.alicia, r, "national", date(2026, 8, 20), 100_000)
    out = rectify(
        app_pool,
        cast.alicia,
        original,
        corrected=60_000,
        when=date(2026, 9, 5),
        standing=standing_of(admin, original),
        vat="21",
        irpf="15",
    )
    made(out)
    run(service_pool, app_pool, OCT_1, [cast.alicia])
    august, september = row(admin, cast.alicia, 2026, 8), row(admin, cast.alicia, 2026, 9)
    assert (august["total_cents"], august["invoice_count"]) == (100_000, 1)
    assert (september["total_cents"], september["national_cents"], september["invoice_count"]) == (-40_000, -40_000, 0)
    assert [(c["base_cents"], c["invoice_count"]) for c in september["by_client"]] == [(-40_000, 0)]


# --- AC-08 y AC-09 · Primer mes y ventana -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("shift", SHIFTS)
def test_a_new_account_without_documents_only_closes_from_its_sign_up_month(
    service_pool: Pool, app_pool: Pool, admin: Connection[DictRow], cast: Cast, shift: datetime | None
) -> None:
    signup = apply_shift(admin, cast.alicia, shift)  # el mes de alta es el que sea: la prueba no depende del reloj real
    run(service_pool, app_pool, now_to_close(signup), [cast.alicia])
    assert list(rows_of(admin, cast.alicia)) == [(signup.year, signup.month)]
    assert row(admin, cast.alicia, signup.year, signup.month)["total_cents"] == 0


def test_an_account_with_an_old_invoice_closes_from_that_month(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 3, 9), 5_000)
    run(service_pool, app_pool, at(2026, 11, 13), [cast.alicia])
    assert [m for _, m in rows_of(admin, cast.alicia)] == list(
        range(3, 11)
    )  # de marzo a octubre; nada de enero ni febrero


def test_only_the_last_twelve_months_are_recalculated_unless_one_is_asked_for(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    old = series(admin, cast.alicia, "2024")
    bill(app_pool, admin, cast.alicia, r, "national", date(2024, 1, 15), 9_000, series_id=old)
    run(service_pool, app_pool, at(2026, 11, 13), [cast.alicia])
    months = rows_of(admin, cast.alicia)
    assert len(months) == 12 and min(months) == (2025, 11) and max(months) == (2026, 10)
    assert (2024, 1) not in months

    result = run(service_pool, app_pool, at(2026, 11, 13), [cast.alicia], month=YearMonth(2024, 1))
    assert result == ClosingResult(closed=1, reopened=0, unchanged=0, failed=0)
    assert row(admin, cast.alicia, 2024, 1)["total_cents"] == 9_000
    assert len(rows_of(admin, cast.alicia)) == 13


def test_an_explicit_month_before_the_first_month_does_nothing(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    result = run(service_pool, app_pool, at(2026, 12, 1), [cast.alicia], month=YearMonth(2020, 1))
    assert result == ClosingResult()
    assert rows_of(admin, cast.alicia) == {}


@pytest.mark.parametrize(
    ("month", "error"),
    [
        (YearMonth(2026, 12), PeriodInFuture),
        (YearMonth(2027, 1), PeriodInFuture),
        (YearMonth(2026, 13), InvalidMonth),
        (YearMonth(1999, 1), InvalidMonth),
    ],
)
def test_a_month_that_does_not_exist_or_has_not_ended_fails_before_touching_anyone(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, month: YearMonth, error: type[Exception]
) -> None:
    figures(admin, app_pool, cast.alicia)
    with pytest.raises(error):
        run(service_pool, app_pool, at(2026, 12, 5), [cast.alicia], month=month)
    assert rows_of(admin, cast.alicia) == {}


# --- AC-10 · El día de Madrid y el cambio de año ------------------------------------------------------------------------------------------


def test_the_close_follows_the_day_in_madrid_at_the_turn_of_the_year(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    bill(app_pool, admin, cast.alicia, r, "national", date(2026, 10, 15), 1_000)
    spend(
        admin, app_pool, cast.alicia, date(2026, 12, 15)
    )  # insertado como dueño de la base: la fecha aún no ha llegado
    run(service_pool, app_pool, datetime(2026, 12, 31, 22, 30, tzinfo=UTC), [cast.alicia])  # 23:30 del 31 en Madrid
    assert max(rows_of(admin, cast.alicia)) == (2026, 11)
    result = run(
        service_pool, app_pool, datetime(2026, 12, 31, 23, 30, tzinfo=UTC), [cast.alicia]
    )  # 00:30 del 1 de enero
    assert result.closed == 1 and max(rows_of(admin, cast.alicia)) == (2026, 12)
    assert row(admin, cast.alicia, 2026, 12)["expenses_cents"] > 0


# --- AC-11 · Cuadra con el 130 ------------------------------------------------------------------------------------------------------------


def test_the_closed_months_add_up_to_the_modelo_130(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    for day, scope, base in (
        (date(2026, 1, 20), "national", 100_000),
        (date(2026, 2, 11), "eu", 40_000),
        (date(2026, 4, 2), "national", 70_000),
        (date(2026, 5, 30), "non_eu", 9_000),
        (date(2026, 7, 7), "national", 55_000),
        (date(2026, 9, 29), "national", 12_345),
    ):
        bill(app_pool, admin, cast.alicia, r, scope, day, base)
    for day in (date(2026, 1, 25), date(2026, 5, 3), date(2026, 8, 18)):
        spend(admin, app_pool, cast.alicia, day, deductible=day.month != 5)
    run(service_pool, app_pool, OCT_1, [cast.alicia])
    months = rows_of(admin, cast.alicia)

    user = CurrentUser(cast.alicia.id, cast.alicia.email, "", "usuario", "active", {})
    quarters = QuarterService(app_pool, FixedClock(OCT_1))
    for quarter in (1, 2, 3):
        boxes = {b.code: b.amount_cents for b in quarters.modelo_130(user, 2026, quarter).boxes}
        upto = [months[(2026, m)] for m in range(1, 3 * quarter + 1)]
        assert sum(m["total_cents"] for m in upto) == boxes["01"]
        assert sum(m["expenses_cents"] for m in upto) == boxes["02"]


# --- AC-12 a AC-14 · Quién, los fallos y el aislamiento -----------------------------------------------------------------------------------


@pytest.mark.parametrize("shift", SHIFTS)
def test_only_active_users_are_closed(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, shift: datetime | None
) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.beto.id,))
    signup = apply_shift(admin, cast.alicia, shift)
    everyone = [cast.alicia, cast.beto, cast.gina, cast.gus, cast.adan]
    run(service_pool, app_pool, now_to_close(max(signup, signup_month(admin, cast.beto))), everyone)
    assert rows_of(admin, cast.alicia)
    for person in (cast.beto, cast.gina, cast.gus, cast.adan):
        assert rows_of(admin, person) == {}


def test_a_failure_with_one_person_does_not_stop_the_others_and_the_logs_carry_no_data(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = ready(admin, cast.alicia)
    # Las facturas llevan el día 1 del mes de alta (la fecha no puede ser futura) y el reloj es el día 1 del mes siguiente: dentro de la ventana de cualquier fecha real.
    last = max(signup_month(admin, cast.alicia), signup_month(admin, cast.beto))
    first_day = day_of(signup_month(admin, cast.alicia), 1)
    bill(app_pool, admin, cast.alicia, r, "national", first_day, 150_000)
    bill(app_pool, admin, cast.alicia, r, "national", first_day, 99_999)
    monkeypatch.setattr("cuadre.closing.rules.CLOSING_MAX_DOCUMENTS", 1)  # Alicia tiene 2 documentos; Beto, ninguno
    with captured_logs("cuadre.jobs.closing") as logs:
        result = run(service_pool, app_pool, now_to_close(last), [cast.alicia, cast.beto])
    assert result.failed == 1 and result.closed == 1
    assert rows_of(admin, cast.alicia) == {} and rows_of(admin, cast.beto)
    text = " ".join(str(r.__dict__) + r.getMessage() for r in logs)
    assert cast.alicia.email not in text and "Cliente" not in text and "150000" not in text and "99999" not in text
    failed = [r for r in logs if r.getMessage() == "closing_failed"]
    assert len(failed) == 1 and failed[0].error == ClosingTooLarge.__name__ and failed[0].user_id == str(cast.alicia.id)


def test_each_person_only_gets_their_own_clients(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    ra, rb = ready(admin, cast.alicia), ready(admin, cast.beto)
    bill(app_pool, admin, cast.alicia, ra, "national", date(2026, 9, 3), 1_000)
    bill(app_pool, admin, cast.beto, rb, "eu", date(2026, 9, 4), 2_000)
    run(service_pool, app_pool, OCT_1, [cast.alicia, cast.beto])
    alicia, beto = row(admin, cast.alicia, 2026, 9), row(admin, cast.beto, 2026, 9)
    assert {c["client_id"] for c in alicia["by_client"]} == {str(ra.clients[("national", "business")])}
    assert {c["client_id"] for c in beto["by_client"]} == {str(rb.clients[("eu", "business")])}
    assert (alicia["total_cents"], beto["total_cents"]) == (1_000, 2_000)


def test_the_logs_of_a_normal_run_carry_only_ids_periods_and_counters(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    figures(admin, app_pool, cast.alicia)
    run(service_pool, app_pool, OCT_1, [cast.alicia])
    spend(admin, app_pool, cast.alicia, date(2026, 9, 28))
    with captured_logs("cuadre.jobs.closing") as logs:
        run(service_pool, app_pool, at(2026, 10, 2), [cast.alicia])
    text = " ".join(str(r.__dict__) + r.getMessage() for r in logs)
    assert cast.alicia.email not in text and "Cliente" not in text and "€" not in text
    reopened = [r for r in logs if r.getMessage() == "closing_reopened"]
    assert [(r.user_id, r.period) for r in reopened] == [(str(cast.alicia.id), "2026-09")]
