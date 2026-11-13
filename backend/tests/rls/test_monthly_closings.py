"""AC-03, AC-04, AC-05 (base), AC-12, AC-19 y AC-20 · La tabla `monthly_closings` y sus funciones (SPEC-W-012 §5.2, D-01, D-03, D-04).

Nadie escribe la tabla directamente: el job (`service_role`) la escribe con `private.close_month`, que valida el payload, guarda la foto del cierre en una
sola sentencia y dice si cerró, reabrió o no cambió nada. La visibilidad por rol y por estado del vínculo la prueba además la matriz de RLS.
"""

import copy
import threading
import time
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.db import service_transaction
from tests.support import Cast, Person, Pool, attempt

CLIENT_A = "11111111-1111-4111-8111-111111111111"
CLIENT_B = "22222222-2222-4222-8222-222222222222"


def payload(**over: Any) -> dict[str, Any]:
    """Un cierre coherente: dos facturas ordinarias, una nacional y otra de la UE."""
    body: dict[str, Any] = {
        "invoice_count": 2,
        "national_cents": 150_000,
        "eu_cents": 50_000,
        "non_eu_cents": 0,
        "total_cents": 200_000,
        "expenses_cents": 30_000,
        "by_client": [
            {
                "client_id": CLIENT_A,
                "name": "Estudio Norte S.L.",
                "scope": "national",
                "base_cents": 150_000,
                "invoice_count": 1,
            },
            {"client_id": CLIENT_B, "name": "Kreativ GmbH", "scope": "eu", "base_cents": 50_000, "invoice_count": 1},
        ],
    }
    body.update(over)
    return body


def close(pool: Pool, owner: Person, year: int, month: int, body: Any) -> str:
    with service_transaction(pool) as conn:
        row = conn.execute(
            "select private.close_month(%s, %s, %s, %s) as result",
            (owner.id, year, month, Jsonb(body) if body is not None else None),
        ).fetchone()
    assert row is not None
    return row["result"]


def stored(admin: Connection[DictRow], owner: Person, year: int = 2026, month: int = 9) -> dict[str, Any] | None:
    return admin.execute(
        "select * from public.monthly_closings where owner_id = %s and year = %s and month = %s",
        (owner.id, year, month),
    ).fetchone()


def count(admin: Connection[DictRow], owner: Person) -> int:
    row = admin.execute("select count(*) as n from public.monthly_closings where owner_id = %s", (owner.id,)).fetchone()
    assert row is not None
    return row["n"]


# --- Cerrar, reabrir y no cambiar nada -------------------------------------------------------------------------------------------------


def test_the_first_close_stores_the_snapshot(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert close(service_pool, cast.alicia, 2026, 9, payload()) == "closed"
    row = stored(admin, cast.alicia)
    assert row is not None
    assert (row["invoice_count"], row["national_cents"], row["eu_cents"], row["non_eu_cents"]) == (
        2,
        150_000,
        50_000,
        0,
    )
    assert (row["total_cents"], row["expenses_cents"], row["revision"]) == (200_000, 30_000, 1)
    assert row["by_client"] == payload()["by_client"]  # tal cual, también el orden
    assert row["first_closed_at"] == row["closed_at"]


def test_repeating_the_same_close_changes_nothing(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    close(service_pool, cast.alicia, 2026, 9, payload())
    before = stored(admin, cast.alicia)
    time.sleep(0.02)
    assert close(service_pool, cast.alicia, 2026, 9, payload()) == "unchanged"
    assert close(service_pool, cast.alicia, 2026, 9, payload()) == "unchanged"
    assert stored(admin, cast.alicia) == before
    assert count(admin, cast.alicia) == 1


def test_a_change_reopens_the_month_and_keeps_the_first_close(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    close(service_pool, cast.alicia, 2026, 9, payload())
    first = stored(admin, cast.alicia)
    assert first is not None
    time.sleep(0.02)
    assert close(service_pool, cast.alicia, 2026, 9, payload(expenses_cents=45_000)) == "reopened"
    second = stored(admin, cast.alicia)
    assert second is not None
    assert (second["revision"], second["expenses_cents"]) == (2, 45_000)
    assert second["first_closed_at"] == first["first_closed_at"] and second["closed_at"] > first["closed_at"]
    assert close(service_pool, cast.alicia, 2026, 9, payload(expenses_cents=45_000)) == "unchanged"
    third = stored(admin, cast.alicia)
    assert third is not None and third["revision"] == 2 and third["closed_at"] == second["closed_at"]


def test_a_change_only_in_the_client_breakdown_also_reopens(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    close(service_pool, cast.alicia, 2026, 9, payload())
    renamed = payload()
    renamed["by_client"][0]["name"] = "Estudio Norte, S.L."
    assert close(service_pool, cast.alicia, 2026, 9, renamed) == "reopened"
    swapped = payload()
    swapped["by_client"] = list(reversed(swapped["by_client"]))
    assert close(service_pool, cast.alicia, 2026, 9, swapped) == "reopened"  # el orden también es parte de la foto
    row = stored(admin, cast.alicia)
    assert row is not None and row["revision"] == 3


def test_each_person_and_month_has_its_own_row(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert close(service_pool, cast.alicia, 2026, 9, payload()) == "closed"
    assert close(service_pool, cast.beto, 2026, 9, payload()) == "closed"
    assert close(service_pool, cast.alicia, 2026, 10, payload()) == "closed"
    assert close(service_pool, cast.alicia, 2025, 9, payload()) == "closed"
    assert count(admin, cast.alicia) == 3 and count(admin, cast.beto) == 1


def test_a_month_with_no_activity_closes_at_zero(service_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    empty = payload(invoice_count=0, national_cents=0, eu_cents=0, total_cents=0, expenses_cents=0, by_client=[])
    assert close(service_pool, cast.alicia, 2026, 9, empty) == "closed"
    row = stored(admin, cast.alicia)
    assert row is not None and row["by_client"] == [] and row["total_cents"] == 0


def test_negative_totals_are_valid_when_there_are_more_corrections_than_invoices(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    body = payload(
        invoice_count=0,
        national_cents=-12_000,
        eu_cents=0,
        total_cents=-12_000,
        by_client=[
            {
                "client_id": CLIENT_A,
                "name": "Estudio Norte S.L.",
                "scope": "national",
                "base_cents": -12_000,
                "invoice_count": 0,
            }
        ],
    )
    assert close(service_pool, cast.alicia, 2026, 9, body) == "closed"


# --- Ejecuciones simultáneas ----------------------------------------------------------------------------------------------------------


def run_together(pool: Pool, owner: Person, bodies: list[dict[str, Any]]) -> list[str]:
    results: list[str] = []
    barrier = threading.Barrier(len(bodies))

    def worker(body: dict[str, Any]) -> None:
        barrier.wait()
        results.append(close(pool, owner, 2026, 9, body))

    threads = [threading.Thread(target=worker, args=(b,)) for b in bodies]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return sorted(results)


def test_two_simultaneous_identical_closes_leave_one_row(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    assert run_together(service_pool, cast.alicia, [payload(), payload()]) == ["closed", "unchanged"]
    row = stored(admin, cast.alicia)
    assert row is not None and row["revision"] == 1 and count(admin, cast.alicia) == 1


def test_two_simultaneous_different_closes_never_lose_a_revision(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    close(service_pool, cast.alicia, 2026, 9, payload())
    assert run_together(service_pool, cast.alicia, [payload(expenses_cents=1), payload(expenses_cents=2)]) == [
        "reopened",
        "reopened",
    ]
    row = stored(admin, cast.alicia)
    assert row is not None and row["revision"] == 3 and row["expenses_cents"] in (1, 2)


# --- Validación: invalid_closing y no se escribe nada ----------------------------------------------------------------------------------


def without(key: str) -> dict[str, Any]:
    body = payload()
    del body[key]
    return body


def entry(**over: Any) -> dict[str, Any]:
    return {**payload()["by_client"][0], **over}


BAD_PAYLOADS: dict[str, Any] = {
    "sin invoice_count": without("invoice_count"),
    "sin by_client": without("by_client"),
    "sin expenses_cents": without("expenses_cents"),
    "importe como texto": payload(national_cents="150000"),
    "importe con decimales": payload(expenses_cents=10.5),
    "importe enorme": payload(expenses_cents=10**16),
    "importe nulo": payload(expenses_cents=None),
    "invoice_count negativo": payload(invoice_count=-1),
    "total que no cuadra": payload(total_cents=1),
    "desglose que no suma un ámbito": payload(by_client=[entry(base_cents=140_000), payload()["by_client"][1]]),
    "desglose con los ámbitos cruzados": payload(
        by_client=[entry(scope="eu"), {**payload()["by_client"][1], "scope": "national"}]
    ),
    "desglose que no suma las facturas": payload(invoice_count=3),
    "ámbito desconocido": payload(by_client=[entry(scope="mars"), payload()["by_client"][1]]),
    # Con las sumas ajustadas para que un ámbito inventado cuadre como si fuera «fuera de la UE»: solo la comprobación del ámbito lo rechaza.
    "ámbito desconocido que cuadra con otro": payload(
        national_cents=0, non_eu_cents=150_000, by_client=[entry(scope="mars"), payload()["by_client"][1]]
    ),
    "client_id que no es uuid": payload(by_client=[entry(client_id="no-es-uuid"), payload()["by_client"][1]]),
    "nombre que no es texto": payload(by_client=[entry(name=5), payload()["by_client"][1]]),
    "base del cliente como texto": payload(by_client=[entry(base_cents="150000"), payload()["by_client"][1]]),
    "invoice_count del cliente negativo": payload(by_client=[entry(invoice_count=-1), payload()["by_client"][1]]),
    "by_client que no es una lista": payload(by_client={}),
    "elemento que no es un objeto": payload(by_client=["x"]),
    "payload nulo": None,
    "payload de JSON null": "json-null",
    "payload que es una lista": [],
}


@pytest.mark.parametrize("case", sorted(BAD_PAYLOADS))
def test_an_incoherent_payload_is_refused_and_nothing_is_written(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast, case: str
) -> None:
    body = BAD_PAYLOADS[case]
    with pytest.raises(psycopg.errors.RaiseException) as caught:
        if body == "json-null":
            with service_transaction(service_pool) as conn:
                conn.execute("select private.close_month(%s, 2026, 9, 'null'::jsonb)", (cast.alicia.id,))
        else:
            close(service_pool, cast.alicia, 2026, 9, copy.deepcopy(body))
    assert str(caught.value).splitlines()[0] == "invalid_closing"
    assert count(admin, cast.alicia) == 0


@pytest.mark.parametrize(("year", "month"), [(2026, 0), (2026, 13), (1999, 9), (10000, 9)])
def test_a_month_that_does_not_exist_is_refused(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast, year: int, month: int
) -> None:
    with pytest.raises(psycopg.errors.RaiseException) as caught:
        close(service_pool, cast.alicia, year, month, payload())
    assert str(caught.value).splitlines()[0] == "invalid_closing"
    assert count(admin, cast.alicia) == 0


def test_the_database_clock_does_not_decide_which_month_may_close(service_pool: Pool, cast: Cast) -> None:
    # El reloj lo inyecta el job: un mes que para la base de datos es futuro se puede cerrar (así se prueba con fechas simuladas).
    assert close(service_pool, cast.alicia, 2999, 1, payload()) == "closed"


# --- Nadie escribe directamente ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto", "gina", "gus", "adan"])
def test_nobody_writes_the_table_directly_not_even_the_owner(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, who: str
) -> None:
    close(service_pool, cast.alicia, 2026, 9, payload())
    person = cast[who]
    statements = (
        (
            "insert into public.monthly_closings (owner_id, year, month, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, expenses_cents) "
            "values (%s, 2026, 10, 0, 0, 0, 0, 0, 0)",
            (person.id,),
        ),
        ("update public.monthly_closings set expenses_cents = 1", None),
        ("delete from public.monthly_closings", None),
        ("truncate public.monthly_closings", None),
    )
    for sql, params in statements:
        assert attempt(app_pool, person, sql, params).sqlstate == "42501", sql
    row = stored(admin, cast.alicia)
    assert row is not None and row["expenses_cents"] == 30_000 and count(admin, person) == (1 if who == "alicia" else 0)


def test_service_role_cannot_write_the_table_directly(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege), service_transaction(service_pool) as conn:
        conn.execute(
            "insert into public.monthly_closings (owner_id, year, month, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, expenses_cents) "
            "values (%s, 2026, 9, 0, 0, 0, 0, 0, 0)",
            (cast.alicia.id,),
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege), service_transaction(service_pool) as conn:
        conn.execute("select * from public.monthly_closings")
    assert count(admin, cast.alicia) == 0


def test_the_table_has_forced_rls_and_only_select_for_authenticated(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select relrowsecurity as rls, relforcerowsecurity as forced from pg_class where oid = 'public.monthly_closings'::regclass"
    ).fetchone()
    assert row == {"rls": True, "forced": True}
    for role, allowed in (("authenticated", {"SELECT"}), ("anon", set()), ("service_role", set())):
        for p in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            found = admin.execute(
                "select has_table_privilege(%s, 'public.monthly_closings', %s) as ok", (role, p)
            ).fetchone()
            assert found is not None and found["ok"] is (p in allowed), (role, p)


def test_there_are_exactly_two_read_policies_and_none_for_the_admin(admin: Connection[DictRow]) -> None:
    found = admin.execute(
        "select policyname, cmd from pg_policies where schemaname = 'public' and tablename = 'monthly_closings' order by 1"
    ).fetchall()
    assert [(r["policyname"], r["cmd"]) for r in found] == [
        ("monthly_closings_select_gestor", "SELECT"),
        ("monthly_closings_select_owner", "SELECT"),
    ]


@pytest.mark.parametrize(
    "function", ["private.close_month(uuid, integer, integer, jsonb)", "private.closing_candidates()"]
)
def test_the_job_functions_are_only_for_service_role(admin: Connection[DictRow], function: str) -> None:
    for role, expected in (("service_role", True), ("authenticated", False), ("anon", False)):
        found = admin.execute("select has_function_privilege(%s, %s, 'execute') as ok", (role, function)).fetchone()
        assert found is not None and found["ok"] is expected, (role, function)


@pytest.mark.parametrize("who", ["alicia", "gina", "adan"])
def test_users_cannot_call_the_job_functions(app_pool: Pool, cast: Cast, who: str) -> None:
    closed = attempt(
        app_pool, cast[who], "select private.close_month(%s, 2026, 9, %s)", (cast.alicia.id, Jsonb(payload()))
    )
    candidates = attempt(app_pool, cast[who], "select * from private.closing_candidates()")
    assert closed.sqlstate == "42501" and candidates.sqlstate == "42501"


# --- Candidatos -------------------------------------------------------------------------------------------------------------------------


def candidates(pool: Pool) -> dict[Any, dict[str, Any]]:
    with service_transaction(pool) as conn:
        rows = conn.execute("select * from private.closing_candidates()").fetchall()
    return {row["owner_id"]: row for row in rows}


def test_candidates_are_the_active_users_with_their_sign_up_date(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    found = candidates(service_pool)
    created = admin.execute("select created_at from public.profiles where id = %s", (cast.alicia.id,)).fetchone()
    assert created is not None
    assert cast.alicia.id in found and found[cast.alicia.id]["created_at"] == created["created_at"]
    assert set(found[cast.alicia.id]) == {"owner_id", "created_at"}  # nada más: ni correo ni datos financieros


def test_candidates_leave_out_gestores_admins_and_suspended_accounts(
    service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.beto.id,))
    found = candidates(service_pool)
    assert cast.alicia.id in found
    for person in (cast.beto, cast.gina, cast.gus, cast.adan):
        assert person.id not in found


# --- Las CHECK y la clave, por nombre ---------------------------------------------------------------------------------------------------


def raw_insert(admin: Connection[DictRow], owner: Person, **over: Any) -> None:
    values: dict[str, Any] = {
        "year": 2026,
        "month": 9,
        "invoice_count": 0,
        "national_cents": 0,
        "eu_cents": 0,
        "non_eu_cents": 0,
        "total_cents": 0,
        "expenses_cents": 0,
        "by_client": Jsonb([]),
        "revision": 1,
    }
    values.update(over)
    admin.execute(
        "insert into public.monthly_closings (owner_id, year, month, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, "
        "expenses_cents, by_client, revision) values (%(owner)s, %(year)s, %(month)s, %(invoice_count)s, %(national_cents)s, %(eu_cents)s, "
        "%(non_eu_cents)s, %(total_cents)s, %(expenses_cents)s, %(by_client)s, %(revision)s)",
        {**values, "owner": owner.id},
    )


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"year": 1999}, "monthly_closings_year_range"),
        ({"year": 10000}, "monthly_closings_year_range"),
        ({"month": 0}, "monthly_closings_month_range"),
        ({"month": 13}, "monthly_closings_month_range"),
        ({"invoice_count": -1}, "monthly_closings_invoice_count_nonneg"),
        ({"revision": 0}, "monthly_closings_revision_positive"),
        ({"total_cents": 1}, "monthly_closings_total_matches"),
        ({"national_cents": 5, "total_cents": 0}, "monthly_closings_total_matches"),
        ({"by_client": Jsonb({})}, "monthly_closings_by_client_is_array"),
        ({"by_client": Jsonb("x")}, "monthly_closings_by_client_is_array"),
    ],
)
def test_the_table_checks(admin: Connection[DictRow], cast: Cast, fields: dict[str, Any], constraint: str) -> None:
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        raw_insert(admin, cast.alicia, **fields)
    assert caught.value.diag.constraint_name == constraint


def test_a_month_is_unique_per_person(admin: Connection[DictRow], cast: Cast) -> None:
    raw_insert(admin, cast.alicia)
    with pytest.raises(psycopg.errors.UniqueViolation) as caught:
        raw_insert(admin, cast.alicia)
    assert caught.value.diag.constraint_name == "monthly_closings_pkey"
    raw_insert(admin, cast.beto)  # otra persona, mismo mes: sí


def test_the_closings_go_away_with_the_account(admin: Connection[DictRow], cast: Cast) -> None:
    raw_insert(admin, cast.beto)
    admin.execute("delete from auth.users where id = %s", (cast.beto.id,))
    assert count(admin, cast.beto) == 0
