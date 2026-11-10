"""SQL del perfil, las series y el logo (SQL explícito, sin ORM; ADR-0003). Toda escritura de series y de logo pasa por `app.*`.

Las funciones reciben una conexión que ya lleva la identidad de la persona (`user_transaction`). `translate_db_error` traduce los errores
con código estable de §5.2 («Para el hito 3» del Anexo B.3); lo que no se reconoce se propaga y la API lo responde como un 500 sin detalles:
son errores de construcción (`changes`, `archived`), de trigger o de base que la validación previa debería haber impedido.
"""

from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.core.errors import ProblemError, forbidden
from cuadre.profile import errors
from cuadre.profile.series import MESSAGES as SERIES_MESSAGES
from cuadre.profile.types import ProfileValues

PROFILE_COLUMNS = (
    "legal_name, tax_id, fiscal_address, activity, iae_epigraph, activity_start_date, vat_regime, irpf_rate, home_pct, iban, "
    "(logo_path IS NOT NULL) AS has_logo, updated_at"
)
SERIES_COLUMNS = (
    "id, code, description, first_number, next_number, is_default, (archived_at IS NOT NULL) AS archived, "
    "(next_number > first_number) AS in_use, created_at"
)

_PLAIN = {
    "series_not_found": errors.series_not_found,
    "series_code_taken": errors.series_code_taken,
    "series_in_use": errors.series_in_use,
    "series_is_default": errors.series_is_default,
    "series_archived": errors.series_archived,
    "invalid_logo": errors.logo_invalid,
}
# `invalid_series` solo llega con estos campos si la API dejó pasar algo que había validado; `changes` y `archived` son un error nuestro.
_SERIES_FIELDS = {"code", "description", "first_number"}
_UNIQUE = {"invoice_series_owner_code_key": errors.series_code_taken}


def translate_db_error(exc: psycopg.Error) -> ProblemError | None:
    """Errores con código estable de las funciones `app.*` -> problem+json. `None` si no es uno de ellos (se propaga: 500)."""
    if exc.sqlstate == "42501":
        return forbidden()
    message = exc.diag.message_primary or ""
    if exc.sqlstate == "P0001":
        if message == "series_code_reserved":
            return errors.invalid_series("code", SERIES_MESSAGES["code_reserved"])
        if message == "invalid_series":
            field = (exc.diag.message_detail or "").strip()
            if field in _SERIES_FIELDS:
                return errors.invalid_series(field, SERIES_MESSAGES[field])
            return None
        factory = _PLAIN.get(message)
        return factory() if factory is not None else None
    if exc.sqlstate == "23505":
        factory = _UNIQUE.get(exc.diag.constraint_name or "")
        return factory() if factory is not None else None
    return None


# --- Perfil ---------------------------------------------------------------------------------------------------------------------


def get_profile(conn: Connection[DictRow]) -> DictRow | None:
    return conn.execute(
        f"SELECT {PROFILE_COLUMNS} FROM public.business_profiles WHERE owner_id = (SELECT auth.uid())"
    ).fetchone()


def update_profile(conn: Connection[DictRow], values: ProfileValues) -> None:
    """Las diez columnas editables (nunca `logo_path`). 0 filas = la persona no tiene perfil: error nuestro."""
    cursor = conn.execute(
        "UPDATE public.business_profiles SET legal_name = %(legal_name)s, tax_id = %(tax_id)s, "
        "fiscal_address = %(fiscal_address)s, activity = %(activity)s, iae_epigraph = %(iae_epigraph)s, "
        "activity_start_date = %(activity_start_date)s, vat_regime = %(vat_regime)s, irpf_rate = %(irpf_rate)s, "
        "home_pct = %(home_pct)s, iban = %(iban)s WHERE owner_id = (SELECT auth.uid())",
        {
            "legal_name": values.legal_name,
            "tax_id": values.tax_id,
            "fiscal_address": values.fiscal_address,
            "activity": values.activity,
            "iae_epigraph": values.iae_epigraph,
            "activity_start_date": values.activity_start_date,
            "vat_regime": values.vat_regime,
            "irpf_rate": values.irpf_rate,
            "home_pct": values.home_pct,
            "iban": values.iban,
        },
    )
    if cursor.rowcount != 1:
        raise LookupError("profile_not_found")


def ensure_year_series(conn: Connection[DictRow]) -> None:
    conn.execute("SELECT app.ensure_year_series()")


def set_logo(conn: Connection[DictRow], path: str) -> str | None:
    """Guarda la ruta y devuelve la anterior (o `None`) para borrar ese objeto."""
    row = conn.execute("SELECT app.set_business_logo(%s) AS previous", (path,)).fetchone()
    assert row is not None
    return row["previous"]


def clear_logo(conn: Connection[DictRow]) -> str | None:
    row = conn.execute("SELECT app.clear_business_logo() AS previous").fetchone()
    assert row is not None
    return row["previous"]


def logo_path(conn: Connection[DictRow]) -> str | None:
    row = conn.execute("SELECT logo_path FROM public.business_profiles WHERE owner_id = (SELECT auth.uid())").fetchone()
    return None if row is None else row["logo_path"]


# --- Series ---------------------------------------------------------------------------------------------------------------------


def list_series(conn: Connection[DictRow]) -> list[DictRow]:
    """La predeterminada primero y después por código; incluye las archivadas y no las rectificativas `R-AAAA` (SPEC-W-007: las crea la emisión)."""
    return conn.execute(
        f"SELECT {SERIES_COLUMNS} FROM public.invoice_series WHERE owner_id = (SELECT auth.uid()) AND kind = 'standard' "
        "ORDER BY is_default DESC, code, id"
    ).fetchall()


def get_series(conn: Connection[DictRow], series_id: UUID) -> DictRow | None:
    return conn.execute(
        f"SELECT {SERIES_COLUMNS} FROM public.invoice_series WHERE id = %s AND owner_id = (SELECT auth.uid()) AND kind = 'standard'",
        (series_id,),
    ).fetchone()


def create_series(
    conn: Connection[DictRow], code: str, description: str | None, first_number: int, make_default: bool
) -> UUID:
    row = conn.execute(
        "SELECT app.create_invoice_series(%s, %s, %s, %s) AS id", (code, description, first_number, make_default)
    ).fetchone()
    assert row is not None
    return row["id"]


def update_series(conn: Connection[DictRow], series_id: UUID, changes: dict[str, object]) -> None:
    conn.execute("SELECT app.update_invoice_series(%s, %s)", (series_id, Jsonb(changes)))


def set_default_series(conn: Connection[DictRow], series_id: UUID) -> None:
    conn.execute("SELECT app.set_default_invoice_series(%s)", (series_id,))


def set_series_archived(conn: Connection[DictRow], series_id: UUID, archived: bool) -> None:
    conn.execute("SELECT app.set_invoice_series_archived(%s, %s)", (series_id, archived))
