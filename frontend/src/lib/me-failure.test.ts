// Qué hacer cuando GET /api/me no devuelve 200. Equivocarse aquí produce bucles de redirección o sesiones perdidas sin motivo.
import assert from "node:assert/strict";
import { test } from "node:test";

import { classifyMeFailure } from "./me-failure.ts";

test("token no válido (401): se cierra la sesión", () => {
  assert.equal(classifyMeFailure({ status: 401, code: "unauthenticated" }), "sign-out");
  assert.equal(classifyMeFailure({ status: 401 }), "sign-out");
});

test("cuenta suspendida y perfil inexistente (403): se cierra la sesión con su aviso", () => {
  assert.equal(classifyMeFailure({ status: 403, code: "account_suspended" }), "suspended");
  assert.equal(classifyMeFailure({ status: 403, code: "profile_missing" }), "profile-missing");
});

test("la API caída o con fallos NUNCA cierra la sesión: se muestra «servicio no disponible»", () => {
  for (const failure of [
    { status: 503, code: "auth_unavailable" },
    { status: 503, code: "database_busy" },
    { status: 500, code: "internal_error" },
    { status: 502 },
    { status: 504 },
    { status: 0 },
    { status: 404 },
    { status: 429 },
    { status: 403, code: "forbidden" },
    { status: 403 },
    {},
  ]) {
    assert.equal(classifyMeFailure(failure), "unavailable", JSON.stringify(failure));
  }
});
