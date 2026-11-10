"""AC-04, AC-05, AC-11, AC-12, AC-21 · Las tablas `invoices` e `invoice_files` y su trigger (SPEC-W-007 §5.2, RES-03, Anexo B.1-D).

Las tablas no se escriben directamente ni el dueño; el trigger defiende la inmutabilidad venga la sentencia de donde venga, y varias comprobaciones
escriben como dueño de la base de datos para demostrarlo. Cada CHECK lleva nombre propio (la API los traduce por nombre) y se prueba en su frontera.
Las funciones `app.*` están en `test_invoices_functions.py`; la visibilidad por rol y por estado del vínculo, además, en la matriz de RLS.
"""

import uuid
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.db import service_transaction
from tests.rls.invoices_support import D1, client, insert_direct, prepare, series
from tests.support import Cast, Pool, attempt

KEYS = ["alicia", "beto", "gina", "gus", "adan"]
PDF = {"size_bytes": 100}


@pytest.fixture
def world(admin: Connection[DictRow], cast: Cast) -> dict[str, Any]:
    """Alicia con su serie y su cliente, y una factura directa; Beto con su serie y su cliente."""
    serie = prepare(admin, cast.alicia)
    cliente = client(admin, cast.alicia)
    return {
        "series": serie,
        "client": cliente,
        "invoice": insert_direct(admin, cast.alicia, serie, cliente),
        "beto_series": series(admin, cast.beto, "2026"),
        "beto_client": client(admin, cast.beto),
    }


def violated(action: Callable[[], object]) -> str:
    """El nombre de la restricción que salta, `ok` si la sentencia entra o el tipo de error si no es una restricción con nombre."""
    try:
        action()
    except psycopg.errors.IntegrityError as exc:
        return exc.diag.constraint_name or type(exc).__name__
    return "ok"


def rectifying(admin: Connection[DictRow], cast: Cast, world: dict[str, Any], **fields: Any) -> uuid.UUID:
    """Una rectificativa válida de la factura de `world` (base −200, IVA 0, total −200) con lo que se quiera cambiar."""
    values: dict[str, Any] = {
        "series_id": series(admin, cast.alicia, f"R-{uuid.uuid4().int % 9000 + 1000}", kind="rectifying"),
        "series_code": "R-2026",
        "kind": "rectifying",
        "rectifies_id": world["invoice"],
        "rectification_reason": "Importe mal calculado",
        "base_cents": -200,
        "total_cents": -200,
        **fields,
    }
    return insert_direct(admin, cast.alicia, values.pop("series_id"), world["client"], **values)


# --- Quién escribe -------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", KEYS)
@pytest.mark.parametrize(
    "statement",
    [
        "update public.invoices set paid_at = now()",
        "update public.invoices set concept = 'x'",
        "delete from public.invoices",
        "truncate public.invoices",
        "update public.invoice_files set size_bytes = 1",
        "delete from public.invoice_files",
        "truncate public.invoice_files",
    ],
)
def test_nobody_writes_the_tables_directly_not_even_the_owner(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, world: dict[str, Any], who: str, statement: str
) -> None:
    out = attempt(app_pool, cast[who], statement)
    assert out.sqlstate == "42501", (who, statement, out.sqlstate, out.message)


@pytest.mark.parametrize("who", KEYS)
def test_nobody_inserts_directly(app_pool: Pool, cast: Cast, world: dict[str, Any], who: str) -> None:
    out = attempt(
        app_pool,
        cast[who],
        "insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes) values (%s, %s, 'x', 'y', 1)",
        (world["invoice"], cast.alicia.id),
    )
    assert out.sqlstate == "42501"
    out = attempt(app_pool, cast[who], "insert into public.invoices (owner_id) values (%s)", (cast[who].id,))
    assert out.sqlstate == "42501"


@pytest.mark.parametrize("table", ["invoices", "invoice_files"])
def test_the_tables_have_forced_rls_and_only_select_for_authenticated(admin: Connection[DictRow], table: str) -> None:
    flags = admin.execute(
        "select relrowsecurity as rls, relforcerowsecurity as forced from pg_class where oid = %s::regclass",
        (f"public.{table}",),
    ).fetchone()
    assert flags == {"rls": True, "forced": True}
    for role in ("authenticated", "anon", "service_role", "public"):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
            if role == "public":
                continue
            allowed = admin.execute(
                "select has_table_privilege(%s, %s, %s) as ok", (role, f"public.{table}", privilege)
            ).fetchone()
            assert allowed is not None
            assert allowed["ok"] == (role == "authenticated" and privilege == "SELECT"), (role, privilege)


@pytest.mark.parametrize("table", ["invoices", "invoice_files"])
def test_there_are_exactly_two_read_policies_and_none_for_the_admin(admin: Connection[DictRow], table: str) -> None:
    policies = admin.execute(
        "select policyname, cmd, roles::text as roles, qual from pg_policies where schemaname = 'public' and tablename = %s order by 1",
        (table,),
    ).fetchall()
    assert [p["policyname"] for p in policies] == [f"{table}_select_gestor", f"{table}_select_owner"]
    assert all(p["cmd"] == "SELECT" and p["roles"] == "{authenticated}" for p in policies)
    assert "is_admin" not in " ".join(p["qual"] for p in policies)


# --- Restricciones con nombre ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("constraint", "bad", "good"),
    [
        (
            "invoices_number_range",
            [{"number": 0}, {"number": 1_000_000}, {"number": -1}],
            [{"number": 1}, {"number": 999_999}],
        ),
        (
            "invoices_issue_date_min",
            [{"issue_date": "1999-12-31"}],
            [{"issue_date": "2000-01-01"}],
        ),
        (
            "invoices_concept_length",
            [{"concept": "a"}, {"concept": "a" * 301}, {"concept": ""}],
            [{"concept": "ab"}, {"concept": "a" * 300}],
        ),
        (
            "invoices_client_address_length",
            [{"client_address": ""}, {"client_address": "a" * 301}],
            [{"client_address": "a"}, {"client_address": "a" * 300}],
        ),
        (
            "invoices_issuer_name_length",
            [{"issuer_name": "a"}, {"issuer_name": "a" * 201}],
            [{"issuer_name": "ab"}, {"issuer_name": "a" * 200}],
        ),
        (
            "invoices_issuer_address_length",
            [{"issuer_address": "abcd"}, {"issuer_address": "a" * 301}],
            [{"issuer_address": "abcde"}, {"issuer_address": "a" * 300}],
        ),
        ("invoices_legal_note_length", [{"legal_note": "a" * 301}], [{"legal_note": "a" * 300}, {"legal_note": None}]),
        (
            "invoices_vat_rate_values",
            [{"vat_rate": 5}, {"vat_rate": 21.5}, {"vat_rate": -1}],
            [{"vat_rate": 0}, {"vat_rate": 4}, {"vat_rate": 10}, {"vat_rate": 21}],
        ),
        (
            "invoices_irpf_rate_values",
            [{"irpf_rate": 5}, {"irpf_rate": 14.99}, {"irpf_rate": 20}],
            [{"irpf_rate": 0}, {"irpf_rate": 7}, {"irpf_rate": 15}],
        ),
        (
            "invoices_base_range",
            [{"base_cents": 10_000_000_000, "total_cents": 10_000_000_000}],
            [{"base_cents": 9_999_999_999, "total_cents": 9_999_999_999}],
        ),
        (
            "invoices_base_positive",
            [{"base_cents": 0, "total_cents": 0}, {"base_cents": -1, "total_cents": -1}],
            [{"base_cents": 1, "total_cents": 1}],
        ),
        (
            "invoices_total_matches",
            [{"total_cents": 999}, {"total_cents": 1001}],
            [{"total_cents": 1000}],
        ),
        (
            "invoices_amounts_sign",
            [{"vat_cents": -1, "total_cents": 999}, {"irpf_cents": -1, "total_cents": 1001}],
            [{"vat_cents": 1, "total_cents": 1001}, {"irpf_cents": 1, "total_cents": 999}],
        ),
        (
            "invoices_rectification_ref",
            [{"rectifies_id": "$invoice"}],  # una ordinaria que dice rectificar
            [],
        ),
        (
            "invoices_rectification_reason",
            [{"rectification_reason": "Motivo suelto"}],  # una ordinaria con motivo
            [],
        ),
    ],
)
def test_each_check_of_invoices_by_name_at_its_boundary(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any], constraint: str, bad: list[dict], good: list[dict]
) -> None:
    def attempt_insert(fields: dict[str, Any]) -> str:
        fields = {k: (world["invoice"] if v == "$invoice" else v) for k, v in fields.items()}
        # Cada intento usa un número distinto: la única fila válida que ya existe tiene el 1.
        number = fields.pop("number", uuid.uuid4().int % 900_000 + 2)
        return violated(
            lambda: insert_direct(admin, cast.alicia, world["series"], world["client"], number=number, **fields)
        )

    for fields in bad:
        # Una ordinaria con referencia a otra: la rectificativa solo se rompe en el CHECK que se prueba.
        assert attempt_insert(fields) == constraint, fields
    for fields in good:
        if "number" in fields:
            # el número es la columna que se prueba: cada valor válido va a una serie nueva (en la de `world` ya está el 1)
            fresh = series(admin, cast.alicia, f"S{uuid.uuid4().hex[:5].upper()}")
            assert (
                violated(lambda f=fields, s=fresh: insert_direct(admin, cast.alicia, s, world["client"], **f)) == "ok"
            )
        else:
            assert attempt_insert(fields) == "ok", fields


def test_the_rectifying_checks_by_name(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    # Una rectificativa válida entra.
    assert violated(lambda: rectifying(admin, cast, world)) == "ok"
    # Sin referencia, sin motivo, con la base en positivo, con el IVA en positivo o ya cobrada: cada una rompe una sola restricción.
    assert violated(lambda: rectifying(admin, cast, world, rectifies_id=None)) == "invoices_rectification_ref"
    assert (
        violated(lambda: rectifying(admin, cast, world, rectification_reason=None)) == "invoices_rectification_reason"
    )
    assert (
        violated(lambda: rectifying(admin, cast, world, base_cents=200, total_cents=200))
        == "invoices_rectifying_base_negative"
    )
    assert (
        violated(lambda: rectifying(admin, cast, world, base_cents=0, total_cents=0))
        == "invoices_rectifying_base_negative"
    )
    assert violated(lambda: rectifying(admin, cast, world, vat_cents=1, total_cents=-199)) == "invoices_amounts_sign"
    assert violated(lambda: rectifying(admin, cast, world, irpf_cents=1, total_cents=-201)) == "invoices_amounts_sign"
    assert violated(lambda: rectifying(admin, cast, world, paid_at="2026-03-03")) == "invoices_rectifying_not_paid"
    assert violated(lambda: rectifying(admin, cast, world, rectification_reason="a")) == "invoices_reason_length"
    assert violated(lambda: rectifying(admin, cast, world, rectification_reason="a" * 301)) == "invoices_reason_length"
    assert violated(lambda: rectifying(admin, cast, world, rectification_reason="ab")) == "ok"
    assert violated(lambda: rectifying(admin, cast, world, rectification_reason="a" * 300)) == "ok"


def test_a_number_is_unique_within_a_series_but_not_across_them(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    assert violated(lambda: insert_direct(admin, cast.alicia, world["series"], world["client"], number=1)) == (
        "invoices_owner_series_number_key"
    )
    other = series(admin, cast.alicia, "2027")
    assert violated(lambda: insert_direct(admin, cast.alicia, other, world["client"], number=1)) == "ok"


def test_an_invoice_cannot_hang_from_another_persons_series_client_or_original(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    assert (
        violated(lambda: insert_direct(admin, cast.alicia, world["beto_series"], world["client"], number=7))
        == "invoices_series_fk"
    )
    assert (
        violated(lambda: insert_direct(admin, cast.alicia, world["series"], world["beto_client"], number=7))
        == "invoices_client_fk"
    )
    beto_invoice = insert_direct(admin, cast.beto, world["beto_series"], world["beto_client"])
    assert violated(lambda: rectifying(admin, cast, world, rectifies_id=beto_invoice)) == "invoices_rectifies_fk"


def test_the_invoice_kind_must_be_the_one_of_its_series(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    ordinary = world["series"]
    assert violated(lambda: rectifying(admin, cast, world, series_id=ordinary, number=9)) == "invoices_series_fk"
    rect = series(admin, cast.alicia, "R-2031", kind="rectifying")
    assert violated(lambda: insert_direct(admin, cast.alicia, rect, world["client"], number=7)) == "invoices_series_fk"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"sha256": "A" * 64}, "invoice_files_sha256_format"),
        ({"sha256": "a" * 63}, "invoice_files_sha256_format"),
        ({"sha256": "g" * 64}, "invoice_files_sha256_format"),
        ({"size_bytes": 0}, "invoice_files_size_range"),
        ({"size_bytes": 1_048_577}, "invoice_files_size_range"),
        ({"storage_path": "otra/ruta.pdf"}, "invoice_files_path_matches"),
        ({"owner": "beto"}, "invoice_files_invoice_fk"),
        ({}, "ok"),
        ({"size_bytes": 1}, "ok"),
        ({"size_bytes": 1_048_576}, "ok"),
    ],
)
def test_the_checks_of_invoice_files(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any], change: dict[str, Any], expected: str
) -> None:
    sha = change.get("sha256", "ab" * 32)
    owner = cast.beto if change.get("owner") == "beto" else cast.alicia
    path = change.get("storage_path", f"{owner.id}/{world['invoice']}-{sha[:16]}.pdf")

    def add() -> None:
        admin.execute(
            "insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes) values (%s, %s, %s, %s, %s)",
            (world["invoice"], owner.id, path, sha, change.get("size_bytes", 100)),
        )

    assert violated(add) == expected


def test_an_invoice_has_at_most_one_pdf(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    sha = "cd" * 32
    path = f"{cast.alicia.id}/{world['invoice']}-{sha[:16]}.pdf"
    sql = "insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes) values (%s, %s, %s, %s, 10)"
    admin.execute(sql, (world["invoice"], cast.alicia.id, path, sha))
    assert violated(lambda: admin.execute(sql, (world["invoice"], cast.alicia.id, path, sha))) == "invoice_files_pkey"


# --- Nada cascadea ---------------------------------------------------------------------------------------------------------------------


def test_nothing_cascades_into_or_out_of_an_invoice(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select conrelid::regclass::text as t, conname, confdeltype as d from pg_constraint "
        "where contype = 'f' and connamespace = 'public'::regnamespace and conrelid in ('public.invoices'::regclass, 'public.invoice_files'::regclass) "
        "order by conname"
    ).fetchall()
    assert {r["conname"] for r in rows} == {
        "invoices_owner_id_fkey",
        "invoices_series_fk",
        "invoices_client_fk",
        "invoices_rectifies_fk",
        "invoice_files_invoice_fk",
    }
    assert all(r["d"] == "r" for r in rows), rows  # r = RESTRICT


@pytest.mark.parametrize("what", ["account", "series", "client", "original", "file-owner"])
def test_an_invoice_cannot_lose_its_account_series_client_or_original(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any], what: str
) -> None:
    rect = rectifying(admin, cast, world)
    assert rect
    statements = {
        "account": ("delete from auth.users where id = %s", cast.alicia.id),
        "series": ("delete from public.invoice_series where id = %s", world["series"]),
        "client": ("delete from public.clients where id = %s", world["client"]),
        "original": ("delete from public.invoices where id = %s", world["invoice"]),
        "file-owner": ("delete from public.profiles where id = %s", cast.alicia.id),
    }
    sql, arg = statements[what]
    with pytest.raises(psycopg.Error):
        admin.execute(sql, (arg,))
    count = admin.execute("select count(*) as n from public.invoices where owner_id = %s", (cast.alicia.id,)).fetchone()
    assert count == {"n": 2}


# --- El trigger ------------------------------------------------------------------------------------------------------------------------

ENUM_CHANGES = {
    "kind": "'rectifying'",
    "client_kind": "'individual'",
    "client_scope": "'eu'",
    "tax_treatment": "'eu_reverse_charge'",
}


def changed_value(column: str, data_type: str) -> str:
    """Una expresión SQL que da un valor DISTINTO del actual para la columna (el trigger salta antes que cualquier CHECK o clave)."""
    if column in ENUM_CHANGES:
        return ENUM_CHANGES[column]
    return {
        "text": f"coalesce({column}, '') || 'x'",
        "uuid": "gen_random_uuid()",
        "integer": f"{column} + 1",
        "bigint": f"{column} + 1",
        "numeric": f"{column} + 1",
        "date": f"{column} + 1",
        "timestamp with time zone": f"{column} + interval '1 second'",
    }[data_type]


def all_columns(admin: Connection[DictRow]) -> list[tuple[str, str]]:
    rows = admin.execute(
        "select column_name, data_type from information_schema.columns where table_schema = 'public' and table_name = 'invoices' "
        "order by ordinal_position"
    ).fetchall()
    return [(r["column_name"], r["data_type"] if r["data_type"] != "USER-DEFINED" else "enum") for r in rows]


def test_paid_at_is_the_only_column_that_changes(admin: Connection[DictRow], world: dict[str, Any]) -> None:
    columns = all_columns(admin)
    assert len(columns) == 31, (
        "¿Una columna nueva en `invoices`? Hay que decidir si la inmutabilidad la cubre (y actualizar este test)"
    )
    for column, data_type in columns:
        if column == "paid_at":
            continue
        with pytest.raises(psycopg.errors.RaiseException, match="invoice_immutable"):
            admin.execute(
                f"update public.invoices set {column} = {changed_value(column, data_type)} where id = %s",
                (world["invoice"],),
            )


def test_paid_at_can_be_set_changed_and_cleared(admin: Connection[DictRow], world: dict[str, Any]) -> None:
    for expression in ("now()", "now() + interval '1 day'", "null"):
        admin.execute(f"update public.invoices set paid_at = {expression} where id = %s", (world["invoice"],))
    assert admin.execute("select paid_at from public.invoices where id = %s", (world["invoice"],)).fetchone() == {
        "paid_at": None
    }


def test_an_update_that_changes_nothing_is_allowed(admin: Connection[DictRow], world: dict[str, Any]) -> None:
    out = admin.execute("update public.invoices set concept = concept where id = %s", (world["invoice"],))
    assert out.rowcount == 1


def test_a_change_together_with_paid_at_is_still_refused(admin: Connection[DictRow], world: dict[str, Any]) -> None:
    with pytest.raises(psycopg.errors.RaiseException, match="invoice_immutable"):
        admin.execute("update public.invoices set paid_at = now(), concept = 'otro' where id = %s", (world["invoice"],))
    assert admin.execute("select paid_at from public.invoices where id = %s", (world["invoice"],)).fetchone() == {
        "paid_at": None
    }


@pytest.mark.parametrize("statement", ["delete from public.invoices where id = %s", "delete from public.invoices"])
def test_not_even_the_database_owner_can_delete_an_invoice(
    admin: Connection[DictRow], world: dict[str, Any], statement: str
) -> None:
    args = (world["invoice"],) if "%s" in statement else ()
    with pytest.raises(psycopg.errors.RaiseException, match="invoice_immutable"):
        admin.execute(statement, args)
    assert admin.execute("select count(*) as n from public.invoices where id = %s", (world["invoice"],)).fetchone() == {
        "n": 1
    }


def test_not_even_the_database_owner_can_truncate(admin: Connection[DictRow], world: dict[str, Any]) -> None:
    # Sin `cascade`, PostgreSQL ya se niega a vaciar una tabla a la que apunta una clave foránea; con él, es el trigger quien lo impide.
    with pytest.raises(psycopg.errors.FeatureNotSupported):
        admin.execute("truncate public.invoices")
    for table in ("public.invoice_files", "public.invoices cascade", "public.invoices, public.invoice_files"):
        with pytest.raises(psycopg.errors.RaiseException, match="invoice_immutable"):
            admin.execute(f"truncate {table}")
    assert admin.execute("select count(*) as n from public.invoices where id = %s", (world["invoice"],)).fetchone() == {
        "n": 1
    }


def test_the_truncate_trigger_of_invoices_works_on_its_own(admin: Connection[DictRow], world: dict[str, Any]) -> None:
    """Con `cascade`, el trigger de `invoice_files` ya impide el vaciado; sin él, ha de impedirlo igualmente el de `invoices`."""
    admin.execute("alter table public.invoice_files disable trigger invoice_files_no_truncate")
    try:
        with pytest.raises(psycopg.errors.RaiseException, match="invoice_immutable"):
            admin.execute("truncate public.invoices cascade")
    finally:
        admin.execute("alter table public.invoice_files enable trigger invoice_files_no_truncate")
    assert admin.execute("select count(*) as n from public.invoices where id = %s", (world["invoice"],)).fetchone() == {
        "n": 1
    }


def test_service_role_cannot_change_an_invoice(service_pool: Pool, cast: Cast, world: dict[str, Any]) -> None:
    for statement in (
        "update public.invoices set concept = 'x'",
        "delete from public.invoices",
        "truncate public.invoices",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), service_transaction(service_pool) as conn:
            conn.execute(statement)


def test_the_pdf_record_is_append_only(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    sha = "ef" * 32
    admin.execute(
        "insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes) values (%s, %s, %s, %s, 10)",
        (world["invoice"], cast.alicia.id, f"{cast.alicia.id}/{world['invoice']}-{sha[:16]}.pdf", sha),
    )
    for statement in (
        "update public.invoice_files set size_bytes = 11",
        "update public.invoice_files set size_bytes = size_bytes",
        "delete from public.invoice_files",
        "truncate public.invoice_files",
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="invoice_immutable"):
            admin.execute(statement)
    assert admin.execute(
        "select size_bytes from public.invoice_files where invoice_id = %s", (world["invoice"],)
    ).fetchone() == {"size_bytes": 10}


# --- Tipos y valores por defecto ---------------------------------------------------------------------------------------------------------


def test_the_enum_labels_are_the_ones_of_the_spec(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select t.typname as name, array_agg(e.enumlabel order by e.enumsortorder) as labels from pg_enum e "
        "join pg_type t on t.oid = e.enumtypid where t.typname in ('invoice_kind', 'invoice_tax_treatment') group by 1 order by 1"
    ).fetchall()
    assert rows == [
        {"name": "invoice_kind", "labels": ["standard", "rectifying"]},
        {
            "name": "invoice_tax_treatment",
            "labels": [
                "national_vat",
                "eu_reverse_charge",
                "eu_consumer_vat",
                "non_eu_consumer_vat",
                "non_eu_not_subject",
            ],
        },
    ]


def test_an_invoice_starts_unpaid_without_vat_or_retention_and_with_its_creation_time(
    admin: Connection[DictRow], world: dict[str, Any]
) -> None:
    row = admin.execute("select * from public.invoices where id = %s", (world["invoice"],)).fetchone()
    assert row is not None
    assert (
        row["paid_at"],
        row["vat_rate"],
        row["vat_cents"],
        row["irpf_rate"],
        row["irpf_cents"],
        row["legal_note"],
    ) == (
        None,
        0,
        0,
        0,
        0,
        None,
    )
    assert row["created_at"] is not None and row["issue_date"] == D1


def test_the_index_for_the_list_exists(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select indexname, indexdef from pg_indexes where schemaname = 'public' and tablename = 'invoices' and indexname like 'invoices_%%'"
    ).fetchall()
    defs = {r["indexname"]: r["indexdef"] for r in rows}
    assert "(owner_id, issue_date DESC, id)" in defs["invoices_owner_date"]
    assert "WHERE (rectifies_id IS NOT NULL)" in defs["invoices_rectifies"]
