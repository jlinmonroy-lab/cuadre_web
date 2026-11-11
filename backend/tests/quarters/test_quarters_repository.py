"""AC-13, AC-14, AC-15, AC-09 · Lectura de las facturas y los gastos de un trimestre con la base real (SPEC-W-008 hito 2, D-09, T8-05 y T8-07).

Los cinco trimestres de B.1 están sembrados con las funciones `app.*` (ver `conftest.py`). Se lee con el repositorio, con la identidad de la persona
(`user_transaction`), se pasa al dominio y se comprueba contra lo calculado a mano: el cuadre completo, de la base de datos a la casilla.
"""

import re
from datetime import date, datetime
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from cuadre.quarters.repository import EXPENSES_SQL, INVOICES_SQL, expense_rows, invoice_rows
from cuadre.tax import UnsupportedVatRate, build_modelo_303, quarter_bounds
from tests.quarters.conftest import Seeded
from tests.rls.expenses_support import insert, params
from tests.support import Cast, Person, Pool, apply_scenario, make_cast, new_document
from tests.tax.test_modelo_303_cases import CASES, EXPECTED_ITEMS

TODAY = date(2026, 6, 1)
FULL_YEAR = (date(2025, 1, 1), date(2026, 1, 1))


def read(pool: Pool, person: Person, start: date, end: date) -> tuple[list[Any], list[Any]]:
    with user_transaction(pool, person.id) as conn:
        return invoice_rows(conn, start, end), expense_rows(conn, start, end)


def model(pool: Pool, person: Person, year: int, quarter: int) -> Any:
    start, end = quarter_bounds(year, quarter)
    invoices, expenses = read(pool, person, start, end)
    return build_modelo_303(year, quarter, invoices, expenses, TODAY)


CASE_IDS = [t["caso"] for t in CASES["trimestres"]]


# --- AC-13 · de la base de datos a la casilla --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES["trimestres"], ids=CASE_IDS)
def test_what_the_database_holds_gives_the_hand_calculated_boxes_to_the_cent(
    app_pool: Pool, seeded: Seeded, case: dict
) -> None:
    result = model(app_pool, seeded.cast.alicia, case["anio"], case["trimestre"])
    assert {b.code: b.amount_cents for b in result.boxes} == case["casillas"]
    assert result.result_kind == case["resultado"]


@pytest.mark.parametrize("case", CASES["trimestres"], ids=CASE_IDS)
def test_every_box_lists_the_documents_that_the_spec_says(app_pool: Pool, seeded: Seeded, case: dict) -> None:  # NFR-08
    result = model(app_pool, seeded.cast.alicia, case["anio"], case["trimestre"])
    back = seeded.from_db
    expected = EXPECTED_ITEMS[case["caso"]]
    for b in result.boxes:
        assert [back[i.id] for i in b.items] == expected.get(b.code, []), f"{case['caso']} casilla {b.code}"


def test_the_rectifications_the_database_computed_are_the_differences_of_the_spec(
    app_pool: Pool, seeded: Seeded
) -> None:
    # Las cuotas y las diferencias de B.1 las calculó una persona; las de aquí, `app.issue_rectifying_invoice` con `cuadre.tax`.
    invoices, _ = read(app_pool, seeded.cast.alicia, date(2025, 7, 1), date(2025, 10, 1))
    got = {seeded.from_db[i.id]: (i.base_cents, i.vat_cents) for i in invoices}
    spec = {
        d["id"]: (d["base"], d["cuota"])
        for t in CASES["trimestres"]
        for d in t["documentos"]
        if d["tipo"] == "rectificativa"
    }
    assert {k: got[k] for k in spec} == spec


def test_the_label_is_the_number_that_the_person_sees(app_pool: Pool, seeded: Seeded) -> None:
    invoices, _ = read(app_pool, seeded.cast.alicia, *FULL_YEAR)
    labels = {seeded.from_db[i.id]: i.label for i in invoices}
    assert labels["A1"] == "2025-001" and labels["A2"] == "2025-002"
    assert labels["R1"] == "R-2025-001" and labels["R6"] == "R-2025-006"
    assert all(re.fullmatch(r"(R-)?2025-\d{3}", label) for label in labels.values())
    assert read(app_pool, seeded.cast.alicia, date(2026, 4, 1), date(2026, 4, 2))[0][0].label == "2026-001"  # X1


def test_the_expense_label_is_the_supplier_and_a_manual_one_arrives_without_lines(
    app_pool: Pool, seeded: Seeded
) -> None:
    _, expenses = read(app_pool, seeded.cast.alicia, date(2025, 10, 1), date(2026, 1, 1))
    by_label = {e.label: e for e in expenses}
    assert set(by_label) == {"ED1", "ED2", "ED4", "ED5", "ED6"}  # ED3 está anulado
    assert by_label["ED5"].lines == () and by_label["ED5"].deductible_vat is False
    assert [(str(x.vat_rate), x.base_cents, x.vat_cents) for x in by_label["ED4"].lines] == [
        ("0", 8_000, 0),
        ("21", 1_000, 210),
    ]
    assert by_label["ED2"].deductible_vat is False and by_label["ED1"].deductible_vat is True
    assert all(e.voided is False for e in expenses)


# --- AC-09 · las fronteras de la consulta ------------------------------------------------------------------------------------------


def ids_of(pool: Pool, seeded: Seeded, start: date, end: date) -> tuple[list[str], list[str]]:
    invoices, expenses = read(pool, seeded.cast.alicia, start, end)
    return [seeded.from_db[i.id] for i in invoices], [e.label for e in expenses]


def test_the_range_includes_the_first_day_and_excludes_the_end(app_pool: Pool, seeded: Seeded) -> None:  # AC-09
    assert ids_of(app_pool, seeded, date(2025, 3, 31), date(2025, 4, 1))[0] == ["A6"]
    assert ids_of(app_pool, seeded, date(2025, 3, 31), date(2025, 4, 2))[0] == ["A6", "B1"]
    assert ids_of(app_pool, seeded, date(2025, 4, 1), date(2025, 4, 2))[0] == ["B1"]
    assert sorted(ids_of(app_pool, seeded, date(2025, 12, 31), date(2026, 1, 1))[1]) == [
        "ED5",
        "ED6",
    ]  # los dos del 31/12 (mismo día: el orden entre ellos es el del id)
    assert (
        ids_of(app_pool, seeded, date(2025, 12, 30), date(2025, 12, 31))[1] == []
    )  # el final es exclusivo: el 31/12 queda fuera
    assert ids_of(app_pool, seeded, date(2026, 1, 1), date(2026, 4, 1)) == ([], [])  # el T1 de 2026 no tiene nada
    assert ids_of(app_pool, seeded, date(2026, 4, 1), date(2026, 4, 2))[0] == ["X1"]


def test_an_empty_or_reversed_range_reads_nothing(app_pool: Pool, seeded: Seeded) -> None:
    assert ids_of(app_pool, seeded, date(2025, 4, 1), date(2025, 4, 1)) == ([], [])
    assert ids_of(app_pool, seeded, date(2025, 7, 1), date(2025, 4, 1)) == ([], [])


# --- AC-14 · aislamiento ------------------------------------------------------------------------------------------------------------


def test_nobody_else_reads_anything_of_alicia_not_even_a_gestor_with_an_active_link(
    app_pool: Pool, seeded: Seeded
) -> None:  # AC-14, T8-05
    cast: Cast = seeded.cast
    apply_scenario(app_pool, cast, "active")  # Alicia -> Gina, aceptado
    for other in (cast.beto, cast.gina, cast.gus, cast.adan):
        assert read(app_pool, other, *FULL_YEAR) == ([], []), other.key
    assert (
        len(read(app_pool, cast.alicia, *FULL_YEAR)[0]) == 23
    )  # 17 facturas de 2025 y 6 rectificativas (X1 es de 2026)


def test_each_person_reads_only_their_own_documents(admin: Connection[DictRow], app_pool: Pool, seeded: Seeded) -> None:
    beto = seeded.cast.beto
    doc = new_document(app_pool, beto)
    insert(admin, params(beto, doc, date=date(2025, 5, 5), name="Gasto de Beto", number="B-1"))
    assert [e.label for e in read(app_pool, beto, *FULL_YEAR)[1]] == ["Gasto de Beto"]
    assert "Gasto de Beto" not in [e.label for e in read(app_pool, seeded.cast.alicia, *FULL_YEAR)[1]]


# --- Datos corruptos y límite ---------------------------------------------------------------------------------------------------------


def test_a_line_with_a_rate_that_cannot_be_read_is_an_error_not_a_hidden_zero(
    admin: Connection[DictRow], app_pool: Pool
) -> None:
    person = make_cast(admin).alicia  # una persona propia: el dato corrupto no debe estorbar a las demás pruebas
    doc = new_document(app_pool, person)
    bad = [{"vat_rate": "veintiuno", "base_cents": 10_000, "vat_cents": 2_100}]
    insert(admin, params(person, doc, date=date(2025, 5, 6), lines=bad, deductible=False, number="C-1"))
    with pytest.raises(UnsupportedVatRate) as error:
        read(app_pool, person, *FULL_YEAR)
    assert "veintiuno" not in str(error.value) and "10000" not in str(error.value)


def test_each_query_stops_after_the_limit_it_is_given(app_pool: Pool, seeded: Seeded) -> None:
    with user_transaction(app_pool, seeded.cast.alicia.id) as conn:
        assert len(invoice_rows(conn, *FULL_YEAR, limit=5)) == 5
        assert len(expense_rows(conn, *FULL_YEAR, limit=2)) == 2
        assert len(invoice_rows(conn, *FULL_YEAR)) == 23  # el límite por defecto (5.001) no recorta nada aquí


def test_the_default_limit_is_one_more_than_the_documents_a_quarter_admits() -> None:
    from cuadre.quarters.repository import DEFAULT_LIMIT
    from cuadre.tax.limits import QUARTER_MAX_DOCUMENTS

    assert DEFAULT_LIMIT == QUARTER_MAX_DOCUMENTS + 1  # así el dominio ve que se pasa del tope y falla en vez de callar


# --- T8-07 · solo lee ----------------------------------------------------------------------------------------------------------------


def counts(admin: Connection[DictRow]) -> tuple[int, int, int]:
    row = admin.execute(
        "select (select count(*) from public.invoices) as i, (select count(*) from public.expenses) as e, "
        "(select count(*) from public.activity_log) as a"
    ).fetchone()
    assert row is not None
    return int(row["i"]), int(row["e"]), int(row["a"])


def test_reading_writes_nothing(admin: Connection[DictRow], app_pool: Pool, seeded: Seeded) -> None:  # T8-07
    before = counts(admin)
    for q in (1, 2, 3, 4):
        model(app_pool, seeded.cast.alicia, 2025, q)
    assert counts(admin) == before


# --- Los índices que la consulta necesita ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "index"), [(INVOICES_SQL, "invoices_owner_date"), (EXPENSES_SQL, "expenses_by_owner_date")]
)
def test_the_queries_can_use_the_owner_and_date_indexes(app_pool: Pool, seeded: Seeded, sql: str, index: str) -> None:
    with user_transaction(app_pool, seeded.cast.alicia.id) as conn:
        conn.execute("set local enable_seqscan = off")
        plan = "\n".join(
            next(iter(r.values()))
            for r in conn.execute(
                "explain " + sql, {"start": FULL_YEAR[0], "end": FULL_YEAR[1], "limit": 10}
            ).fetchall()
        )
    assert index in plan, plan


def test_the_voided_expenses_are_never_read(admin: Connection[DictRow], app_pool: Pool, seeded: Seeded) -> None:
    alicia = seeded.cast.alicia
    _, expenses = read(app_pool, alicia, date(2025, 11, 18), date(2025, 11, 19))
    assert expenses == []  # ED3 es del 18/11 y está anulado
    row = admin.execute("select voided_at from public.expenses where id = %s", (seeded.to_db["ED3"],)).fetchone()
    assert row is not None and isinstance(row["voided_at"], datetime)  # existe en la base, pero no se lee
