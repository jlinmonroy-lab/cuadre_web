import { ArrowLeft, Ban, ShieldAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { CategoryForm } from "@/components/expenses/category-form";
import { ExpenseBadges } from "@/components/expenses/expense-badges";
import { VoidButton } from "@/components/expenses/void-button";
import { OriginalViewer } from "@/components/documents/original-viewer";
import { getDocument } from "@/lib/documents-api";
import { docTypeLabel, formatMoment } from "@/lib/documents";
import { categoryLabel, formatDay } from "@/lib/expenses";
import { getExpense } from "@/lib/expenses-api";
import { formatCents } from "@/lib/money";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Gasto registrado" };

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-0.5">
      <dt className="text-[13px] font-semibold text-ink-soft">{label}</dt>
      <dd className="[overflow-wrap:anywhere]">{children}</dd>
    </div>
  );
}

const rateText = (rate: string) => `${rate.replace(".", ",")} %`;

export default async function ExpensePage(props: PageProps<"/gastos/registrados/[id]">) {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const { id } = await props.params;
  const expense = await getExpense(id);
  if (!expense) notFound();
  // El original solo existe si el gasto viene de un documento (y el documento sigue ahí: uno anulado puede haberse descartado después).
  const document = expense.document_id ? await getDocument(expense.document_id) : null;
  const hasOriginal = document !== null && document.status !== "uploading";
  const voided = expense.voided_at !== null;
  const manual = expense.origin === "manual";

  return (
    <>
      <header className="mb-6 grid gap-2">
        <Link href="/gastos" className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Gastos
        </Link>
        <h1 className="[overflow-wrap:anywhere]">{expense.supplier_name}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <ExpenseBadges expense={expense} />
          <span className="text-[13px] text-ink-soft">Registrado {formatMoment(expense.created_at)}</span>
        </div>
      </header>

      <div className="grid gap-6">
        {voided ? (
          <div role="status" className="flex items-start gap-3 rounded-md border border-status-error bg-status-error-bg px-4 py-3 text-status-error">
            <Ban aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
            <div className="grid gap-1">
              <p className="font-semibold">Este gasto está anulado.</p>
              <p className="text-sm">Se anuló el {formatMoment(expense.voided_at)}. Ya no cuenta en tus cuentas y no admite cambios.</p>
              {document ? (
                <p className="text-sm">
                  <Link href={`/gastos/${document.id}`} className="font-semibold underline underline-offset-2">
                    Ver el documento
                  </Link>
                </p>
              ) : null}
            </div>
          </div>
        ) : null}

        {expense.suspicion_acknowledged ? (
          <p className="flex items-start gap-2 rounded-md border border-status-doubt-line bg-status-doubt-bg px-4 py-3 text-sm text-status-doubt">
            <ShieldAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>Se registró después de confirmar que se compararon los datos con el original: el documento contenía texto que parecía una instrucción.</span>
          </p>
        ) : null}

        <div className={hasOriginal ? "grid items-start gap-8 min-[1280px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" : "grid gap-8"}>
          <section aria-labelledby="datos-gasto-titulo" className="grid min-w-0 content-start gap-6">
            <h2 id="datos-gasto-titulo">Datos del gasto</h2>
            <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <Item label="Fecha">{formatDay(expense.expense_date)}</Item>
              <Item label={manual ? "Concepto" : "Proveedor"}>{expense.supplier_name}</Item>
              {expense.supplier_tax_id ? <Item label="NIF del proveedor">{expense.supplier_tax_id}</Item> : null}
              {expense.invoice_number ? <Item label="Número de factura">{expense.invoice_number}</Item> : null}
              {expense.doc_type ? <Item label="Tipo de documento">{docTypeLabel(expense.doc_type)}</Item> : null}
              {voided ? <Item label="Categoría">{categoryLabel(expense.category)}</Item> : null}
            </dl>

            {expense.tax_breakdown.length > 0 ? (
              <table className="w-full max-w-lg border-collapse text-[15px]">
                <caption className="mb-1.5 text-left text-[13px] font-semibold text-ink-soft">Desglose de IVA</caption>
                <thead>
                  <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
                    <th scope="col" className="py-1.5 pr-4 text-left font-semibold">
                      Tipo
                    </th>
                    <th scope="col" className="py-1.5 pr-4 text-right font-semibold">
                      Base
                    </th>
                    <th scope="col" className="py-1.5 text-right font-semibold">
                      Cuota
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {expense.tax_breakdown.map((line, index) => (
                    <tr key={index} className="border-b border-rule">
                      <td className="py-1.5 pr-4">{rateText(line.vat_rate)}</td>
                      <td className="py-1.5 pr-4 text-right tabular-nums">{formatCents(line.base_cents)}</td>
                      <td className="py-1.5 text-right tabular-nums">{formatCents(line.vat_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}

            <table className="w-full max-w-lg border-collapse text-[15px]">
              <caption className="sr-only">Importes</caption>
              <tbody>
                <tr className="border-b border-rule">
                  <th scope="row" className="py-1.5 pr-4 text-left font-normal">
                    Base imponible
                  </th>
                  <td className="py-1.5 text-right tabular-nums">{formatCents(expense.base_cents)}</td>
                </tr>
                {expense.vat_cents > 0 ? (
                  <tr className="border-b border-rule">
                    <th scope="row" className="py-1.5 pr-4 text-left font-normal">
                      IVA
                    </th>
                    <td className="py-1.5 text-right tabular-nums">{formatCents(expense.vat_cents)}</td>
                  </tr>
                ) : null}
                {expense.withholding_cents > 0 ? (
                  <tr className="border-b border-rule">
                    <th scope="row" className="py-1.5 pr-4 text-left font-normal">
                      Retención de IRPF
                    </th>
                    <td className="py-1.5 text-right tabular-nums">−{formatCents(expense.withholding_cents)}</td>
                  </tr>
                ) : null}
                <tr>
                  <th scope="row" className="py-2 pr-4 text-left font-bold">
                    Total
                  </th>
                  <td className="py-2 text-right text-lg font-bold tabular-nums">{formatCents(expense.total_cents)}</td>
                </tr>
              </tbody>
            </table>

            <p className="text-sm">
              <strong>IVA deducible: {expense.vat_cents === 0 ? "no hay IVA que deducir" : expense.deductible_vat ? "sí" : "no"}.</strong>
              {expense.supplier_scope === "eu" ? " El IVA de un proveedor de la UE no se deduce en el 303 de Cuadre; el gasto cuenta en el 130." : ""}
            </p>

            {voided ? null : (
              <div className="grid gap-5 border-t border-rule pt-5">
                <CategoryForm expenseId={expense.id} current={expense.category} />
                <div>
                  <VoidButton expenseId={expense.id} fromDocument={!manual} />
                </div>
              </div>
            )}
          </section>
          {hasOriginal && document ? <OriginalViewer documentId={document.id} mimeType={document.mime_type} filename={document.original_filename} /> : null}
        </div>
      </div>
    </>
  );
}
