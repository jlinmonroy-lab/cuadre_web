// Lecturas del chat para el Server Component de /asistente (list_chat_conversations y get_chat_conversation). Corren en el servidor con el token de la
// sesión. Un 401 cierra la sesión con aviso, un 403 lleva a /403, una conversación que no existe (o es de otra persona: la API no lo distingue) es
// `missing` y cualquier otro fallo es «servicio no disponible» (app/error.tsx): nunca se enseña el cuerpo de un error.
import "server-only";

import type { components } from "@/api/schema";
import { authenticatedApi, failRead } from "@/lib/api-actions";
import { ServiceUnavailableError } from "@/lib/session";

export type ConversationSummary = components["schemas"]["ConversationSummary"];
export type ConversationDetail = components["schemas"]["ConversationDetail"];

export async function getConversations(): Promise<ConversationSummary[]> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/chat/conversations");
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return result.data.items;
  return failRead(result.response.status);
}

export async function getConversation(conversationId: string): Promise<{ status: "ok"; data: ConversationDetail } | { status: "missing" }> {
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.GET("/api/chat/conversations/{conversation_id}", { params: { path: { conversation_id: conversationId } } });
  } catch {
    throw new ServiceUnavailableError();
  }
  if (result.data) return { status: "ok", data: result.data };
  if (result.response.status === 404) return { status: "missing" };
  return failRead(result.response.status);
}
