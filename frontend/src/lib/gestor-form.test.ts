// SPEC-W-010 §5.5, AC-19 · El formulario de invitación: qué se envía, y dónde se pinta cada error de la API.
import assert from "node:assert/strict";
import { test } from "node:test";

import { INVITE_FORM_FIELDS, fieldErrorsFromInviteProblem, inviteMessage, toInviteBody, valuesFromInviteForm } from "./gestor-form.ts";
import { describeProblem } from "./problems.ts";

// Los caracteres raros se construyen con código: la herramienta que escribe este archivo los convertiría en invisibles.
const code = (n: number) => String.fromCharCode(n);

const problem = (status: number, body: Record<string, unknown>) => describeProblem({ status, body });

test("el único campo es el correo", () => {
  assert.deepEqual([...INVITE_FORM_FIELDS], ["email"]);
});

test("del formulario solo se lee el correo; lo demás se ignora", () => {
  const form = new Map<string, unknown>([["email", "Gestor@Example.test"], ["status", "active"], ["owner_id", "x"]]);
  assert.deepEqual(valuesFromInviteForm((name) => form.get(name)), { email: "Gestor@Example.test" });
  assert.deepEqual(valuesFromInviteForm(() => undefined), { email: "" });
  assert.deepEqual(valuesFromInviteForm(() => new Blob(["x"])), { email: "" });
  assert.deepEqual(valuesFromInviteForm(() => 5), { email: "" });
});

test("un campo con otro nombre no sustituye al correo", () => {
  const form = new Map<string, unknown>([["gestor_email", "otro@example.test"], ["Email", "x@example.test"]]);
  assert.deepEqual(valuesFromInviteForm((name) => form.get(name)), { email: "" });
});

test("el cuerpo recorta los espacios y no cambia las mayúsculas (lo trata el servidor)", () => {
  assert.deepEqual(toInviteBody({ email: "  Gestor@Example.test  " }), { email: "Gestor@Example.test" });
  assert.deepEqual(toInviteBody({}), { email: "" });
});

test("los controles y los caracteres invisibles no llegan a la API", () => {
  assert.deepEqual(toInviteBody({ email: `${code(0)}a${code(0x200b)}@${code(0x202e)}example.test${code(0x7f)}` }), { email: "a @ example.test" });
  assert.deepEqual(toInviteBody({ email: `a${code(10)}b@example.test` }), { email: "a b@example.test" });
});

test("los errores del correo van junto al campo con el texto del servidor", () => {
  const cases: [number, string, string][] = [
    [422, "invalid_email", "Escribe un correo electrónico válido."],
    [422, "cannot_invite_self", "No puedes invitarte a ti mismo."],
    [409, "invitation_already_open", "Ya hay una invitación pendiente o un acceso activo para ese correo."],
  ];
  for (const [status, codeName, detail] of cases) {
    assert.deepEqual(fieldErrorsFromInviteProblem(problem(status, { code: codeName, detail })), { email: detail }, codeName);
  }
});

test("un cuerpo mal formado usa nuestro texto, no el genérico de la API", () => {
  const generic = problem(422, { code: "validation_error", detail: "Revisa los datos enviados." });
  assert.deepEqual(fieldErrorsFromInviteProblem(generic), { email: "Escribe un correo electrónico válido." });
});

test("el límite de invitaciones y los fallos del servicio no son del campo", () => {
  const limit = problem(422, { code: "too_many_open_invitations", detail: "Ya tienes 5 invitaciones o accesos abiertos. Revoca alguno para invitar a otra persona." });
  assert.equal(fieldErrorsFromInviteProblem(limit), undefined);
  assert.equal(limit.message, "Ya tienes 5 invitaciones o accesos abiertos. Revoca alguno para invitar a otra persona.");
  assert.equal(fieldErrorsFromInviteProblem(problem(503, { code: "service_unavailable" })), undefined);
  assert.equal(fieldErrorsFromInviteProblem(problem(403, { code: "forbidden" })), undefined);
  assert.equal(fieldErrorsFromInviteProblem(problem(500, {})), undefined);
});

test("el texto de un 5xx no se refleja ni siquiera con el código de un error del correo", () => {
  const sneaky = problem(500, { code: "invalid_email", detail: "Traceback (most recent call last)" });
  assert.ok(!JSON.stringify(fieldErrorsFromInviteProblem(sneaky) ?? {}).includes("Traceback"));
});

test("el mensaje de éxito dice a quién se invitó; si el correo no salió, avisa de que queda pendiente", () => {
  assert.equal(inviteMessage({ gestor_email: "gestor@example.test", email_sent: true }), "Invitación enviada a gestor@example.test. Cuando la acepte, podrá consultar tu contabilidad.");
  const failed = inviteMessage({ gestor_email: "gestor@example.test", email_sent: false });
  assert.match(failed, /no hemos podido enviar el correo/);
  assert.match(failed, /Queda pendiente/);
  assert.ok(!failed.includes("gestor@example.test"));
});
