"use client";

import Link from "next/link";
import { useActionState, type ReactNode } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { initialExpenseValues } from "@/lib/expense-form";
import { createExpense } from "@/lib/expenses-actions";
import { CATEGORY_LABELS, EXPENSE_CATEGORIES } from "@/lib/expenses";
import { initialFormState } from "@/lib/form-state";

type Control = { id: string; "aria-invalid": true | undefined; "aria-describedby": string | undefined };

/** Etiqueta + control + ayuda + error, enlazados con `aria-describedby`. */
function Row({ name, label, error, hint, children }: { name: string; label: string; error?: string | undefined; hint?: string; children: (control: Control) => ReactNode }) {
  const id = `gasto-${name}`;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id} className="text-[13px] font-semibold text-ink-soft">
        {label}
      </Label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy })}
      {hint ? (
        <p id={hintId} className="text-xs text-ink-soft">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-[13px] font-semibold text-status-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * «Gasto sin factura» (RF-011): para lo que no lleva factura con IVA, como la cuota de autónomos. Un dato que no se entiende se señala
 * junto a su campo y no se envía; la fecha futura o fuera de rango la decide la API (con el «hoy» de Madrid) y vuelve junto a su campo.
 */
export function ExpenseForm({ today }: { today: string }) {
  const [state, action, pending] = useActionState(createExpense, initialFormState);
  const values = state.values ?? initialExpenseValues(today);
  const errors = state.fieldErrors ?? {};
  const fieldIds = { expense_date: "gasto-expense_date", concept: "gasto-concept", category: "gasto-category", amount: "gasto-amount" };

  return (
    <form action={action} noValidate className="grid max-w-3xl gap-6">
      <ErrorSummary state={state} fieldIds={fieldIds} />
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(220px,1fr))]">
        <Row name="expense_date" label="Fecha" error={errors["expense_date"]}>
          {(control) => <Input {...control} name="expense_date" type="date" max={today} defaultValue={values["expense_date"] ?? ""} />}
        </Row>
        <Row name="concept" label="Concepto" error={errors["concept"]}>
          {(control) => <Input {...control} name="concept" maxLength={200} autoComplete="off" placeholder="Cuota de autónomos" defaultValue={values["concept"] ?? ""} />}
        </Row>
        <Row name="category" label="Categoría" error={errors["category"]}>
          {(control) => (
            <NativeSelect {...control} name="category" defaultValue={values["category"] ?? ""}>
              {EXPENSE_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {CATEGORY_LABELS[category]}
                </option>
              ))}
            </NativeSelect>
          )}
        </Row>
        <Row name="amount" label="Importe (€)" error={errors["amount"]} hint="Por ejemplo 294,00. Sin IVA: este gasto no lleva factura.">
          {(control) => <Input {...control} name="amount" inputMode="decimal" autoComplete="off" placeholder="Ej.: 294,00" defaultValue={values["amount"] ?? ""} className="text-right tabular-nums" />}
        </Row>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-5">
        <Button type="submit" disabled={pending}>
          {pending ? "Guardando…" : "Guardar gasto"}
        </Button>
        <Link href="/gastos" className={buttonVariants({ variant: "outline" })}>
          Cancelar
        </Link>
      </div>
    </form>
  );
}
