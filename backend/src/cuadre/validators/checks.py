"""`validate`: las comprobaciones deterministas de un gasto (SPEC-W-003 §5.1, RF-010, US-005).

Una lista **cerrada y ordenada** de hasta once comprobaciones, cada una con su etiqueta y, si falla, su motivo en español; los avisos, que no
bloquean; la vista previa (ámbito, deducibilidad, categoría sugerida) y, solo si todo pasa, los valores ya normalizados que se registrarán.
Pura: no toca la base de datos, la red ni ningún reloj (`today` llega en el contexto). `injection_suspected` no cambia el resultado de ninguna
comprobación: solo obliga a reconocerlo (NFR-07).
"""

from cuadre.validators.categories import suggest_category
from cuadre.validators.dates import issue_date_problem
from cuadre.validators.deductibility import EU_NOTE, Deductibility, deductible_vat
from cuadre.validators.duplicates import is_hard_duplicate, is_possible_duplicate, normalize_invoice_number
from cuadre.validators.limits import CURRENCY, DOC_TYPES_REGISTRABLE, DOC_TYPES_WITH_MANDATORY_NUMBER, MAX_TAX_LINES
from cuadre.validators.tax_id import TaxId, normalize_tax_id
from cuadre.validators.types import (
    Check,
    CheckCode,
    InvoiceData,
    Preview,
    RegistrableValues,
    Validation,
    ValidationContext,
    ValidationWarning,
    WarningCode,
)
from cuadre.validators.vat import (
    amounts_problem,
    lines_complete,
    rates_problem,
    sums,
    total_problem,
    withholding_problem,
)

LABELS: dict[CheckCode, str] = {
    CheckCode.doc_type: "Tipo de documento válido",
    CheckCode.required_data: "Datos obligatorios completos",
    CheckCode.doubts_reviewed: "Datos dudosos revisados",
    CheckCode.supplier_tax_id: "NIF del proveedor válido",
    CheckCode.issue_date: "Fecha correcta y no futura",
    CheckCode.currency: "Importe en euros",
    CheckCode.vat_rates: "Tipos de IVA permitidos",
    CheckCode.vat_amounts: "Cuota acorde al tipo de IVA",
    CheckCode.withholding: "Retención acorde a su porcentaje",
    CheckCode.total: "Base más IVA igual al total",
    CheckCode.not_duplicate: "No está registrada ya",
}
TOTAL_WITH_WITHHOLDING_LABEL = "Base más IVA menos retención igual al total"


def _check(code: CheckCode, problem: str | None, label: str | None = None) -> Check:
    return Check(code, label or LABELS[code], "ok" if problem is None else "failed", problem)


def _doc_type_problem(data: InvoiceData) -> str | None:
    if data.doc_type is None:
        return "Elige el tipo de documento."
    if data.doc_type not in DOC_TYPES_REGISTRABLE:
        return (
            f"Un documento de tipo «{data.doc_type}» no se puede registrar como gasto: elige factura, ticket o recibo."
        )
    return None


def _required_data_problem(data: InvoiceData) -> str | None:
    missing: list[str] = []
    if data.supplier_name is None:
        missing.append("el nombre del proveedor")
    if data.doc_type in DOC_TYPES_WITH_MANDATORY_NUMBER and data.invoice_number is None:
        missing.append("el número de factura")
    if not data.tax_lines:
        missing.append("el desglose de IVA")
    elif not lines_complete(data.tax_lines):
        missing.append("el tipo, la base o la cuota de alguna línea de IVA")
    if data.total_cents is None:
        missing.append("el total")
    problems: list[str] = []
    if missing:
        problems.append("Faltan " + ", ".join(missing) + ".")
    if len(data.tax_lines) > MAX_TAX_LINES:
        problems.append(f"Hay más de {MAX_TAX_LINES} líneas de IVA.")
    negative = (
        any((line.base_cents or 0) < 0 or (line.vat_cents or 0) < 0 for line in data.tax_lines)
        or (data.withholding is not None and (data.withholding.amount_cents or 0) < 0)
        or (data.total_cents is not None and data.total_cents <= 0)
    )
    if negative:
        problems.append(
            "Los importes deben ser positivos y el total mayor que cero (los abonos no se registran todavía)."
        )
    return " ".join(problems) or None


def _doubts_problem(context: ValidationContext) -> str | None:
    if context.has_review:
        return None
    count = context.doubtful_count
    what = "un dato dudoso" if count == 1 else f"{count} datos dudosos"
    return f"La lectura marcó {what}: compruébalo con el original y guarda los cambios."


def _tax_id_problem(data: InvoiceData, tax: TaxId | None) -> str | None:
    if tax is not None:
        return None
    if data.supplier_tax_id is None:
        return "Falta el NIF del proveedor."
    return "No se reconoce como NIF español ni NIF-IVA de la UE: revisa el dígito o la letra de control."


def _currency_problem(data: InvoiceData) -> str | None:
    if data.currency is None or data.currency == CURRENCY:
        return None
    return "La factura no está en euros: anótala como gasto sin factura con el importe que te cargaron en euros."


def _duplicate_problem(tax: TaxId | None, number_key: str | None, context: ValidationContext) -> str | None:
    if is_hard_duplicate(tax.key if tax else None, number_key, context.existing):
        return "Ya hay un gasto registrado con el mismo NIF del proveedor y el mismo número de factura."
    return None


def _recipient_mismatch(data: InvoiceData, context: ValidationContext) -> bool:
    """Solo si la factura trae un NIF de destinatario y el perfil tiene el suyo. Uno que no se entiende cuenta como distinto."""
    if not (
        data.recipient_tax_id
        and data.recipient_tax_id.strip()
        and context.owner_tax_id
        and context.owner_tax_id.strip()
    ):
        return False
    recipient = normalize_tax_id(data.recipient_tax_id)
    owner = normalize_tax_id(context.owner_tax_id)
    return recipient is None or owner is None or recipient.key != owner.key


def _values(
    data: InvoiceData, tax: TaxId | None, number_key: str | None, deductibility: Deductibility
) -> RegistrableValues | None:
    if (
        tax is None
        or data.issue_date is None
        or data.supplier_name is None
        or data.doc_type is None
        or data.total_cents is None
    ):
        return None
    bases, vats = sums(data.tax_lines)
    return RegistrableValues(
        expense_date=data.issue_date,
        supplier_name=data.supplier_name.strip(),
        supplier_tax_id=tax.key,
        supplier_scope=tax.scope,
        invoice_number=data.invoice_number,
        invoice_number_key=number_key,
        doc_type=data.doc_type,
        base_cents=bases,
        vat_cents=vats,
        withholding_cents=0 if data.withholding is None else (data.withholding.amount_cents or 0),
        total_cents=data.total_cents,
        tax_lines=data.tax_lines,
        deductible_vat=deductibility.deductible,
    )


def validate(data: InvoiceData, context: ValidationContext) -> Validation:
    tax = normalize_tax_id(data.supplier_tax_id)
    scope = tax.scope if tax is not None else None
    tax_key = tax.key if tax is not None else None
    number_key = normalize_invoice_number(data.invoice_number)

    checks: list[Check] = [
        _check(CheckCode.doc_type, _doc_type_problem(data)),
        _check(CheckCode.required_data, _required_data_problem(data)),
    ]
    if context.doubtful_count > 0:
        checks.append(_check(CheckCode.doubts_reviewed, _doubts_problem(context)))
    checks += [
        _check(CheckCode.supplier_tax_id, _tax_id_problem(data, tax)),
        _check(
            CheckCode.issue_date,
            issue_date_problem(data.issue_date, malformed=data.issue_date_malformed, today=context.today),
        ),
        _check(CheckCode.currency, _currency_problem(data)),
        _check(CheckCode.vat_rates, rates_problem(data.tax_lines, scope)),
        _check(CheckCode.vat_amounts, amounts_problem(data.tax_lines)),
    ]
    if data.withholding is not None:
        checks.append(_check(CheckCode.withholding, withholding_problem(data.withholding, data.tax_lines)))
    checks += [
        _check(
            CheckCode.total,
            total_problem(data.tax_lines, data.withholding, data.total_cents),
            TOTAL_WITH_WITHHOLDING_LABEL if data.withholding is not None else None,
        ),
        _check(CheckCode.not_duplicate, _duplicate_problem(tax, number_key, context)),
    ]

    warnings: list[ValidationWarning] = []
    if is_possible_duplicate(tax_key, number_key, data.issue_date, data.total_cents, context.existing):
        warnings.append(
            ValidationWarning(
                WarningCode.possible_duplicate,
                "Ya hay un gasto con el mismo proveedor, día e importe: comprueba que no es el mismo.",
            )
        )
    if _recipient_mismatch(data, context):
        warnings.append(
            ValidationWarning(
                WarningCode.recipient_mismatch,
                "La factura no va a tu NIF: el destinatario no coincide con el de tu perfil.",
            )
        )
    if scope == "eu":
        warnings.append(ValidationWarning(WarningCode.eu_supplier, EU_NOTE))

    vat_total = sums(data.tax_lines)[1] if lines_complete(data.tax_lines) else None
    deductibility = deductible_vat(data.doc_type, scope, vat_total, data.recipient_tax_id, context.owner_tax_id)
    can_register = all(check.ok for check in checks)
    return Validation(
        can_register=can_register,
        requires_acknowledgement=context.injection_suspected,
        checks=tuple(checks),
        warnings=tuple(warnings),
        preview=Preview(scope, deductibility.deductible, deductibility.note, suggest_category(data.supplier_name)),
        values=_values(data, tax, number_key, deductibility) if can_register else None,
    )
