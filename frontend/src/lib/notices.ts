// `?aviso=` elige un texto de una lista cerrada: nunca se pinta lo que llegue en la URL (suplantación de mensajes, XSS).
// Sin dependencias ni alias: lo ejecutan directamente los tests.

export type Notice = { tone: "info" | "success" | "error"; text: string };

// Un Map (no un objeto): «constructor» o «toString» no deben resolverse a miembros de Object.prototype.
const NOTICES = new Map<string, Notice>([
  ["restablecida", Object.freeze({ tone: "success", text: "Contraseña actualizada. Ya puedes iniciar sesión." })],
  ["suspendida", Object.freeze({ tone: "error", text: "Tu cuenta está suspendida y no puedes acceder." })],
  ["perfil", Object.freeze({ tone: "error", text: "No hemos encontrado tu perfil. Inténtalo de nuevo más tarde." })],
  ["enlace", Object.freeze({ tone: "error", text: "El enlace no es válido o ha caducado. Pide uno nuevo." })],
  ["sesion", Object.freeze({ tone: "info", text: "Tu sesión ha caducado. Inicia sesión de nuevo." })],
  ["descartado", Object.freeze({ tone: "success", text: "Documento descartado." })],
  // SPEC-W-003: registrar, anotar y anular un gasto.
  ["registrado", Object.freeze({ tone: "success", text: "Gasto registrado." })],
  ["anotado", Object.freeze({ tone: "success", text: "Gasto anotado." })],
  ["anulado", Object.freeze({ tone: "success", text: "Gasto anulado." })],
  ["anulado-documento", Object.freeze({ tone: "success", text: "Gasto anulado: el documento vuelve a «Para revisar»." })],
]);

export function noticeFor(code: unknown): Notice | null {
  return typeof code === "string" ? (NOTICES.get(code) ?? null) : null;
}
