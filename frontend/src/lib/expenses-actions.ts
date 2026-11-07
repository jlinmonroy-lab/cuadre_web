"use server";

// Server Actions de gastos: registrar un documento, anotar un gasto sin factura, cambiar la categoría y anular. A diferencia de la lectura
// de una factura, son CORTAS (no esperan a ningún servicio externo), así que no necesitan Route Handlers. Todo lo que reciben es entrada
// no confiable (las Server Actions son POST públicos y el proxy no las ve): se valida aquí, se comprueba la sesión y la API vuelve a
// decidir (403 al gestor, 404 al gasto ajeno, 409 y 422 con su texto). No hay ninguna regla fiscal aquí: las comprobaciones son del servidor.
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import { isDocumentId } from "@/lib/documents";
import { fieldErrorsFromProblem, toExpenseBody, valuesFromExpenseForm } from "@/lib/expense-form";
import { isExpenseCategory, isExpenseId } from "@/lib/expenses";
import type { FormState } from "@/lib/form-state";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";

const UNKNOWN_DOCUMENT: FormState = { status: "error", message: "No encontramos ese documento." };
const UNKNOWN_EXPENSE: FormState = { status: "error", message: "No encontramos ese gasto." };
const CHOOSE_CATEGORY: FormState = { status: "error", message: "Elige una categoría de la lista." };
const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };

// --- Registrar el gasto de un documento --------------------------------------------------------------------------------------------

/**
 * «Registrar gasto» (`useActionState` con el id enlazado). Si sale bien redirige a la lista con el aviso; si no, devuelve el texto de la API
 * y refresca la pantalla (las comprobaciones que ve la persona deben ser las que el servidor acaba de calcular).
 */
export async function confirmDocument(documentId: string, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!isDocumentId(documentId)) return UNKNOWN_DOCUMENT;
  const category = formData.get("category");
  if (!isExpenseCategory(category)) return CHOOSE_CATEGORY;
  const acknowledge = formData.get("acknowledge_suspicion") === "on";

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/documents/{document_id}/confirm", {
      params: { path: { document_id: documentId } },
      body: { category, acknowledge_suspicion: acknowledge },
    });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) redirect("/gastos?aviso=registrado");

  const problem = problemOf(result.response, result.error);
  if (problem.status === 404 || problem.status === 409 || problem.status === 422) refresh();
  return { status: "error", message: problem.message };
}

// --- Gasto sin factura -------------------------------------------------------------------------------------------------------------

/** «Guardar gasto» del formulario `/gastos/nuevo`. Un dato que no se entiende se señala junto a su campo y no se envía. */
export async function createExpense(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromExpenseForm((name) => formData.get(name));
  const parsed = toExpenseBody(values);
  if (!parsed.ok) return { status: "error", fieldErrors: parsed.errors, values };

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/expenses", { body: parsed.body });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) redirect("/gastos?aviso=anotado");

  const problem = problemOf(result.response, result.error);
  const fieldErrors = fieldErrorsFromProblem(problem);
  if (fieldErrors) return { status: "error", fieldErrors, values };
  return { status: "error", message: problem.message, values };
}

// --- Corregir y anular -------------------------------------------------------------------------------------------------------------

/** Cambia la categoría de un gasto no anulado (`useActionState` con el id enlazado). */
export async function setExpenseCategory(expenseId: string, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!isExpenseId(expenseId)) return UNKNOWN_EXPENSE;
  const category = formData.get("category");
  if (!isExpenseCategory(category)) return { ...CHOOSE_CATEGORY, values: {} };

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/expenses/{expense_id}/category", {
      params: { path: { expense_id: expenseId } },
      body: { category },
    });
  } catch {
    return { ...UNAVAILABLE, values: { category } };
  }
  if (result.data) {
    refresh(); // la lista y el detalle reflejan el cambio en la misma respuesta
    return { status: "sent", message: "Categoría actualizada.", values: { category } };
  }
  const problem = problemOf(result.response, result.error);
  if (problem.status === 404 || problem.status === 409) refresh();
  return { status: "error", message: problem.message, values: { category } };
}

/**
 * «Anular gasto». Si sale bien, un gasto de documento lleva al documento (que vuelve a «Para revisar») y uno sin factura, a la lista;
 * en los dos casos con su aviso. Si falla, devuelve el texto de la API (no devuelve nada si sale bien: redirige).
 */
export async function voidExpense(expenseId: string): Promise<FormState> {
  if (!isExpenseId(expenseId)) return UNKNOWN_EXPENSE;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/expenses/{expense_id}/void", { params: { path: { expense_id: expenseId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) {
    const documentId = result.data.document_id;
    redirect(isDocumentId(documentId) ? `/gastos/${documentId}?aviso=anulado-documento` : "/gastos?aviso=anulado");
  }
  const problem = problemOf(result.response, result.error);
  if (problem.status === 404 || problem.status === 409) refresh(); // ya estaba anulado o ya no existe: la pantalla lo muestra
  return { status: "error", message: problem.message };
}
