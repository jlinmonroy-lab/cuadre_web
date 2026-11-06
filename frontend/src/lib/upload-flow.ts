// Orquestación de la subida de facturas de compra (SPEC-W-002 §5.5, AC-01, AC-04, AC-05). Lógica pura con dependencias inyectadas:
// el componente le da las funciones reales (Server Action, `fetch`) y los tests le dan dobles. Sin React ni alias.
//
// Cada archivo recorre: reservar (Server Action) → subir (el NAVEGADOR sube directo a Storage con la URL firmada, solo
// `Content-Type`) → leer (Route Handler, hasta 45 s). La lectura va por un Route Handler y no por una Server Action porque Next
// despacha las Server Actions de una en una: varios archivos se leerían uno detrás de otro y el refresco automático se congelaría.
import { quoteName, type FileLike, type MimeType } from "./documents.ts";

export type UploadSource = "file" | "camera";

export type ReserveInput = { filename: string; mimeType: MimeType; sizeBytes: number; source: UploadSource };
/** Lo que el navegador necesita para subir: la URL firmada (una sola subida, caduca) y el tipo declarado. */
export type UploadTarget = { url: string; headers: Record<string, string> };

export type ReserveResult = { ok: true; id: string; upload: UploadTarget } | { ok: false; message: string };
export type PutResult = { ok: true } | { ok: false };
export type ReadResult = { ok: true; status: string } | { ok: false; code: string; message: string; retryAfter?: number };

export type UploadDeps = {
  reserve(input: ReserveInput): Promise<ReserveResult>;
  put(target: UploadTarget, file: Blob): Promise<PutResult>;
  read(documentId: string): Promise<ReadResult>;
  /** Descarta una reserva que no llegó a buen puerto. Cualquier fallo se ignora. */
  discard(documentId: string): Promise<unknown>;
};

export type Step = "queued" | "reserving" | "uploading" | "reading" | "done" | "error";
/** Qué hace «Reintentar»: empezar de cero (nueva reserva), repetir solo la lectura (mismo documento) o nada (no se puede arreglar). */
export type Retry = "restart" | "reading" | "none";

export type UploadItem = {
  key: string;
  name: string;
  size: number;
  mimeType: MimeType;
  source: UploadSource;
  step: Step;
  documentId: string | null;
  /** Estado del documento al terminar la lectura (`review`, `extraction_failed`…). */
  result: string | null;
  message: string | null;
  retry: Retry | null;
};
export type ItemPatch = Partial<Pick<UploadItem, "step" | "documentId" | "result" | "message" | "retry">>;

export function newItem(key: string, file: FileLike, mimeType: MimeType, source: UploadSource): UploadItem {
  return { key, name: file.name, size: file.size, mimeType, source, step: "queued", documentId: null, result: null, message: null, retry: null };
}

export const NETWORK_MESSAGE = "No hemos podido conectar con el servicio. Comprueba tu conexión e inténtalo de nuevo.";
const SESSION_MESSAGE = "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar.";
const UNAVAILABLE_MESSAGE = "El servicio de lectura no responde ahora mismo. Inténtalo de nuevo en unos segundos.";
const CONFIRM_MESSAGE =
  "No hemos podido confirmar la lectura. Si el documento sigue leyéndose, lo verás en la lista; si no, pulsa «Reintentar».";

/** Motivos tras los que repetir no sirve: el documento ya está descartado o el archivo volvería a fallar igual. */
const NO_RETRY = new Set(["file_type_mismatch", "upload_size_mismatch", "document_not_found", "session"]);

async function quietly(work: Promise<unknown>): Promise<void> {
  try {
    await work;
  } catch {
    // una reserva que no se pudo descartar es inofensiva (no sale en la lista y no ocupa ninguna lectura)
  }
}

export async function runUpload(
  deps: UploadDeps,
  item: UploadItem,
  file: Blob,
  emit: (patch: ItemPatch) => void,
  from: "start" | "reading" = "start",
): Promise<void> {
  let documentId = from === "reading" ? item.documentId : null;

  if (documentId === null) {
    emit({ step: "reserving", message: null, retry: null });
    let reserved: ReserveResult;
    try {
      reserved = await deps.reserve({ filename: item.name, mimeType: item.mimeType, sizeBytes: item.size, source: item.source });
    } catch {
      reserved = { ok: false, message: NETWORK_MESSAGE };
    }
    if (!reserved.ok) {
      emit({ step: "error", message: reserved.message, retry: "restart" });
      return;
    }

    emit({ step: "uploading", documentId: reserved.id });
    let put: PutResult;
    try {
      put = await deps.put(reserved.upload, file);
    } catch {
      put = { ok: false };
    }
    if (!put.ok) {
      await quietly(deps.discard(reserved.id));
      emit({
        step: "error",
        documentId: null,
        message: `No se pudo subir ${quoteName(item.name)}. Comprueba tu conexión e inténtalo de nuevo.`,
        retry: "restart",
      });
      return;
    }
    documentId = reserved.id;
  }

  emit({ step: "reading", documentId, message: null, retry: null });
  let read: ReadResult;
  try {
    read = await deps.read(documentId);
  } catch {
    read = { ok: false, code: "network", message: CONFIRM_MESSAGE };
  }
  if (read.ok) emit({ step: "done", result: read.status, message: null, retry: null });
  else emit({ step: "error", message: read.message, retry: NO_RETRY.has(read.code) ? "none" : "reading" });
}

// --- Varios archivos a la vez ---------------------------------------------------------------------------------------------------

/** Ejecuta como mucho `limit` tareas a la vez, por orden de llegada. Que una falle no detiene la cola. */
export function createLimiter(limit: number): <T>(task: () => Promise<T>) => Promise<T> {
  let running = 0;
  const waiting: (() => void)[] = [];
  const drain = () => {
    while (running < limit) {
      const start = waiting.shift();
      if (!start) return;
      running++;
      start();
    }
  };
  return <T>(task: () => Promise<T>) =>
    new Promise<T>((resolve, reject) => {
      waiting.push(() => {
        // `new Promise` convierte también una excepción síncrona de la tarea en un rechazo: no puede dejar `running` sin restar.
        new Promise<T>((done) => done(task()))
          .then(resolve, reject)
          .finally(() => {
            running--;
            drain();
          });
      });
      drain();
    });
}

// --- Las dos llamadas del navegador ---------------------------------------------------------------------------------------------

/**
 * `PUT` directo a Storage. Solo `Content-Type` y sin credenciales: la URL firmada ya es la autorización, y Storage responde con
 * `Access-Control-Allow-Origin: *`, que el navegador rechazaría si la petición llevara cookies.
 */
export async function putToStorage(fetchFn: typeof fetch, target: UploadTarget, file: Blob): Promise<PutResult> {
  const contentType = target.headers["Content-Type"];
  const headers: Record<string, string> = contentType ? { "Content-Type": contentType } : {};
  try {
    const response = await fetchFn(target.url, { method: "PUT", headers, body: file, credentials: "omit", cache: "no-store" });
    return response.ok ? { ok: true } : { ok: false };
  } catch {
    return { ok: false };
  }
}

/** Pide la lectura al Route Handler de la web (`/gastos/<id>/leer` o `/releer`), que llama a la API con la sesión de las cookies. */
export async function readViaHandler(fetchFn: typeof fetch, documentId: string, mode: "read" | "reread" = "read"): Promise<ReadResult> {
  let response: Response;
  try {
    response = await fetchFn(`/gastos/${encodeURIComponent(documentId)}/${mode === "read" ? "leer" : "releer"}`, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    return { ok: false, code: "network", message: CONFIRM_MESSAGE };
  }

  // Sin sesión, el proxy redirige a /login: llega HTML, no JSON.
  if (response.redirected) return { ok: false, code: "session", message: SESSION_MESSAGE };
  let body: unknown = null;
  if ((response.headers.get("content-type") ?? "").includes("json")) body = await response.json().catch(() => null);

  if (response.ok && isObject(body) && typeof body["status"] === "string") return { ok: true, status: body["status"] };

  const header = response.headers.get("retry-after") ?? "";
  const retryAfter = /^\d{1,3}$/.test(header) && Number(header) > 0 ? Number(header) : undefined;
  if (isObject(body) && typeof body["code"] === "string" && typeof body["message"] === "string") {
    return { ok: false, code: body["code"], message: body["message"], ...(retryAfter ? { retryAfter } : {}) };
  }
  return { ok: false, code: "unavailable", message: UNAVAILABLE_MESSAGE, ...(retryAfter ? { retryAfter } : {}) };
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
