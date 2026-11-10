"use server";

// Server Actions de clientes: crear, editar, archivar y reactivar. Son CORTAS (no esperan a ningún servicio externo). Todo lo que reciben es
// entrada no confiable (las Server Actions son POST públicos y el proxy no las ve): se valida la forma aquí, se comprueba la sesión y la API
// vuelve a decidir (403 al gestor, 404 al cliente ajeno, 409 y 422 con su texto). No hay ninguna regla fiscal aquí: el NIF, el país y el ámbito
// los valida el servidor. Ni el nombre, ni el NIF, ni el domicilio de un cliente se escriben en ningún registro: los errores solo llevan el
// texto que devuelve el servidor.
import { refresh } from "next/cache";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import { fieldErrorsFromClientProblem, isClientId, toClientBody, valuesFromClient, valuesFromClientForm } from "@/lib/clients-form";
import type { FormState } from "@/lib/form-state";
import { SERVICE_UNAVAILABLE, type Problem } from "@/lib/problems";

const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };
const UNKNOWN_CLIENT: FormState = { status: "error", message: "No encontramos ese cliente." };

/**
 * Un error de la API para el formulario. Con errores de campo, cada texto va junto a su campo y en el resumen; el titular solo se añade si dice
 * algo más que ellos (el `client_tax_id_taken` ya es el texto del campo: repetirlo como titular sería leerlo dos veces).
 */
function failure(problem: Problem, values: Record<string, string>): FormState {
  const fieldErrors = fieldErrorsFromClientProblem(problem);
  if (!fieldErrors) return { status: "error", message: problem.message, values };
  return problem.code === "client_tax_id_taken" ? { status: "error", fieldErrors, values } : { status: "error", message: problem.message, fieldErrors, values };
}

/** «Añadir cliente»: todo o nada. El ámbito y el estado de VIES los calcula el servidor. */
export async function createClient(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromClientForm((name) => formData.get(name));
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/clients", { body: toClientBody(values) });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    // Sin `values`: el formulario se vacía para el siguiente cliente.
    return { status: "sent", message: "Cliente añadido." };
  }
  return failure(problemOf(result.response, result.error), values);
}

/** «Editar» un cliente (`useActionState` con el id enlazado). Sustituye todos los datos; el servidor recalcula el ámbito y el VIES. */
export async function updateClient(clientId: string, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!isClientId(clientId)) return UNKNOWN_CLIENT;
  const values = valuesFromClientForm((name) => formData.get(name));
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/clients/{client_id}", { params: { path: { client_id: clientId } }, body: toClientBody(values) });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    // Se repuebla con lo guardado (normalizado: el NIF en mayúsculas y sin separadores).
    return { status: "sent", message: "Cliente guardado.", values: valuesFromClient(result.data) };
  }
  const problem = problemOf(result.response, result.error);
  // Un cliente archivado o que ya no existe: la lista cambió, se refresca para que la pantalla lo diga.
  if (problem.status === 404 || problem.code === "client_archived") refresh();
  return failure(problem, values);
}

/** «Archivar» o «Reactivar» (`archived` es lo que se quiere, no lo que hay). Un cliente no se borra. */
export async function setClientArchived(clientId: string, archived: boolean): Promise<FormState> {
  if (!isClientId(clientId)) return UNKNOWN_CLIENT;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/clients/{client_id}/archived", { params: { path: { client_id: clientId } }, body: { archived } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: archived ? "Cliente archivado." : "Cliente reactivado." };
  }
  const problem = problemOf(result.response, result.error);
  refresh();
  return { status: "error", message: problem.message };
}
