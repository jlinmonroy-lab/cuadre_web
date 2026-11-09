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
    await expect(page.getByRole("heading", { level: 2, name: "Próximamente" })).toBeVisible();
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
