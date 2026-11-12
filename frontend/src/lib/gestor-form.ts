// Formulario de invitación ↔ cuerpo de la API (SPEC-W-010 §5.5, hito 3). Puro: lo ejecutan directamente los tests.
//
// La interfaz no valida el correo: lo hace el servidor (formato, no a uno mismo, duplicados y límite) y responde sin revelar si la persona
// existe. Aquí solo se limpia el texto, se cruza con el cuerpo y se lleva cada error de la API junto al campo.
import type { components } from "@/api/schema";

import type { Problem } from "./problems.ts";

export type InviteBody = components["schemas"]["InviteInput"];
export type InvitedAccess = components["schemas"]["InvitedAccess"];

/** El único campo del formulario. */
export const INVITE_FORM_FIELDS = ["email"] as const;

/** Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API. */
const code = (n: number) => String.fromCharCode(n);
const CONTROL = new RegExp(
  `[${code(0)}-${code(0x1f)}${code(0x7f)}-${code(0x9f)}${code(0x200b)}-${code(0x200f)}${code(0x2028)}-${code(0x202e)}${code(0x2060)}${code(0xfeff)}]`,
  "g",
);

/** Lee del `FormData` solo el campo conocido (entrada no confiable: se ignora todo lo demás). */
export function valuesFromInviteForm(get: (name: string) => unknown): Record<string, string> {
  const value = get("email");
  return { email: typeof value === "string" ? value : "" };
}

/** El cuerpo de la API: sin controles ni espacios sobrantes. Mayúsculas y formato los trata el servidor. */
export function toInviteBody(values: Record<string, string>): InviteBody {
  return { email: (values["email"] ?? "").replace(CONTROL, " ").trim() };
}

/** Los códigos de la API que hablan del correo que se acaba de escribir: su texto va junto al campo. */
const EMAIL_CODES: ReadonlySet<string> = new Set(["invalid_email", "cannot_invite_self", "invitation_already_open", "validation_error"]);

/** Errores por campo de una invitación rechazada, o `undefined` si el error no es del correo (el límite de invitaciones, un fallo del servicio…). */
export function fieldErrorsFromInviteProblem(problem: Problem): Record<string, string> | undefined {
  if (!EMAIL_CODES.has(problem.code)) return undefined;
  // `validation_error` es un cuerpo mal formado (p. ej. un correo de más de 320 caracteres): el texto genérico de la API no explica nada.
  return { email: problem.code === "validation_error" ? "Escribe un correo electrónico válido." : problem.message };
}

/** Lo que se le dice a la persona al invitar: si el correo no salió, la invitación existe igualmente y queda pendiente. */
export function inviteMessage(access: Pick<InvitedAccess, "gestor_email" | "email_sent">): string {
  return access.email_sent
    ? `Invitación enviada a ${access.gestor_email}. Cuando la acepte, podrá consultar tu contabilidad.`
    : "La invitación se ha creado, pero no hemos podido enviar el correo. Queda pendiente; puedes revocarla y volver a invitar.";
}
