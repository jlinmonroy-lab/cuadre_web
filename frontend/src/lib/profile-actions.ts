"use server";

// Server Actions del perfil: guardar el perfil, gestionar las series y el logo. Son CORTAS (no esperan a ningún servicio externo). Todo lo
// que reciben es entrada no confiable (las Server Actions son POST públicos y el proxy no las ve): se valida la forma aquí, se comprueba la
// sesión y la API vuelve a decidir (403 al gestor, 404 a la serie ajena, 409 y 422 con su texto). No hay ninguna regla fiscal aquí.
// Ni el NIF ni el IBAN se escriben en ningún registro: los errores solo llevan el texto que devuelve el servidor.
import { refresh } from "next/cache";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import type { FormState } from "@/lib/form-state";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";
import {
  LOGO_TYPES,
  fieldErrorsFromProfileProblem,
  fieldErrorsFromSeriesProblem,
  isUuid,
  logoProblem,
  toProfileBody,
  toSeriesBody,
  valuesFromProfile,
  valuesFromProfileForm,
  valuesFromSeriesForm,
} from "@/lib/profile-form";
import type { ReserveResult } from "@/lib/upload-flow";

const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };
const UNKNOWN_SERIES: FormState = { status: "error", message: "No encontramos esa serie." };
const SAVED = "Cambios guardados.";

// --- Perfil ---------------------------------------------------------------------------------------------------------------------

/** «Guardar» del perfil: todo o nada. Un dato que no se puede ni enviar se señala junto a su campo; el resto lo valida el servidor. */
export async function saveProfile(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromProfileForm((name) => formData.get(name));
  const parsed = toProfileBody(values);
  if (!parsed.ok) return { status: "error", fieldErrors: parsed.errors, values };

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/profile", { body: parsed.body });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    // Se repuebla con lo guardado (normalizado: el NIF en mayúsculas, el IBAN sin separadores y agrupado al mostrarlo).
    return { status: "sent", message: SAVED, values: valuesFromProfile(result.data) };
  }

  const problem = problemOf(result.response, result.error);
  const fieldErrors = fieldErrorsFromProfileProblem(problem);
  if (fieldErrors) return { status: "error", message: problem.message, fieldErrors, values };
  return { status: "error", message: problem.message, values };
}

// --- Series ---------------------------------------------------------------------------------------------------------------------

/** «Añadir serie». El código se pasa a mayúsculas en el servidor. */
export async function createSeries(_previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromSeriesForm((name) => formData.get(name));
  const parsed = toSeriesBody(values);
  if (!parsed.ok) return { status: "error", fieldErrors: parsed.errors, values };

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/invoice-series", {
      body: {
        code: parsed.body.code,
        description: parsed.body.description,
        first_number: parsed.body.first_number,
        make_default: formData.get("make_default") === "on",
      },
    });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: "Serie añadida." };
  }
  const problem = problemOf(result.response, result.error);
  const fieldErrors = problem.code === "series_code_taken" ? { code: problem.message } : fieldErrorsFromSeriesProblem(problem);
  return fieldErrors ? { status: "error", fieldErrors, values } : { status: "error", message: problem.message, values };
}

/** «Editar» una serie (`useActionState` con el id enlazado). `code` y `first_number` solo llegan si la serie no está en uso. */
export async function updateSeries(seriesId: string, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!isUuid(seriesId)) return UNKNOWN_SERIES;
  const values = valuesFromSeriesForm((name) => formData.get(name));
  const parsed = toSeriesBody(values);
  if (!parsed.ok) return { status: "error", fieldErrors: parsed.errors, values };

  // Solo se envía lo que el formulario trajo: una serie en uso deshabilita el código y el número inicial (no llegan en el FormData).
  const body: { description: string | null; code?: string; first_number?: number } = { description: parsed.body.description };
  if (formData.has("code") && parsed.body.code !== "") body.code = parsed.body.code;
  if (formData.has("first_number") && parsed.body.first_number !== null) body.first_number = parsed.body.first_number;

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PATCH("/api/invoice-series/{series_id}", { params: { path: { series_id: seriesId } }, body });
  } catch {
    return { ...UNAVAILABLE, values };
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: "Serie guardada." };
  }
  const problem = problemOf(result.response, result.error);
  if (problem.status === 404 || problem.status === 409) refresh();
  const fieldErrors = problem.code === "series_code_taken" ? { code: problem.message } : fieldErrorsFromSeriesProblem(problem);
  return fieldErrors ? { status: "error", fieldErrors, values } : { status: "error", message: problem.message, values };
}

export async function setDefaultSeries(seriesId: string): Promise<FormState> {
  if (!isUuid(seriesId)) return UNKNOWN_SERIES;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/invoice-series/{series_id}/default", { params: { path: { series_id: seriesId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: "Serie predeterminada cambiada." };
  }
  const problem = problemOf(result.response, result.error);
  refresh();
  return { status: "error", message: problem.message };
}

/** «Archivar» o «Reactivar» (`archived` es lo que se quiere, no lo que hay). */
export async function setSeriesArchived(seriesId: string, archived: boolean): Promise<FormState> {
  if (!isUuid(seriesId)) return UNKNOWN_SERIES;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PATCH("/api/invoice-series/{series_id}", { params: { path: { series_id: seriesId } }, body: { archived } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) {
    refresh();
    return { status: "sent", message: archived ? "Serie archivada." : "Serie reactivada." };
  }
  const problem = problemOf(result.response, result.error);
  refresh();
  return { status: "error", message: problem.message };
}

// --- Logo -----------------------------------------------------------------------------------------------------------------------

/** Reserva la subida del logo y devuelve la URL firmada: el NAVEGADOR sube directo a Storage (ADR-0016). Comprueba tipo y tamaño antes. */
export async function reserveLogo(input: unknown): Promise<ReserveResult> {
  const { mimeType, sizeBytes } = (typeof input === "object" && input !== null ? input : {}) as Record<string, unknown>;
  if (typeof mimeType !== "string" || typeof sizeBytes !== "number" || !Number.isSafeInteger(sizeBytes)) {
    return { ok: false, message: "No se puede subir ese archivo." };
  }
  const problem = logoProblem({ type: mimeType, size: sizeBytes });
  if (problem !== null || !(LOGO_TYPES as readonly string[]).includes(mimeType)) {
    return { ok: false, message: problem ?? "No se puede subir ese archivo." };
  }

  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/profile/logo", { body: { mime_type: mimeType, size_bytes: sizeBytes } });
  } catch {
    return { ok: false, message: SERVICE_UNAVAILABLE.message };
  }
  if (!result.data) return { ok: false, message: problemOf(result.response, result.error).message };
  const { upload_id: id, upload } = result.data;
  return { ok: true, id, upload: { url: upload.url, headers: upload.headers } };
}

export type LogoResult = { ok: true } | { ok: false; message: string };

/** Comprueba en el servidor lo subido (existe, tipo, tamaño y firma), lo guarda y borra el logo anterior. */
export async function completeLogo(uploadId: unknown): Promise<LogoResult> {
  if (!isUuid(uploadId)) return { ok: false, message: "No encontramos esa subida." };
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.POST("/api/profile/logo/{upload_id}/complete", { params: { path: { upload_id: uploadId } } });
  } catch {
    return { ok: false, message: SERVICE_UNAVAILABLE.message };
  }
  if (!result.data) return { ok: false, message: problemOf(result.response, result.error).message };
  refresh();
  return { ok: true };
}

export async function removeLogo(): Promise<LogoResult> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.DELETE("/api/profile/logo");
  } catch {
    return { ok: false, message: SERVICE_UNAVAILABLE.message };
  }
  if (result.response.status !== 204) return { ok: false, message: problemOf(result.response, result.error).message };
  refresh();
  return { ok: true };
}

/** URL firmada de lectura (60 s) para la vista previa, o `null` si no hay logo o no se pudo. Nunca se registra. */
export async function getLogoUrl(): Promise<string | null> {
  const api = await authenticatedApi();
  try {
    const result = await api.GET("/api/profile/logo");
    return result.data?.url ?? null;
  } catch {
    return null;
  }
}
