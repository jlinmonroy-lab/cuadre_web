"use server";

// Server Actions del asistente: borrar una conversación y valorar una respuesta. Son CORTAS (no esperan a ningún servicio externo). Todo lo que reciben es
// entrada no confiable (las Server Actions son POST públicos y el proxy no las ve): se valida la forma aquí y la API vuelve a decidir (403 al gestor,
// 404 a lo ajeno). Nada de lo que se ha escrito o respondido se escribe en ningún registro.
import { refresh } from "next/cache";

import { authenticatedApi, problemOf } from "@/lib/api-actions";
import { isReason, isUuid } from "@/lib/chat";
import type { FormState } from "@/lib/form-state";
import { SERVICE_UNAVAILABLE } from "@/lib/problems";

const UNAVAILABLE: FormState = { status: "error", message: SERVICE_UNAVAILABLE.message };

/** Borra la conversación con sus mensajes y valoraciones. No se puede deshacer. */
export async function deleteConversation(conversationId: string): Promise<FormState> {
  if (!isUuid(conversationId)) return { status: "error", message: "No encontramos esa conversación." };
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.DELETE("/api/chat/conversations/{conversation_id}", { params: { path: { conversation_id: conversationId } } });
  } catch {
    return UNAVAILABLE;
  }
  if (result.response.status === 204) {
    refresh();
    return { status: "sent", message: "Conversación borrada." };
  }
  return { status: "error", message: problemOf(result.response, result.error).message };
}

/** Valora (o cambia la valoración de) una respuesta del asistente. «No útil» exige un motivo de la lista cerrada; «útil» no lleva ninguno. */
export async function rateMessage(messageId: string, rating: string, reason: string | null): Promise<FormState> {
  if (!isUuid(messageId)) return { status: "error", message: "No encontramos esa respuesta." };
  if (rating !== "up" && rating !== "down") return { status: "error", message: "Elige «útil» o «no útil»." };
  if (rating === "down" && !isReason(reason)) return { status: "error", message: "Elige qué ha fallado." };
  const api = await authenticatedApi();
  let result;
  try {
    result = await api.PUT("/api/chat/messages/{message_id}/feedback", {
      params: { path: { message_id: messageId } },
      body: { rating, reason: rating === "up" ? null : isReason(reason) ? reason : null },
    });
  } catch {
    return UNAVAILABLE;
  }
  if (result.data) return { status: "sent", message: "Valoración guardada." };
  return { status: "error", message: problemOf(result.response, result.error).message };
}
