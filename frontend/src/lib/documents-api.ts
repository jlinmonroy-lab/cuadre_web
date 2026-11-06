// Lecturas de documentos para los Server Components de Gastos (list_documents, get_document, get_document_preview).
// Corren en el servidor con el token de la sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403 y cualquier otro fallo
// es «servicio no disponible» (app/error.tsx): nunca se enseña el cuerpo de un error.
import "server-only";

import { redirect } from "next/navigation";

import type { components } from "@/api/schema";
import { apiFor, sessionToken } from "@/lib/api-server";
import { isDocumentId } from "@/lib/documents";
import { ServiceUnavailableError } from "@/lib/session";

export type DocumentSummary = components["schemas"]["DocumentSummary"];
export type DocumentDetail = components["schemas"]["Document"];
export type DocumentPreview = components["schemas"]["PreviewResponse"];

async function authenticatedApi() {
  const token = await sessionToken();
  if (!token) redirect("/login");
  return apiFor(token);
}

/** Qué hacer con un estado que no es el esperado. */
function fail(status: number): never {
  if (status === 401) redirect("/auth/cerrar?aviso=sesion");
  if (status === 403) redirect("/403");
  throw new ServiceUnavailableError();
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/documents");
  } catch {
    throw new ServiceUnavailableError();
  }
  return result.data ?? fail(result.response.status);
}

/** El documento, o `null` si no existe (también si es de otra persona o está descartado: la API no lo distingue). */
export async function getDocument(id: string): Promise<DocumentDetail | null> {
  if (!isDocumentId(id)) return null;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/documents/{document_id}", { params: { path: { document_id: id } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data;
  return result.response.status === 404 ? null : fail(result.response.status);
}

/** URL firmada de 60 s para ver el original. `null` si no hay archivo que enseñar o Storage no responde: la pantalla sigue sirviendo. */
export async function getPreview(id: string): Promise<DocumentPreview | null> {
  if (!isDocumentId(id)) return null;
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/documents/{document_id}/preview", { params: { path: { document_id: id } } });
  } catch {
    return null;
  }
  if (result.data) return result.data;
  if (result.response.status === 401 || result.response.status === 403) fail(result.response.status);
  return null; // 404, 409 (todavía sin archivo), 503…: se pinta la pantalla sin el original
}
