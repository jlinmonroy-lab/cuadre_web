// Gastos registrados en la interfaz (SPEC-W-003 §5.5): etiquetas de las categorías, cuándo se puede registrar, marcas y fechas.
// Puro: lo ejecutan directamente los tests. La interfaz NO valida nada fiscal: muestra lo que calcula el servidor (D-02).
import type { components } from "@/api/schema";

import { isDocumentId } from "./documents.ts";

type Schemas = components["schemas"];
export type ExpenseCategory = Schemas["ExpenseCategory"];
export type Validation = Schemas["Validation"];
export type CheckItem = Schemas["CheckItem"];
export type CheckCode = Schemas["CheckCode"];

// --- Códigos de comprobación ----------------------------------------------------------------------------------------------------

/** Lista cerrada de las comprobaciones. Como las categorías, está tipada contra el cliente generado: una nueva en la API no compila hasta que se añade. */
const CHECK_CODE_SET: Record<CheckCode, true> = {
  doc_type: true,
  required_data: true,
  doubts_reviewed: true,
  supplier_tax_id: true,
  issue_date: true,
  currency: true,
  vat_rates: true,
  vat_amounts: true,
  withholding: true,
  total: true,
  not_duplicate: true,
};
export const CHECK_CODES = Object.keys(CHECK_CODE_SET) as CheckCode[];

export function isCheckCode(value: unknown): value is CheckCode {
  return typeof value === "string" && Object.hasOwn(CHECK_CODE_SET, value);
}

// --- Categorías -----------------------------------------------------------------------------------------------------------------

/**
 * Etiquetas de las ocho categorías (las del prototipo). Tipado contra el enum del cliente generado: añadir una categoría en la API sin
 * etiqueta aquí NO COMPILA, y quitar una etiqueta sobrante tampoco. El orden es el del enum.
 */
export const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  software: "Software",
  workspace: "Coworking y oficina",
  supplies: "Material",
  utilities: "Suministros y teléfono",
  advisory: "Asesoría",
  self_employed_fee: "Cuota de autónomos",
  training: "Formación",
  other: "Otros",
};

export const EXPENSE_CATEGORIES = Object.keys(CATEGORY_LABELS) as ExpenseCategory[];

/** La categoría que propone el formulario «Gasto sin factura», como el prototipo. */
export const DEFAULT_MANUAL_CATEGORY: ExpenseCategory = "self_employed_fee";

export function isExpenseCategory(value: unknown): value is ExpenseCategory {
  return typeof value === "string" && Object.hasOwn(CATEGORY_LABELS, value);
}

export function categoryLabel(value: string | null | undefined): string {
  return isExpenseCategory(value) ? CATEGORY_LABELS[value] : "Sin categoría";
}

/** Un identificador de gasto es un UUID, igual que el de un documento. Se comprueba antes de ponerlo en una ruta o llamar a la API. */
export const isExpenseId = isDocumentId;

// --- Cuándo se puede registrar --------------------------------------------------------------------------------------------------

export type GateInput = {
  /** Lo que devuelve el servidor para lo GUARDADO (`null` si no hay nada guardado que comprobar). */
  validation: Validation | null;
  /** Hay cambios en el formulario que todavía no se han guardado: lo que se ve ya no es lo que se comprobó (D-02). */
  dirty: boolean;
  /** La casilla «He comparado los datos con el original». */
  acknowledged: boolean;
  /** Hay un registro en curso. */
  pending: boolean;
};
export type Gate = { enabled: boolean; reason: string | null };

/**
 * La ÚNICA regla de cuándo se puede pulsar «Registrar gasto»: cambios guardados, comprobaciones del servidor en verde y, si el servidor
 * lo pide por una sospecha de instrucciones ocultas, la casilla marcada. El motivo es el texto que se enseña junto al botón (un botón
 * desactivado no recibe el foco, así que la razón no puede ir solo en él). El servidor y la base vuelven a decidirlo.
 */
export function registerGate({ validation, dirty, acknowledged, pending }: GateInput): Gate {
  if (pending) return { enabled: false, reason: null };
  if (dirty) return { enabled: false, reason: "Guarda los cambios para volver a comprobar." };
  if (validation === null) return { enabled: false, reason: "Rellena y guarda los datos de la factura para poder comprobarlos." };
  if (!validation.can_register) return { enabled: false, reason: "Corrige las comprobaciones marcadas y guarda los cambios." };
  if (validation.requires_acknowledgement && !acknowledged) {
    return { enabled: false, reason: "Marca que has comparado los datos con el original." };
  }
  return { enabled: true, reason: null };
}

export type CheckView = { ok: boolean; label: string; detail: string | null; statusText: string };

/** Una comprobación para pintarla: icono (lo pone el componente), texto y motivo. El color nunca va solo (T3-11). */
export function checkView(check: CheckItem): CheckView {
  const ok = check.status === "ok";
  return {
    ok,
    label: check.label,
    detail: ok ? null : (check.detail ?? "Revisa este dato."),
    statusText: ok ? "Correcta" : "Por revisar",
  };
}

// --- Marcas ---------------------------------------------------------------------------------------------------------------------

export type BadgeTone = "neutral" | "eu" | "doubt";
export type ExpenseBadge = { label: string; tone: BadgeTone };

type Badged = { origin: "document" | "manual"; vat_cents: number; deductible_vat: boolean; supplier_scope: "national" | "eu" | null };

/** «Sin factura», «UE» e «IVA no deducible» (este último solo si hay IVA que deducir y no se deduce). */
export function expenseBadges(expense: Badged): ExpenseBadge[] {
  const badges: ExpenseBadge[] = [];
  if (expense.origin === "manual") badges.push({ label: "Sin factura", tone: "neutral" });
  if (expense.supplier_scope === "eu") badges.push({ label: "UE", tone: "eu" });
  if (expense.vat_cents > 0 && !expense.deductible_vat) badges.push({ label: "IVA no deducible", tone: "doubt" });
  return badges;
}

// --- Paginación -----------------------------------------------------------------------------------------------------------------

const CURSOR = /^[A-Za-z0-9_-]{1,200}$/;

/** El `?cursor=` de la URL, o `null`. Solo se acepta con la forma del cursor (base64url); la API vuelve a validarlo. */
export function cursorParam(value: unknown): string | null {
  return typeof value === "string" && CURSOR.test(value) ? value : null;
}

// --- Fechas ---------------------------------------------------------------------------------------------------------------------

const DAY = new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });
const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** `2026-10-28` → `28/10/2026`. «—» si no es una fecha de la forma `AAAA-MM-DD`. No pasa por la zona horaria del navegador. */
export function formatDay(iso: string | null | undefined): string {
  const match = typeof iso === "string" ? ISO_DAY.exec(iso) : null;
  if (!match) return "—";
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  // Una fecha imposible (30 de febrero) no se "arregla" desplazándola al mes siguiente: se rechaza.
  const real = date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  return real ? DAY.format(date) : "—";
}

const MADRID = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit" });

/** El día de hoy en Europe/Madrid como `AAAA-MM-DD` (para el `max` y el valor inicial de la fecha; la API decide el límite de verdad). */
export function madridDay(now: Date): string {
  return MADRID.format(now);
}
