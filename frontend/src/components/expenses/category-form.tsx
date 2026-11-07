"use client";

import { CircleCheck } from "lucide-react";
import { useActionState, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { setExpenseCategory } from "@/lib/expenses-actions";
import { CATEGORY_LABELS, EXPENSE_CATEGORIES, type ExpenseCategory } from "@/lib/expenses";
import { initialFormState } from "@/lib/form-state";

/** Cambiar la categoría de un gasto no anulado (RF-011, AC-12). Lo único que se puede cambiar de un gasto registrado, junto con anularlo. */
export function CategoryForm({ expenseId, current }: { expenseId: string; current: ExpenseCategory }) {
  const [state, action, pending] = useActionState(setExpenseCategory.bind(null, expenseId), initialFormState);
  const [value, setValue] = useState<ExpenseCategory>(current);

  return (
    <form action={action} className="grid gap-2">
      <Label htmlFor="detalle-categoria" className="text-[13px] font-semibold text-ink-soft">
        Categoría
      </Label>
      <div className="flex flex-wrap items-center gap-2">
        <NativeSelect
          id="detalle-categoria"
          name="category"
          value={value}
          onChange={(event) => setValue(event.target.value as ExpenseCategory)}
          className="max-w-xs"
        >
          {EXPENSE_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {CATEGORY_LABELS[category]}
            </option>
          ))}
        </NativeSelect>
        <Button type="submit" variant="outline" disabled={pending || value === current}>
          {pending ? "Guardando…" : "Cambiar categoría"}
        </Button>
      </div>
      {state.status === "sent" ? (
        <p role="status" className="flex items-center gap-2 text-sm font-semibold text-status-ok">
          <CircleCheck aria-hidden="true" className="size-4 shrink-0" />
          {state.message}
        </p>
      ) : null}
      {state.status === "error" ? (
        <p role="alert" className="text-sm font-semibold text-status-error">
          {state.message}
        </p>
      ) : null}
    </form>
  );
}
