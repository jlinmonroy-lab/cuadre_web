// Los borradores de los modelos 303 y 130 en la interfaz (SPEC-W-008 y SPEC-W-009, §5.5). Puro: lo ejecutan directamente los tests.
//
// La interfaz MUESTRA lo que dice el servidor y no calcula ningún impuesto: ni una cuota, ni una suma, ni un resultado, ni un plazo. Aquí solo se
// leen el modelo, el año y el trimestre de la dirección, se elige qué casillas se ven, se agrupan y se redactan los textos con lo que ya devolvió la API.
import type { components } from "@/api/schema";

import { formatDate, formatLongDate } from "./invoices.ts";
import { formatCents } from "./money.ts";

export type Modelo303 = components["schemas"]["Modelo303"];
export type Box303 = components["schemas"]["Box303"];
export type Item303 = components["schemas"]["Item303"];
export type Modelo130 = components["schemas"]["Modelo130"];
export type Box130 = components["schemas"]["Box130"];
export type Item130 = components["schemas"]["Item130"];

/** El modelo que enseña la pantalla: `?model=130`; sin parámetro, el 303. */
export type ModelKey = "303" | "130";

export type Quarter = 1 | 2 | 3 | 4;
export type QuarterQuery = { year: number; quarter: Quarter };

export const QUARTERS: readonly Quarter[] = [1, 2, 3, 4];
const MONTHS: Record<Quarter, string> = { 1: "enero a marzo", 2: "abril a junio", 3: "julio a septiembre", 4: "octubre a diciembre" };
const MIN_YEAR = 2000;
const MAX_YEAR = 9998;

const isQuarter = (value: number): value is Quarter => value === 1 || value === 2 || value === 3 || value === 4;

/** El año y el trimestre de una fecha ISO `AAAA-MM-DD`. */
export function quarterOfDate(iso: string): QuarterQuery {
  const month = Number(iso.slice(5, 7));
  const quarter = Math.floor((month - 1) / 3) + 1;
  return { year: Number(iso.slice(0, 4)), quarter: isQuarter(quarter) ? quarter : 1 };
}

const first = (value: string | string[] | undefined): string | undefined => (Array.isArray(value) ? value[0] : value);

/**
 * `?year=&quarter=`: cada parámetro por su cuenta, como en la API. Lo ausente o ilegible vale el de hoy en Madrid (`today`): una dirección rara
 * enseña el trimestre en curso, nunca una página de error. Un trimestre futuro SÍ se pasa tal cual: el servidor lo rechaza con su texto.
 */
export function parseQuarterQuery(params: Record<string, string | string[] | undefined>, today: string): QuarterQuery {
  const current = quarterOfDate(today);
  const rawYear = first(params["year"]);
  const rawQuarter = first(params["quarter"]);
  const year = rawYear !== undefined && /^\d{4}$/.test(rawYear) && Number(rawYear) >= MIN_YEAR && Number(rawYear) <= MAX_YEAR ? Number(rawYear) : current.year;
  const quarter = rawQuarter !== undefined && /^[1-4]$/.test(rawQuarter) ? (Number(rawQuarter) as Quarter) : current.quarter;
  return { year, quarter };
}

/** `T2 de 2025`. */
export const quarterTitle = (year: number, quarter: Quarter): string => `T${quarter} de ${year}`;
/** `abril a junio`. */
export const quarterMonths = (quarter: Quarter): string => MONTHS[quarter];

/** Un trimestre se ofrece si ya ha empezado (el primer día es hoy o antes). */
export function quarterEnabled(year: number, quarter: Quarter, today: string): boolean {
  const month = String(3 * quarter - 2).padStart(2, "0");
  return `${String(year).padStart(4, "0")}-${month}-01` <= today;
}

/** `?model=130` es el 130; cualquier otra cosa, o nada, es el 303: una dirección rara nunca da error. */
export function parseModel(params: Record<string, string | string[] | undefined>): ModelKey {
  return first(params["model"]) === "130" ? "130" : "303";
}

/** La dirección de un trimestre. Las del 303 no llevan `model` (no cambian); las del 130 lo llevan delante. */
export const quarterHref = (year: number, quarter: Quarter, model: ModelKey = "303"): string =>
  model === "130" ? `/trimestres?model=130&year=${year}&quarter=${quarter}` : `/trimestres?year=${year}&quarter=${quarter}`;

export type Banner = { label: string; text: string; tone: "neutral" | "doubt" | "ok" };

/** El estado del plazo, siempre escrito: el color solo refuerza. La fecha es la del calendario que manda el servidor (el mismo en los dos modelos). */
export function deadlineBanner(model: Pick<Modelo303 | Modelo130, "deadline_status" | "deadline">): Banner {
  const date = formatLongDate(model.deadline);
  switch (model.deadline_status) {
    case "en_curso":
      return { label: "Trimestre en curso", text: `Se presenta hasta el ${date}.`, tone: "neutral" };
    case "plazo_abierto":
      return { label: "Plazo abierto", text: `Presenta hasta el ${date}.`, tone: "doubt" };
    case "plazo_cerrado":
      return { label: "Plazo cerrado", text: `El plazo terminó el ${date}.`, tone: "ok" };
  }
}

/** El resultado del 303 con palabras. El importe va sin signo cuando el texto ya dice «a compensar». */
export function resultText(kind: Modelo303["result_kind"], cents: number): string {
  switch (kind) {
    case "a_ingresar":
      return `${formatCents(cents)} a ingresar`;
    case "a_compensar":
      return `${formatCents(-cents)} a compensar en próximos trimestres`;
    case "a_cero":
      return "0,00 €: nada que ingresar ni compensar";
    case "sin_actividad":
      return "Sin actividad en este trimestre";
  }
}

// Las casillas de base y cuota de los tipos reducidos solo se enseñan si tienen documentos: el resto de la hoja sale siempre, como el prototipo.
const HIDDEN_WHEN_EMPTY = new Set(["01", "03", "04", "06"]);

/** Las casillas que se enseñan, en el orden en que llegan. */
export function visibleBoxes(boxes: readonly Box303[]): Box303[] {
  return boxes.filter((box) => !(HIDDEN_WHEN_EMPTY.has(box.code) && box.items.length === 0));
}

export type BoxGroup = Box303["group"];
export const GROUP_ORDER: readonly BoxGroup[] = ["devengado", "deducible", "resultado", "adicional"];
export const GROUP_LABEL: Record<BoxGroup, string> = {
  devengado: "IVA devengado",
  deducible: "IVA deducible",
  resultado: "Resultado",
  adicional: "Información adicional",
};

/** Las casillas por grupo, en el orden de la hoja; un grupo sin casillas visibles no sale. */
export function groupBoxes(boxes: readonly Box303[]): { group: BoxGroup; label: string; boxes: Box303[] }[] {
  const visible = visibleBoxes(boxes);
  return GROUP_ORDER.map((group) => ({ group, label: GROUP_LABEL[group], boxes: visible.filter((box) => box.group === group) })).filter(
    (entry) => entry.boxes.length > 0,
  );
}

/** «Ver la factura», «Ver las 3 facturas», «Ver el gasto», «Ver los 2 gastos»; `null` si la casilla no tiene documentos. */
export function itemSummary(box: Pick<Box303, "items">): string | null {
  const count = box.items.length;
  const kind = box.items[0]?.kind;
  if (kind === undefined) return null; // sin documentos
  if (kind === "invoice") return count === 1 ? "Ver la factura" : `Ver las ${count} facturas`;
  return count === 1 ? "Ver el gasto" : `Ver los ${count} gastos`;
}

/** A dónde lleva un documento: la factura tiene su detalle; los gastos, solo su lista. */
export function itemHref(item: Pick<Item303, "kind" | "id">): string {
  return item.kind === "invoice" ? `/facturas/${item.id}` : "/gastos";
}

/** El importe de un documento que cuenta en una casilla: la base o la cuota, según lo que suma la casilla. */
export function itemAmount(item: Pick<Item303, "base_cents" | "vat_cents">, measure: Box303["measure"]): string {
  return formatCents(measure === "vat" ? item.vat_cents : item.base_cents);
}

const listText = (items: readonly string[]): string =>
  items.length <= 1 ? (items[0] ?? "") : `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;

/** De qué se compone una casilla derivada (27, 45 y 46); `null` en las que suman documentos. */
export function componentsText(box: Pick<Box303, "code" | "components">): string | null {
  const parts = box.components;
  if (parts.length === 0) return null;
  if (box.code === "46" && parts.length === 2) return `Casilla ${parts[0]} menos casilla ${parts[1]}`;
  if (parts.length === 1) return `Igual a la casilla ${parts[0]}`;
  return `Suma de las casillas ${listText(parts)}`;
}

// --- Lo que pinta una fila de casilla (los dos modelos) ----------------------------------------------------------------------------------

/** Un documento de una casilla, ya escrito. `href` es `null` si no enlaza a ningún sitio (un gasto, o un trimestre que no se puede leer). */
export type BoxLineItem = { key: string; label: string; date: string; amount: string; href: string | null };

/** Una fila de la hoja, ya escrita: la pinta un único componente para el 303 y para el 130. */
export type BoxLineView = {
  code: string;
  label: string;
  amount: string;
  derived: string | null;
  isResult: boolean;
  summary: string | null;
  items: BoxLineItem[];
  /** Si algún documento es un gasto, el desplegable cierra con «Ir a Gastos». */
  expensesLink: boolean;
};

/** La fila de una casilla del 303: lo mismo que la pantalla del 303 ya enseñaba. */
export function boxView303(box: Box303): BoxLineView {
  return {
    code: box.code,
    label: box.label,
    amount: formatCents(box.amount_cents),
    derived: componentsText(box),
    isResult: box.code === "46",
    summary: itemSummary(box),
    items: box.items.map((item) => ({
      key: `${item.kind}-${item.id}`,
      label: item.label,
      date: formatDate(item.date),
      amount: itemAmount(item, box.measure),
      href: item.kind === "invoice" ? itemHref(item) : null,
    })),
    expensesLink: box.items.some((item) => item.kind === "expense"),
  };
}

// --- Modelo 130 -------------------------------------------------------------------------------------------------------------------------

/** El resultado del 130 con palabras. Un resultado cero o negativo es «nada que ingresar»: no se arrastra ni se compensa. */
export function resultText130(kind: Modelo130["result_kind"], cents: number): string {
  switch (kind) {
    case "a_ingresar":
      return `${formatCents(cents)} a ingresar`;
    case "nada_que_ingresar":
      return "Nada que ingresar este trimestre";
    case "sin_actividad":
      return "Sin actividad en este periodo";
  }
}

/** El porcentaje de los ingresos que lleva retención, solo como información; `null` si el servidor no lo da (la casilla 01 no es positiva). */
export function withheldShareText(percent: number | null): string | null {
  return percent === null ? null : `El ${percent} % de tus ingresos acumulados este año lleva retención.`;
}

export type BoxGroup130 = Box130["group"];
export const GROUP_ORDER_130: readonly BoxGroup130[] = ["rendimiento", "pagos", "resultado"];
export const GROUP_LABEL_130: Record<BoxGroup130, string> = {
  rendimiento: "Rendimiento de la actividad (estimación directa)",
  pagos: "Pagos ya hechos y retenciones",
  resultado: "Resultado",
};

/** Las casillas del 130 por grupo, en el orden de la hoja. Salen siempre las siete, también a cero; un grupo sin casillas no sale. */
export function groupBoxes130(boxes: readonly Box130[]): { group: BoxGroup130; label: string; boxes: Box130[] }[] {
  return GROUP_ORDER_130.map((group) => ({ group, label: GROUP_LABEL_130[group], boxes: boxes.filter((box) => box.group === group) })).filter(
    (entry) => entry.boxes.length > 0,
  );
}

/** De qué se compone una casilla derivada del 130 (03, 04 y 07); `null` en las que suman documentos. */
export function componentsText130(box: Pick<Box130, "code" | "components">): string | null {
  const parts = box.components;
  if (parts.length === 0) return null;
  if (box.code === "03" && parts.length === 2) return `Casilla ${parts[0]} menos casilla ${parts[1]}`;
  if (box.code === "04" && parts.length === 1) return `20 % de la casilla ${parts[0]}, si es positiva`;
  if (box.code === "07" && parts.length === 3) return `Casilla ${parts[0]} menos casillas ${parts[1]} y ${parts[2]}`;
  return `Suma de las casillas ${listText(parts)}`;
}

/** «Ver la factura», «Ver los 2 gastos», «Ver el trimestre anterior»…; en la 06, «con retención». `null` si la casilla no tiene documentos. */
export function itemSummary130(box: Pick<Box130, "code" | "items">): string | null {
  const count = box.items.length;
  const kind = box.items[0]?.kind;
  if (kind === undefined) return null;
  if (kind === "quarter") return count === 1 ? "Ver el trimestre anterior" : `Ver los ${count} trimestres anteriores`;
  const withheld = box.code === "06" ? " con retención" : "";
  if (kind === "invoice") return count === 1 ? `Ver la factura${withheld}` : `Ver las ${count} facturas${withheld}`;
  return count === 1 ? "Ver el gasto" : `Ver los ${count} gastos`;
}

/** A dónde lleva un documento del 130: la factura, a su detalle; el trimestre anterior, a su propio 130; el gasto, a ningún sitio (la lista va aparte). */
export function itemHref130(item: Pick<Item130, "kind" | "id">, year: number): string | null {
  if (item.kind === "invoice") return `/facturas/${item.id}`;
  if (item.kind === "quarter") {
    const quarter = Number(item.id.slice(1));
    return item.id.startsWith("T") && isQuarter(quarter) ? quarterHref(year, quarter, "130") : null;
  }
  return null;
}

/** La fila de una casilla del 130. `year` es el del borrador: de él cuelgan los enlaces a los trimestres anteriores. */
export function boxView130(box: Box130, year: number): BoxLineView {
  return {
    code: box.code,
    label: box.label,
    amount: formatCents(box.amount_cents),
    derived: componentsText130(box),
    isResult: box.code === "07",
    summary: itemSummary130(box),
    items: box.items.map((item) => ({
      key: `${item.kind}-${item.id}`,
      label: item.label,
      date: formatDate(item.date),
      amount: formatCents(item.amount_cents),
      href: itemHref130(item, year),
    })),
    expensesLink: box.items.some((item) => item.kind === "expense"),
  };
}
