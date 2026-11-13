"""Reglas puras del cierre mensual (SPEC-W-012 §5.1, D-02, D-05, D-06). Sin base de datos, sin red y sin reloj propio.

Quien llama pasa el «hoy en Europe/Madrid» (`cuadre.core.clock.today_in_madrid`) y los documentos ya leídos. Todo son enteros: los importes viajan en
céntimos (RES-02) y una entrada que no lo sea se rechaza en vez de redondearse.
"""

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from cuadre.closing.limits import CLOSING_MAX_DOCUMENTS, FIRST_YEAR, LAST_YEAR, MAX_WINDOW_MONTHS, WINDOW_MONTHS
from cuadre.closing.types import (
    KINDS,
    SCOPES,
    ClientTotals,
    MonthExpense,
    MonthInvoice,
    MonthTotals,
    YearMonth,
)
from cuadre.tax.periods import PeriodInFuture


class InvalidMonth(ValueError):
    """El año o el mes no existen (año fuera de 2000-9998 o mes fuera de 1-12)."""

    code = "invalid_period"


class ClosingTooLarge(ValueError):
    """Hay más documentos de los que caben en una ejecución del cierre."""

    code = "closing_too_large"


# --- Calendario -------------------------------------------------------------------------------------------------------------------------


def month_bounds(month: YearMonth) -> tuple[date, date]:
    """El primer día del mes y el primero del siguiente (el final es exclusivo)."""
    following = month.next()
    return date(month.year, month.month, 1), date(following.year, following.month, 1)


def window_bounds(months: Sequence[YearMonth]) -> tuple[date, date]:
    """Desde el primer día del primer mes hasta el primero del mes siguiente al último (exclusivo): lo que hay que leer para toda la ventana."""
    if not months:
        raise ValueError("La ventana está vacía.")
    return month_bounds(min(months))[0], month_bounds(max(months))[1]


def first_active_month(*days: date | None) -> YearMonth | None:
    """El mes más antiguo entre las fechas dadas (el alta de la cuenta, la primera factura y el primer gasto), ignorando las ausentes."""
    present = [YearMonth.of(day) for day in days if day is not None]
    return min(present) if present else None


def closing_window(today: date, first: YearMonth | None, months: int = WINDOW_MONTHS) -> tuple[YearMonth, ...]:
    """Los meses a cerrar, del más antiguo al más reciente: hasta `months` meses ya terminados contados desde el anterior al de `today`, sin pasar de
    `first` (el primer mes con actividad) ni de enero de 2000. Vacía si la persona no tiene actividad o aún no ha terminado su primer mes."""
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= MAX_WINDOW_MONTHS:
        raise ValueError(f"La ventana debe ser de 1 a {MAX_WINDOW_MONTHS} meses.")
    last = YearMonth.of(today).previous()
    if first is None or first > last:
        return ()
    start = max(first, last.shift(-(months - 1)), YearMonth(FIRST_YEAR, 1))
    if start > last:
        return ()
    span = (last.year * 12 + last.month) - (start.year * 12 + start.month)
    return tuple(start.shift(offset) for offset in range(span + 1))


def explicit_window(today: date, year: int, month: int) -> tuple[YearMonth, ...]:
    """Un único mes pedido a mano (`--month`): tiene que existir, no ser anterior a enero de 2000 y haber terminado. Aunque esté fuera de los 12 meses."""
    valid = (
        isinstance(year, int)
        and isinstance(month, int)
        and not isinstance(year, bool)
        and not isinstance(month, bool)
        and FIRST_YEAR <= year <= LAST_YEAR
        and 1 <= month <= 12
    )
    if not valid:
        raise InvalidMonth("El año o el mes no existen.")
    requested = YearMonth(year, month)
    if requested >= YearMonth.of(today):
        raise PeriodInFuture("El mes todavía no ha terminado.")
    return (requested,)


# --- Cálculo ----------------------------------------------------------------------------------------------------------------------------


def _whole(value: Any, what: str) -> int:
    """Un importe en céntimos: un entero de verdad (ni `bool`, ni decimal, ni texto)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} debe ser un entero en céntimos.")
    return value


def _check_invoice(invoice: MonthInvoice) -> None:
    _whole(invoice.base_cents, "El importe de la factura")
    if invoice.kind not in KINDS:
        raise ValueError("Tipo de factura desconocido.")
    if invoice.scope not in SCOPES:
        raise ValueError("Ámbito desconocido.")


def _check_expense(expense: MonthExpense) -> None:
    _whole(expense.base_cents, "La base del gasto")
    _whole(expense.vat_cents, "El IVA del gasto")


def _group(documents: Iterable[Any], day_of: Any) -> dict[YearMonth, list[Any]]:
    grouped: dict[YearMonth, list[Any]] = {}
    for document in documents:
        grouped.setdefault(YearMonth.of(day_of(document)), []).append(document)
    return grouped


def _month_totals(month: YearMonth, invoices: list[MonthInvoice], expenses: list[MonthExpense]) -> MonthTotals:
    by_scope = dict.fromkeys(SCOPES, 0)
    # Una entrada por cliente y ámbito: si una factura de un cliente cambió de ámbito durante el mes, sus importes siguen sumando cada ámbito.
    clients: dict[tuple[str, str], list[Any]] = {}
    standard = 0
    # De la más antigua a la más reciente: el nombre que queda es el de la última factura del cliente en el mes.
    for invoice in sorted(invoices, key=lambda i: (i.issue_date, i.id)):
        by_scope[invoice.scope] += invoice.base_cents
        entry = clients.setdefault((invoice.client_id, invoice.scope), [invoice.client_name, 0, 0])
        entry[0] = invoice.client_name
        entry[1] += invoice.base_cents
        if invoice.kind == "standard":
            entry[2] += 1
            standard += 1

    by_client = tuple(
        sorted(
            (
                ClientTotals(client_id=client_id, name=name, scope=scope, base_cents=base, invoice_count=count)  # type: ignore[arg-type]
                for (client_id, scope), (name, base, count) in clients.items()
            ),
            key=lambda c: (-c.base_cents, c.name, c.client_id, c.scope),
        )
    )
    spent = sum(e.base_cents + (0 if e.deductible_vat else e.vat_cents) for e in expenses if not e.voided)
    return MonthTotals(
        year=month.year,
        month=month.month,
        invoice_count=standard,
        national_cents=by_scope["national"],
        eu_cents=by_scope["eu"],
        non_eu_cents=by_scope["non_eu"],
        total_cents=sum(by_scope.values()),
        expenses_cents=spent,
        by_client=by_client,
    )


def build_months(
    invoices: Sequence[MonthInvoice], expenses: Sequence[MonthExpense], months: Iterable[YearMonth]
) -> list[MonthTotals]:
    """La foto de cada mes pedido, en el mismo orden. Agrupa los documentos una sola vez (la ventana de 12 meses son dos consultas) y filtra cada mes por
    la fecha de cada documento: se le pueden pasar todos juntos. Falla con `ClosingTooLarge` si hay demasiados y con `TypeError` si un importe no es entero."""
    if len(invoices) + len(expenses) > CLOSING_MAX_DOCUMENTS:
        raise ClosingTooLarge("Hay más documentos de los que caben en el cierre.")
    for invoice in invoices:
        _check_invoice(invoice)
    for expense in expenses:
        _check_expense(expense)
    invoices_by_month = _group(invoices, lambda i: i.issue_date)
    expenses_by_month = _group(expenses, lambda e: e.expense_date)
    return [_month_totals(m, invoices_by_month.get(m, []), expenses_by_month.get(m, [])) for m in months]


def build_month(
    year: int, month: int, invoices: Sequence[MonthInvoice], expenses: Sequence[MonthExpense]
) -> MonthTotals:
    """La foto de un mes (el mes en curso o uno pendiente se calculan en vivo con esta misma función)."""
    if (
        isinstance(year, bool)
        or isinstance(month, bool)
        or not isinstance(year, int)
        or not isinstance(month, int)
        or not FIRST_YEAR <= year <= LAST_YEAR
        or not 1 <= month <= 12
    ):
        raise InvalidMonth("El año o el mes no existen.")
    return build_months(invoices, expenses, [YearMonth(year, month)])[0]


def payload_of(totals: MonthTotals) -> dict[str, Any]:
    """Exactamente el objeto que valida `private.close_month`: enteros y, en `by_client`, el orden del cálculo (forma parte de la foto)."""
    return {
        "invoice_count": totals.invoice_count,
        "national_cents": totals.national_cents,
        "eu_cents": totals.eu_cents,
        "non_eu_cents": totals.non_eu_cents,
        "total_cents": totals.total_cents,
        "expenses_cents": totals.expenses_cents,
        "by_client": [
            {
                "client_id": c.client_id,
                "name": c.name,
                "scope": c.scope,
                "base_cents": c.base_cents,
                "invoice_count": c.invoice_count,
            }
            for c in totals.by_client
        ],
    }
