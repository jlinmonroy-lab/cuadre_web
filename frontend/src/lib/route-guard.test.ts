// El proxy solo mejora la experiencia (la autorización real está en la API y en la RLS), pero AC-04 exige este comportamiento.
import assert from "node:assert/strict";
import { readdirSync, statSync } from "node:fs";
import { test } from "node:test";

import { routeGuard } from "./route-guard.ts";

const anon = (pathname: string, search = "") => routeGuard({ pathname, search, authenticated: false });
const authed = (pathname: string, search = "") => routeGuard({ pathname, search, authenticated: true });

test("AC-04 · sin sesión, una portada lleva a /login?next=<ruta>", () => {
  assert.deepEqual(anon("/inicio"), { redirect: "/login?next=/inicio" });
  assert.deepEqual(anon("/cartera"), { redirect: "/login?next=/cartera" });
  assert.deepEqual(anon("/admin"), { redirect: "/login?next=/admin" });
  assert.deepEqual(anon("/403"), { redirect: "/login?next=/403" });
});

test("Gastos exige sesión, también sus subrutas y los Route Handlers de lectura", () => {
  assert.deepEqual(anon("/gastos"), { redirect: "/login?next=/gastos" });
  assert.deepEqual(anon("/perfil"), { redirect: "/login?next=/perfil" });
  assert.deepEqual(anon("/gestor"), { redirect: "/login?next=/gestor" });
  assert.deepEqual(anon("/gestor", "?actividad=120"), { redirect: "/login?next=/gestor%3Factividad%3D120" });
  assert.equal(authed("/gestor"), null);
  assert.equal(authed("/perfil"), null);
  assert.deepEqual(anon("/clientes"), { redirect: "/login?next=/clientes" });
  assert.deepEqual(anon("/clientes", "?archivados=1"), { redirect: "/login?next=/clientes%3Farchivados%3D1" });
  assert.equal(authed("/clientes"), null);
  assert.deepEqual(anon("/gastos/3f2a-1"), { redirect: "/login?next=/gastos/3f2a-1" });
  assert.deepEqual(anon("/gastos/3f2a-1/leer"), { redirect: "/login?next=/gastos/3f2a-1/leer" });
  assert.deepEqual(anon("/gastos", "?aviso=descartado"), { redirect: "/login?next=/gastos%3Faviso%3Ddescartado" });
  for (const page of ["/gastos", "/gastos/3f2a-1", "/gastos/3f2a-1/releer"]) assert.equal(authed(page), null, page);
});

test("la ruta anidada y la query se conservan, codificadas", () => {
  assert.deepEqual(anon("/inicio/mes"), { redirect: "/login?next=/inicio/mes" });
  assert.deepEqual(anon("/inicio", "?mes=2026-10&x=1"), { redirect: "/login?next=/inicio%3Fmes%3D2026-10%26x%3D1" });
});

test("las rutas con nombre parecido a una portada no se confunden", () => {
  for (const open of ["/administracion", "/iniciox", "/carteras", "/gestores", "/gastosx", "/mis-gastos", "/auth/confirm", "/", "/login", "/registro", "/recuperar"]) {
    assert.equal(anon(open), null, open);
  }
});

test("el límite de segmento también rige para las pantallas de acceso y /403", () => {
  for (const similar of ["/403x", "/restablecerx", "/auth/confirmar"]) assert.equal(anon(similar), null, similar);
  for (const similar of ["/loginx", "/registros", "/recuperar-cuenta", "/logins/ana"]) {
    assert.equal(authed(similar), null, similar);
  }
});

test("con sesión, las páginas de acceso devuelven a la raíz (que lleva a la portada del rol)", () => {
  for (const page of ["/login", "/registro", "/recuperar"]) assert.deepEqual(authed(page), { redirect: "/" }, page);
});

test("con sesión, las portadas y la raíz se sirven", () => {
  for (const page of ["/", "/inicio", "/cartera", "/admin", "/403", "/inicio/mes", "/restablecer", "/auth/confirm"]) {
    assert.equal(authed(page), null, page);
  }
});

test("/restablecer exige la sesión que crea el enlace de recuperación", () => {
  assert.deepEqual(anon("/restablecer"), { redirect: "/recuperar?aviso=enlace" });
});

test("/auth/confirm es accesible sin sesión: es quien la crea", () => {
  assert.equal(anon("/auth/confirm"), null);
});

// Una pantalla nueva no puede quedar sin clasificar: se enumeran las carpetas reales.
const APP = new URL("../app/", import.meta.url);
const folders = (group: string) =>
  readdirSync(new URL(`${group}/`, APP))
    .filter((name) => statSync(new URL(`${group}/${name}`, APP)).isDirectory())
    .filter((name) => !name.startsWith("_") && !name.startsWith("("));

test("toda ruta de (app) exige sesión", () => {
  const routes = folders("(app)");
  assert.ok(routes.length >= 4, `se esperaban al menos inicio, cartera, admin y 403; hay ${routes.join(", ")}`);
  for (const route of routes) {
    assert.deepEqual(anon(`/${route}`), { redirect: `/login?next=/${route}` }, `/${route} está sin proteger`);
  }
});

test("toda ruta de (auth) está clasificada: solo anónimos o solo con enlace", () => {
  const routes = folders("(auth)");
  assert.ok(routes.length >= 4, `se esperaban login, registro, recuperar y restablecer; hay ${routes.join(", ")}`);
  for (const route of routes) {
    const classified = authed(`/${route}`) !== null || anon(`/${route}`) !== null;
    assert.ok(classified, `/${route} no tiene regla en route-guard.ts`);
  }
});
