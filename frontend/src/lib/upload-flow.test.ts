// AC-01, AC-04, AC-05 · Reservar → subir → leer, con sus fallos y sus reintentos, y el tope de archivos a la vez.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  NETWORK_MESSAGE,
  createLimiter,
  newItem,
  putToStorage,
  readViaHandler,
  runUpload,
  type ItemPatch,
  type PutResult,
  type ReadResult,
  type ReserveResult,
  type UploadDeps,
  type UploadItem,
} from "./upload-flow.ts";

const FILE = new Blob(["%PDF-1.4 sintetico"], { type: "application/pdf" });
const TARGET = { url: "https://storage.test/upload?token=SECRETO", headers: { "Content-Type": "application/pdf" } };

function item(): UploadItem {
  return newItem("k1", { name: "factura.pdf", type: "application/pdf", size: 18 }, "application/pdf", "file");
}

type Doubles = {
  reserve?: () => Promise<ReserveResult> | ReserveResult;
  put?: () => Promise<PutResult> | PutResult;
  read?: () => Promise<ReadResult> | ReadResult;
  discard?: (id: string) => unknown;
};

function setup(doubles: Doubles = {}) {
  const calls: string[] = [];
  const deps: UploadDeps = {
    async reserve(input) {
      calls.push(`reserve:${input.filename}:${input.mimeType}:${input.sizeBytes}:${input.source}`);
      return (await doubles.reserve?.()) ?? { ok: true, id: "doc-1", upload: TARGET };
    },
    async put(target, file) {
      calls.push(`put:${target.url}:${file.size}`);
      return (await doubles.put?.()) ?? { ok: true };
    },
    async read(id) {
      calls.push(`read:${id}`);
      return (await doubles.read?.()) ?? { ok: true, status: "review" };
    },
    async discard(id) {
      calls.push(`discard:${id}`);
      return doubles.discard?.(id);
    },
  };
  const states: UploadItem[] = [];
  let current = item();
  const emit = (patch: ItemPatch) => {
    current = { ...current, ...patch };
    states.push(current);
  };
  return { deps, calls, states, emit, get current() { return current; }, set current(next: UploadItem) { current = next; } };
}

test("camino feliz: reserva, sube y lee, en ese orden", async () => {
  const run = setup();
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.deepEqual(run.calls, ["reserve:factura.pdf:application/pdf:18:file", `put:${TARGET.url}:18`, "read:doc-1"]);
  assert.deepEqual(run.states.map((s) => s.step), ["reserving", "uploading", "reading", "done"]);
  assert.equal(run.current.documentId, "doc-1");
  assert.equal(run.current.result, "review");
  assert.equal(run.current.message, null);
});

test("la foto de la cámara se reserva con origen «camera»", async () => {
  const run = setup();
  const photo = newItem("k2", { name: "foto.jpg", type: "image/jpeg", size: 5 }, "image/jpeg", "camera");
  await runUpload(run.deps, photo, FILE, run.emit);
  assert.equal(run.calls[0], "reserve:foto.jpg:image/jpeg:5:camera");
});

test("una lectura fallida del agente sigue siendo «hecho»: la persona la ve en la lista y puede rellenarla a mano (AC-05)", async () => {
  const run = setup({ read: () => ({ ok: true, status: "extraction_failed" }) });
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.equal(run.current.step, "done");
  assert.equal(run.current.result, "extraction_failed");
});

test("si la reserva falla (429, tipo, tamaño…) no se sube ni se lee nada y se puede empezar de nuevo", async () => {
  const run = setup({ reserve: () => ({ ok: false, message: "Ya hay 5 documentos leyéndose." }) });
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.deepEqual(run.calls, ["reserve:factura.pdf:application/pdf:18:file"]);
  assert.equal(run.current.step, "error");
  assert.equal(run.current.message, "Ya hay 5 documentos leyéndose.");
  assert.equal(run.current.retry, "restart");
});

test("si la reserva lanza una excepción, mensaje de conexión", async () => {
  const run = setup({ reserve: () => Promise.reject(new Error("boom")) });
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.equal(run.current.message, NETWORK_MESSAGE);
  assert.equal(run.current.retry, "restart");
});

test("si la subida falla, se descarta la reserva y se puede empezar de cero", async () => {
  const run = setup({ put: () => ({ ok: false }) });
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.deepEqual(run.calls, ["reserve:factura.pdf:application/pdf:18:file", `put:${TARGET.url}:18`, "discard:doc-1"]);
  assert.equal(run.current.step, "error");
  assert.equal(run.current.documentId, null, "ya no hay documento al que volver");
  assert.equal(run.current.retry, "restart");
  assert.match(run.current.message ?? "", /No se pudo subir «factura\.pdf»/);
});

test("si además falla el descarte, el error es el mismo (se ignora)", async () => {
  const run = setup({ put: () => Promise.reject(new Error("red")), discard: () => Promise.reject(new Error("tampoco")) });
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.equal(run.current.step, "error");
  assert.equal(run.current.retry, "restart");
});

test("fallos de la lectura: unos se reintentan sobre el mismo documento y otros no", async () => {
  const cases: [string, "reading" | "none"][] = [
    ["upload_missing", "reading"],
    ["too_many_processing", "reading"],
    ["storage_unavailable", "reading"],
    ["network", "reading"],
    ["unavailable", "reading"],
    ["internal_error", "reading"],
    ["file_type_mismatch", "none"], // el documento ya está descartado y el archivo volvería a fallar
    ["upload_size_mismatch", "none"],
    ["document_not_found", "none"],
    ["session", "none"],
  ];
  for (const [code, retry] of cases) {
    const run = setup({ read: () => ({ ok: false, code, message: `fallo ${code}` }) });
    await runUpload(run.deps, run.current, FILE, run.emit);
    assert.equal(run.current.step, "error", code);
    assert.equal(run.current.retry, retry, code);
    assert.equal(run.current.message, `fallo ${code}`, code);
    assert.equal(run.current.documentId, "doc-1", "el documento se conserva para poder repetir la lectura");
  }
});

test("si la lectura lanza una excepción, se explica que puede seguir leyéndose y se puede repetir", async () => {
  const run = setup({ read: () => Promise.reject(new Error("corte")) });
  await runUpload(run.deps, run.current, FILE, run.emit);
  assert.equal(run.current.retry, "reading");
  assert.match(run.current.message ?? "", /No hemos podido confirmar la lectura/);
});

test("«Reintentar» la lectura no reserva ni sube otra vez", async () => {
  const run = setup();
  run.current = { ...item(), documentId: "doc-9", step: "error", retry: "reading", message: "x" };
  await runUpload(run.deps, run.current, FILE, run.emit, "reading");
  assert.deepEqual(run.calls, ["read:doc-9"]);
  assert.equal(run.current.step, "done");
  assert.equal(run.current.message, null);
});

test("pedir «reading» sin documento equivale a empezar de cero", async () => {
  const run = setup();
  await runUpload(run.deps, run.current, FILE, run.emit, "reading");
  assert.equal(run.calls[0], "reserve:factura.pdf:application/pdf:18:file");
});

// --- Límite de archivos a la vez ------------------------------------------------------------------------------------------------

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

test("el limitador no pasa de N tareas a la vez y respeta el orden de llegada", async () => {
  const limit = createLimiter(3);
  let running = 0;
  let peak = 0;
  const started: number[] = [];
  const tasks = Array.from({ length: 10 }, (_, index) =>
    limit(async () => {
      started.push(index);
      running++;
      peak = Math.max(peak, running);
      await pause(5);
      running--;
      return index;
    }),
  );
  assert.deepEqual(await Promise.all(tasks), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.equal(peak, 3);
  assert.deepEqual(started, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
});

test("una tarea que falla no detiene la cola", async () => {
  const limit = createLimiter(1);
  const results = await Promise.allSettled([
    limit(() => Promise.reject(new Error("falla"))),
    limit(async () => "sigue"),
    limit(() => {
      throw new Error("síncrona");
    }),
    limit(async () => "y sigue"),
  ]);
  assert.deepEqual(
    results.map((r) => r.status),
    ["rejected", "fulfilled", "rejected", "fulfilled"],
  );
});

// --- Las dos llamadas del navegador ---------------------------------------------------------------------------------------------

test("el PUT lleva solo Content-Type, sin credenciales, y el archivo", async () => {
  const seen: { url: string; init: RequestInit }[] = [];
  const fetchFn = (async (url: string, init: RequestInit) => {
    seen.push({ url, init });
    return new Response(null, { status: 200 });
  }) as unknown as typeof fetch;
  const target = { url: TARGET.url, headers: { "Content-Type": "application/pdf", Authorization: "Bearer X", apikey: "Y" } };

  assert.deepEqual(await putToStorage(fetchFn, target, FILE), { ok: true });
  const [call] = seen;
  assert.equal(call?.url, TARGET.url);
  assert.equal(call?.init.method, "PUT");
  assert.deepEqual(call?.init.headers, { "Content-Type": "application/pdf" }, "nada más que el tipo, aunque la reserva trajese otras cabeceras");
  assert.equal(call?.init.credentials, "omit");
  assert.equal(call?.init.body, FILE);
});

test("el PUT fallido (409, 413, 415, 403, red) es un fallo", async () => {
  for (const status of [403, 409, 413, 415, 500]) {
    const fetchFn = (async () => new Response(null, { status })) as unknown as typeof fetch;
    assert.deepEqual(await putToStorage(fetchFn, TARGET, FILE), { ok: false }, String(status));
  }
  const broken = (async () => {
    throw new TypeError("Failed to fetch");
  }) as unknown as typeof fetch;
  assert.deepEqual(await putToStorage(broken, TARGET, FILE), { ok: false });
});

const json = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), { ...init, headers: { "content-type": "application/json", ...init.headers } });

test("la lectura va al Route Handler de la web, con las cookies de la propia web", async () => {
  const seen: { url: string; init: RequestInit }[] = [];
  const fetchFn = (async (url: string, init: RequestInit) => {
    seen.push({ url, init });
    return json({ id: "d", status: "review" });
  }) as unknown as typeof fetch;

  assert.deepEqual(await readViaHandler(fetchFn, "abc-123"), { ok: true, status: "review" });
  assert.deepEqual(await readViaHandler(fetchFn, "abc-123", "reread"), { ok: true, status: "review" });
  assert.deepEqual(seen.map((s) => s.url), ["/gastos/abc-123/leer", "/gastos/abc-123/releer"]);
  assert.equal(seen[0]?.init.method, "POST");
  assert.equal(seen[0]?.init.credentials, "same-origin");
});

test("el id va codificado en la ruta", async () => {
  let url = "";
  const fetchFn = (async (u: string) => {
    url = u;
    return json({ status: "review" });
  }) as unknown as typeof fetch;
  await readViaHandler(fetchFn, "../x?y=1");
  assert.equal(url, "/gastos/..%2Fx%3Fy%3D1/leer");
});

test("errores del handler: código, mensaje en español y Retry-After", async () => {
  const fetchFn = (async () =>
    json({ code: "too_many_processing", message: "Ya hay 5 documentos leyéndose." }, { status: 429, headers: { "retry-after": "10" } })) as unknown as typeof fetch;
  assert.deepEqual(await readViaHandler(fetchFn, "d"), {
    ok: false,
    code: "too_many_processing",
    message: "Ya hay 5 documentos leyéndose.",
    retryAfter: 10,
  });
});

test("sin sesión (redirección al login) no se puede reintentar", async () => {
  const redirected = Object.defineProperty(new Response("<html></html>", { status: 200, headers: { "content-type": "text/html" } }), "redirected", { value: true });
  const result = await readViaHandler((async () => redirected) as unknown as typeof fetch, "d");
  assert.equal(result.ok, false);
  assert.equal(result.ok ? "" : result.code, "session");
});

test("una respuesta que no es lo esperado (HTML de un proxy, JSON raro) es «servicio no disponible»", async () => {
  for (const response of [
    new Response("<html>Bad gateway</html>", { status: 502, headers: { "content-type": "text/html" } }),
    json({ algo: "raro" }, { status: 500 }),
    json([1, 2, 3], { status: 500 }),
    new Response("{no json", { status: 500, headers: { "content-type": "application/json" } }),
  ]) {
    const result = await readViaHandler((async () => response) as unknown as typeof fetch, "d");
    assert.equal(result.ok, false);
    assert.equal(result.ok ? "" : result.code, "unavailable");
  }
});

test("un fallo de red al pedir la lectura es «no se pudo confirmar», repetible", async () => {
  const broken = (async () => {
    throw new TypeError("Failed to fetch");
  }) as unknown as typeof fetch;
  const result = await readViaHandler(broken, "d");
  assert.equal(result.ok, false);
  assert.equal(result.ok ? "" : result.code, "network");
});

test("Retry-After del handler: solo segundos enteros y positivos", async () => {
  const with429 = (header: string | null) =>
    (async () => json({ code: "too_many_processing", message: "Espera." }, { status: 429, headers: header === null ? {} : { "retry-after": header } })) as unknown as typeof fetch;
  const after = async (header: string | null) => {
    const result = await readViaHandler(with429(header), "d");
    return result.ok ? "ok" : result.retryAfter;
  };
  assert.equal(await after("10"), 10);
  assert.equal(await after("120"), 120);
  for (const bad of ["1.5", "0", "-3", "abc", "1e2", "Wed, 21 Oct 2026 07:28:00 GMT", "", "1000", null]) assert.equal(await after(bad), undefined, String(bad));
});
