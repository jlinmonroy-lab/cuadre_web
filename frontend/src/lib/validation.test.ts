// Validación de formularios de acceso. Es ayuda de experiencia: Supabase Auth vuelve a validar (longitud mínima, p. ej.).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PASSWORD_MAX_BYTES,
  PASSWORD_MIN,
  validateLogin,
  validateRecovery,
  validateReset,
  validateSignup,
} from "./validation.ts";

const good = { name: "Alicia Prueba", email: "alicia@example.test", password: "contraseña-larga-1" };

test("el mínimo de contraseña es el de la spec (T-16)", () => {
  assert.equal(PASSWORD_MIN, 10);
});

test("registro válido: normaliza el correo y recorta el nombre", () => {
  const result = validateSignup({ name: "  Alicia   Prueba ", email: "  Alicia@Example.TEST ", password: good.password });
  assert.deepEqual(result.errors, {});
  assert.deepEqual(result.values, { name: "Alicia Prueba", email: "alicia@example.test" });
});

test("los valores devueltos al formulario NUNCA incluyen la contraseña", () => {
  for (const result of [
    validateSignup({ ...good, password: "corta" }),
    validateLogin({ email: good.email, password: "x" }),
    validateReset({ password: "corta", confirm: "otra" }),
  ]) {
    assert.ok(!("password" in result.values) && !("confirm" in result.values), JSON.stringify(result.values));
  }
});

test("el correo es obligatorio y debe parecer un correo", () => {
  assert.equal(validateSignup({ ...good, email: "" }).errors.email, "Escribe tu correo.");
  assert.equal(validateSignup({ ...good, email: "   " }).errors.email, "Escribe tu correo.");
  for (const bad of ["alicia", "alicia@", "@example.test", "a@b", "a b@example.test", "a@@example.test", "a@example..", "a@example.t"]) {
    assert.equal(validateSignup({ ...good, email: bad }).errors.email, "Escribe un correo válido, por ejemplo nombre@dominio.es.", bad);
  }
  assert.equal(validateSignup({ ...good, email: `${"a".repeat(250)}@example.test` }).errors.email !== undefined, true);
});

test("la contraseña del registro exige 10 caracteres", () => {
  assert.equal(validateSignup({ ...good, password: "123456789" }).errors.password, "La contraseña debe tener al menos 10 caracteres.");
  assert.equal(validateSignup({ ...good, password: "1234567890" }).errors.password, undefined);
  assert.equal(validateSignup({ ...good, password: "" }).errors.password, "Escribe una contraseña.");
});

test("la contraseña no se recorta: los espacios cuentan", () => {
  assert.equal(validateSignup({ ...good, password: "         1" }).errors.password, undefined);
  assert.equal(validateSignup({ ...good, password: "          " }).errors.password, undefined);
});

test("la contraseña admite como máximo 72 bytes (límite de bcrypt), no 72 caracteres", () => {
  assert.equal(PASSWORD_MAX_BYTES, 72);
  assert.equal(validateSignup({ ...good, password: "a".repeat(72) }).errors.password, undefined);
  assert.equal(
    validateSignup({ ...good, password: "a".repeat(73) }).errors.password,
    "La contraseña es demasiado larga: el máximo es de 72 bytes (los acentos y símbolos cuentan más de uno).",
  );
  // 37 × «ñ» = 37 caracteres pero 74 bytes.
  assert.notEqual(validateSignup({ ...good, password: "ñ".repeat(37) }).errors.password, undefined);
  assert.equal(validateSignup({ ...good, password: "ñ".repeat(36) }).errors.password, undefined);
});

test("el nombre es obligatorio y tiene hasta 80 caracteres", () => {
  assert.equal(validateSignup({ ...good, name: "" }).errors.name, "Escribe tu nombre.");
  assert.equal(validateSignup({ ...good, name: "   " }).errors.name, "Escribe tu nombre.");
  assert.equal(validateSignup({ ...good, name: "a".repeat(80) }).errors.name, undefined);
  assert.equal(validateSignup({ ...good, name: "a".repeat(81) }).errors.name, "El nombre no puede superar los 80 caracteres.");
  assert.equal(validateSignup({ ...good, name: "Ana\u0007" }).errors.name, "El nombre contiene caracteres no válidos.");
});

test("inicio de sesión: no impone el mínimo de la contraseña, solo que exista", () => {
  assert.deepEqual(validateLogin({ email: good.email, password: "x" }).errors, {});
  assert.equal(validateLogin({ email: good.email, password: "" }).errors.password, "Escribe tu contraseña.");
  assert.equal(validateLogin({ email: "", password: "x" }).errors.email, "Escribe tu correo.");
});

test("recuperación: solo el correo", () => {
  assert.deepEqual(validateRecovery({ email: " Ana@Example.test " }), { errors: {}, values: { email: "ana@example.test" } });
  assert.equal(validateRecovery({ email: "nope" }).errors.email, "Escribe un correo válido, por ejemplo nombre@dominio.es.");
});

test("restablecer: nueva contraseña con el mínimo y confirmación idéntica", () => {
  assert.deepEqual(validateReset({ password: "una-contraseña-nueva", confirm: "una-contraseña-nueva" }).errors, {});
  assert.equal(validateReset({ password: "corta", confirm: "corta" }).errors.password, "La contraseña debe tener al menos 10 caracteres.");
  assert.equal(validateReset({ password: "una-contraseña-nueva", confirm: "otra-distinta-1" }).errors.confirm, "Las contraseñas no coinciden.");
  assert.equal(validateReset({ password: "una-contraseña-nueva", confirm: "" }).errors.confirm, "Las contraseñas no coinciden.");
});

test("valores que no son texto se tratan como vacíos (FormData puede traer File o null)", () => {
  const result = validateSignup({ name: null, email: undefined, password: new File([], "x") } as never);
  assert.equal(result.errors.name, "Escribe tu nombre.");
  assert.equal(result.errors.email, "Escribe tu correo.");
  assert.equal(result.errors.password, "Escribe una contraseña.");
});
