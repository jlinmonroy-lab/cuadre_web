import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ExpenseForm } from "@/components/expenses/expense-form";
import { madridDay } from "@/lib/expenses";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Gasto sin factura" };

export default async function NewExpensePage() {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const today = madridDay(new Date()); // solo propone la fecha y limita el selector: el límite de verdad lo pone la API

  return (
    <>
      <header className="mb-6 grid gap-2">
        <Link href="/gastos" className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-action underline underline-offset-2 hover:text-action-hover">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Gastos
        </Link>
        <h1>Gasto sin factura</h1>
        <p className="max-w-[70ch] text-ink-soft">Para gastos que no llevan factura con IVA, como la cuota de autónomos o las comisiones del banco.</p>
      </header>
      <ExpenseForm today={today} />
    </>
  );
}
