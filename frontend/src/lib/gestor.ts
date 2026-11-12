// «Mi gestor» en la interfaz del autónomo (SPEC-W-010 §5.5, hito 3). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor: el estado de cada acceso (`expired` ya lo calcula la API), las anotaciones y el registro de
// actividad. Aquí solo se redactan frases, se da formato a las fechas y se resuelve a qué gestor se refiere cada entrada. Nada de lo que
// llega por la red se refleja sin pasar por una lista cerrada o por un formato.
import type { components } from "@/api/schema";

export type GestorAccess = components["schemas"]["GestorAccess"];
export type GestorNote = components["schemas"]["GestorNote"];
export type ActivityEntry = components["schemas"]["ActivityEntry"];
export type AccessStatus = GestorAccess["status"];

// --- Estados --------------------------------------------------------------------------------------------------------------------

export const STATUS_LABEL: Record<AccessStatus, string> = {
  pending: "Pendiente de aceptar",
  active: "Activo",
  declined: "Rechazada",
  revoked: "Revocada",
  expired: "Caducada",
};

/** Cómo se pinta el estado (además del texto, que siempre se escribe): `ok` = acceso vigente, `wait` = espera respuesta, `closed` = ya no vale. */
export type Tone = "ok" | "wait" | "closed";
export const STATUS_TONE: Record<AccessStatus, Tone> = { pending: "wait", active: "ok", declined: "closed", revoked: "closed", expired: "closed" };

/** Solo una invitación pendiente o un acceso activo se pueden revocar; el servidor lo vuelve a comprobar. */
export function canRevoke(status: AccessStatus): boolean {
  return status === "pending" || status === "active";
}

/** Los accesos abiertos (pendientes o activos) cuentan para el límite de invitaciones. */
export function openCount(accesses: readonly Pick<GestorAccess, "status">[]): number {
  return accesses.filter((access) => canRevoke(access.status)).length;
}

// --- Fechas ---------------------------------------------------------------------------------------------------------------------

const WHEN = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Madrid",
});
const DAY = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric", timeZone: "Europe/Madrid" });

/** Instante (ISO con zona) en hora de Madrid, con año: `5 nov 2026, 10:32`. */
export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : WHEN.format(date);
}

/** Solo el día, en hora de Madrid: `19 nov 2026`. */
export function formatExpiry(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : DAY.format(date);
}

/** Lo que añade la línea bajo la insignia del estado (que ya va escrito): solo una invitación pendiente caduca. */
export function accessDetail(access: Pick<GestorAccess, "status" | "expires_at">): string {
  return access.status === "pending" ? `Caduca el ${formatExpiry(access.expires_at)}` : "";
}

// --- Identificadores y cursor ---------------------------------------------------------------------------------------------------

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
/** Los ids de acceso, factura y gasto son UUID: lo demás ni se envía a la API ni se convierte en enlace. */
export const isUuid = (value: unknown): value is string => typeof value === "string" && UUID.test(value);

const CURSOR = /^[0-9]{1,18}$/;
/** El cursor del registro de actividad viene de la dirección (entrada no confiable): solo un número entero; lo demás es «sin cursor». */
export function parseCursor(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" && CURSOR.test(value) ? value : undefined;
}

// --- Anotaciones ----------------------------------------------------------------------------------------------------------------

export type NoteTarget = { label: string; href: string | null };

/** A qué se refiere una anotación: una factura y un gasto tienen su página; un documento, no. Sin entidad (o con una desconocida), nada. */
export function noteTarget(note: Pick<GestorNote, "entity_type" | "entity_id">): NoteTarget | null {
  const { entity_type: type, entity_id: id } = note;
  if (type === null || id === null) return null;
  if (type === "invoice") return { label: "Sobre una factura", href: isUuid(id) ? `/facturas/${id}` : null };
  if (type === "expense") return { label: "Sobre un gasto", href: isUuid(id) ? `/gastos/${id}` : null };
  if (type === "document") return { label: "Sobre un documento", href: null };
  return null;
}

// --- Registro de actividad ------------------------------------------------------------------------------------------------------

/** El correo del acceso al que se refiere una entrada (`entity_id` = id del acceso), o `null` si ya no está en la lista. */
export function emailOfAccess(accesses: readonly Pick<GestorAccess, "id" | "gestor_email">[], id: string | null): string | null {
  if (id === null) return null;
  return accesses.find((access) => access.id === id)?.gestor_email ?? null;
}

const YOUR_GESTOR = "tu gestor";

/** Qué lectura fue, en pasado y sin datos: la tabla es cerrada (un tipo desconocido no se refleja). */
// Son `Map` y no objetos: un `entity_type` como «constructor» o «toString» no puede resolver por la cadena de prototipos.
const READ_TEXT = new Map([
  ["portfolio", "abrió tu ficha"],
  ["invoices", "consultó tus facturas"],
  ["invoice", "consultó una factura"],
  ["invoice_pdf", "descargó el PDF de una factura"],
  ["expenses", "consultó tus gastos"],
  ["documents", "consultó tus documentos pendientes"],
  ["document_original", "descargó el original de un documento"],
  ["profile", "consultó tu perfil y tus series"],
  ["clients", "consultó tus clientes"],
  ["notes", "consultó sus anotaciones"],
]);
const MODEL_TEXT = new Map([
  ["modelo_303", "modelo 303"],
  ["modelo_130", "modelo 130"],
]);

/** `T2 de 2025`; sin periodo (o con uno imposible), nada. */
function periodText(entry: Pick<ActivityEntry, "year" | "quarter">): string {
  const { year, quarter } = entry;
  if (year === null || quarter === null) return "";
  if (!Number.isInteger(year) || !Number.isInteger(quarter) || quarter < 1 || quarter > 4 || year < 2000 || year > 2100) return "";
  return ` del T${quarter} de ${year}`;
}

export type ActivityLine = {
  /** La frase completa: «Tu gestor consultó tus facturas». */
  text: string;
  /** El correo del gestor al que se refiere, si se sabe (se enseña aparte). */
  gestor: string | null;
};

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/**
 * La frase de una entrada del registro. Las acciones del propio autónomo (invitar, revocar) no llevan el correo del gestor: se resuelve con
 * la lista de accesos por el id que guarda la entrada, y si ya no está se dice «tu gestor». Una acción desconocida no se refleja.
 */
export function describeActivity(entry: ActivityEntry, accesses: readonly Pick<GestorAccess, "id" | "gestor_email">[]): ActivityLine {
  const resolved = entry.entity_type === "gestor_access" ? emailOfAccess(accesses, entry.entity_id) : null;
  const gestor = entry.actor_email ?? resolved;
  const who = capital(YOUR_GESTOR);
  switch (entry.action) {
    case "gestor_access.invited":
      return { text: `Invitaste a ${resolved ?? YOUR_GESTOR}`, gestor: resolved };
    case "gestor_access.accepted":
      return { text: `${who} aceptó tu invitación`, gestor };
    case "gestor_access.declined":
      return { text: `${who} rechazó tu invitación`, gestor };
    case "gestor_access.revoked":
      return entry.actor_role === "gestor"
        ? { text: `${who} renunció a su acceso`, gestor }
        : { text: `Revocaste el acceso de ${resolved ?? YOUR_GESTOR}`, gestor: resolved };
    case "gestor.note_added":
      return { text: `${who} añadió una anotación`, gestor };
    case "gestor.read": {
      const model = entry.entity_type === null ? undefined : MODEL_TEXT.get(entry.entity_type);
      if (model !== undefined) return { text: `${who} consultó el borrador del ${model}${periodText(entry)}`, gestor };
      const read = entry.entity_type === null ? undefined : READ_TEXT.get(entry.entity_type);
      return { text: `${who} ${read ?? "consultó datos de tu cuenta"}`, gestor };
    }
    default:
      return { text: "Actividad en el acceso de tu gestor", gestor };
  }
}
