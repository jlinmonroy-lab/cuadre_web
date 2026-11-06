// SPEC-W-002 §5.1, AC-04, AC-10 · Qué archivos se intentan subir y cómo se nombran los estados.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ACCEPT_FILES,
  DOC_TYPES,
  DOC_TYPE_LABELS,
  DOUBT_FIELD_LABELS,
  DOUBT_REASON_TEXT,
  MAX_UPLOAD_BYTES,
  MIME_TYPES,
  STATUSES,
  checkFile,
  declaredMimeType,
  docTypeLabel,
  doubtReasonText,
  failureHint,
  formatBytes,
  formatDay,
  formatMoment,
  httpUrl,
  isDocumentId,
  isReading,
  quoteName,
  statusView,
} from "./documents.ts";

const file = (name: string, type: string, size = 1000) => ({ name, type, size });

test("el tope es de 15 MiB, como la API, la CHECK y el bucket", () => {
  assert.equal(MAX_UPLOAD_BYTES, 15728640);
});

test("manda el tipo del navegador cuando es uno de los admitidos", () => {
  for (const type of MIME_TYPES) assert.equal(declaredMimeType(file("x.bin", type)), type);
  assert.equal(declaredMimeType(file("x", "IMAGE/PNG")), "image/png");
  assert.equal(declaredMimeType(file("x", "application/pdf; charset=binary")), "application/pdf");
});

test("sin tipo (Windows con .heic) o con uno genérico, manda la extensión", () => {
  assert.equal(declaredMimeType(file("foto.heic", "")), "image/heic");
  assert.equal(declaredMimeType(file("FOTO.HEIC", "")), "image/heic");
  assert.equal(declaredMimeType(file("foto.heif", "")), "image/heic");
  assert.equal(declaredMimeType(file("factura.pdf", "application/octet-stream")), "application/pdf");
  assert.equal(declaredMimeType(file("a.b.c.jpeg", "")), "image/jpeg");
  assert.equal(declaredMimeType(file("a.jpg", "")), "image/jpeg");
  assert.equal(declaredMimeType(file("a.png", "")), "image/png");
  assert.equal(declaredMimeType(file("a.webp", "")), "image/webp");
});

test("image/heif es el mismo formato que image/heic", () => {
  assert.equal(declaredMimeType(file("x.heic", "image/heif")), "image/heic");
  assert.equal(declaredMimeType(file("sin-extension", "image/heif")), "image/heic");
});

test("lo que no es de los cinco tipos no se declara", () => {
  for (const [name, type] of [
    ["a.txt", "text/plain"],
    ["a.zip", "application/zip"],
    ["a.gif", "image/gif"],
    ["a.svg", "image/svg+xml"],
    ["a.exe", ""],
    ["sin-extension", ""],
    ["pdf", ""], // «pdf» sin punto no es una extensión
    [".pdf.exe", ""],
    ["a.constructor", ""],
    ["a.__proto__", ""],
    ["a.toString", ""],
  ] as const) {
    assert.equal(declaredMimeType(file(name, type)), null, name);
  }
});

test("checkFile acepta los cinco tipos hasta 15 MiB incluidos", () => {
  for (const type of MIME_TYPES) assert.deepEqual(checkFile(file("x", type, 1)), { ok: true, mimeType: type });
  assert.deepEqual(checkFile(file("x.pdf", "application/pdf", MAX_UPLOAD_BYTES)), { ok: true, mimeType: "application/pdf" });
});

test("checkFile rechaza con un mensaje en español, sin tocar los demás archivos", () => {
  const tooBig = checkFile(file("grande.pdf", "application/pdf", MAX_UPLOAD_BYTES + 1));
  assert.equal(tooBig.ok, false);
  assert.match(tooBig.ok ? "" : tooBig.message, /«grande\.pdf» pesa 15 MB y el máximo es de 15 MB/);

  const empty = checkFile(file("vacio.pdf", "application/pdf", 0));
  assert.deepEqual(empty, { ok: false, message: "«vacio.pdf» está vacío." });

  const wrong = checkFile(file("nota.txt", "text/plain"));
  assert.match(wrong.ok ? "" : wrong.message, /«nota\.txt» no es un tipo admitido\. Sube un PDF o una imagen JPG, PNG, HEIC o WebP\./);
});

test("el tipo se decide antes que el tamaño: un .exe enorme es «tipo no admitido»", () => {
  const result = checkFile(file("a.exe", "application/x-msdownload", MAX_UPLOAD_BYTES * 2));
  assert.match(result.ok ? "" : result.message, /no es un tipo admitido/);
});

test("quoteName acorta los nombres largos y no interpreta nada", () => {
  assert.equal(quoteName("a.pdf"), "«a.pdf»");
  const long = `${"x".repeat(80)}.pdf`;
  assert.equal([...quoteName(long)].length, 47 + 1 + 2); // 47 caracteres + «…» + las dos comillas
  assert.ok(quoteName(long).endsWith("…»"));
  assert.equal(quoteName("<img src=x onerror=alert(1)>.pdf"), "«<img src=x onerror=alert(1)>.pdf»"); // React lo escapa al pintar
});

test("tamaños legibles", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(1023), "1023 B");
  assert.equal(formatBytes(1536), "1,5 KB");
  assert.equal(formatBytes(2.5 * 1024 * 1024), "2,5 MB");
  assert.equal(formatBytes(MAX_UPLOAD_BYTES), "15 MB");
});

test("el atributo accept lista extensiones y tipos, y la cámara solo imágenes", () => {
  for (const extension of [".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"]) assert.ok(ACCEPT_FILES.includes(extension), extension);
  for (const type of MIME_TYPES) assert.ok(ACCEPT_FILES.includes(type), type);
});

test("estados: siempre con texto, y el tono solo refuerza", () => {
  assert.deepEqual(statusView("processing", 0), { label: "Leyendo…", detail: null, tone: "neutral" });
  assert.deepEqual(statusView("review", 0), { label: "Para revisar", detail: "Lectura completa", tone: "ok" });
  assert.deepEqual(statusView("review", 1), { label: "Para revisar", detail: "1 dato dudoso", tone: "doubt" });
  assert.deepEqual(statusView("review", 3), { label: "Para revisar", detail: "3 datos dudosos", tone: "doubt" });
  assert.deepEqual(statusView("extraction_failed", 0), { label: "No se pudo leer", detail: null, tone: "error" });
  for (const status of STATUSES) {
    const view = statusView(status, 2);
    assert.ok(view.label.length > 0, status);
  }
});

test("solo processing está leyendo (el refresco automático depende de esto)", () => {
  assert.equal(isReading("processing"), true);
  for (const other of STATUSES.filter((s) => s !== "processing")) assert.equal(isReading(other), false, other);
});

test("los seis tipos de documento tienen nombre; lo desconocido es «Documento»", () => {
  for (const type of DOC_TYPES) assert.ok(DOC_TYPE_LABELS[type], type);
  assert.equal(docTypeLabel("full_invoice"), "Factura completa");
  assert.equal(docTypeLabel("not_an_invoice"), "No es una factura");
  for (const unknown of [null, undefined, "", "constructor", "__proto__", "inventado"]) assert.equal(docTypeLabel(unknown), "Documento", String(unknown));
});

test("los campos dudosos del contrato tienen nombre, y el total es `total`", () => {
  for (const field of ["doc_type", "supplier_name", "supplier_tax_id", "recipient_tax_id", "invoice_number", "issue_date", "currency", "tax_breakdown", "withholding", "total"]) {
    assert.ok(DOUBT_FIELD_LABELS[field], field);
  }
  assert.equal(DOUBT_FIELD_LABELS["total_cents"], undefined);
});

test("cada motivo de duda tiene un texto que pide comprobar", () => {
  for (const reason of ["illegible", "ambiguous", "missing", "inconsistent"]) assert.ok(DOUBT_REASON_TEXT[reason], reason);
  assert.equal(doubtReasonText("illegible"), "No se lee con claridad: compruébalo.");
  for (const unknown of ["", "constructor", "__proto__", "otro"]) assert.equal(doubtReasonText(unknown), "Compruébalo.", unknown);
});

test("fechas de calendario sin desplazarse por la zona horaria", () => {
  assert.equal(formatDay("2026-11-01"), "1 nov 2026");
  assert.equal(formatDay("2026-01-31"), "31 ene 2026");
  for (const bad of [null, undefined, "", "01/11/2026", "2026-13-40", "2026-11-01T00:00:00", "x"]) assert.equal(formatDay(bad), "—", String(bad));
});

test("instantes en hora de Madrid", () => {
  assert.match(formatMoment("2026-11-05T09:32:00+00:00"), /5 nov,? 10:32/); // CET (UTC+1)
  assert.match(formatMoment("2026-07-05T09:32:00+00:00"), /5 jul,? 11:32/); // CEST (UTC+2)
  for (const bad of [null, undefined, "", "mañana"]) assert.equal(formatMoment(bad), "—", String(bad));
});

test("un identificador de documento es un UUID y nada más", () => {
  assert.equal(isDocumentId("3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"), true);
  assert.equal(isDocumentId("3F2A1B4C-5D6E-4F70-8A9B-0C1D2E3F4A5B"), true);
  for (const bad of ["", "abc", "../x", "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5", "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5bb", "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b/leer", "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b\n", null, undefined, 3, {}]) {
    assert.equal(isDocumentId(bad), false, String(bad));
  }
});

test("solo se redirige al original si la URL es http(s) y sin credenciales", () => {
  assert.equal(httpUrl("https://abc.supabase.co/storage/v1/object/sign/documents/x.pdf?token=t"), "https://abc.supabase.co/storage/v1/object/sign/documents/x.pdf?token=t");
  assert.equal(httpUrl("http://127.0.0.1:54321/storage/v1/object/sign/documents/x.pdf?token=t"), "http://127.0.0.1:54321/storage/v1/object/sign/documents/x.pdf?token=t");
  for (const bad of ["javascript:alert(1)", "data:text/html,<script>1</script>", "file:///etc/passwd", "ftp://x.test/a", "//evil.test/x", "/relativa", "https://user:pass@x.test/a", "https://user@x.test/a", "", "no es una url", null, undefined, 3]) {
    assert.equal(httpUrl(bad), null, String(bad));
  }
});

test("la pista tras un fallo solo se añade cuando el mensaje del motivo no dice qué hacer", () => {
  for (const code of ["unreadable", "upstream_error", "agents_unavailable"]) assert.equal(failureHint(code), null, code);
  for (const code of ["timeout", "invalid_response", "internal", "payload_too_large", "unsupported_media_type", "otro"]) {
    assert.match(failureHint(code) ?? "", /volver a leerlo o escribir los datos/, code);
  }
});
