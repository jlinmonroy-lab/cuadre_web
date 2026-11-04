// `?aviso=` selecciona un texto de una lista cerrada: nunca se pinta lo que llegue en la URL (suplantación de mensajes, XSS).
import assert from "node:assert/strict";
import { test } from "node:test";

import { noticeFor } from "./notices.ts";

test("avisos conocidos", () => {
  assert.deepEqual(noticeFor("restablecida"), { tone: "success", text: "Contraseña actualizada. Ya puedes iniciar sesión." });
  assert.deepEqual(noticeFor("suspendida"), { tone: "error", text: "Tu cuenta está suspendida y no puedes acceder." });
  assert.deepEqual(noticeFor("perfil"), { tone: "error", text: "No hemos encontrado tu perfil. Inténtalo de nuevo más tarde." });
  assert.deepEqual(noticeFor("enlace"), { tone: "error", text: "El enlace no es válido o ha caducado. Pide uno nuevo." });
  assert.deepEqual(noticeFor("sesion"), { tone: "info", text: "Tu sesión ha caducado. Inicia sesión de nuevo." });
});

test("lo desconocido no produce aviso, ni siquiera con nombres de Object.prototype", () => {
  for (const unknown of [null, undefined, "", "hackeado", "<script>alert(1)</script>", "Restablecida", "constructor", "__proto__", "toString", "hasOwnProperty", ["restablecida"], 3]) {
    assert.equal(noticeFor(unknown as never), null, String(unknown));
  }
});
