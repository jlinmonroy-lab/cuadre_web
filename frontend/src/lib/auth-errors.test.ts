// Los mensajes de acceso no revelan si una cuenta existe (SPEC-W-001 §5.3).
import assert from "node:assert/strict";
import { test } from "node:test";

import { loginMessage, recoveryOutcome, resetOutcome, signupOutcome } from "./auth-errors.ts";

const WRONG = "Correo o contraseña incorrectos.";
const RATE = "Demasiados intentos. Espera unos minutos.";
const OTHER = "No hemos podido iniciar sesión. Inténtalo de nuevo.";

test("entrar: credenciales erróneas, cuenta inexistente y correo sin confirmar dan EL MISMO mensaje", () => {
  for (const code of ["invalid_credentials", "email_not_confirmed", "user_not_found", "invalid_grant", "user_banned"]) {
    assert.equal(loginMessage({ code, status: 400 }), WRONG, code);
  }
  assert.equal(loginMessage({ status: 400, message: "Invalid login credentials" }), WRONG);
});

test("entrar: el límite de intentos se dice como tal", () => {
  assert.equal(loginMessage({ code: "over_request_rate_limit", status: 429 }), RATE);
  assert.equal(loginMessage({ status: 429 }), RATE);
});

test("entrar: cualquier otro fallo es genérico", () => {
  assert.equal(loginMessage({ status: 500 }), OTHER);
  assert.equal(loginMessage({ code: "unexpected_failure", status: 502 }), OTHER);
  assert.equal(loginMessage({}), OTHER);
  assert.equal(loginMessage(null), OTHER);
});

test("registrar: el éxito y «la cuenta ya existía» dicen lo mismo", () => {
  const ok = signupOutcome(null);
  assert.equal(ok.kind, "sent");
  assert.deepEqual(signupOutcome({ code: "user_already_exists", status: 422 }), ok);
  assert.deepEqual(signupOutcome({ code: "email_exists", status: 422 }), ok);
});

test("registrar: contraseña débil, límite, registro cerrado y fallos", () => {
  assert.deepEqual(signupOutcome({ code: "weak_password", status: 422 }), {
    kind: "field",
    field: "password",
    message: "La contraseña es demasiado débil. Prueba con una más larga o menos habitual.",
  });
  for (const code of ["over_email_send_rate_limit", "over_request_rate_limit"]) {
    assert.deepEqual(signupOutcome({ code, status: 429 }), { kind: "error", message: RATE });
  }
  assert.deepEqual(signupOutcome({ code: "signup_disabled", status: 422 }), {
    kind: "error",
    message: "El registro no está disponible ahora mismo.",
  });
  assert.deepEqual(signupOutcome({ code: "unexpected_failure", status: 500 }), {
    kind: "error",
    message: "No hemos podido crear la cuenta. Inténtalo de nuevo.",
  });
});

test("recuperar: siempre el mismo resultado, exista o no la cuenta", () => {
  const sent = recoveryOutcome(null);
  assert.equal(sent.kind, "sent");
  for (const error of [
    { code: "user_not_found", status: 400 },
    { code: "unexpected_failure", status: 500 },
    { status: 422 },
    {},
  ]) {
    assert.deepEqual(recoveryOutcome(error), sent, JSON.stringify(error));
  }
});

test("recuperar: solo el límite de envíos se distingue (no depende de que la cuenta exista)", () => {
  assert.deepEqual(recoveryOutcome({ code: "over_email_send_rate_limit", status: 429 }), { kind: "error", message: RATE });
  assert.deepEqual(recoveryOutcome({ status: 429 }), { kind: "error", message: RATE });
});

test("restablecer: éxito, contraseña repetida o débil, enlace caducado, límite y fallos", () => {
  assert.deepEqual(resetOutcome(null), { kind: "done" });
  assert.deepEqual(resetOutcome({ code: "same_password", status: 422 }), {
    kind: "field",
    field: "password",
    message: "Elige una contraseña distinta de la anterior.",
  });
  assert.deepEqual(resetOutcome({ code: "weak_password", status: 422 }), {
    kind: "field",
    field: "password",
    message: "La contraseña es demasiado débil. Prueba con una más larga o menos habitual.",
  });
  for (const error of [
    { code: "session_not_found", status: 403 },
    { code: "session_expired", status: 401 },
    { code: "refresh_token_not_found", status: 400 },
    { status: 401 },
  ]) {
    assert.deepEqual(resetOutcome(error), { kind: "expired" }, JSON.stringify(error));
  }
  assert.deepEqual(resetOutcome({ code: "over_request_rate_limit", status: 429 }), { kind: "error", message: RATE });
  assert.deepEqual(resetOutcome({ code: "unexpected_failure", status: 500 }), {
    kind: "error",
    message: "No hemos podido cambiar la contraseña. Inténtalo de nuevo.",
  });
});
