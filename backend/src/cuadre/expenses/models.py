"""Modelos de petición y respuesta de gastos (SPEC-W-003 §5.3). De ellos sale el cliente TypeScript.

Los cuerpos se validan con `extra="forbid"` e importes ESTRICTOS en céntimos (ni `12.5` ni `"120.00"`): la interfaz señala junto al campo lo
que no se puede interpretar y no llega aquí. La forma se valida aquí; lo fiscal, en `cuadre.validators`; y lo que protege la contabilidad,
también en la base (hito 2).
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from cuadre.agents.text import clean_text
from cuadre.documents.models import CENTS_MAX, ISO_DATE, DocumentStatus
from cuadre.validators import ExpenseCategory

CONCEPT_MAX = 200
DocType = Literal["full_invoice", "simplified_invoice", "ticket", "receipt"]
Scope = Literal["national", "eu"]
Cents = Annotated[StrictInt, Field(ge=0, le=CENTS_MAX)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Peticiones -----------------------------------------------------------------------------------------------------------------


class ConfirmRequest(_Strict):
    """`acknowledge_suspicion`: la persona confirma que comparó los datos con el original (solo se exige si hay sospecha, NFR-07)."""

    category: ExpenseCategory
    acknowledge_suspicion: StrictBool = False


class SetCategory(_Strict):
    category: ExpenseCategory


class CreateExpense(_Strict):
    expense_date: date
    concept: str
    category: ExpenseCategory
    amount_cents: Annotated[StrictInt, Field(gt=0, le=CENTS_MAX)]

    @field_validator("expense_date", mode="before")
    @classmethod
    def _iso_date_only(cls, value: Any) -> Any:
        """`AAAA-MM-DD` y nada más: ni fecha con hora, ni marca de tiempo, ni fecha como número."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str) and ISO_DATE.fullmatch(value):
            return value
        raise ValueError("La fecha debe tener la forma AAAA-MM-DD.")

    @field_validator("concept", mode="before")
    @classmethod
    def _clean_concept(cls, value: Any) -> Any:
        """Sin caracteres de control (un NUL rompería el texto) y con los espacios colapsados; lo vacío queda como `""`."""
        if not isinstance(value, str):
            return value
        return clean_text(value, CONCEPT_MAX * 4) or ""

    @field_validator("concept")
    @classmethod
    def _concept_length(cls, value: str) -> str:
        if not value:
            raise ValueError("Escribe el concepto del gasto.")
        if len(value) > CONCEPT_MAX:
            raise ValueError(f"El concepto es demasiado largo (máximo {CONCEPT_MAX} caracteres).")
        return value


# --- Respuestas -------------------------------------------------------------------------------------------------------------------


class ExpenseTaxLine(BaseModel):
    vat_rate: str
    base_cents: int
    vat_cents: int


class ExpenseSummary(BaseModel):
    """Una fila de «Gastos registrados»."""

    id: UUID
    origin: Literal["document", "manual"]
    expense_date: date
    supplier_name: str
    category: ExpenseCategory
    total_cents: int
    vat_cents: int
    deductible_vat: bool
    supplier_scope: Scope | None
    document_id: UUID | None


class Expense(ExpenseSummary):
    doc_type: DocType | None
    supplier_tax_id: str | None
    invoice_number: str | None
    base_cents: int
    withholding_cents: int
    tax_breakdown: list[ExpenseTaxLine]
    suspicion_acknowledged: bool
    created_at: datetime
    voided_at: datetime | None


class ExpensePage(BaseModel):
    items: list[ExpenseSummary]
    next_cursor: str | None


class VoidResult(BaseModel):
    id: UUID
    document_id: UUID | None
    document_status: DocumentStatus | None
