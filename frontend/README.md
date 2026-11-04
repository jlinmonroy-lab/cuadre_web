# frontend

Interfaz de cuadre-web: Next.js 16 (App Router, Cache Components), TypeScript, Tailwind v4 y shadcn/ui. Es parte del monorepo; la
puesta en marcha, las reglas y las decisiones están en el [README de la raíz](../README.md), en [`CLAUDE.md`](../CLAUDE.md) y en
[`SPEC-W-001`](../docs/04-specs/SPEC-W-001-base-auth-roles-rls.md).

```powershell
copy .env.example .env.local        # solo variables públicas (NEXT_PUBLIC_*); ver el comentario del archivo
npm ci
npm run dev                          # http://localhost:3000  (abre SIEMPRE localhost, no 127.0.0.1: las cookies de sesión van por host)
npm run lint ; npm run typecheck ; npm run test:unit
npm run gen:api [-- --check]         # src/api/schema.d.ts desde ../backend/openapi.json (no se edita a mano)
npm run build ; npm run check:bundle # el build no puede contener la clave de servicio
npm run e2e:install                  # una vez: Chromium, Firefox y WebKit
npm run test:e2e                     # Playwright (3 motores × 390 y 1.440 px) contra `next start`; ver playwright.config.ts
npx playwright test roles --project=chromium-1440   # un archivo y un proyecto
```

- Los datos van por la API con el cliente generado (`src/api`); `@supabase/ssr` solo gestiona la sesión (`src/lib/supabase`).
- `src/proxy.ts` es el antiguo «middleware» (Next.js 16): refresca la sesión y redirige, pero **no autoriza**.
- Las fuentes (Domine y Public Sans) se descargan al compilar: `npm run build` necesita red.
