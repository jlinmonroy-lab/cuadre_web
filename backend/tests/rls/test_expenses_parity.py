"""T3-04 · una fuente por regla: lo que repiten Python y SQL se compara con la propia base (SPEC-W-003 §5.2, §5.1).

La normalización del número de factura, las categorías, los tipos de documento, la tolerancia y los límites viven a la vez en
`cuadre.validators` y en el esquema. Esta es la prueba que impide que se separen sin que nadie se entere. Necesita la base: por eso
está en `tests/rls` (la puerta de despliegue) y no en `tests/validators`, que es pura.
"""

import random
import re
from datetime import UTC, datetime
from typing import Any

from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.documents.models import TEXT_LIMITS
from cuadre.validators import ExpenseCategory, normalize_tax_id
from cuadre.validators.duplicates import normalize_invoice_number
from cuadre.validators.limits import (
    DOC_TYPES_REGISTRABLE,
    EARLIEST_DATE,
    MAX_TAX_LINES,
    TAX_ID_KEY,
    TOLERANCE_CENTS,
)
from tests.rls.expenses_support import INSERT, params
from tests.support import Cast, new_document
from tests.validators import corpus

Pool = Any


def scalar(admin: Connection[DictRow], sql: str, *args: Any) -> Any:
    row = admin.execute(sql, args).fetchone()
    assert row is not None
    return next(iter(row.values()))


def constraint_definition(admin: Connection[DictRow], name: str) -> str:
    return str(
        scalar(
            admin,
            "select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'public.expenses'::regclass and conname = %s",
            name,
        )
    )


# --- el número de factura ----------------------------------------------------------------------------------------------------------

NUMBERS = [
    "A-311", "a311", "A 311", " a-311 ", "A.311", "A_311", "a/311", "NS-2026-9921", "2026/0001", "Nº 5", "N°5", "No. 12",
    "ÁÉÍ-12", "ñandú 3", "straße 9", "ﬁnal 1", "３４５", "٣٤٥", "A 311", "A 311", "A\n311", "A\t311", "A\r\n311",
    "İstanbul 1", "ı-1", "Ω-7", "x" * 64, "---", "   ", "", "0", "00", "a" * 3 + "-" + "B" * 3, "#1", "(2026)-7", "[A]1", "A+1",
]  # fmt: skip


def random_numbers(count: int) -> list[str]:
    rng = random.Random(20261107)
    alphabet = (
        "abcxyzABCXYZ0123456789 -_./\\#º°ª,;:()[]{}+*'\"`~!?@$%^&=<>|"
        "áéíóúñÁÉÍÓÚÑüÜçÇàèìòùâêîôûäëïöß ﬁﬂİıΩωЖж٣٤٥３４５  \n\t\r​́"
    )
    return ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24))) for _ in range(count)]


def test_the_invoice_number_key_of_the_database_is_the_one_python_computes(admin: Connection[DictRow]) -> None:
    """Se lee la expresión de la columna generada DEL CATÁLOGO y se aplica a un corpus: no es una copia de la spec."""
    expression = scalar(
        admin,
        "select pg_get_expr(d.adbin, d.adrelid) from pg_attrdef d join pg_attribute a "
        "on a.attrelid = d.adrelid and a.attnum = d.adnum "
        "where d.adrelid = 'public.expenses'::regclass and a.attname = 'invoice_number_key'",
    )
    assert "invoice_number" in expression
    corpus_numbers = [*NUMBERS, *random_numbers(2000)]
    with admin.transaction(force_rollback=True):
        admin.execute(
            f"create temp table zz_key_parity (n serial, invoice_number text, "  # noqa: S608
            f"invoice_number_key text generated always as ({expression}) stored)"
        )
        with admin.cursor() as cursor:
            cursor.executemany("insert into zz_key_parity (invoice_number) values (%s)", [(v,) for v in corpus_numbers])
        stored = admin.execute("select invoice_number, invoice_number_key from zz_key_parity order by n").fetchall()
    assert len(stored) == len(corpus_numbers)
    differences = [
        (row["invoice_number"], row["invoice_number_key"], normalize_invoice_number(row["invoice_number"]))
        for row in stored
        if row["invoice_number_key"] != normalize_invoice_number(row["invoice_number"])
    ]
    assert differences == []
    assert normalize_invoice_number(None) is None


def test_the_stored_column_gives_the_same_key_as_python_on_real_rows(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    doc = new_document(app_pool, cast.alicia)
    now = datetime.now(UTC)
    for number in ("A-311", " a 311 ", "Nº 5", "ﬁnal 1", "３４５", "---", "x" * 64):
        row = admin.execute(INSERT, params(cast.alicia, doc, number=number, voided=now)).fetchone()
        assert row is not None
        key = scalar(admin, "select invoice_number_key from public.expenses where id = %s", row["id"])
        assert key == normalize_invoice_number(number), number


# --- enums y listas ------------------------------------------------------------------------------------------------------------------


def enum_labels(admin: Connection[DictRow], name: str) -> list[str]:
    rows = admin.execute(
        "select e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid where t.typname = %s order by e.enumsortorder",
        (name,),
    ).fetchall()
    return [r["enumlabel"] for r in rows]


def test_the_categories_of_the_database_are_the_ones_of_the_code_in_the_same_order(admin: Connection[DictRow]) -> None:
    assert enum_labels(admin, "expense_category") == [c.value for c in ExpenseCategory]


def test_the_other_enums(admin: Connection[DictRow]) -> None:
    assert enum_labels(admin, "expense_origin") == ["document", "manual"]
    assert enum_labels(admin, "supplier_scope") == ["national", "eu"]


def test_the_registrable_document_types_are_the_ones_of_the_check(admin: Connection[DictRow]) -> None:
    definition = constraint_definition(admin, "expenses_doc_type_known")
    assert set(re.findall(r"'([a-z_]+)'::text", definition)) == set(DOC_TYPES_REGISTRABLE)


# --- constantes ------------------------------------------------------------------------------------------------------------------------


def test_the_limits_of_the_database_are_the_ones_of_the_validators(admin: Connection[DictRow]) -> None:
    assert scalar(admin, "select private.expense_max_tax_lines()") == MAX_TAX_LINES
    assert scalar(admin, "select private.expense_earliest_date()") == EARLIEST_DATE
    assert f"<= {TOLERANCE_CENTS}" in constraint_definition(admin, "expenses_total_coherent")
    # PostgreSQL guarda `BETWEEN 1 AND n` como `>= 1 AND <= n`.
    assert f"<= {TEXT_LIMITS['supplier_name']})" in constraint_definition(admin, "expenses_supplier_name_length")
    assert f"<= {TEXT_LIMITS['invoice_number']})" in constraint_definition(admin, "expenses_invoice_number_length")


def test_the_check_of_the_tax_id_is_the_key_pattern_of_the_validators(admin: Connection[DictRow]) -> None:
    assert f"'^{TAX_ID_KEY.pattern}$'" in constraint_definition(admin, "expenses_tax_id_form")


def test_every_key_the_normalizer_produces_fits_the_check(
    admin: Connection[DictRow], app_pool: Pool, cast: Cast
) -> None:
    """Las 27 formas sintéticas del spike (B.1), tal como las guarda el normalizador, entran en la tabla."""
    doc = new_document(app_pool, cast.alicia)
    now = datetime.now(UTC)
    raws = [*corpus.ES_ALL, *corpus.EU_VAT.values()]
    keys = [normalize_tax_id(raw) for raw in raws]
    assert all(key is not None for key in keys) and len(keys) >= 27
    for index, key in enumerate(keys):
        assert key is not None
        scope = "national" if key.scope == "national" else "eu"
        admin.execute(
            INSERT,
            params(cast.alicia, doc, tax_id=key.key, scope=scope, number=f"N{index}", voided=now, deductible=False),
        )
    assert scalar(admin, "select count(*) from public.expenses where owner_id = %s", cast.alicia.id) == len(keys)


def test_the_database_pattern_rejects_a_trailing_line_break_like_python(admin: Connection[DictRow]) -> None:
    pattern = f"^{TAX_ID_KEY.pattern}$"
    for value, fine in (
        ("B00000042", True),
        ("B00000042" + chr(10), False),
        (chr(10) + "B00000042", False),
        ("b00000042", False),
    ):
        assert scalar(admin, "select %s ~ %s", value, pattern) is fine, repr(value)
        assert (TAX_ID_KEY.fullmatch(value) is not None) is fine, repr(value)


def test_today_is_computed_in_the_madrid_time_zone(admin: Connection[DictRow]) -> None:
    """`now()` no se puede fijar, así que la frontera de medianoche se prueba en Python con reloj fijo (hito 1); aquí, que la zona es esa."""
    definition = scalar(admin, "select pg_get_functiondef('private.today_madrid()'::regprocedure)")
    assert "'Europe/Madrid'" in definition
    assert scalar(admin, "select private.today_madrid() = (now() at time zone 'Europe/Madrid')::date") is True
