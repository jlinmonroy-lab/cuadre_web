// Portada, etiqueta y navegación de cada rol (SPEC-W-001 §5.3). Los identificadores de rol van en español (CLAUDE.md).
import assert from "node:assert/strict";
import { test } from "node:test";

import { homeFor, isRole, navFor, portadaOwner, roleLabel } from "./roles.ts";

test("isRole reconoce solo los tres roles", () => {
  for (const role of ["usuario", "gestor", "admin"]) assert.equal(isRole(role), true);
  for (const other of ["", "Admin", "root", "superadmin", null, undefined, 3, "constructor", "__proto__"]) {
    assert.equal(isRole(other), false, `no es un rol: ${String(other)}`);
  }
});

test("cada rol tiene su portada", () => {
  assert.equal(homeFor("usuario"), "/inicio");
  assert.equal(homeFor("gestor"), "/cartera");
  assert.equal(homeFor("admin"), "/admin");
});

test("las etiquetas están en español", () => {
  assert.equal(roleLabel("usuario"), "Autónomo");
  assert.equal(roleLabel("gestor"), "Gestor");
  assert.equal(roleLabel("admin"), "Administrador");
});

test("navegación del autónomo: solo Inicio está activo", () => {
  const nav = navFor("usuario");
  assert.deepEqual(
    nav.map((item) => item.label),
    ["Inicio", "Clientes", "Facturas", "Gastos", "Contabilidad mensual", "Trimestres"],
  );
  assert.deepEqual(nav[0], { label: "Inicio", href: "/inicio" });
  for (const future of nav.slice(1)) assert.deepEqual(future, { label: future.label, href: null });
});

test("navegación del gestor: Cartera activa", () => {
  assert.deepEqual(navFor("gestor"), [{ label: "Cartera", href: "/cartera" }]);
});

test("navegación del administrador: Cuentas desactivada", () => {
  assert.deepEqual(navFor("admin"), [{ label: "Cuentas", href: null }]);
});

test("cada portada pertenece a un solo rol, respetando el límite de segmento", () => {
  assert.equal(portadaOwner("/inicio"), "usuario");
  assert.equal(portadaOwner("/inicio/mes"), "usuario");
  assert.equal(portadaOwner("/cartera"), "gestor");
  assert.equal(portadaOwner("/cartera/ana"), "gestor");
  assert.equal(portadaOwner("/admin"), "admin");
  assert.equal(portadaOwner("/admin/cuentas"), "admin");
  for (const none of ["/", "/403", "/login", "/administracion", "/iniciox", "/carteras", "/inicio-x", "/x/inicio"]) {
    assert.equal(portadaOwner(none), null, none);
  }
});
