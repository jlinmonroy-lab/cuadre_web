"""AC-15, AC-12, AC-16, AC-17 · Lectura de las facturas y los gastos del año con la base real (SPEC-W-009 hito 2, D-12, T9-05 y T9-07).

Los 23 documentos de B.1 están sembrados con las funciones `app.*` (ver `conftest.py`). Se lee con el repositorio, con la identidad de la persona
(`user_transaction`), se pasa al dominio del 130 y se comprueba contra lo calculado a mano: el cuadre completo, de la base de datos a la casilla.
"""

import re
from datetime import date, datetime

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import user_transaction
from cuadre.quarters.repository import COST_SQL, INCOME_SQL, YEAR_DEFAULT_LIMIT, cost_rows, income_rows
from cuadre.tax import CostRow, IncomeRow, Modelo130, build_modelo_130, quarter_bounds, year_start
from cuadre.tax.limits import YEAR_MAX_DOCUMENTS
from tests.quarters.conftest import Seeded
from tests.rls.expenses_support import insert, params
from tests.support import Cast, Person, Pool, apply_scenario, make_cast, new_document
from tests.tax.test_modelo_130_cases import CASES, EVERY_CASE

TODAY = date(2026, 6, 1)
FULL_2025 = (date(2025, 1, 1), date(2026, 1, 1))
DOCUMENTS = {d["id"]: d for d in CASES["documentos"]}
CASE_IDS = [c["caso"] for c in EVERY_CASE]
INCOMES_2025 = [d for d in DOCUMENTS.values() if d["tipo"] in ("factura", "rectificativa") and d["fecha"] < "2026"]
COSTS_2025 = [d for d in DOCUMENTS.values() if d["tipo"] == "gasto" and not d["anulado"]]


def read(pool: Pool, person: Person, start: date, end: date) -> tuple[list[IncomeRow], list[CostRow]]:
    with user_transaction(pool, person.id) as conn:
        return income_rows(conn, start, end), cost_rows(conn, start, end)


def model(pool: Pool, person: Person, year: int, quarter: int) -> Modelo130:
    _, end = quarter_bounds(year, quarter)
    incomes, costs = read(pool, person, year_start(year), end)
    return build_modelo_130(year, quarter, incomes, costs, TODAY)


# --- AC-15 · de la base de datos a la casilla --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", EVERY_CASE, ids=CASE_IDS)
def test_what_the_database_holds_gives_the_hand_calculated_boxes_to_the_cent(
    app_pool: Pool, seeded_130: Seeded, case: dict
) -> None:
    result = model(app_pool, seeded_130.cast.alicia, case["anio"], case["trimestre"])
    assert {b.code: b.amount_cents for b in result.boxes} == case["casillas"]
    assert result.result_kind == case["resultado"]
    assert result.withheld_share_percent == case["porcentaje_retencion"]


@pytest.mark.parametrize("case", EVERY_CASE, ids=CASE_IDS)
def test_every_box_lists_the_documents_that_the_spec_says(
    app_pool: Pool, seeded_130: Seeded, case: dict
) -> None:  # NFR-08
    result = model(app_pool, seeded_130.cast.alicia, case["anio"], case["trimestre"])
    back = seeded_130.from_db
    for b in result.boxes:
        got = [i.id if i.kind == "quarter" else back[i.id] for i in b.items]
        assert got == case["documentos"].get(b.code, []), f"{case['caso']} casilla {b.code}"
        assert sum(i.amount_cents for i in b.items) == b.amount_cents or not b.items


def test_the_amounts_the_database_computed_are_the_ones_of_the_spec(app_pool: Pool, seeded_130: Seeded) -> None:
    # La retención y la diferencia de la rectificativa de B.1 las calculó una persona; las de aquí, `app.*` con `cuadre.tax`.
    incomes, _ = read(app_pool, seeded_130.cast.alicia, *FULL_2025)
    got = {seeded_130.from_db[i.id]: (i.base_cents, i.irpf_cents) for i in incomes}
    spec = {
        k: (d["base"], d["retencion"])
        for k, d in DOCUMENTS.items()
        if d["tipo"] in ("factura", "rectificativa") and k != "X1"
    }
    assert got == spec


def test_the_label_is_the_number_that_the_person_sees(app_pool: Pool, seeded_130: Seeded) -> None:
    incomes, costs = read(app_pool, seeded_130.cast.alicia, *FULL_2025)
    labels = {seeded_130.from_db[i.id]: i.label for i in incomes}
    assert labels["A1"] == "2025-001" and labels["B3"] == "R-2025-001"
    assert all(re.fullmatch(r"(R-)?2025-\d{3}", label) for label in labels.values())
    assert {c.label for c in costs} == {k for k, d in DOCUMENTS.items() if d["tipo"] == "gasto" and not d["anulado"]}


def test_a_cost_arrives_with_its_base_its_vat_and_whether_the_vat_is_deducted(
    app_pool: Pool, seeded_130: Seeded
) -> None:
    _, costs = read(app_pool, seeded_130.cast.alicia, *FULL_2025)
    got = {c.label: (c.base_cents, c.vat_cents, c.deductible_vat) for c in costs}
    spec = {k: (d["base"], d["iva"], d["iva_deducible"]) for k, d in DOCUMENTS.items() if d["tipo"] == "gasto"}
    assert got == {k: v for k, v in spec.items() if not DOCUMENTS[k]["anulado"]}
    assert got["G3"] == (12_000, 0, False)  # un gasto sin factura: su importe, sin IVA y sin deducirlo
    assert all(c.voided is False for c in costs)


def test_the_rows_arrive_by_date_then_id(app_pool: Pool, seeded_130: Seeded) -> None:
    incomes, costs = read(app_pool, seeded_130.cast.alicia, *FULL_2025)
    assert [(i.issue_date, i.id) for i in incomes] == sorted((i.issue_date, i.id) for i in incomes)
    assert [(c.expense_date, c.id) for c in costs] == sorted((c.expense_date, c.id) for c in costs)


def test_the_voided_expenses_are_never_read(admin: Connection[DictRow], app_pool: Pool, seeded_130: Seeded) -> None:
    _, costs = read(app_pool, seeded_130.cast.alicia, date(2025, 3, 12), date(2025, 3, 13))
    assert costs == []  # G4 es del 12/03 y está anulado
    row = admin.execute("select voided_at from public.expenses where id = %s", (seeded_130.to_db["G4"],)).fetchone()
    assert row is not None and isinstance(row["voided_at"], datetime)  # existe en la base, pero no se lee


# --- AC-12 · las fronteras de la consulta ------------------------------------------------------------------------------------------


def ids_of(pool: Pool, seeded: Seeded, start: date, end: date) -> tuple[list[str], list[str]]:
    incomes, costs = read(pool, seeded.cast.alicia, start, end)
    return [seeded.from_db[i.id] for i in incomes], [c.label for c in costs]


def test_the_range_includes_the_first_day_and_excludes_the_end(app_pool: Pool, seeded_130: Seeded) -> None:  # AC-12
    assert ids_of(app_pool, seeded_130, date(2025, 3, 28), date(2025, 3, 29))[0] == ["A4"]
    assert ids_of(app_pool, seeded_130, date(2025, 3, 28), date(2025, 4, 10))[0] == [
        "A4"
    ]  # B1 es del 10/04: final exclusivo
    assert ids_of(app_pool, seeded_130, date(2025, 3, 28), date(2025, 4, 11))[0] == ["A4", "B1"]
    assert ids_of(app_pool, seeded_130, date(2025, 12, 31), date(2026, 1, 1)) == (["D2"], ["G12"])
    assert ids_of(app_pool, seeded_130, date(2025, 12, 30), date(2025, 12, 31)) == ([], [])
    assert ids_of(app_pool, seeded_130, date(2026, 1, 1), date(2026, 4, 1)) == ([], [])  # el T1 de 2026 no tiene nada
    assert ids_of(app_pool, seeded_130, date(2026, 1, 1), date(2026, 4, 2)) == (["X1"], [])


def test_an_empty_or_reversed_range_reads_nothing(app_pool: Pool, seeded_130: Seeded) -> None:
    assert ids_of(app_pool, seeded_130, date(2025, 4, 10), date(2025, 4, 10)) == ([], [])
    assert ids_of(app_pool, seeded_130, date(2025, 7, 1), date(2025, 4, 1)) == ([], [])


# --- AC-16 · aislamiento ------------------------------------------------------------------------------------------------------------


def test_nobody_else_reads_anything_of_alicia_not_even_a_gestor_with_an_active_link(
    app_pool: Pool, seeded_130: Seeded
) -> None:  # AC-16, T9-05
    cast: Cast = seeded_130.cast
    apply_scenario(app_pool, cast, "active")  # Alicia -> Gina, aceptado
    for other in (cast.beto, cast.gina, cast.gus, cast.adan):
        assert read(app_pool, other, *FULL_2025) == ([], []), other.key
    incomes, costs = read(app_pool, cast.alicia, *FULL_2025)
    assert len(incomes) == len(INCOMES_2025) == 10  # 9 facturas de 2025 y la rectificativa B3 (X1 es de 2026)
    assert len(costs) == len(COSTS_2025) == 10  # los 12 gastos de B.1 menos los 2 anulados


def test_each_person_reads_only_their_own_documents(
    admin: Connection[DictRow], app_pool: Pool, seeded_130: Seeded
) -> None:
    beto = seeded_130.cast.beto
    doc = new_document(app_pool, beto)
    insert(admin, params(beto, doc, date=date(2025, 5, 5), name="Gasto de Beto", number="B-1"))
    assert [c.label for c in read(app_pool, beto, *FULL_2025)[1]] == ["Gasto de Beto"]
    assert "Gasto de Beto" not in [c.label for c in read(app_pool, seeded_130.cast.alicia, *FULL_2025)[1]]


# --- El 130 no lee las líneas de IVA ------------------------------------------------------------------------------------------------


def test_a_line_with_a_rate_that_cannot_be_read_does_not_break_the_130(
    admin: Connection[DictRow], app_pool: Pool
) -> None:
    person = make_cast(admin).alicia  # una persona propia: el dato corrupto no debe estorbar a las demás pruebas
    doc = new_document(app_pool, person)
    bad = [{"vat_rate": "veintiuno", "base_cents": 10_000, "vat_cents": 2_100}]
    insert(admin, params(person, doc, date=date(2025, 5, 6), lines=bad, deductible=False, number="C-1"))
    _, costs = read(app_pool, person, *FULL_2025)
    assert [(c.base_cents, c.vat_cents, c.deductible_vat) for c in costs] == [(10_000, 2_100, False)]
    assert model(app_pool, person, 2025, 2).boxes[1].amount_cents == 12_100  # base + IVA no deducible


# --- Límite ----------------------------------------------------------------------------------------------------------------------------


def test_each_query_stops_after_the_limit_it_is_given(app_pool: Pool, seeded_130: Seeded) -> None:
    with user_transaction(app_pool, seeded_130.cast.alicia.id) as conn:
        assert len(income_rows(conn, *FULL_2025, limit=5)) == 5
        assert len(cost_rows(conn, *FULL_2025, limit=2)) == 2
        assert len(income_rows(conn, *FULL_2025)) == 10  # el límite por defecto (10.001) no recorta nada aquí


def test_the_default_limit_is_one_more_than_the_documents_a_year_admits() -> None:
    assert (
        YEAR_DEFAULT_LIMIT == YEAR_MAX_DOCUMENTS + 1
    )  # así el dominio ve que se pasa del tope y falla en vez de callar


# --- T9-07 · solo lee ----------------------------------------------------------------------------------------------------------------


def counts(admin: Connection[DictRow]) -> tuple[int, int, int]:
    row = admin.execute(
        "select (select count(*) from public.invoices) as i, (select count(*) from public.expenses) as e, "
        "(select count(*) from public.activity_log) as a"
    ).fetchone()
    assert row is not None
    return int(row["i"]), int(row["e"]), int(row["a"])


def test_reading_writes_nothing(admin: Connection[DictRow], app_pool: Pool, seeded_130: Seeded) -> None:  # T9-07
    before = counts(admin)
    for q in (1, 2, 3, 4):
        model(app_pool, seeded_130.cast.alicia, 2025, q)
    assert counts(admin) == before


# --- Los índices que la consulta necesita ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("sql", "index"), [(INCOME_SQL, "invoices_owner_date"), (COST_SQL, "expenses_by_owner_date")])
def test_the_queries_can_use_the_owner_and_date_indexes(
    app_pool: Pool, seeded_130: Seeded, sql: str, index: str
) -> None:
    with user_transaction(app_pool, seeded_130.cast.alicia.id) as conn:
        conn.execute("set local enable_seqscan = off")
        plan = "\n".join(
            next(iter(r.values()))
            for r in conn.execute(
                "explain " + sql, {"start": FULL_2025[0], "end": FULL_2025[1], "limit": 10}
            ).fetchall()
        )
    assert index in plan, plan
