// Genera la clave ES256 de desarrollo que usa la pila local de Supabase (supabase/signing_keys.json).
// La CLI exige que el archivo exista cuando `signing_keys_path` está configurado, así que se inicializa con `[]`.
// El archivo está en .gitignore: nunca se versiona. El CI lo genera antes de `supabase start`.
// Ejecutarlo de nuevo añade una clave más (rotación); para empezar de cero, borra el archivo.
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const keysFile = resolve(root, "supabase", "signing_keys.json");

if (!existsSync(keysFile)) {
  mkdirSync(dirname(keysFile), { recursive: true });
  writeFileSync(keysFile, "[]\n", "utf8");
  console.log("creado supabase/signing_keys.json vacío");
}

const result = spawnSync("npx", ["supabase", "gen", "signing-key", "--algorithm", "ES256", "--append"], {
  cwd: root,
  stdio: "inherit",
  shell: true,
});
process.exit(result.status ?? 1);
