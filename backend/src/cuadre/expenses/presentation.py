"""De una fila de `expenses` y del resultado de los validadores a lo que ve la persona (SPEC-W-003 §5.3).

El gasto expone todo lo que guarda salvo `owner_id`. El resultado de `cuadre.validators` se copia tal cual a los modelos de la API: la
interfaz no valida nada, solo lo muestra.
"""

from psycopg.rows import DictRow

from cuadre import validators
from cuadre.expenses.models import Expense, ExpenseSummary, ExpenseTaxLine
from cuadre.expenses.validation_models import CheckItem, Preview, Validation, WarningItem


def to_summary(row: DictRow) -> ExpenseSummary:
    return ExpenseSummary(
        id=row["id"],
        origin=row["origin"],
        expense_date=row["expense_date"],
        supplier_name=row["supplier_name"],
        category=row["category"],
        total_cents=row["total_cents"],
        vat_cents=row["vat_cents"],
        deductible_vat=row["deductible_vat"],
        supplier_scope=row["supplier_scope"],
        document_id=row["document_id"],
    )


def to_expense(row: DictRow) -> Expense:
    return Expense(
        **to_summary(row).model_dump(),
        doc_type=row["doc_type"],
        supplier_tax_id=row["supplier_tax_id"],
        invoice_number=row["invoice_number"],
        base_cents=row["base_cents"],
        withholding_cents=row["withholding_cents"],
        tax_breakdown=[ExpenseTaxLine.model_validate(line) for line in row["tax_breakdown"]],
        suspicion_acknowledged=row["suspicion_acknowledged"],
        created_at=row["created_at"],
        voided_at=row["voided_at"],
    )


def to_validation(result: validators.Validation) -> Validation:
    return Validation(
        can_register=result.can_register,
        requires_acknowledgement=result.requires_acknowledgement,
        checks=[CheckItem(code=c.code, label=c.label, status=c.status, detail=c.detail) for c in result.checks],
        warnings=[WarningItem(code=w.code, message=w.message) for w in result.warnings],
        preview=Preview(
            supplier_scope=result.preview.supplier_scope,
            deductible_vat=result.preview.deductible_vat,
            deductible_note=result.preview.deductible_note,
            suggested_category=result.preview.suggested_category,
        ),
    )
