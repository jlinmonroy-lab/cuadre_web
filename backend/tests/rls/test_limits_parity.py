"""T5-03 · Una fuente por regla: lo que dice `cuadre.profile.limits` y lo que impone la base son lo mismo (SPEC-W-005 §5.2).

Las fronteras salen de las constantes del dominio y se comprueban contra los CHECK: si alguien cambia un número en un sitio y no en el otro,
falla aquí. Es la prueba que dejó anotada B.2 para el hito 2.
"""

from datetime import date
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.profile import limits, normalize_series_code, year_series_code
from tests.support import Cast, Person

GOOD_UUID = "0123abcd-4567-89ab-cdef-0123456789ab"


def accepted(admin: Connection[DictRow], person: Person, column: str, value: Any) -> bool:
    try:
        admin.execute(f"update public.business_profiles set {column} = %s where owner_id = %s", (value, person.id))
        return True
    except psycopg.errors.CheckViolation:
        return False


@pytest.mark.parametrize(
    ("column", "low", "high"),
    [
        ("legal_name", limits.LEGAL_NAME_MIN, limits.LEGAL_NAME_MAX),
        ("fiscal_address", limits.FISCAL_ADDRESS_MIN, limits.FISCAL_ADDRESS_MAX),
    ],
)
def test_the_required_text_bounds_are_the_domains(
    admin: Connection[DictRow], cast: Cast, column: str, low: int, high: int
) -> None:
    assert not accepted(admin, cast.alicia, column, "a" * (low - 1))
    assert accepted(admin, cast.alicia, column, "a" * low)
    assert accepted(admin, cast.alicia, column, "a" * high)
    assert not accepted(admin, cast.alicia, column, "a" * (high + 1))


def test_the_activity_and_iae_bounds_are_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    assert accepted(admin, cast.alicia, "activity", "a" * limits.ACTIVITY_MAX)
    assert not accepted(admin, cast.alicia, "activity", "a" * (limits.ACTIVITY_MAX + 1))
    iae_max = int(limits.IAE_RAW.pattern.rsplit(",", 1)[1].rstrip("}"))
    assert accepted(admin, cast.alicia, "iae_epigraph", "a" * iae_max)
    assert not accepted(admin, cast.alicia, "iae_epigraph", "a" * (iae_max + 1))


def test_the_allowed_retentions_are_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    for rate in limits.IRPF_RATES:
        assert accepted(admin, cast.alicia, "irpf_rate", rate)
    for rate in (
        min(limits.IRPF_RATES) - 1,
        max(limits.IRPF_RATES) + 1,
        (min(limits.IRPF_RATES) + max(limits.IRPF_RATES)) / 2,
    ):
        assert not accepted(admin, cast.alicia, "irpf_rate", rate), rate


def test_the_only_regime_is_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    assert accepted(admin, cast.alicia, "vat_regime", limits.REGIME)
    assert not accepted(admin, cast.alicia, "vat_regime", limits.REGIME.upper())


def test_the_logo_extensions_are_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    for ext in limits.LOGO_TYPES.values():
        assert accepted(admin, cast.alicia, "logo_path", f"{cast.alicia.id}/{GOOD_UUID}.{ext}"), ext
    assert not accepted(admin, cast.alicia, "logo_path", f"{cast.alicia.id}/{GOOD_UUID}.svg")


def test_the_logo_bucket_limits_are_the_domains(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select public, file_size_limit, allowed_mime_types from storage.buckets where id = 'logos'"
    ).fetchone()
    assert row is not None
    assert row["public"] is False
    assert row["file_size_limit"] == limits.LOGO_MAX_BYTES
    assert sorted(row["allowed_mime_types"]) == sorted(limits.LOGO_TYPES)


CODES = [
    "2026", "A", "AB", "FAC", "F-1", "ABCDEFGH", "A-B-C-D", "R-2026",
    "", "-A", "A-", "ABCDEFGHI", "fac", "AB CD", "A_B", "Ñ", "A\n", "٣", "--", "ß", "ı",
]  # fmt: skip


@pytest.mark.parametrize("code", CODES)
def test_the_series_code_pattern_is_the_domains(admin: Connection[DictRow], code: str) -> None:
    """La base exige mayúsculas; el dominio acepta minúsculas y las pasa a mayúsculas. Lo que el dominio da por bueno, la base lo admite."""
    row = admin.execute("select %s ~ '^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$' as ok", (code,)).fetchone()
    assert row is not None
    normalized = normalize_series_code(code)
    if normalized is not None:
        assert row["ok"] or code != normalized  # sin pasar a mayúsculas, solo las ya mayúsculas pasan
        ok_after = admin.execute("select %s ~ '^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$' as ok", (normalized,)).fetchone()
        assert ok_after is not None and ok_after["ok"]
    else:
        assert row["ok"] is False


def test_the_series_numeric_bounds_are_the_domains(admin: Connection[DictRow]) -> None:
    ranges = admin.execute(
        "select pg_get_constraintdef(oid) as d from pg_constraint where conname = 'invoice_series_first_number_range'"
    ).fetchone()
    assert ranges is not None
    assert str(limits.SERIES_FIRST_NUMBER_MIN) in ranges["d"] and str(limits.SERIES_FIRST_NUMBER_MAX) in ranges["d"]
    description = admin.execute(
        "select pg_get_constraintdef(oid) as d from pg_constraint where conname = 'invoice_series_description_length'"
    ).fetchone()
    assert description is not None and str(limits.SERIES_DESCRIPTION_MAX) in description["d"]


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        ("2026-11-07 12:00:00+00", date(2026, 11, 7)),
        ("2026-12-31 22:59:59+00", date(2026, 12, 31)),  # 23:59:59 en Madrid
        ("2026-12-31 23:00:00+00", date(2027, 1, 1)),  # medianoche en Madrid
        ("2026-12-31 23:30:00+00", date(2027, 1, 1)),
        ("2027-06-30 22:30:00+00", date(2027, 7, 1)),  # horario de verano
    ],
)
def test_the_year_series_code_matches_the_sql_expression_at_the_madrid_boundary(
    admin: Connection[DictRow], instant: str, expected: date
) -> None:
    """`ensure_year_series` usa `to_char(private.today_madrid(), 'YYYY')`; `today_madrid()` es `(now() at time zone 'Europe/Madrid')::date`."""
    row = admin.execute(
        "select to_char((%s::timestamptz at time zone 'Europe/Madrid')::date, 'YYYY') as year, (%s::timestamptz at time zone 'Europe/Madrid')::date as d",
        (instant, instant),
    ).fetchone()
    assert row is not None and row["d"] == expected
    assert row["year"] == year_series_code(expected)
