// El texto del agente y el de la persona se pintan SIEMPRE como texto plano (SPEC-W-004 D-10, AC-18): ni HTML sin escapar, ni evaluación de código, ni un
// enlace que no pase por `linkHref`. Es una vigilancia de código fuente: si alguien añade `dangerouslySetInnerHTML` al asistente, esta prueba falla.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const ROOT = new URL("../", import.meta.url);
const assistantFiles = readdirSync(new URL("components/assistant/", ROOT)).map((name) => `components/assistant/${name}`);
const files = [...assistantFiles, "lib/chat.ts", "lib/chat-handler.ts", "lib/chat-api.ts", "lib/chat-actions.ts", "app/(app)/asistente/page.tsx", "app/(app)/asistente/enviar/route.ts"];
const FORBIDDEN = [/dangerouslySetInnerHTML/, /\binnerHTML\b/, /\bouterHTML\b/, /insertAdjacentHTML/, /\beval\s*\(/, /new\s+Function\s*\(/, /document\.write/, /\bMarkdown\b/i, /marked|markdown-it|remark|rehype/];

for (const file of files) {
  test(`${file} no interpreta HTML, Markdown ni código`, () => {
    const source = readFileSync(new URL(file, ROOT), "utf-8");
    for (const pattern of FORBIDDEN) assert.ok(!pattern.test(source.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")), `${file}: ${pattern}`);
  });
}

test("cada enlace de una cita pasa por linkHref y lleva rel=noopener noreferrer", () => {
  const view = readFileSync(new URL("components/assistant/message-view.tsx", ROOT), "utf-8");
  assert.match(view, /linkHref\(citation\.url\)/);
  assert.match(view, /rel="noopener noreferrer"/);
  assert.equal((view.match(/<a /g) ?? []).length, 1);
});

test("el navegador no ve la clave del agente ni el token: ningún archivo del asistente los nombra", () => {
  for (const file of assistantFiles) {
    const source = readFileSync(new URL(file, ROOT), "utf-8");
    // La credencial de servicio no se escribe entera ni aquí: otra regla del repositorio prohíbe nombrarla en cualquier archivo del frontend.
    const forbidden = new RegExp(["AGENTS_API_KEY", ["SERVICE", "ROLE"].join("_"), "access_token", "Bearer"].join("|"));
    assert.ok(!forbidden.test(source), file);
  }
});
