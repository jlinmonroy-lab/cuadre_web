"""T7-02 / AC-24 · Una fuente por regla: lo que dicen `cuadre.invoicing` y `cuadre.tax` y lo que impone la base son lo mismo (SPEC-W-007 §5.2).

Las fronteras salen de las constantes del dominio y se comprueban contra los CHECK, las funciones y las políticas del bucket: si alguien cambia un
número en un sitio y no en el otro, falla aquí. Es la prueba que dejó anotada B.2 para el hito 2.
"""

import uuid
from datetime import date
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.invoicing import (
    invoice_pdf_path,
    is_reserved_series_code,
    pdf_path_owner,
    rectifying_series_code,
)
from cuadre.invoicing import limits as inv
from cuadre.profile import limits as profile_limits
from cuadre.tax import TREATMENTS, VAT_RATES
from cuadre.validators.limits import EARLIEST_DATE
from tests.rls.invoices_support import client, code_of, insert_direct, issue, made, prepare, ready, series, terms
from tests.support import Cast, Pool, call

SHA = "0123456789abcdef" * 4


@pytest.fixture
def world(admin: Connection[DictRow], cast: Cast) -> dict[str, Any]:
    serie = prepare(admin, cast.alicia)
    return {"series": serie, "client": client(admin, cast.alicia)}


def fits(admin: Connection[DictRow], cast: Cast, world: dict[str, Any], **fields: Any) -> bool:
    """¿Admite la tabla una factura ordinaria válida con estos cambios? Cada intento va a una serie nueva: el número no choca."""
    fresh = series(admin, cast.alicia, f"S{uuid.uuid4().hex[:6].upper()}")
    try:
        insert_direct(admin, cast.alicia, fresh, world["client"], **fields)
    except psycopg.errors.CheckViolation:
        return False
    return True


# --- Texto ---------------------------------------------------------------------------------------------------------------------------------


def test_the_concept_bounds_are_the_domains(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    low, high = inv.CONCEPT_MIN, inv.CONCEPT_MAX
    assert not fits(admin, cast, world, concept="a" * (low - 1))
    assert fits(admin, cast, world, concept="a" * low)
    assert fits(admin, cast, world, concept="ñ" * high)  # se cuentan caracteres, no bytes
    assert not fits(admin, cast, world, concept="a" * (high + 1))


def test_the_reason_bounds_are_the_domains(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    original = insert_direct(admin, cast.alicia, world["series"], world["client"])

    def accepted(reason: str) -> bool:
        rect = series(admin, cast.alicia, f"R-{uuid.uuid4().int % 9000 + 1000}", kind="rectifying")
        try:
            insert_direct(
                admin,
                cast.alicia,
                rect,
                world["client"],
                kind="rectifying",
                rectifies_id=original,
                rectification_reason=reason,
                base_cents=-1,
                total_cents=-1,
            )
        except psycopg.errors.CheckViolation:
            return False
        return True

    low, high = inv.REASON_MIN, inv.REASON_MAX
    assert not accepted("a" * (low - 1))
    assert accepted("a" * low)
    assert accepted("ñ" * high)
    assert not accepted("a" * (high + 1))


# --- Importes y número --------------------------------------------------------------------------------------------------------------------


def test_the_base_bounds_are_the_domains(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    def base(value: int) -> dict[str, int]:
        return {"base_cents": value, "total_cents": value}

    assert not fits(admin, cast, world, **base(inv.BASE_MIN - 1))
    assert fits(admin, cast, world, **base(inv.BASE_MIN))
    assert fits(admin, cast, world, **base(inv.BASE_MAX))
    assert not fits(admin, cast, world, **base(inv.BASE_MAX + 1))


def test_the_base_bounds_are_also_the_functions(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    r = ready(admin, cast.alicia)
    cid = r.clients[("eu", "business")]  # sin IVA ni retención: el total es la base
    for value, expected in (
        (inv.BASE_MIN - 1, False),
        (inv.BASE_MIN, True),
        (inv.BASE_MAX, True),
        (inv.BASE_MAX + 1, False),
    ):
        given = {**terms("eu", "business", max(value, 1)), "total_cents": value}
        out = issue(app_pool, cast.alicia, cid, r.series, base=value, scope="eu", kind="business", given=given)
        assert (not out.error) is expected, (value, out.message, out.detail)
        if not expected:
            assert (code_of(out), out.detail) == ("invalid_invoice", "base_cents")


def test_the_number_bounds_are_the_domains(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    assert not fits(admin, cast, world, number=inv.NUMBER_MIN - 1)
    assert fits(admin, cast, world, number=inv.NUMBER_MIN)
    assert fits(admin, cast, world, number=inv.NUMBER_MAX)
    assert not fits(admin, cast, world, number=inv.NUMBER_MAX + 1)


def test_the_series_counter_can_go_one_past_the_last_number(admin: Connection[DictRow], cast: Cast) -> None:
    """`next_number` admite hasta 1.000.000: tras emitir el 999.999 el contador no rompe la CHECK de la serie."""
    top = series(admin, cast.alicia, "TOP", first=inv.NUMBER_MAX)
    admin.execute("update public.invoice_series set next_number = %s where id = %s", (inv.NUMBER_MAX + 1, top))


def test_the_vat_rates_are_the_domains_plus_zero(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    allowed = {0, *(int(rate) for rate in VAT_RATES)}
    for rate in range(0, 25):
        assert fits(admin, cast, world, vat_rate=rate) is (rate in allowed), rate


def test_the_retention_rates_are_the_profiles_plus_zero(
    admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    allowed = {0, *(int(rate) for rate in profile_limits.IRPF_RATES)}
    for rate in range(0, 25):
        assert fits(admin, cast, world, irpf_rate=rate) is (rate in allowed), rate


def test_the_earliest_date_is_the_domains(admin: Connection[DictRow], cast: Cast, world: dict[str, Any]) -> None:
    assert not fits(admin, cast, world, issue_date=date.fromordinal(EARLIEST_DATE.toordinal() - 1))
    assert fits(admin, cast, world, issue_date=EARLIEST_DATE)


# --- Enums -------------------------------------------------------------------------------------------------------------------------------


def labels(admin: Connection[DictRow], enum: str) -> list[str]:
    rows = admin.execute(
        "select e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid where t.typname = %s order by e.enumsortorder",
        (enum,),
    ).fetchall()
    return [r["enumlabel"] for r in rows]


def test_the_treatments_are_the_domains(admin: Connection[DictRow]) -> None:
    assert labels(admin, "invoice_tax_treatment") == list(TREATMENTS)


def test_the_series_kinds_are_the_domains(admin: Connection[DictRow]) -> None:
    assert labels(admin, "invoice_kind") == list(inv.SERIES_KINDS)


# --- La serie rectificativa ----------------------------------------------------------------------------------------------------------------

CODES = [
    "R-2026", "R-0000", "R-9999", "R-26", "R-202", "R-20266", "R-ABCD", "R2026", "r-2026", "XR-2026", "R-2026A", "R-٢٠٢٦", "R-２０２６",
    "R-2026\n", "",
]  # fmt: skip


@pytest.mark.parametrize("code", CODES)
def test_the_reserved_code_pattern_is_the_domains(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, code: str
) -> None:
    """Lo que el dominio llama reservado, la base lo rechaza al crear una serie ordinaria; lo demás, si tiene formato válido, entra."""
    out = call(app_pool, cast.alicia, "create_invoice_series", code, None, None, False)
    in_db_reserved = out.sqlstate == "P0001" and out.message == "series_code_reserved"
    assert in_db_reserved is is_reserved_series_code(code), (code, out.message)


@pytest.mark.parametrize("year", [2000, 2026, 2099, 9999])
def test_the_yearly_code_is_the_one_the_database_makes(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, year: int
) -> None:
    sid = made(call(app_pool, cast.alicia, "ensure_rectifying_series", year))
    row = admin.execute("select code, kind from public.invoice_series where id = %s", (sid,)).fetchone()
    assert row == {"code": rectifying_series_code(year), "kind": "rectifying"}
    assert is_reserved_series_code(row["code"])


# --- El PDF ------------------------------------------------------------------------------------------------------------------------------


def test_the_pdf_hash_prefix_and_path_are_the_domains(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    original = insert_direct(admin, cast.alicia, world["series"], world["client"])
    path = invoice_pdf_path(str(cast.alicia.id), str(original), SHA)
    assert not call(app_pool, cast.alicia, "attach_invoice_pdf", original, path, SHA, 100).error
    assert admin.execute(
        "select storage_path from public.invoice_files where invoice_id = %s", (original,)
    ).fetchone() == {"storage_path": path}
    assert inv.PDF_PATH.fullmatch(path) is not None and path.split("-")[-1] == SHA[: inv.PDF_HASH_PREFIX] + ".pdf"


def paths(owner: uuid.UUID) -> list[str]:
    inv_id, other = uuid.uuid4(), uuid.uuid4()
    good = f"{owner}/{inv_id}-{SHA[:16]}.pdf"
    return [
        good,
        good.upper(),
        good.replace(".pdf", ".PDF"),
        good.replace(".pdf", ".png"),
        good.replace("-" + SHA[:16], "-" + SHA[:15]),
        good.replace("-" + SHA[:16], "-" + SHA[:16].upper()),
        good.replace("-" + SHA[:16], "-" + SHA[:17]),
        good.replace("-" + SHA[:16], "-" + "G" * 16),
        good.replace("-" + SHA[:16], ""),
        good + "/",
        "x/" + good,
        f"{owner}/{inv_id}/{other}-{SHA[:16]}.pdf",
        f"{owner}/{inv_id}.pdf",
        f"not-a-uuid/{inv_id}-{SHA[:16]}.pdf",
        f"{owner}/not-a-uuid-{SHA[:16]}.pdf",
        f"{owner}/{inv_id}-{SHA[:16]}.pdf\n",
        "",
        "/",
    ]


def test_the_bucket_folder_rule_is_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    """`private.invoice_file_folder_owner` y `cuadre.invoicing.pdf_path_owner` reconocen exactamente las mismas rutas (y ninguna lanza)."""
    for path in paths(cast.alicia.id):
        row = admin.execute("select private.invoice_file_folder_owner(%s) as owner", (path,)).fetchone()
        assert row is not None
        domain = pdf_path_owner(path)
        assert (str(row["owner"]) if row["owner"] else None) == domain, repr(path)


def test_the_files_check_accepts_the_domains_path_and_nothing_else(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    original = insert_direct(admin, cast.alicia, world["series"], world["client"])
    good = invoice_pdf_path(str(cast.alicia.id), str(original), SHA)
    sql = "insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes) values (%s, %s, %s, %s, 10)"
    for path in (good.upper(), good.replace(".pdf", ".png"), good.replace("-" + SHA[:16], "-" + SHA[:15])):
        with pytest.raises(psycopg.errors.CheckViolation):
            admin.execute(sql, (original, cast.alicia.id, path, SHA))
    admin.execute(sql, (original, cast.alicia.id, good, SHA))


def test_the_size_limit_is_the_buckets(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, world: dict[str, Any]
) -> None:
    bucket = admin.execute(
        "select public, file_size_limit, allowed_mime_types from storage.buckets where id = 'invoices'"
    ).fetchone()
    assert bucket == {"public": False, "file_size_limit": 1_048_576, "allowed_mime_types": ["application/pdf"]}
    original = insert_direct(admin, cast.alicia, world["series"], world["client"])
    path = invoice_pdf_path(str(cast.alicia.id), str(original), SHA)
    too_big = call(app_pool, cast.alicia, "attach_invoice_pdf", original, path, SHA, bucket["file_size_limit"] + 1)
    assert (code_of(too_big), too_big.detail) == ("invalid_invoice", "size_bytes")
    assert not call(app_pool, cast.alicia, "attach_invoice_pdf", original, path, SHA, bucket["file_size_limit"]).error
