"""AC-05, AC-08, AC-17 · Los CHECK nuevos de `business_profiles` y el privilegio de `logo_path` (SPEC-W-005 §5.2, D-13, D-14).

Se escribe directamente como dueño de la base de datos para demostrar que ni una CHECK ni el `REVOKE` dependen de que la API se porte bien. Cada
violación se identifica por el NOMBRE de la restricción: la API la traducirá por nombre (hito 3). No hay CHECK de NIF ni de IBAN (D-14).
"""

import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Person, Pool, attempt

TABLE = "public.business_profiles"
GOOD_UUID = "0123abcd-4567-89ab-cdef-0123456789ab"


def write(admin: Connection[DictRow], person: Person, column: str, value: Any) -> None:
    admin.execute(f"update {TABLE} set {column} = %s where owner_id = %s", (value, person.id))


def violated(admin: Connection[DictRow], person: Person, column: str, value: Any) -> str:
    with pytest.raises(psycopg.errors.CheckViolation) as info:
        write(admin, person, column, value)
    return info.value.diag.constraint_name or ""


def logo(person: Person, name: str) -> str:
    return f"{person.id}/{name}"


# --- Las CHECK, una a una -----------------------------------------------------------------------------------------------------------

VIOLATIONS = [
    ("irpf_rate", 10, "business_profiles_irpf_rate_allowed"),
    ("irpf_rate", 0, "business_profiles_irpf_rate_allowed"),
    ("irpf_rate", 7.5, "business_profiles_irpf_rate_allowed"),
    ("irpf_rate", 15.01, "business_profiles_irpf_rate_allowed"),
    ("vat_regime", "recargo", "business_profiles_vat_regime_general"),
    ("vat_regime", "", "business_profiles_vat_regime_general"),
    ("vat_regime", "General", "business_profiles_vat_regime_general"),
    ("legal_name", "x", "business_profiles_legal_name_length"),
    ("legal_name", "", "business_profiles_legal_name_length"),
    ("legal_name", "a" * 201, "business_profiles_legal_name_length"),
    ("fiscal_address", "abcd", "business_profiles_fiscal_address_length"),
    ("fiscal_address", "a" * 301, "business_profiles_fiscal_address_length"),
    ("activity", "a" * 201, "business_profiles_activity_length"),
    ("iae_epigraph", "<script>", "business_profiles_iae_epigraph_format"),
    ("iae_epigraph", "a" * 21, "business_profiles_iae_epigraph_format"),
    ("iae_epigraph", "", "business_profiles_iae_epigraph_format"),
    ("iae_epigraph", "8\n44", "business_profiles_iae_epigraph_format"),
    ("iae_epigraph", "844.1\n", "business_profiles_iae_epigraph_format"),
]
ACCEPTED = [
    ("irpf_rate", 7),
    ("irpf_rate", 15),
    ("irpf_rate", None),
    ("vat_regime", "general"),
    ("legal_name", "ab"),
    ("legal_name", "a" * 200),
    ("legal_name", None),
    ("fiscal_address", "abcde"),
    ("fiscal_address", "a" * 300),
    ("activity", "a" * 200),
    ("activity", None),
    ("iae_epigraph", "844.1"),
    ("iae_epigraph", "8 44"),
    ("iae_epigraph", "A-1"),
    ("iae_epigraph", "a" * 20),
    ("iae_epigraph", None),
    ("tax_id", "TEST-0001"),  # sin CHECK de NIF (D-14): lo valida Python
    ("tax_id", "esto no es un NIF"),
    ("iban", "ES00 no es un IBAN"),  # ni de IBAN
]


@pytest.mark.parametrize(("column", "value", "constraint"), VIOLATIONS)
def test_each_check_rejects_its_values_by_name(
    admin: Connection[DictRow], cast: Cast, column: str, value: Any, constraint: str
) -> None:
    assert violated(admin, cast.alicia, column, value) == constraint


@pytest.mark.parametrize(("column", "value"), ACCEPTED)
def test_each_check_accepts_what_it_should(admin: Connection[DictRow], cast: Cast, column: str, value: Any) -> None:
    write(admin, cast.alicia, column, value)
    row = admin.execute(f"select {column} as v from {TABLE} where owner_id = %s", (cast.alicia.id,)).fetchone()
    assert row is not None and (row["v"] == value or str(row["v"]) == str(value) or value is None)


def test_the_retention_check_does_not_replace_the_old_range_check(admin: Connection[DictRow]) -> None:
    names = {
        r["conname"]
        for r in admin.execute(
            "select conname from pg_constraint where conrelid = 'public.business_profiles'::regclass and contype = 'c'"
        ).fetchall()
    }
    assert {
        "business_profiles_irpf_rate_check",  # 0 a 100 (SPEC-W-001)
        "business_profiles_home_pct_check",
        "business_profiles_irpf_rate_allowed",
        "business_profiles_vat_regime_general",
        "business_profiles_legal_name_length",
        "business_profiles_fiscal_address_length",
        "business_profiles_activity_length",
        "business_profiles_iae_epigraph_format",
        "business_profiles_logo_path_format",
    } <= names


# --- La ruta del logo ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ext", ["png", "jpg", "webp"])
def test_the_logo_path_accepts_the_owners_folder_and_the_three_extensions(
    admin: Connection[DictRow], cast: Cast, ext: str
) -> None:
    write(admin, cast.alicia, "logo_path", logo(cast.alicia, f"{GOOD_UUID}.{ext}"))


def test_the_logo_path_may_be_empty(admin: Connection[DictRow], cast: Cast) -> None:
    write(admin, cast.alicia, "logo_path", logo(cast.alicia, f"{GOOD_UUID}.png"))
    write(admin, cast.alicia, "logo_path", None)


@pytest.mark.parametrize(
    "name",
    [
        f"{GOOD_UUID}.svg",
        f"{GOOD_UUID}.gif",
        f"{GOOD_UUID}.PNG",
        "logo.png",
        f"x/{GOOD_UUID}.png",
        f"{GOOD_UUID.upper()}.png",
        f"{GOOD_UUID}.png\n",
        f"{GOOD_UUID}.png/",
        ".png",
        "",
    ],
)
def test_the_logo_path_rejects_anything_else_in_the_owners_folder(
    admin: Connection[DictRow], cast: Cast, name: str
) -> None:
    assert violated(admin, cast.alicia, "logo_path", logo(cast.alicia, name)) == "business_profiles_logo_path_format"


def test_the_logo_path_rejects_another_persons_folder(admin: Connection[DictRow], cast: Cast) -> None:
    other = f"{cast.beto.id}/{GOOD_UUID}.png"
    assert violated(admin, cast.alicia, "logo_path", other) == "business_profiles_logo_path_format"
    assert (
        violated(admin, cast.alicia, "logo_path", f"{uuid.uuid4()}/{GOOD_UUID}.png")
        == "business_profiles_logo_path_format"
    )


# --- El privilegio de `logo_path` (D-13) ------------------------------------------------------------------------------------------------


EDITABLE = [
    "legal_name",
    "tax_id",
    "fiscal_address",
    "activity",
    "iae_epigraph",
    "activity_start_date",
    "vat_regime",
    "irpf_rate",
    "iban",
    "home_pct",
]


def can_update(admin: Connection[DictRow], role: str, column: str) -> bool:
    row = admin.execute(
        "select has_column_privilege(%s, 'public.business_profiles', %s, 'UPDATE') as ok", (role, column)
    ).fetchone()
    assert row is not None
    return bool(row["ok"])


def test_authenticated_can_edit_ten_columns_and_not_logo_path(admin: Connection[DictRow]) -> None:
    assert [c for c in EDITABLE if not can_update(admin, "authenticated", c)] == []
    assert can_update(admin, "authenticated", "logo_path") is False
    assert can_update(admin, "authenticated", "owner_id") is False
    assert can_update(admin, "authenticated", "updated_at") is False


def test_nobody_else_can_edit_logo_path(admin: Connection[DictRow]) -> None:
    for role in ("anon", "service_role", "public"):
        assert can_update(admin, role, "logo_path") is False, role


def test_the_owner_cannot_write_logo_path_directly_but_can_write_the_rest(app_pool: Pool, cast: Cast) -> None:
    path = logo(cast.alicia, f"{GOOD_UUID}.png")
    out = attempt(
        app_pool,
        cast.alicia,
        "update public.business_profiles set logo_path = %s where owner_id = %s",
        (path, cast.alicia.id),
    )
    assert out.sqlstate == "42501"
    out = attempt(
        app_pool,
        cast.alicia,
        "update public.business_profiles set iban = %s where owner_id = %s",
        ("ES3600000000050000000001", cast.alicia.id),
    )
    assert not out.error and out.rowcount == 1


def test_nobody_else_writes_the_profile_not_even_the_gestor_or_the_admin(app_pool: Pool, cast: Cast) -> None:
    """`legal_name = 'x'` incumple la CHECK, pero la RLS filtra antes: una gestora afecta a 0 filas y el CHECK ni se evalúa (B.1)."""
    for who in (cast.gina, cast.adan, cast.beto):
        out = attempt(
            app_pool, who, "update public.business_profiles set legal_name = 'x' where owner_id = %s", (cast.alicia.id,)
        )
        assert not out.error and out.rowcount == 0, who.key
    out = attempt(
        app_pool,
        cast.alicia,
        "update public.business_profiles set legal_name = 'x' where owner_id = %s",
        (cast.alicia.id,),
    )
    assert out.sqlstate == "23514" and out.constraint == "business_profiles_legal_name_length"
    out = attempt(
        app_pool,
        cast.alicia,
        "update public.business_profiles set legal_name = 'Alicia Demo' where owner_id = %s",
        (cast.alicia.id,),
    )
    assert not out.error and out.rowcount == 1


def test_the_existing_seeds_values_still_satisfy_every_check(admin: Connection[DictRow]) -> None:
    """Las filas que había (retenciones 7 y 15, régimen general) caben en las CHECK nuevas: la migración las validó al crearlas."""
    bad = admin.execute(
        "select count(*) as n from public.business_profiles where irpf_rate is not null and irpf_rate not in (7, 15)"
    ).fetchone()
    assert bad is not None and bad["n"] == 0
