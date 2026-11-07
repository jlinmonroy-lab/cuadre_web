"""AC-14 · `GET /api/expenses` y `GET /api/expenses/{id}`: lista paginada por cursor, filtros y detalle (SPEC-W-003 §5.3).

120 gastos de varios meses y categorías (tres por fecha y con la misma hora de creación en grupos, para probar el desempate) y uno anulado.
El orden es el del índice: `expense_date`, `created_at` e `id`, de más reciente a más antiguo.
"""

import base64
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.validators import ExpenseCategory
from tests.documents.conftest import Api
from tests.expenses.support import manual, registered
from tests.support import Person

CATEGORIES = [c.value for c in ExpenseCategory]


def seed(admin: Connection[DictRow], person: Person, count: int = 120) -> list[UUID]:
    """`count` gastos manuales: 3 por fecha (cada 5 días desde el 1 de enero) y una hora de creación por pares, para forzar empates."""
    first = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        (
            person.id,
            date(2026, 1, 1) + timedelta(days=(i // 3) * 5),
            f"Gasto {i}",
            CATEGORIES[i % 8],
            100 + i,
            100 + i,
            first + timedelta(seconds=i // 2, microseconds=123456),
        )
        for i in range(count)
    ]
    with admin.cursor() as cursor:
        cursor.executemany(
            "insert into public.expenses (owner_id, origin, expense_date, supplier_name, category, base_cents, vat_cents, "
            "total_cents, deductible_vat, created_at) values (%s, 'manual', %s, %s, %s::public.expense_category, %s, 0, %s, false, %s)",
            rows,
        )
    return expected(admin, person)


def expected(admin: Connection[DictRow], person: Person) -> list[UUID]:
    """Los identificadores que debe devolver la lista, en su orden."""
    found = admin.execute(
        "select id from public.expenses where owner_id = %s and voided_at is null "
        "order by expense_date desc, created_at desc, id desc",
        (person.id,),
    ).fetchall()
    return [r["id"] for r in found]


def page(api: Api, person: Person, **params: Any) -> Any:
    return api.request("GET", "/api/expenses", person, params=params)


def walk(api: Api, person: Person, **params: Any) -> list[str]:
    """Todas las páginas, siguiendo `next_cursor`."""
    ids: list[str] = []
    cursor: str | None = None
    for _ in range(300):
        response = page(api, person, **params, **({"cursor": cursor} if cursor else {}))
        assert response.status_code == 200, response.text
        body = response.json()
        ids += [item["id"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            return ids
    raise AssertionError("la paginación no termina")


@pytest.fixture
def many(api: Api, admin: Connection[DictRow]) -> list[UUID]:
    alicia = api.cast.alicia
    seed(admin, alicia)
    victim = admin.execute(
        "select id from public.expenses where owner_id = %s and supplier_name = 'Gasto 7'", (alicia.id,)
    ).fetchone()
    assert victim is not None
    admin.execute("update public.expenses set voided_at = now() where id = %s", (victim["id"],))
    return expected(admin, alicia)


# --- páginas --------------------------------------------------------------------------------------------------------------------


def test_ac14_pages_of_50_from_the_most_recent_without_repeating_or_skipping(api: Api, many: list[UUID]) -> None:
    alicia = api.cast.alicia
    assert len(many) == 119
    first = page(api, alicia).json()
    assert len(first["items"]) == 50 and first["next_cursor"]
    assert [item["id"] for item in first["items"]] == [str(i) for i in many[:50]]

    assert walk(api, alicia) == [str(i) for i in many]


@pytest.mark.parametrize("limit", [1, 7, 50, 100])
def test_any_page_size_covers_the_list_exactly_once(api: Api, many: list[UUID], limit: int) -> None:
    assert walk(api, api.cast.alicia, limit=limit) == [str(i) for i in many]


def test_the_last_page_has_no_cursor_and_an_exact_fit_does_not_invent_one(
    api: Api, admin: Connection[DictRow], many: list[UUID]
) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    everything = page(api, alicia, limit=100).json()
    assert len(everything["items"]) == 100 and everything["next_cursor"]
    tail = page(api, alicia, limit=100, cursor=everything["next_cursor"]).json()
    assert len(tail["items"]) == 19 and tail["next_cursor"] is None

    seed(admin, beto, 100)  # justo una página llena
    full = page(api, beto, limit=100).json()
    assert len(full["items"]) == 100 and full["next_cursor"] is None


def test_the_voided_expense_is_not_listed_but_its_detail_is_available(
    api: Api, admin: Connection[DictRow], many: list[UUID]
) -> None:
    alicia = api.cast.alicia
    listed = set(walk(api, alicia))
    victim = admin.execute(
        "select id from public.expenses where owner_id = %s and supplier_name = 'Gasto 7'", (alicia.id,)
    ).fetchone()
    assert victim is not None and str(victim["id"]) not in listed

    detail = api.request("GET", f"/api/expenses/{victim['id']}", alicia)
    assert detail.status_code == 200 and detail.json()["voided_at"] is not None


def test_an_empty_list_is_an_empty_page(api: Api) -> None:
    assert page(api, api.cast.alicia).json() == {"items": [], "next_cursor": None}


def test_the_items_have_the_summary_fields_only(api: Api) -> None:
    alicia = api.cast.alicia
    manual(api, alicia)
    (item,) = page(api, alicia).json()["items"]
    assert set(item) == {
        "id",
        "origin",
        "expense_date",
        "supplier_name",
        "category",
        "total_cents",
        "vat_cents",
        "deductible_vat",
        "supplier_scope",
        "document_id",
    }


def test_each_person_sees_only_their_own(api: Api, admin: Connection[DictRow], many: list[UUID]) -> None:
    beto = api.cast.beto
    assert page(api, beto).json() == {"items": [], "next_cursor": None}
    mine = manual(api, beto)
    assert [i["id"] for i in page(api, beto).json()["items"]] == [mine["id"]]
    assert len(walk(api, api.cast.alicia)) == 119


def test_a_document_expense_and_a_manual_one_are_listed_together(api: Api) -> None:
    alicia = api.cast.alicia
    _, from_document = registered(api, alicia)
    from_hand = manual(api, alicia, expense_date="2026-11-01")
    items = page(api, alicia).json()["items"]
    assert [i["id"] for i in items] == [from_hand["id"], from_document["id"]]
    assert [i["origin"] for i in items] == ["manual", "document"]


# --- filtros ----------------------------------------------------------------------------------------------------------------------


def dates_of(admin: Connection[DictRow], ids: list[str]) -> list[tuple[date, str]]:
    rows = admin.execute(
        "select expense_date, category::text as category from public.expenses where id = any(%s)", (ids,)
    ).fetchall()
    return [(r["expense_date"], r["category"]) for r in rows]


def test_the_year_and_month_filters(api: Api, admin: Connection[DictRow], many: list[UUID]) -> None:
    alicia = api.cast.alicia
    in_year = walk(api, alicia, year=2026)
    assert in_year == [str(i) for i in many], "todos son de 2026"
    assert walk(api, alicia, year=2025) == []

    march = walk(api, alicia, year=2026, month=3)
    found = dates_of(admin, march)
    assert march and all(day.year == 2026 and day.month == 3 for day, _ in found)
    wanted = [str(i) for i in many if dates_of(admin, [str(i)])[0][0].month == 3]
    assert march == wanted


def test_the_category_filter_and_its_combination_with_paging(
    api: Api, admin: Connection[DictRow], many: list[UUID]
) -> None:
    alicia = api.cast.alicia
    software = walk(api, alicia, category="software", limit=5)
    assert software and {c for _, c in dates_of(admin, software)} == {"software"}
    wanted = [str(i) for i in many if dates_of(admin, [str(i)])[0][1] == "software"]
    assert software == wanted

    combined = walk(api, alicia, category="training", year=2026, month=2, limit=2)
    assert {c for _, c in dates_of(admin, combined)} <= {"training"}
    assert all((d.year, d.month) == (2026, 2) for d, _ in dates_of(admin, combined))


@pytest.mark.parametrize(
    "params",
    [
        {"month": 3},  # el mes necesita el año
        {"month": 0, "year": 2026},
        {"month": 13, "year": 2026},
        {"year": 1999},
        {"year": 2101},
        {"year": "dos mil"},
        {"limit": 0},
        {"limit": 101},
        {"limit": -1},
        {"limit": "muchos"},
        {"category": "inventada"},
    ],
)
def test_bad_parameters_are_a_422(api: Api, params: dict[str, Any]) -> None:
    response = page(api, api.cast.alicia, **params)
    assert response.status_code == 422 and response.json()["code"] == "validation_error", response.text


def test_the_month_without_year_error_points_at_the_month(api: Api) -> None:
    errors = page(api, api.cast.alicia, month=3).json()["errors"]
    assert [e["loc"] for e in errors] == ["query.month"]


# --- cursor -------------------------------------------------------------------------------------------------------------------------


def b64(value: Any) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


GOOD = {"d": "2026-01-01", "c": "2026-01-01T00:00:00+00:00", "i": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}
BAD_CURSORS = [
    "abc",
    "!!!",
    "a b",
    "../../etc/passwd",
    b64({}),
    b64([]),
    b64("texto"),
    b64({**GOOD, "extra": 1}),
    b64({"d": GOOD["d"], "c": GOOD["c"]}),
    b64({**GOOD, "d": 20260101}),
    b64({**GOOD, "d": "2026-1-1"}),
    b64({**GOOD, "d": "20260101"}),  # formato básico: fromisoformat lo admite, el cursor no
    b64({**GOOD, "d": "2026-02-30"}),
    b64({**GOOD, "c": "2026-01-01T00:00:00"}),  # sin zona horaria
    b64({**GOOD, "c": "ayer"}),
    b64({**GOOD, "i": "no-es-un-uuid"}),
    b64({**GOOD, "i": GOOD["i"].upper()}),  # el uuid no está en su forma canónica
    b64({**GOOD, "i": GOOD["i"].replace("-", "")}),
    b64(b"\xff\xfe\x00"),
    b64(b"{"),
]


@pytest.mark.parametrize("cursor", BAD_CURSORS, ids=[f"{i}" for i in range(len(BAD_CURSORS))])
def test_a_cursor_that_is_not_ours_is_a_422_invalid_cursor(api: Api, cursor: str) -> None:
    response = page(api, api.cast.alicia, cursor=cursor)
    assert response.status_code == 422 and response.json()["code"] == "invalid_cursor", response.text


def test_a_well_formed_cursor_only_moves_the_window_over_the_callers_own_rows(
    api: Api, admin: Connection[DictRow]
) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    seed(admin, beto, 5)
    mine = manual(api, alicia, expense_date="2026-01-02")
    forged = b64({"d": "2026-12-31", "c": "2026-12-31T00:00:00+00:00", "i": "ffffffff-ffff-4fff-8fff-ffffffffffff"})
    items = page(api, alicia, cursor=forged).json()["items"]
    assert [i["id"] for i in items] == [mine["id"]], "nunca aparecen filas de otra persona"


def test_an_over_long_cursor_is_refused_before_it_is_read(api: Api) -> None:
    assert page(api, api.cast.alicia, cursor="a" * 201).status_code == 422


# --- detalle --------------------------------------------------------------------------------------------------------------------------


def test_the_detail_has_every_field_and_the_original_document_can_be_opened(api: Api) -> None:
    alicia = api.cast.alicia
    document_id, created = registered(api, alicia)
    detail = api.request("GET", f"/api/expenses/{created['id']}", alicia)
    assert detail.status_code == 200 and detail.json() == created
    assert set(detail.json()) >= {
        "doc_type",
        "supplier_tax_id",
        "invoice_number",
        "tax_breakdown",
        "created_at",
        "voided_at",
    }
    assert api.preview(alicia, document_id).status_code == 200


def test_an_unknown_or_foreign_expense_detail_is_a_404(api: Api) -> None:
    alicia, beto = api.cast.alicia, api.cast.beto
    mine = manual(api, alicia)
    for target in (mine["id"], "00000000-0000-4000-8000-000000000000"):
        response = api.request("GET", f"/api/expenses/{target}", beto)
        assert response.status_code == 404 and response.json()["code"] == "expense_not_found"
    assert api.request("GET", "/api/expenses/no-es-un-uuid", alicia).status_code == 422
