"use server";

// Server Actions de Gastos: reservar una subida, guardar las correcciones y descartar. Todo lo que reciben es entrada no confiable
// (las Server Actions son POST públicos y el proxy no las ve): se valida aquí, se comprueba la sesión y la API vuelve a decidir
// (403 al gestor, 404 al documento ajeno). La lectura (`complete`/`retry`) NO está aquí: va por Route Handlers, ver `upload-flow.ts`.
import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { apiFor, sessionToken } from "@/lib/api-server";
import { MAX_UPLOAD_BYTES, MIME_TYPES, isDocumentId } from "@/lib/documents";
import type { FormState } from "@/lib/form-state";
import { SERVICE_UNAVAILABLE, describeProblem, type Problem } from "@/lib/problems";
import { toReviewBody, valuesFromForm } from "@/lib/review";
import type { ReserveInput, ReserveResult } from "@/lib/upload-flow";

type Api = ReturnType<typeof apiFor>;

async function session(): Promise<Api> {
  const token = await sessionToken();
  if (!token) redirect("/login");
  return apiFor(token);
}

/** 401 y 403 no se "muestran": llevan a donde corresponde. Lo demás se devuelve para pintarlo junto a la acción. */
function problemOf(response: Response, error: unknown): Problem {
  if (response.status === 401) redirect("/auth/cerrar?aviso=sesion");
  if (response.status === 403) redirect("/403");
  return describeProblem({ status: response.status, body: error, retryAfter: response.headers.get("retry-after") });
}

// --- Reservar una subida ---------------------------------------------------------------------------------------------------------

function parseReserve(input: unknown): ReserveInput | null {
  if (typeof input !== "object" || input === null) return null;
  const { filename, mimeType, sizeBytes, source } = input as Record<string, unknown>;
  if (typeof filename !== "string" || filename.length === 0 || filename.length > 1000) return null;
  if (typeof mimeType !== "string" || !(MIME_TYPES as readonly string[]).includes(mimeType)) return null;
  if (typeof sizeBytes !== "number" || !Number.isSafeInteger(sizeBytes) || sizeBytes < 1 || sizeBytes > MAX_UPLOAD_BYTES) return null;
  if (source !== "file" && source !== "camera") return null;
  return { filename, mimeType: mimeType as ReserveInput["mimeType"], sizeBytes, source };
}

export async function reserveUpload(input: unknown): Promise<ReserveResult> {
  const body = parseReserve(input);
  if (body === null) return { ok: false, message: "No se puede subir ese archivo: comprueba que sea un PDF o una imagen de menos de 15 MB." };

  const api = await session();
  let result;
  try {
    result = await api.POST("/api/documents", {
      body: { filename: body.filename, mime_type: body.mimeType, size_bytes: body.sizeBytes, source: body.source },
    });
  } catch {
    return { ok: false, message: SERVICE_UNAVAILABLE.message };
  }
  if (!result.data) return { ok: false, message: problemOf(result.response, result.error).message };

  const { id, upload } = result.data;
  return { ok: true, id, upload: { url: upload.url, headers: upload.headers } };
}

// --- Descartar -------------------------------------------------------------------------------------------------------------------

/** Descarte silencioso de una reserva que no llegó a subirse. Nunca lanza ni redirige: es limpieza, no una acción de la persona. */
export async function discardReservation(documentId: unknown): Promise<void> {
  if (!isDocumentId(documentId)) return;
  const token = await sessionToken();
  if (!token) return;
  try {
    await apiFor(token).DELETE("/api/documents/{document_id}", { params: { path: { document_id: documentId } } });
  } catch {
    // inofensivo: una reserva en `uploading` no sale en la lista ni ocupa ninguna lectura
  }
}

/** «Descartar» de la pantalla de revisión. Si sale bien, vuelve a la lista con un aviso (no devuelve nada: redirige). */
export async function discardDocument(documentId: string): Promise<FormState> {
  if (!isDocumentId(documentId)) return { status: "error", message: "No encontramos ese documento." };
  const api = await session();
  let result;
  try {
    result = await api.DELETE("/api/documents/{document_id}", { params: { path: { document_id: documentId } } });
  } catch {
    return { status: "error", message: SERVICE_UNAVAILABLE.message };
  }
  // Ya descartado (409) o inexistente (404): para la persona el resultado es el que querían.
  if (result.response.ok || result.response.status === 409 || result.response.status === 404) redirect("/gastos?aviso=descartado");
  return { status: "error", message: problemOf(result.response, result.error).message };
}

// --- Corregir --------------------------------------------------------------------------------------------------------------------

/** Guarda las correcciones (`useActionState` con el id enlazado). Un importe que no se entiende se señala junto a su campo y no se guarda. */
export async function saveReview(documentId: string, _previous: FormState, formData: FormData): Promise<FormState> {
  const values = valuesFromForm((name) => formData.get(name));
  if (!isDocumentId(documentId)) return { status: "error", message: "No encontramos ese documento.", values };

  const parsed = toReviewBody(values);
  if (!parsed.ok) return { status: "error", fieldErrors: parsed.errors, values };

  const api = await session();
  let result;
  try {
    result = await api.PUT("/api/documents/{document_id}/review", {
      params: { path: { document_id: documentId } },
      body: parsed.body,
    });
  } catch {
    return { status: "error", message: SERVICE_UNAVAILABLE.message, values };
  }
  if (!result.data) {
    const problem = problemOf(result.response, result.error);
    // Un 409 aquí es «ya no se puede corregir» (se descartó o se está leyendo): el texto de la API lo explica.
    return { status: "error", message: problem.message, values };
  }

  refresh(); // la cabecera y la lista reflejan el cambio en la misma respuesta
  return { status: "sent", message: "Cambios guardados.", values };
}
