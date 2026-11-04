// Un inicio de sesión por rol y por motor, por la propia interfaz, guardado para las pruebas que solo necesitan «estar dentro».
// Un token de acceso dura 1 h: nadie refresca durante la batería, así que compartir la sesión no choca con la rotación de refresh tokens.
import { mkdirSync } from "node:fs";
import path from "node:path";

import { test as setup, expect } from "@playwright/test";

import { AUTH_DIR, PEOPLE, ROLE_KEYS, SEED_PASSWORD } from "./helpers/env";
import { login } from "./helpers/session";

setup.describe.configure({ mode: "parallel" });

for (const role of ROLE_KEYS) {
  setup(`sesión de ${role}`, async ({ page }, testInfo) => {
    const person = PEOPLE[role];
    await login(page, person.email, SEED_PASSWORD);
    await expect(page).toHaveURL(person.home);

    const engine = testInfo.project.name.replace("setup-", "");
    mkdirSync(AUTH_DIR, { recursive: true });
    await page.context().storageState({ path: path.join(AUTH_DIR, `${engine}-${role}.json`) });
  });
}
