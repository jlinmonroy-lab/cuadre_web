// SPEC-W-010 §5.5, AC-16, AC-19 · Estados de los accesos, fechas, anotaciones y frases del registro de actividad de «Mi gestor».
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  STATUS_LABEL,
  STATUS_TONE,
  accessDetail,
  canRevoke,
  describeActivity,
  emailOfAccess,
  formatExpiry,
  formatWhen,
  isUuid,
  noteTarget,
  openCount,
  parseCursor,
  type AccessStatus,
  type ActivityEntry,
} from "./gestor.ts";

const ACCESS_ID = "3f2a9c1e-5b7d-4e8a-9c3b-1a2b3c4d5e6f";
const OTHER_ID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";
const ACCESSES = [
  { id: ACCESS_ID, gestor_email: "gestor@example.test" },
  { id: OTHER_ID, gestor_email: "otro@example.test" },
];

const entry = (over: Partial<ActivityEntry>): ActivityEntry => ({
  id: 1,
  occurred_at: "2026-11-05T09:32:00Z",
  action: "gestor.read",
  actor_role: "gestor",
  actor_email: "gestor@example.test",
  entity_type: null,
  entity_id: null,
  year: null,
  quarter: null,
  ...over,
});

// --- Estados --------------------------------------------------------------------------------------------------------------------

test("cada estado se escribe en español y tiene un tono", () => {
  assert.deepEqual(STATUS_LABEL, {
    pending: "Pendiente de aceptar",
    active: "Activo",
    declined: "Rechazada",
    revoked: "Revocada",
    expired: "Caducada",
  });
  assert.deepEqual(STATUS_TONE, { pending: "wait", active: "ok", declined: "closed", revoked: "closed", expired: "closed" });
});

test("solo una invitación pendiente o un acceso activo se pueden revocar", () => {
  const verdicts = Object.fromEntries((Object.keys(STATUS_LABEL) as AccessStatus[]).map((status) => [status, canRevoke(status)]));
  assert.deepEqual(verdicts, { pending: true, active: true, declined: false, revoked: false, expired: false });
});

test("los accesos abiertos son los pendientes y los activos", () => {
  const statuses = ["pending", "active", "declined", "revoked", "expired", "active"] as const;
  assert.equal(openCount(statuses.map((status) => ({ status }))), 3);
  assert.equal(openCount([]), 0);
});

test("el detalle bajo la insignia dice la caducidad solo de una invitación pendiente", () => {
  assert.equal(accessDetail({ status: "pending", expires_at: "2026-11-19T09:32:00Z" }), "Caduca el 19 nov 2026");
  for (const status of ["active", "declined", "revoked", "expired"] as const) {
    assert.equal(accessDetail({ status, expires_at: "2026-11-19T09:32:00Z" }), "", status);
  }
});

// --- Fechas ---------------------------------------------------------------------------------------------------------------------

test("las fechas se enseñan en hora de Madrid, con año y sin pasar el día de largo", () => {
  assert.equal(formatWhen("2026-11-05T09:32:00Z"), "5 nov 2026, 10:32"); // invierno: UTC+1
  assert.equal(formatWhen("2026-07-05T22:30:00Z"), "6 jul 2026, 00:30"); // verano: UTC+2 y cambia el día
  assert.equal(formatWhen("2026-12-31T23:30:00Z"), "1 ene 2027, 00:30"); // cambia el año
  assert.equal(formatExpiry("2026-12-31T23:30:00Z"), "1 ene 2027");
  assert.equal(formatExpiry("2026-11-05T09:32:00Z"), "5 nov 2026");
});

test("una fecha ausente o imposible se enseña como raya, no como «Invalid Date»", () => {
  for (const bad of [null, undefined, "", "no-es-fecha", "2026-13-45T99:99:00Z"]) {
    assert.equal(formatWhen(bad), "—", String(bad));
    assert.equal(formatExpiry(bad), "—", String(bad));
  }
});

// --- Identificadores y cursor ---------------------------------------------------------------------------------------------------

test("solo un UUID en minúsculas es un id", () => {
  assert.equal(isUuid(ACCESS_ID), true);
  for (const bad of ["", "abc", ACCESS_ID.toUpperCase(), `${ACCESS_ID}x`, ` ${ACCESS_ID}`, "../etc", null, undefined, 3, {}]) {
    assert.equal(isUuid(bad), false, String(bad));
  }
});

test("el cursor es un entero de hasta 18 cifras; lo demás es «sin cursor»", () => {
  assert.equal(parseCursor("120"), "120");
  assert.equal(parseCursor("0"), "0");
  assert.equal(parseCursor("123456789012345678"), "123456789012345678");
  for (const bad of [undefined, "", "-1", "1.5", "abc", "12 ", "1; drop", "1234567890123456789", ["1", "2"]]) {
    assert.equal(parseCursor(bad as string | string[] | undefined), undefined, String(bad));
  }
});

// --- Anotaciones ----------------------------------------------------------------------------------------------------------------

test("una anotación enlaza a su factura o a su gasto y nombra un documento sin enlazarlo", () => {
  assert.deepEqual(noteTarget({ entity_type: "invoice", entity_id: ACCESS_ID }), { label: "Sobre una factura", href: `/facturas/${ACCESS_ID}` });
  assert.deepEqual(noteTarget({ entity_type: "expense", entity_id: ACCESS_ID }), { label: "Sobre un gasto", href: `/gastos/${ACCESS_ID}` });
  assert.deepEqual(noteTarget({ entity_type: "document", entity_id: ACCESS_ID }), { label: "Sobre un documento", href: null });
});

test("sin entidad, o con una desconocida, una anotación no apunta a nada; un id raro no se convierte en enlace", () => {
  assert.equal(noteTarget({ entity_type: null, entity_id: null }), null);
  assert.equal(noteTarget({ entity_type: "invoice", entity_id: null }), null);
  assert.equal(noteTarget({ entity_type: null, entity_id: ACCESS_ID }), null);
  assert.equal(noteTarget({ entity_type: "client" as never, entity_id: ACCESS_ID }), null);
  assert.deepEqual(noteTarget({ entity_type: "invoice", entity_id: "../../admin" }), { label: "Sobre una factura", href: null });
  assert.deepEqual(noteTarget({ entity_type: "expense", entity_id: "x" }), { label: "Sobre un gasto", href: null });
});

// --- Registro de actividad ------------------------------------------------------------------------------------------------------

test("el correo de un acceso sale de su id, y si ya no está se devuelve null", () => {
  assert.equal(emailOfAccess(ACCESSES, ACCESS_ID), "gestor@example.test");
  assert.equal(emailOfAccess(ACCESSES, OTHER_ID), "otro@example.test");
  assert.equal(emailOfAccess(ACCESSES, "00000000-0000-4000-8000-000000000000"), null);
  assert.equal(emailOfAccess(ACCESSES, null), null);
  assert.equal(emailOfAccess([], ACCESS_ID), null);
});

test("invitar y revocar nombran al gestor con el correo del acceso al que se refiere la entrada", () => {
  const invited = describeActivity(entry({ action: "gestor_access.invited", actor_role: "usuario", actor_email: null, entity_type: "gestor_access", entity_id: ACCESS_ID }), ACCESSES);
  assert.deepEqual(invited, { text: "Invitaste a gestor@example.test", gestor: "gestor@example.test" });
  const revoked = describeActivity(entry({ action: "gestor_access.revoked", actor_role: "usuario", actor_email: null, entity_type: "gestor_access", entity_id: OTHER_ID }), ACCESSES);
  assert.deepEqual(revoked, { text: "Revocaste el acceso de otro@example.test", gestor: "otro@example.test" });
});

test("si el acceso ya no está en la lista se dice «tu gestor», sin inventar un correo", () => {
  const gone = { actor_role: "usuario" as const, actor_email: null, entity_type: "gestor_access", entity_id: "00000000-0000-4000-8000-000000000000" };
  assert.deepEqual(describeActivity(entry({ action: "gestor_access.invited", ...gone }), ACCESSES), { text: "Invitaste a tu gestor", gestor: null });
  assert.deepEqual(describeActivity(entry({ action: "gestor_access.revoked", ...gone }), ACCESSES), { text: "Revocaste el acceso de tu gestor", gestor: null });
});

test("solo una entrada de acceso se resuelve contra la lista de accesos: el id de otra entidad no nombra a nadie", () => {
  const read = describeActivity(entry({ action: "gestor.read", actor_email: null, entity_type: "invoice", entity_id: ACCESS_ID }), ACCESSES);
  assert.deepEqual(read, { text: "Tu gestor consultó una factura", gestor: null });
  const note = describeActivity(entry({ action: "gestor.note_added", actor_email: null, entity_type: "gestor_note", entity_id: ACCESS_ID }), ACCESSES);
  assert.equal(note.gestor, null);
});

test("aceptar, rechazar y añadir una anotación las hace el gestor, con su correo aparte", () => {
  assert.deepEqual(describeActivity(entry({ action: "gestor_access.accepted" }), ACCESSES), { text: "Tu gestor aceptó tu invitación", gestor: "gestor@example.test" });
  assert.deepEqual(describeActivity(entry({ action: "gestor_access.declined" }), ACCESSES), { text: "Tu gestor rechazó tu invitación", gestor: "gestor@example.test" });
  assert.deepEqual(describeActivity(entry({ action: "gestor.note_added", entity_type: "gestor_note" }), ACCESSES), { text: "Tu gestor añadió una anotación", gestor: "gestor@example.test" });
});

test("si fue el gestor quien se dio de baja, la frase no dice que el autónomo revocó", () => {
  const line = describeActivity(entry({ action: "gestor_access.revoked", actor_role: "gestor" }), ACCESSES);
  assert.deepEqual(line, { text: "Tu gestor renunció a su acceso", gestor: "gestor@example.test" });
});

test("cada lectura tiene su frase y nunca lleva datos", () => {
  const expected: Record<string, string> = {
    portfolio: "Tu gestor abrió tu ficha",
    invoices: "Tu gestor consultó tus facturas",
    invoice: "Tu gestor consultó una factura",
    invoice_pdf: "Tu gestor descargó el PDF de una factura",
    expenses: "Tu gestor consultó tus gastos",
    documents: "Tu gestor consultó tus documentos pendientes",
    document_original: "Tu gestor descargó el original de un documento",
    profile: "Tu gestor consultó tu perfil y tus series",
    clients: "Tu gestor consultó tus clientes",
    notes: "Tu gestor consultó sus anotaciones",
  };
  for (const [type, text] of Object.entries(expected)) {
    assert.deepEqual(describeActivity(entry({ entity_type: type }), ACCESSES), { text, gestor: "gestor@example.test" }, type);
  }
});

test("el borrador del 303 y del 130 dicen el trimestre y el año si el registro los trae", () => {
  assert.equal(describeActivity(entry({ entity_type: "modelo_303", year: 2025, quarter: 2 }), ACCESSES).text, "Tu gestor consultó el borrador del modelo 303 del T2 de 2025");
  assert.equal(describeActivity(entry({ entity_type: "modelo_130", year: 2026, quarter: 4 }), ACCESSES).text, "Tu gestor consultó el borrador del modelo 130 del T4 de 2026");
  assert.equal(describeActivity(entry({ entity_type: "modelo_303" }), ACCESSES).text, "Tu gestor consultó el borrador del modelo 303");
  assert.equal(describeActivity(entry({ entity_type: "modelo_130", year: 2025, quarter: null }), ACCESSES).text, "Tu gestor consultó el borrador del modelo 130");
});

test("un periodo imposible no se escribe", () => {
  for (const [year, quarter] of [[2025, 0], [2025, 5], [2025, 1.5], [1999, 1], [2101, 1], [2025.5, 1]] as const) {
    assert.equal(describeActivity(entry({ entity_type: "modelo_303", year, quarter }), ACCESSES).text, "Tu gestor consultó el borrador del modelo 303", `${year} T${quarter}`);
  }
});

test("un tipo o una acción desconocidos no se reflejan: frase genérica", () => {
  assert.equal(describeActivity(entry({ entity_type: "<script>alert(1)</script>" }), ACCESSES).text, "Tu gestor consultó datos de tu cuenta");
  assert.equal(describeActivity(entry({ entity_type: "constructor" }), ACCESSES).text, "Tu gestor consultó datos de tu cuenta");
  assert.equal(describeActivity(entry({ entity_type: null }), ACCESSES).text, "Tu gestor consultó datos de tu cuenta");
  assert.equal(describeActivity(entry({ action: "<b>x</b>" }), ACCESSES).text, "Actividad en el acceso de tu gestor");
  assert.equal(describeActivity(entry({ action: "toString" }), ACCESSES).text, "Actividad en el acceso de tu gestor");
});

test("el correo de una lectura es el del gestor que actuó, aunque no esté en la lista de accesos", () => {
  const line = describeActivity(entry({ entity_type: "invoices", actor_email: "otro.gestor@example.test" }), []);
  assert.deepEqual(line, { text: "Tu gestor consultó tus facturas", gestor: "otro.gestor@example.test" });
});
