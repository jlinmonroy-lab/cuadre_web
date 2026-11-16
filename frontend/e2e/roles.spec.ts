// AC-02 · Cada rol aterriza en su portada, con su navegación; las portadas ajenas llevan a /403.
import { PEOPLE, ROLE_KEYS, SEED_PASSWORD, type RoleKey } from "./helpers/env";
import { expect, settle, test } from "./helpers/fixtures";
import { expectNavigation, login } from "./helpers/session";

for (const role of ROLE_KEYS) {
  const person = PEOPLE[role];

  test(`portada por rol · ${role} inicia sesión y aterriza en ${person.home}`, async ({ page }) => {
    await login(page, person.email, SEED_PASSWORD);

    await expect(page).toHaveURL(person.home);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(`Hola, ${person.name}`);
    await expect(page.getByRole("main").getByText(person.roleLabel, { exact: true })).toBeVisible();
    await expectNavigation(page, person);
    // Cada portada enseña lo suyo: el gestor ya tiene su cartera (SPEC-W-010); el autónomo ya no tiene nada «Próximamente» (SPEC-W-013) y el administrador sí.
    if (role === "alicia") await expect(page.getByRole("heading", { level: 2, name: "Próximamente" })).toHaveCount(0);
    else await expect(page.getByRole("heading", { level: 2, name: role === "gina" ? "Tu cartera" : "Próximamente" })).toBeVisible();
  });

  test(`portada por rol · «/» lleva a la portada de ${role}`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto("/");
    await expect(page).toHaveURL(person.home);
  });

  const foreign = ROLE_KEYS.filter((other) => other !== role);
  test(`portada por rol · ${role} no ve las portadas de ${foreign.join(" ni ")}`, async ({ pageAs }) => {
    const page = await pageAs(role);
    for (const other of foreign) {
      const target = PEOPLE[other as RoleKey].home;
      await settle(page); // la /403 precarga la portada propia: no se navega con esa petición RSC a medias
      await page.goto(target);
      await expect(page).toHaveURL("/403");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
      await expect(page.getByRole("link", { name: "Volver a mi portada" })).toHaveAttribute("href", person.home);
    }
    await page.getByRole("link", { name: "Volver a mi portada" }).click();
    await expect(page).toHaveURL(person.home);
  });
}

// SPEC-W-006 AC-16 · «Clientes» es solo del autónomo: el gestor y el administrador no lo ven y /clientes los lleva a /403.
test("Clientes · el autónomo lo ve activo en el menú y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  await page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Clientes" }).click();
  await expect(page).toHaveURL("/clientes");
  await expect(page.getByRole("heading", { level: 1, name: "Clientes" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Clientes" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Clientes · ${role} no lo ve en el menú y /clientes lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Clientes", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/clientes");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
  });
}

// SPEC-W-007 AC-22 · «Facturas» es solo del autónomo: el gestor y el administrador no la ven y /facturas (y la descarga de un PDF) los lleva a /403.
test("Facturas · el autónomo la ve activa en el menú y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  await page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Facturas" }).click();
  await expect(page).toHaveURL("/facturas");
  await expect(page.getByRole("heading", { level: 1, name: "Facturas" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Facturas" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Facturas · ${role} no la ve en el menú y /facturas la lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Facturas", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/facturas");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
    // La descarga de un PDF (aunque el id no exista) tampoco es suya: 403 y sin cuerpo de la API.
    const download = await page.request.get("/facturas/00000000-0000-4000-8000-000000000000/pdf");
    expect(download.status()).toBe(403);
    expect(await download.text()).toBe("No tienes acceso a esta factura.");
  });
}

// SPEC-W-008 AC-18 · «Trimestres» es solo del autónomo: el gestor y el administrador no lo ven y /trimestres los lleva a /403.
test("Trimestres · el autónomo lo ve activo en el menú y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  await page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Trimestres" }).click();
  await expect(page).toHaveURL("/trimestres");
  await expect(page.getByRole("heading", { level: 1, name: "Trimestres" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Trimestres" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Trimestres · ${role} no lo ve en el menú y /trimestres lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Trimestres", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/trimestres");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
  });
}

// SPEC-W-009 · La pestaña «Modelo 130» de «Trimestres» es del autónomo igual que el 303: el gestor y el administrador van a /403 también con `?model=130`.
test("Trimestres · el autónomo llega al Modelo 130 desde su pestaña", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto("/trimestres");
  await page.getByRole("navigation", { name: "Modelo", exact: true }).getByRole("link", { name: "Modelo 130", exact: true }).click();
  await expect(page).toHaveURL(/\/trimestres\?model=130&year=\d{4}&quarter=[1-4]$/);
  await expect(page.getByRole("heading", { level: 2, name: /Modelo 130/ })).toBeVisible();
});

for (const role of ["gina", "adan"] as const) {
  test(`Trimestres · ${role} no ve el Modelo 130 y /trimestres?model=130 lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await settle(page);
    await page.goto("/trimestres?model=130&year=2025&quarter=1");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
    await expect(page.getByText("IRPF, pago fraccionado")).toHaveCount(0);
  });
}

// SPEC-W-005 AC-20 · «Perfil» es solo del autónomo: el gestor y el administrador no lo ven y /perfil los lleva a /403.
test("Perfil · el autónomo lo ve activo en el menú y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  await page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Perfil" }).click();
  await expect(page).toHaveURL("/perfil");
  await expect(page.getByRole("heading", { level: 1, name: "Perfil" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Apartados" }).getByRole("link", { name: "Perfil" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Perfil · ${role} no lo ve en el menú y /perfil lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Perfil", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/perfil");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
  });
}

// SPEC-W-012 AC-18 · «Contabilidad mensual» es solo del autónomo: activa en el menú, entre Gastos y Trimestres; el gestor y el administrador no la ven y /mensual
// los lleva a /403.
test("Contabilidad mensual · el autónomo la ve activa en el menú, entre Gastos y Trimestres, y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  const nav = page.getByRole("navigation", { name: "Apartados" });
  await expect(nav.getByRole("link", { name: "Perfil" })).toBeAttached(); // `allInnerTexts()` no espera
  const labels = await nav.getByRole("listitem").allInnerTexts();
  const gastos = labels.findIndex((label) => label.startsWith("Gastos"));
  expect(labels[gastos + 1]).toContain("Contabilidad mensual");
  expect(labels[gastos + 2]).toContain("Reporte mensual");
  expect(labels[gastos + 3]).toBe("Trimestres");
  await expect(nav.getByText("Próximamente")).toHaveCount(0); // ya no queda ningún apartado desactivado
  await nav.getByRole("link", { name: "Contabilidad mensual" }).click();
  await expect(page).toHaveURL("/mensual");
  await expect(page.getByRole("heading", { level: 1, name: "Contabilidad mensual" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Contabilidad mensual" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Contabilidad mensual · ${role} no la ve en el menú y /mensual lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Contabilidad mensual", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/mensual");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
  });
}

// SPEC-W-013 AC-15 · «Reporte mensual» es solo del autónomo: activo en el menú, justo tras «Contabilidad mensual»; el gestor y el administrador no lo ven y
// /reporte los lleva a /403.
test("Reporte mensual · el autónomo lo ve activo en el menú, tras Contabilidad mensual, y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  const nav = page.getByRole("navigation", { name: "Apartados" });
  await expect(nav.getByRole("link", { name: "Perfil" })).toBeAttached(); // `allInnerTexts()` no espera
  const labels = await nav.getByRole("listitem").allInnerTexts();
  const mensual = labels.findIndex((label) => label.startsWith("Contabilidad mensual"));
  expect(labels[mensual + 1]).toContain("Reporte mensual");
  await expect(page.getByRole("heading", { level: 2, name: "Próximamente" })).toHaveCount(0); // la portada del autónomo ya no anuncia nada
  await nav.getByRole("link", { name: "Reporte mensual" }).click();
  await expect(page).toHaveURL("/reporte");
  await expect(page.getByRole("heading", { level: 1, name: "Reporte mensual" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Reporte mensual" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Reporte mensual · ${role} no lo ve en el menú y /reporte lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Reporte mensual", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/reporte");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
  });
}

// SPEC-W-010 AC-21 · «Mi gestor» es solo del autónomo y «Cartera» solo del gestor: el otro rol no ve el apartado ajeno y sus rutas (también la ficha de un
// autónomo) lo llevan a /403.
test("Mi gestor · el autónomo lo ve activo en el menú, entre Trimestres y Perfil, y llega a su pantalla", async ({ pageAs }) => {
  const page = await pageAs("alicia");
  await page.goto(PEOPLE.alicia.home);
  const nav = page.getByRole("navigation", { name: "Apartados" });
  // `allInnerTexts()` no espera: sin esto, a 390 px leía la lista antes de que el menú estuviera pintado y fallaba ~1 de cada 2 veces.
  await expect(nav.getByRole("link", { name: "Perfil" })).toBeAttached();
  const labels = await nav.getByRole("listitem").allInnerTexts();
  const trimestres = labels.findIndex((label) => label.startsWith("Trimestres"));
  expect(labels[trimestres + 1]).toBe("Mi gestor");
  expect(labels[trimestres + 2]).toBe("Perfil");
  await expect(nav.getByText("Cartera", { exact: true })).toHaveCount(0);
  await nav.getByRole("link", { name: "Mi gestor" }).click();
  await expect(page).toHaveURL("/gestor");
  await expect(page.getByRole("heading", { level: 1, name: "Mi gestor" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Mi gestor" })).toHaveAttribute("aria-current", "page");
});

for (const role of ["gina", "adan"] as const) {
  test(`Mi gestor · ${role} no lo ve en el menú y /gestor lo lleva a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Mi gestor", { exact: true })).toHaveCount(0);
    await settle(page);
    await page.goto("/gestor");
    await expect(page).toHaveURL("/403");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
  });
}

for (const role of ["alicia", "adan"] as const) {
  test(`Cartera · ${role} no la ve y /cartera y la ficha de un autónomo lo llevan a /403`, async ({ pageAs }) => {
    const page = await pageAs(role);
    await page.goto(PEOPLE[role].home);
    await expect(page.getByRole("navigation", { name: "Apartados" }).getByText("Cartera", { exact: true })).toHaveCount(0);
    for (const target of ["/cartera", "/cartera/3f2a9c1e-5b7d-4e8a-9c3b-1a2b3c4d5e6f", "/cartera/3f2a9c1e-5b7d-4e8a-9c3b-1a2b3c4d5e6f?tab=facturas"]) {
      await settle(page);
      await page.goto(target);
      await expect(page).toHaveURL("/403");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
    }
  });
}
