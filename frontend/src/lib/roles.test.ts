// Portada, etiqueta y navegación de cada rol (SPEC-W-001 §5.3). Los identificadores de rol van en español (CLAUDE.md).
import assert from "node:assert/strict";
import { test } from "node:test";

import { homeFor, isRole, navFor, portadaOwner, roleLabel, sectionOwner } from "./roles.ts";

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

test("navegación del autónomo: todos sus apartados están activos, también Contabilidad mensual y Reporte mensual", () => {
  const nav = navFor("usuario");
  assert.deepEqual(
    nav.map((item) => item.label),
    ["Inicio", "Clientes", "Facturas", "Gastos", "Contabilidad mensual", "Reporte mensual", "Trimestres", "Mi gestor", "Asistente", "Perfil"],
  );
  const active = nav.filter((item) => item.href !== null);
  assert.deepEqual(active, [
    { label: "Inicio", href: "/inicio" },
    { label: "Clientes", href: "/clientes" },
    { label: "Facturas", href: "/facturas" },
    { label: "Gastos", href: "/gastos" },
    { label: "Contabilidad mensual", href: "/mensual" },
    { label: "Reporte mensual", href: "/reporte" },
    { label: "Trimestres", href: "/trimestres" },
    { label: "Mi gestor", href: "/gestor" },
    { label: "Asistente", href: "/asistente" },
    { label: "Perfil", href: "/perfil" },
  ]);
  for (const future of nav.filter((item) => item.href === null)) assert.deepEqual(future, { label: future.label, href: null });
});

test("«Mi gestor» es del autónomo: el gestor tiene «Cartera» y el administrador ninguno de los dos", () => {
  const labels = (role: "usuario" | "gestor" | "admin") => navFor(role).map((item) => item.label);
  assert.ok(labels("usuario").includes("Mi gestor") && !labels("usuario").includes("Cartera"));
  assert.ok(labels("gestor").includes("Cartera") && !labels("gestor").includes("Mi gestor"));
  assert.ok(!labels("admin").includes("Mi gestor") && !labels("admin").includes("Cartera"));
});

test("«Mi gestor» va tras «Trimestres», «Asistente» tras «Mi gestor» y «Perfil» el último", () => {
  const labels = navFor("usuario").map((item) => item.label);
  assert.equal(labels.indexOf("Mi gestor"), labels.indexOf("Trimestres") + 1);
  assert.equal(labels.indexOf("Asistente"), labels.indexOf("Mi gestor") + 1);
  assert.equal(labels.indexOf("Perfil"), labels.indexOf("Asistente") + 1);
  assert.equal(labels.at(-1), "Perfil");
});

test("«Asistente» es solo del autónomo: ni el gestor ni el administrador lo tienen", () => {
  const labels = (role: "usuario" | "gestor" | "admin") => navFor(role).map((item) => item.label);
  assert.ok(labels("usuario").includes("Asistente"));
  assert.ok(!labels("gestor").includes("Asistente") && !labels("admin").includes("Asistente"));
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

test("los apartados con pantalla propia pertenecen a un solo rol, respetando el límite de segmento", () => {
  assert.equal(sectionOwner("/gastos"), "usuario");
  assert.equal(sectionOwner("/gastos/3f2a"), "usuario");
  assert.equal(sectionOwner("/gastos/3f2a/leer"), "usuario");
  assert.equal(sectionOwner("/perfil"), "usuario");
  assert.equal(sectionOwner("/perfil/logo"), "usuario");
  assert.equal(sectionOwner("/clientes"), "usuario");
  assert.equal(sectionOwner("/clientes/3f2a"), "usuario");
  assert.equal(sectionOwner("/facturas"), "usuario");
  assert.equal(sectionOwner("/facturas/3f2a"), "usuario");
  assert.equal(sectionOwner("/facturas/3f2a/pdf"), "usuario");
  assert.equal(sectionOwner("/trimestres"), "usuario");
  assert.equal(sectionOwner("/trimestres/2025"), "usuario");
  assert.equal(sectionOwner("/gestor"), "usuario");
  assert.equal(sectionOwner("/gestor/algo"), "usuario");
  assert.equal(sectionOwner("/asistente"), "usuario");
  assert.equal(sectionOwner("/asistente/enviar"), "usuario");
  // Las portadas siguen siendo suyas.
  assert.equal(sectionOwner("/inicio"), "usuario");
  assert.equal(sectionOwner("/cartera/ana"), "gestor");
  assert.equal(sectionOwner("/admin"), "admin");
  for (const none of ["/", "/403", "/login", "/gastosx", "/gastos-x", "/x/gastos", "/mis-gastos", "/Gastos", "/perfilx", "/perfil-x", "/Perfil", "/clientesx", "/clientes-x", "/x/clientes", "/Clientes", "/facturasx", "/facturas-x", "/x/facturas", "/Facturas", "/trimestresx", "/trimestres-x", "/x/trimestres", "/Trimestres", "/gestores", "/gestor-x", "/x/gestor", "/Gestor", "/mi-gestor", "/asistentex", "/asistente-x", "/x/asistente", "/Asistente"]) {
    assert.equal(sectionOwner(none), null, none);
  }
});

test("una portada no es un apartado y un apartado no es una portada", () => {
  assert.equal(portadaOwner("/gastos"), null);
  assert.equal(portadaOwner("/gastos/3f2a"), null);
});
