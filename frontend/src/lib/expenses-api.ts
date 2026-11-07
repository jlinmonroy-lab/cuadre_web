// Lecturas de gastos para los Server Components (list_expenses, get_expense). Corren en el servidor con el token de la sesión.
// Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo es «servicio no disponible» (app/error.tsx):
// nunca se enseña el cuerpo de un error.
import "server-only";

import { redirect } from "next/navigation";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead } from "@/lib/api-actions";
import { isExpenseId } from "@/lib/expenses";
import { ServiceUnavailableError } from "@/lib/session";

export type ExpenseSummary = components["schemas"]["ExpenseSummary"];
export type ExpenseDetail = components["schemas"]["Expense"];
export type ExpensePage = components["schemas"]["ExpensePage"];

/**
 * Una página de gastos vivos, del más reciente al más antiguo. Con un `cursor` que la API no reconoce (manipulado, o de una versión
 * anterior) se vuelve a la primera página: la lista se resuelve recargándola.
 */
export async function listExpenses(cursor: string | null): Promise<ExpensePage> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/expenses", { params: { query: cursor ? { cursor } : {} } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  if (cursor && result.response.status === 422) redirect("/gastos");
  return failRead(result.response.status);
}

/** El gasto (también uno anulado), o `null` si no existe (también si es de otra persona: la API no lo distingue). */
export async function getExpense(id: string): Promise<ExpenseDetail | null> {
  if (!isExpenseId(id)) return null;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/expenses/{expense_id}", { params: { path: { expense_id: id } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return result.response.status === 404 ? null : failRead(result.response.status);
}
