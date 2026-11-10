// Facturas en la interfaz (SPEC-W-007 §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y no calcula ningún impuesto: ni el IVA, ni la retención, ni el ámbito, ni la mención. Aquí solo se
// da formato (fechas, importes con signo, tipos), se leen los filtros de la dirección y se redacta una frase con lo que ya devolvió la API.
import type { components } from "@/api/schema";

import { formatCents } from "./money.ts";

export type Invoice = components["schemas"]["Invoice"];
export type InvoicePreview = components["schemas"]["InvoicePreview"];
export type Scope = Invoice["client"]["scope"];

export const SCOPE_LABEL: Record<Scope, string> = { national: "Nacional", eu: "UE", non_eu: "Fuera de la UE" };
export const SCOPES = ["national", "eu", "non_eu"] as const;

/** Fecha ISO `AAAA-MM-DD` → `dd/mm/aaaa`. Solo reordena el texto (no pasa por `Date`: una zona horaria no puede mover el día). */
export function formatDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : iso;
}

const LONG_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
/** `2026-11-10` → `10 de noviembre de 2026`. */
export function formatLongDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  const month = match ? LONG_MONTHS[Number(match[2]) - 1] : undefined;
  return match && month ? `${Number(match[3])} de ${month} de ${match[1]}` : iso;
}

/** El día de hoy en Madrid como `AAAA-MM-DD` (el servidor valida con el reloj de Madrid: «la fecha no puede ser futura»). */
export function madridToday(now: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Tipo en porcentaje tal como lo manda la API (`"21.00"`, `"7.50"`): `21`, `7,5`. Lo que no es un tipo se devuelve igual. */
export function rateText(rate: string): string {
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(rate)) return rate;
  return String(Number(rate)).replace(".", ",");
}

const isZeroRate = (rate: string) => Number(rate) === 0;

/** El IVA de una factura: el importe, o «Sin IVA» cuando el tipo es 0. */
export function vatText(invoice: Pick<Invoice, "vat_rate" | "vat_cents">): string {
  return isZeroRate(invoice.vat_rate) ? "Sin IVA" : formatCents(invoice.vat_cents);
}

/**
 * La retención de una factura, como lo que se RESTA al cobrar: `−150,00 €` en una ordinaria y `+30,00 €` en una rectificativa que devuelve
 * retención (su importe es negativo). «—» si no hay.
 */
export function retentionText(invoice: Pick<Invoice, "irpf_cents">): string {
  if (invoice.irpf_cents === 0) return "—";
  const amount = formatCents(Math.abs(invoice.irpf_cents));
  return invoice.irpf_cents > 0 ? `−${amount}` : `+${amount}`;
}

/** Texto del estado de cobro. Una rectificativa no se cobra: no tiene estado. */
export function paymentLabel(invoice: Pick<Invoice, "kind" | "paid_at">): string | null {
  if (invoice.kind === "rectifying") return null;
  return invoice.paid_at ? "Cobrada" : "Pendiente";
}

export const kindLabel = (kind: Invoice["kind"]) => (kind === "rectifying" ? "Rectificativa" : "Ordinaria");

// --- Filtros de la lista (por la dirección: `?year=&scope=&paid=`) ----------------------------------------------------------------------

export type ListQuery = { year: number; scope: Scope | undefined; paid: boolean | undefined };

const first = (value: string | string[] | undefined): string | undefined => (Array.isArray(value) ? value[0] : value);

/** Lee los filtros de la dirección. Lo desconocido se ignora (nunca llega a la API): año fuera de 2000–9998 → el actual; ámbito o cobro raros → todos. */
export function parseListQuery(params: Record<string, string | string[] | undefined>, currentYear: number): ListQuery {
  const rawYear = first(params["year"]);
  const year = rawYear !== undefined && /^\d{4}$/.test(rawYear) && Number(rawYear) >= 2000 && Number(rawYear) <= 9998 ? Number(rawYear) : currentYear;
  const rawScope = first(params["scope"]);
  const scope = (SCOPES as readonly string[]).includes(rawScope ?? "") ? (rawScope as Scope) : undefined;
  const rawPaid = first(params["paid"]);
  const paid = rawPaid === "paid" ? true : rawPaid === "unpaid" ? false : undefined;
  return { year, scope, paid };
}

/** Los años que se ofrecen: del actual hacia atrás (cinco), más el elegido si queda fuera; el más reciente primero. */
export function yearOptions(currentYear: number, selected: number): number[] {
  const years = new Set<number>([selected]);
  for (let year = currentYear; year > currentYear - 5; year -= 1) years.add(year);
  return [...years].sort((a, b) => b - a);
}

// --- Condiciones de facturación de un cliente (frase redactada con lo que devolvió `preview_invoice`) ----------------------------------

/**
 * «Sus facturas llevarán IVA del 21 % y retención de IRPF del 15 %.» / «Sus facturas irán sin IVA y sin retención, con la mención «…».»
 * Sale de los campos del servidor (tipo de IVA, tipo de retención, mención); no hay ninguna regla fiscal aquí.
 */
export function conditionsText(preview: Pick<InvoicePreview, "vat_rate" | "irpf_rate" | "legal_note">): string {
  const noVat = isZeroRate(preview.vat_rate);
  const noRetention = isZeroRate(preview.irpf_rate);
  const vat = noVat ? "sin IVA" : `IVA del ${rateText(preview.vat_rate)} %`;
  const retention = noRetention ? "sin retención" : `retención de IRPF del ${rateText(preview.irpf_rate)} %`;
  const verb = noVat ? "irán" : "llevarán";
  const note = preview.legal_note ? `, con la mención «${preview.legal_note}»` : "";
  return `Sus facturas ${verb} ${vat} y ${retention}${note}.`;
}

/** Qué se enseña como condiciones de un cliente en `/clientes`. */
export type Conditions =
  | { status: "ok"; text: string }
  | { status: "address" } // sin domicilio: no se puede facturar
  | { status: "profile"; text: string } // falta algo en el perfil (retención o datos del emisor): el texto es el del servidor
  | { status: "none" }; // archivado, o la API no respondió: no se enseña nada
