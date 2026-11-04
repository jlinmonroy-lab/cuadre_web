// AC-02 · Cada rol aterriza en su portada, con su navegación; las portadas ajenas llevan a /403.
import { PEOPLE, ROLE_KEYS, SEED_PASSWORD, type RoleKey } from "./helpers/env";
import { expect, test } from "./helpers/fixtures";
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
      await page.goto(target);
      await expect(page).toHaveURL("/403");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("No tienes acceso a esta sección");
      await expect(page.getByRole("link", { name: "Volver a mi portada" })).toHaveAttribute("href", person.home);
    }
    await page.getByRole("link", { name: "Volver a mi portada" }).click();
    await expect(page).toHaveURL(person.home);
  });
}
