// Documentos de compra en la interfaz (SPEC-W-002 §5.1, §5.5): qué archivos se admiten, cómo se llaman los estados y los datos.
// Sin dependencias ni alias: lo ejecutan directamente los tests.

/** Igual que la API (constante `MAX_UPLOAD_BYTES` de `cuadre.documents`), la CHECK de la tabla y el bucket de Storage. */
export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export const MIME_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/heic", "image/webp"] as const;
export type MimeType = (typeof MIME_TYPES)[number];

const BY_EXTENSION: Record<string, MimeType> = {
  pdf: "application/pdf",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  heic: "image/heic",
  heif: "image/heic",
  webp: "image/webp",
};

/** Para el atributo `accept` del selector de archivos (extensiones y tipos: algunos móviles solo miran uno de los dos). */
export const ACCEPT_FILES =
  ".pdf,.jpg,.jpeg,.png,.heic,.heif,.webp,application/pdf,image/jpeg,image/png,image/heic,image/heif,image/webp";

export type FileLike = { name: string; type: string; size: number };

function isMimeType(value: string): value is MimeType {
  return (MIME_TYPES as readonly string[]).includes(value);
}

/**
 * Tipo que se declara a la API. Manda `file.type`; si viene vacío o no es de los admitidos (Windows da `''` a los `.heic`, algunos
 * móviles `application/octet-stream`), se mira la extensión. `image/heif` es el mismo formato que `image/heic`.
 * La API vuelve a comprobar el contenido del archivo: esto solo decide qué se intenta subir.
 */
export function declaredMimeType(file: Pick<FileLike, "name" | "type">): MimeType | null {
  const type = file.type.split(";")[0]?.trim().toLowerCase() ?? "";
  if (isMimeType(type)) return type;
  if (type === "image/heif") return "image/heic";
  const extension = file.name.includes(".") ? (file.name.split(".").pop() ?? "").toLowerCase() : "";
  return Object.hasOwn(BY_EXTENSION, extension) ? (BY_EXTENSION[extension] ?? null) : null;
}

const SIZE = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${SIZE.format(bytes / 1024)} KB`;
  return `${SIZE.format(bytes / (1024 * 1024))} MB`;
}

/** Nombre de archivo para un mensaje: entre comillas latinas y acortado. */
export function quoteName(name: string): string {
  const chars = [...name];
  return `«${chars.length > 48 ? `${chars.slice(0, 47).join("")}…` : name}»`;
}

export type FileCheck = { ok: true; mimeType: MimeType } | { ok: false; message: string };

/** Comprueba un archivo ANTES de reservarlo: tipo, vacío y tamaño. Un fallo no impide que se suban los demás. */
export function checkFile(file: FileLike): FileCheck {
  const mimeType = declaredMimeType(file);
  if (mimeType === null) {
    return { ok: false, message: `${quoteName(file.name)} no es un tipo admitido. Sube un PDF o una imagen JPG, PNG, HEIC o WebP.` };
  }
  if (file.size <= 0) return { ok: false, message: `${quoteName(file.name)} está vacío.` };
  if (file.size > MAX_UPLOAD_BYTES) {
    return { ok: false, message: `${quoteName(file.name)} pesa ${formatBytes(file.size)} y el máximo es de 15 MB.` };
  }
  return { ok: true, mimeType };
}

// --- Estados --------------------------------------------------------------------------------------------------------------------

export const STATUSES = ["uploading", "processing", "review", "extraction_failed", "discarded", "registered"] as const;
export type DocumentStatus = (typeof STATUSES)[number];

export type Tone = "ok" | "doubt" | "error" | "neutral";
export type StatusView = { label: string; detail: string | null; tone: Tone };

/** Texto y tono de un estado. El color nunca va solo: siempre hay texto (T2-11). */
export function statusView(status: DocumentStatus, doubtfulCount: number): StatusView {
  switch (status) {
    case "uploading":
      return { label: "Subiendo", detail: null, tone: "neutral" };
    case "processing":
      return { label: "Leyendo…", detail: null, tone: "neutral" };
    case "review":
      return doubtfulCount > 0
        ? { label: "Para revisar", detail: `${doubtfulCount} ${doubtfulCount === 1 ? "dato dudoso" : "datos dudosos"}`, tone: "doubt" }
        : { label: "Para revisar", detail: "Lectura completa", tone: "ok" };
    case "extraction_failed":
      return { label: "No se pudo leer", detail: null, tone: "error" };
    case "discarded":
      return { label: "Descartado", detail: null, tone: "neutral" };
    case "registered":
      return { label: "Registrado", detail: null, tone: "ok" };
  }
}

export const isReading = (status: string): boolean => status === "processing";

/** Motivos de fallo cuyo texto (de la API) ya propone reintentar o rellenar a mano: no necesitan una frase más. */
const SELF_EXPLAINING_FAILURES = new Set(["unreadable", "upstream_error", "agents_unavailable"]);

/** Qué hacer tras un fallo de lectura, cuando el propio mensaje del motivo no lo dice. */
export function failureHint(code: string): string | null {
  return SELF_EXPLAINING_FAILURES.has(code) ? null : "Puedes volver a leerlo o escribir los datos tú mismo en el formulario.";
}

const DOCUMENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Un identificador de documento es un UUID. Se comprueba antes de ponerlo en una ruta o de llamar a la API con él. */
export const isDocumentId = (value: unknown): value is string => typeof value === "string" && DOCUMENT_ID.test(value);

// --- Datos leídos ---------------------------------------------------------------------------------------------------------------

export const DOC_TYPES = ["full_invoice", "simplified_invoice", "ticket", "receipt", "other", "not_an_invoice"] as const;
export type DocType = (typeof DOC_TYPES)[number];

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  full_invoice: "Factura completa",
  simplified_invoice: "Factura simplificada",
  ticket: "Ticket",
  receipt: "Recibo",
  other: "Otro documento",
  not_an_invoice: "No es una factura",
};

export function docTypeLabel(value: string | null | undefined): string {
  return value !== null && value !== undefined && Object.hasOwn(DOC_TYPE_LABELS, value) ? DOC_TYPE_LABELS[value as DocType] : "Documento";
}

/** Campo del contrato (`doubtful_fields[].field`) → nombre para la persona. Ojo: el importe total se llama `total`, no `total_cents`. */
export const DOUBT_FIELD_LABELS: Record<string, string> = {
  doc_type: "Tipo de documento",
  supplier_name: "Proveedor",
  supplier_tax_id: "NIF del proveedor",
  recipient_tax_id: "NIF del destinatario",
  invoice_number: "Número de factura",
  issue_date: "Fecha",
  currency: "Moneda",
  tax_breakdown: "Desglose de IVA",
  withholding: "Retención",
  total: "Total",
};

export const DOUBT_REASON_TEXT: Record<string, string> = {
  illegible: "No se lee con claridad: compruébalo.",
  ambiguous: "Puede leerse de más de una forma: compruébalo.",
  missing: "No aparece en el documento: complétalo si lo tienes.",
  inconsistent: "No cuadra con el resto de datos: compruébalo.",
};

export function doubtReasonText(reason: string): string {
  return Object.hasOwn(DOUBT_REASON_TEXT, reason) ? (DOUBT_REASON_TEXT[reason] ?? "Compruébalo.") : "Compruébalo.";
}

/** La URL firmada del original llega de la API: solo se redirige a ella si es http(s) y no lleva credenciales. */
export function httpUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username !== "" || url.password !== "") return null;
    return url.href;
  } catch {
    return null;
  }
}

// --- Fechas ---------------------------------------------------------------------------------------------------------------------

const DAY = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const MOMENT = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Madrid",
});

/** `2026-11-01` → `1 nov 2026`. Una fecha de calendario no cambia con la zona horaria. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "—";
  const date = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? "—" : DAY.format(date);
}

/** Instante (ISO con zona) en hora de Madrid: `5 nov, 10:32`. */
export function formatMoment(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : MOMENT.format(date);
}
