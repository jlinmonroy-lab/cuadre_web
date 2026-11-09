"use client";

import Link from "next/link";
import { useActionState } from "react";

import { ErrorSummary } from "@/components/error-summary";
import { FormRow } from "@/components/form-row";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { initialExpenseValues } from "@/lib/expense-form";
import { createExpense } from "@/lib/expenses-actions";
import { CATEGORY_LABELS, EXPENSE_CATEGORIES } from "@/lib/expenses";
import { initialFormState } from "@/lib/form-state";

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
        <FormRow idPrefix="gasto" name="expense_date" label="Fecha" error={errors["expense_date"]}>
          {(control) => <Input {...control} name="expense_date" type="date" max={today} defaultValue={values["expense_date"] ?? ""} />}
        </FormRow>
        <FormRow idPrefix="gasto" name="concept" label="Concepto" error={errors["concept"]}>
          {(control) => <Input {...control} name="concept" maxLength={200} autoComplete="off" placeholder="Cuota de autónomos" defaultValue={values["concept"] ?? ""} />}
        </FormRow>
        <FormRow idPrefix="gasto" name="category" label="Categoría" error={errors["category"]}>
          {(control) => (
            <NativeSelect {...control} name="category" defaultValue={values["category"] ?? ""}>
              {EXPENSE_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {CATEGORY_LABELS[category]}
                </option>
              ))}
            </NativeSelect>
          )}
        </FormRow>
        <FormRow idPrefix="gasto" name="amount" label="Importe (€)" error={errors["amount"]} hint="Por ejemplo 294,00. Sin IVA: este gasto no lleva factura.">
          {(control) => <Input {...control} name="amount" inputMode="decimal" autoComplete="off" placeholder="Ej.: 294,00" defaultValue={values["amount"] ?? ""} className="text-right tabular-nums" />}
        </FormRow>
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
