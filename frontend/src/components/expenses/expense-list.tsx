import Link from "next/link";

import { ExpenseBadges } from "@/components/expenses/expense-badges";
import type { BadgeTone } from "@/lib/expenses";
import type { ExpenseSummary } from "@/lib/expenses-api";
import { categoryLabel, formatDay } from "@/lib/expenses";
import { formatCents } from "@/lib/money";

const LINK = "[overflow-wrap:anywhere] font-bold text-ink hover:text-action hover:underline";
const PLAIN = "[overflow-wrap:anywhere] font-bold text-ink";
const ownerExpenseHref = (id: string): string | null => `/gastos/registrados/${id}`;

/**
 * «Gastos registrados»: tarjetas apiladas hasta 1.279 px y tabla desde 1.280 (con la barra lateral, a menos ancho una tabla de cinco
 * columnas obligaría a desplazarse en horizontal, T3-11). Las dos vistas están en el DOM y solo una se muestra: la otra va con
 * `display: none`, así que no existe para el lector de pantalla. Todo lo que viene de la lectura se pinta como texto.
 */
export function ExpenseList<T extends ExpenseSummary>({
  expenses,
  hrefFor = ownerExpenseHref,
  extraBadges,
  empty = "Todavía no hay gastos registrados. Cuando registres una factura o anotes un gasto sin factura, aparecerá aquí.",
}: {
  expenses: T[];
  /** A dónde lleva el nombre de un gasto; `null` = sin enlace (la ficha del gestor no tiene detalle de gasto). */
  hrefFor?: (id: string) => string | null;
  empty?: string;
  /** Marcas que se suman a las de cada gasto (en la ficha del gestor, «Anulado»). */
  extraBadges?: (expense: T) => { label: string; tone: BadgeTone }[];
}) {
  if (expenses.length === 0) {
    return <p className="rounded-panel border border-rule bg-sheet px-5 py-8 text-center text-ink-soft">{empty}</p>;
  }
  return (
    <>
      <ul className="grid gap-3 min-[1280px]:hidden">
        {expenses.map((expense) => (
          <li key={expense.id}>
            <article className="relative grid gap-2 rounded-panel border border-rule bg-sheet p-4 transition-colors hover:border-rule-strong hover:bg-white sm:grid-cols-[1fr_auto] sm:items-start sm:gap-x-6">
              <div className="grid min-w-0 gap-1.5">
                <h3 className="text-[15px] leading-snug">
                  {/* El enlace cubre toda la tarjeta (::after), pero su nombre accesible es solo el título. */}
                  {hrefFor(expense.id) !== null ? (
                    <Link href={hrefFor(expense.id) ?? "#"} className={`${LINK} after:absolute after:inset-0 after:content-['']`}>
                      {expense.supplier_name}
                    </Link>
                  ) : (
                    <span className={PLAIN}>{expense.supplier_name}</span>
                  )}
                </h3>
                <p className="text-[13px] text-ink-soft">
                  {formatDay(expense.expense_date)} · {categoryLabel(expense.category)}
                </p>
                <ExpenseBadges expense={expense} extra={extraBadges?.(expense)} />
              </div>
              <p className="text-lg font-bold tabular-nums sm:text-right">{formatCents(expense.total_cents)}</p>
            </article>
          </li>
        ))}
      </ul>

      <div className="hidden min-[1280px]:block">
        <table className="w-full border-collapse text-left text-[15px]">
          <caption className="sr-only">Gastos registrados, del más reciente al más antiguo</caption>
          <thead>
            <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
              <th scope="col" className="w-28 py-2 pr-4 font-semibold">
                Fecha
              </th>
              <th scope="col" className="py-2 pr-4 font-semibold">
                Proveedor o concepto
              </th>
              <th scope="col" className="w-52 py-2 pr-4 font-semibold">
                Categoría
              </th>
              <th scope="col" className="w-36 py-2 pr-4 text-right font-semibold">
                Total
              </th>
              <th scope="col" className="w-64 py-2 font-semibold">
                Marcas
              </th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((expense) => (
              <tr key={expense.id} className="border-b border-rule align-top hover:bg-sheet">
                <td className="py-3 pr-4 whitespace-nowrap">{formatDay(expense.expense_date)}</td>
                <th scope="row" className="py-3 pr-4 font-normal">
                  {hrefFor(expense.id) !== null ? (
                    <Link href={hrefFor(expense.id) ?? "#"} className={LINK}>
                      {expense.supplier_name}
                    </Link>
                  ) : (
                    <span className={PLAIN}>{expense.supplier_name}</span>
                  )}
                </th>
                <td className="py-3 pr-4">{categoryLabel(expense.category)}</td>
                <td className="py-3 pr-4 text-right font-bold tabular-nums">{formatCents(expense.total_cents)}</td>
                <td className="py-3">
                  <ExpenseBadges expense={expense} extra={extraBadges?.(expense)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
