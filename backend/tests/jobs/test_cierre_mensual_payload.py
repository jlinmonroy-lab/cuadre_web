"""AC-20 y deriva con la base de datos · Lo que calcula `cuadre.closing` lo acepta `private.close_month` (SPEC-W-012 §5.2 y §5.4).

El cálculo puro y la función SQL validan la misma forma por separado; esta prueba los junta para que no se separen sin que nadie lo note.
"""

import random
from datetime import date

import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.closing import MonthExpense, MonthInvoice, YearMonth, build_months, payload_of
from cuadre.db import service_transaction
from tests.jobs.test_cierre_mensual_properties import YEAR, random_docs
from tests.support import Cast, Person, Pool


def close(pool: Pool, owner: Person, month: YearMonth, body: dict) -> str:  # type: ignore[type-arg]
    with service_transaction(pool) as conn:
        row = conn.execute(
            "select private.close_month(%s, %s, %s, %s) as result", (owner.id, month.year, month.month, Jsonb(body))
        ).fetchone()
    assert row is not None
    return row["result"]


def test_a_calculated_month_is_accepted_and_repeating_it_changes_nothing(service_pool: Pool, cast: Cast) -> None:
    invoices = [
        MonthInvoice(
            "i1",
            date(2026, 9, 3),
            "standard",
            150_000,
            "11111111-1111-4111-8111-111111111111",
            "Estudio Norte S.L.",
            "national",
        ),
        MonthInvoice(
            "i2", date(2026, 9, 9), "standard", 50_000, "22222222-2222-4222-8222-222222222222", "Kreativ GmbH", "eu"
        ),
        MonthInvoice(
            "i3",
            date(2026, 9, 12),
            "rectifying",
            -10_000,
            "11111111-1111-4111-8111-111111111111",
            "Estudio Norte S.L.",
            "national",
        ),
    ]
    expenses = [MonthExpense("e1", date(2026, 9, 4), 10_000, 2_100, False, False)]
    (month,) = build_months(invoices, expenses, [YearMonth(2026, 9)])
    body = payload_of(month)
    assert close(service_pool, cast.alicia, YearMonth(2026, 9), body) == "closed"
    assert (
        close(service_pool, cast.alicia, YearMonth(2026, 9), payload_of(month)) == "unchanged"
    )  # mismo orden, misma foto


def test_an_empty_month_is_accepted(service_pool: Pool, cast: Cast) -> None:
    (month,) = build_months([], [], [YearMonth(2026, 9)])
    assert close(service_pool, cast.alicia, YearMonth(2026, 9), payload_of(month)) == "closed"


@pytest.mark.parametrize("seed", range(40))
def test_any_random_month_is_accepted_by_the_database_function(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast, seed: int
) -> None:
    rng = random.Random(7000 + seed)
    invoices, expenses = random_docs(rng, count=40)
    months = [YearMonth(YEAR, m) for m in range(1, 13)]
    for month in build_months(invoices, expenses, months):
        body = payload_of(month)
        ym = YearMonth(month.year, month.month)
        assert close(service_pool, cast.alicia, ym, body) == "closed"
        assert close(service_pool, cast.alicia, ym, payload_of(month)) == "unchanged"
    row = admin.execute(
        "select count(*) as n from public.monthly_closings where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert row == {"n": 12}


def test_a_late_document_reopens_the_month_through_the_whole_chain(service_pool: Pool, cast: Cast) -> None:
    base = [
        MonthInvoice(
            "i1",
            date(2026, 9, 3),
            "standard",
            100_000,
            "11111111-1111-4111-8111-111111111111",
            "Estudio Norte S.L.",
            "national",
        )
    ]
    sep = YearMonth(2026, 9)
    assert close(service_pool, cast.alicia, sep, payload_of(build_months(base, [], [sep])[0])) == "closed"
    late = [
        *base,
        MonthInvoice(
            "i2", date(2026, 9, 1), "standard", 5_000, "22222222-2222-4222-8222-222222222222", "Kreativ GmbH", "eu"
        ),
    ]
    assert close(service_pool, cast.alicia, sep, payload_of(build_months(late, [], [sep])[0])) == "reopened"
