"""La comprobación de una lectura, en un solo sitio (SPEC-W-003 §5.3, D-02).

`Document.validation` y el registro del gasto salen de AQUÍ: la interfaz muestra lo que el servidor calcula y el servidor registra
exactamente lo que acaba de comprobar. Se calcula sobre lo guardado (`review` si existe, `extraction` si no: `review` sustituye a la lectura
entera) y con lo que no sale del documento: el reloj (`today`, ya en Europe/Madrid), el NIF del perfil y los gastos vivos del proveedor.
"""

from datetime import date
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre import validators
from cuadre.expenses import presentation, repository
from cuadre.expenses.validation_models import Validation

# Los únicos estados desde los que se puede registrar un gasto (D-11 incluye `extraction_failed` rellenado a mano).
REGISTRABLE_STATES = frozenset({"review", "extraction_failed"})


def stored_reading(row: DictRow) -> dict[str, Any] | None:
    """Lo que se registraría: `review` si existe, `extraction` si no."""
    reading = row["review"] if row["review"] is not None else row["extraction"]
    return reading if isinstance(reading, dict) else None


def evaluate(conn: Connection[DictRow], row: DictRow, today: date) -> validators.Validation:
    """Todas las comprobaciones. Sin nada guardado, las de «datos obligatorios» fallan (así `confirm` nunca registra en blanco)."""
    data = validators.from_stored(stored_reading(row) or {})
    tax = validators.normalize_tax_id(data.supplier_tax_id)
    extraction = row["extraction"] if isinstance(row["extraction"], dict) else {}
    doubtful = extraction.get("doubtful_fields")
    context = validators.ValidationContext(
        today=today,
        owner_tax_id=repository.profile_tax_id(conn),
        existing=repository.existing_for_supplier(conn, tax.key) if tax is not None else (),
        has_review=row["review"] is not None,
        doubtful_count=len(doubtful) if isinstance(doubtful, list) else 0,
        injection_suspected=bool(row["injection_suspected"]),
    )
    return validators.validate(data, context)


def document_validation(conn: Connection[DictRow], row: DictRow, today: date) -> Validation | None:
    """`Document.validation`: nula si el documento no está en un estado registrable o no hay nada guardado que comprobar."""
    if row["status"] not in REGISTRABLE_STATES or stored_reading(row) is None:
        return None
    return presentation.to_validation(evaluate(conn, row, today))
