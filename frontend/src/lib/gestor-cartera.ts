// La cartera del gestor y la ficha de cada autónomo (SPEC-W-010 §5.5, hito 4). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y el gestor solo lee: aquí se eligen la pestaña y la página de la dirección, se redactan los textos de los
// pendientes y de las invitaciones y se construyen las direcciones de la ficha. Nada de lo que llega de la dirección se refleja sin pasar por una lista
// cerrada o por un número; ninguna regla de acceso vive aquí (la API y la base de datos deciden).
import type { components } from "@/api/schema";

import { formatExpiry, isUuid, type NoteLinks } from "./gestor.ts";
import type { ListQuery } from "./invoices.ts";
import type { Problem } from "./problems.ts";
import type { ModelKey, Quarter, TaxLinks } from "./tax.ts";

export type PortfolioEntry = components["schemas"]["PortfolioEntry"];
export type GestorInvitation = components["schemas"]["GestorInvitation"];
export type NoteInput = components["schemas"]["NoteInput"];

// --- Pestañas de la ficha -------------------------------------------------------------------------------------------------------

export const TABS = ["facturas", "gastos", "documentos", "trimestres", "perfil", "anotaciones"] as const;
export type Tab = (typeof TABS)[number];
export const TAB_LABEL: Record<Tab, string> = {
  facturas: "Facturas",
  gastos: "Gastos",
  documentos: "Documentos",
  trimestres: "Trimestres",
  perfil: "Perfil y clientes",
  anotaciones: "Anotaciones",
};

const first = (value: string | string[] | undefined): string | undefined => (Array.isArray(value) ? value[0] : value);

/** `?tab=`: solo una pestaña de la lista; cualquier otra cosa, o nada, es Facturas (una dirección rara nunca da error). */
export function parseTab(params: Record<string, string | string[] | undefined>): Tab {
  const raw = first(params["tab"]);
  return TABS.find((tab) => tab === raw) ?? "facturas";
}

// --- Páginas de la lista de facturas --------------------------------------------------------------------------------------------

/** Facturas por página. La API admite hasta 200; se piden `PAGE_SIZE + 1` para saber si hay otra página sin un recuento. */
export const PAGE_SIZE = 50;
const MAX_PAGE = 10_000;

/** `?pagina=`: un entero de 1 a 10.000; lo demás es la primera página. */
export function parsePage(params: Record<string, string | string[] | undefined>): number {
  const raw = first(params["pagina"]);
  if (raw === undefined || !/^[0-9]{1,5}$/.test(raw)) return 1;
  const page = Number(raw);
  return page >= 1 && page <= MAX_PAGE ? page : 1;
}

/** Cuántas filas se saltan para llegar a esa página. */
export const pageOffset = (page: number): number => (page - 1) * PAGE_SIZE;

/** De las `PAGE_SIZE + 1` filas pedidas: las que se enseñan y si hay página siguiente. */
export function splitPage<T>(rows: readonly T[]): { items: T[]; hasNext: boolean } {
  return { items: rows.slice(0, PAGE_SIZE), hasNext: rows.length > PAGE_SIZE };
}

// --- Direcciones ----------------------------------------------------------------------------------------------------------------

/** La ficha de un autónomo, en una pestaña. Facturas es la de por defecto, pero se escribe siempre: la dirección dice dónde se está. */
export const fichaHref = (ownerId: string, tab: Tab = "facturas"): string => `/cartera/${ownerId}?tab=${tab}`;

/** El detalle de una factura del autónomo, visto por el gestor. */
export const invoiceDetailHref = (ownerId: string, invoiceId: string): string => `/cartera/${ownerId}/facturas/${invoiceId}`;
export const invoicePdfHref = (ownerId: string, invoiceId: string): string => `/cartera/${ownerId}/facturas/${invoiceId}/pdf`;
export const documentOriginalHref = (ownerId: string, documentId: string): string => `/cartera/${ownerId}/documentos/${documentId}/original`;

/** La lista de facturas con sus filtros y su página; lo que vale lo de por defecto no se escribe (la dirección se queda corta). */
export function invoicesHref(ownerId: string, query: ListQuery, page: number, currentYear: number): string {
  const params = new URLSearchParams({ tab: "facturas" });
  if (query.year !== currentYear) params.set("year", String(query.year));
  if (query.scope !== undefined) params.set("scope", query.scope);
  if (query.paid !== undefined) params.set("paid", query.paid ? "paid" : "unpaid");
  if (page > 1) params.set("pagina", String(page));
  return `/cartera/${ownerId}?${params.toString()}`;
}

/** La lista de gastos, desde un cursor. */
export const expensesHref = (ownerId: string, cursor?: string): string =>
  cursor === undefined ? fichaHref(ownerId, "gastos") : `${fichaHref(ownerId, "gastos")}&cursor=${encodeURIComponent(cursor)}`;

/** Un trimestre de un modelo en la pestaña Trimestres. El 303 no lleva `model` (como en el autónomo). */
export function quarterTabHref(ownerId: string, year: number, quarter: Quarter, model: ModelKey): string {
  const base = fichaHref(ownerId, "trimestres");
  return model === "130" ? `${base}&model=130&year=${year}&quarter=${quarter}` : `${base}&year=${year}&quarter=${quarter}`;
}

/** Los enlaces de la hoja del 303 y del 130 cuando la mira el gestor: a su detalle de factura, a sus trimestres y a su lista de gastos. */
export function gestorTaxLinks(ownerId: string): TaxLinks {
  return {
    invoice: (id) => invoiceDetailHref(ownerId, id),
    quarter: (year, quarter, model) => quarterTabHref(ownerId, year, quarter, model),
    expenses: fichaHref(ownerId, "gastos"),
  };
}

/** Los enlaces de una anotación del gestor: la factura tiene detalle; el gasto, no. */
export function gestorNoteLinks(ownerId: string): NoteLinks {
  return { invoice: (id) => invoiceDetailHref(ownerId, id), expense: () => null };
}

/** Un id de la dirección que no es un UUID no llega a la API ni a ninguna ruta: se trata como «no encontrado». */
export const isOwnerId = isUuid;

// --- Textos ---------------------------------------------------------------------------------------------------------------------

/** Los pendientes de un autónomo: el número y las palabras (no solo un número ni solo un color). */
export function pendingText(count: number): string {
  if (!Number.isInteger(count) || count <= 0) return "Sin pendientes";
  return count === 1 ? "1 documento para revisar" : `${count} documentos para revisar`;
}

/** La caducidad de una invitación recibida. */
export const invitationExpiry = (expiresAt: string): string => `Caduca el ${formatExpiry(expiresAt)}`;

// --- Anotaciones ----------------------------------------------------------------------------------------------------------------

/** Controles (también los bidireccionales y los de ancho cero): no deben llegar a un campo de texto ni a la API. Los saltos de línea SÍ valen en una anotación. */
const code = (n: number) => String.fromCharCode(n);
const CONTROL = new RegExp(
  `[${code(0)}-${code(8)}${code(0xb)}${code(0xc)}${code(0xe)}-${code(0x1f)}${code(0x7f)}-${code(0x9f)}${code(0x200b)}-${code(0x200f)}${code(0x2028)}-${code(0x202e)}${code(0x2060)}${code(0xfeff)}]`,
  "g",
);

/** Lee del `FormData` solo el texto de la anotación (entrada no confiable: se ignora todo lo demás). */
export function valuesFromNoteForm(get: (name: string) => unknown): Record<string, string> {
  const value = get("body");
  return { body: typeof value === "string" ? value : "" };
}

/** El cuerpo de la API. La anotación puede ir ligada a una factura (solo desde su detalle); el servidor comprueba que sea del autónomo. */
export function toNoteBody(values: Record<string, string>, invoiceId: string | null): NoteInput {
  const body = (values["body"] ?? "").replace(CONTROL, " ").trim();
  return invoiceId !== null && isUuid(invoiceId) ? { body, entity_type: "invoice", entity_id: invoiceId } : { body };
}

/**
 * Errores por campo de una anotación rechazada: el del texto va junto al campo; el de lo que se enlaza (una factura que no existe o no es de este
 * autónomo) no es un campo del formulario y va en el resumen. Sin `invalid_note`, ninguno.
 */
export function fieldErrorsFromNoteProblem(problem: Problem): Record<string, string> | undefined {
  if (problem.code !== "invalid_note") return undefined;
  const field = problem.noteFields?.[0]?.field ?? "body";
  return field === "body" ? { body: problem.message } : undefined;
}
