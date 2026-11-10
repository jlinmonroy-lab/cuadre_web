// Route Handlers de facturas sin red: errores de la vista previa y cabeceras de la descarga del PDF (SPEC-W-007 §5.5).
import assert from "node:assert/strict";
import { test } from "node:test";

import { pdfFailure, pdfHeaders, previewError, safePdfFilename } from "./invoice-handlers.ts";
import type { Problem } from "./problems.ts";

const problem = (overrides: Partial<Problem>): Problem => ({ status: 422, code: "invalid_invoice", message: "Revisa los campos marcados.", ...overrides });

test("la vista previa enseña solo los errores del cliente, la serie, el importe y el IVA", () => {
  const reply = previewError(
    problem({
      invoiceFields: [
        { field: "client_id", message: "Elige un cliente." },
        { field: "issue_date", message: "La fecha no puede ser futura." },
        { field: "concept", message: "Describe el servicio." },
        { field: "base_cents", message: "Importe mal." },
        { field: "vat_rate", message: "IVA mal." },
        { field: "series_id", message: "Elige una serie activa." },
      ],
    }),
  );
  assert.deepEqual(reply, {
    status: "error",
    code: "invalid_invoice",
    message: "Revisa los campos marcados.",
    fieldErrors: { client_id: "Elige un cliente.", series_id: "Elige una serie activa.", base: "Importe mal.", vat_rate: "IVA mal." },
  });
});

test("si el único error es de la fecha o el concepto, la vista previa dice solo que revises los datos", () => {
  const reply = previewError(problem({ invoiceFields: [{ field: "issue_date", message: "La fecha no puede ser futura." }] }));
  assert.deepEqual(reply, { status: "error", code: "invalid_invoice", message: "Revisa los datos de la factura para ver la vista previa.", fieldErrors: {} });
});

test("el perfil incompleto y la retención sin elegir llegan como titular", () => {
  const missing = [{ field: "tax_id", label: "NIF" }];
  assert.deepEqual(previewError(problem({ code: "profile_incomplete", message: "Completa tu perfil.", missing })), {
    status: "error",
    code: "profile_incomplete",
    message: "Completa tu perfil.",
    fieldErrors: {},
    missing,
  });
  assert.deepEqual(previewError(problem({ status: 422, code: "irpf_rate_missing", message: "Elige tu retención." })), {
    status: "error",
    code: "irpf_rate_missing",
    message: "Elige tu retención.",
    fieldErrors: {},
  });
  const billable = problem({ status: 409, code: "client_not_billable", field: "address", message: "Falta el domicilio." });
  assert.equal(previewError(billable).fieldErrors["client_id"], "Falta el domicilio.");
});

test("el nombre del archivo es sencillo o `factura.pdf`", () => {
  assert.equal(safePdfFilename('attachment; filename="2026-001.pdf"'), "2026-001.pdf");
  assert.equal(safePdfFilename('attachment; filename="R-2026-003.pdf"'), "R-2026-003.pdf");
  const bad = [
    null,
    "",
    "attachment",
    'attachment; filename="../../x.pdf"',
    'attachment; filename="a b.pdf"',
    'attachment; filename="x.exe"',
    `attachment; filename="${"a".repeat(60)}.pdf"`,
    'attachment; filename="a\r\nSet-Cookie: x.pdf"',
    'attachment; filename="a..b.pdf"',
  ];
  for (const disposition of bad) assert.equal(safePdfFilename(disposition), "factura.pdf", String(disposition));
});

test("el PDF se entrega siempre como adjunto, sin caché y con tipo fijo", () => {
  const upstream: Record<string, string> = {
    "content-type": "application/pdf",
    "content-disposition": 'attachment; filename="2026-001.pdf"',
    "cache-control": "public, max-age=999",
    "set-cookie": "x=1",
  };
  assert.deepEqual(pdfHeaders((name) => upstream[name] ?? null), {
    "content-type": "application/pdf",
    "content-disposition": 'attachment; filename="2026-001.pdf"',
    "cache-control": "private, no-store",
    "x-content-type-options": "nosniff",
  });
  assert.equal(pdfHeaders(() => "Application/PDF; charset=binary")?.["content-type"], "application/pdf");
  for (const type of [null, "", "text/html", "application/json", "application/pdfx", "image/png"]) {
    assert.equal(pdfHeaders((name) => (name === "content-type" ? type : null)), null, String(type));
  }
});

test("cuando la API no entrega el PDF, el texto es en español y el 5xx nunca enseña su cuerpo", () => {
  assert.deepEqual(pdfFailure(problem({ status: 401 })), { status: 401, text: "Tu sesión ha caducado. Vuelve a iniciar sesión para continuar." });
  assert.deepEqual(pdfFailure(problem({ status: 403 })), { status: 403, text: "No tienes acceso a esta factura." });
  assert.deepEqual(pdfFailure(problem({ status: 404 })), { status: 404, text: "No encontramos esa factura." });
  const pending = problem({ status: 409, code: "invoice_pdf_pending", message: "Esta factura aún no tiene PDF." });
  assert.deepEqual(pdfFailure(pending), { status: 409, text: "Esta factura aún no tiene PDF." });
  const unavailable = "El servicio no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.";
  assert.deepEqual(pdfFailure(problem({ status: 503, message: "traza interna", retryAfter: 5 })), { status: 503, text: unavailable, retryAfter: 5 });
  assert.deepEqual(pdfFailure(problem({ status: 500, message: "traza" })), { status: 503, text: unavailable });
  assert.deepEqual(pdfFailure(problem({ status: 422 })), { status: 503, text: unavailable });
});
