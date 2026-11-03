# ADR-0010 · Calidad: pytest, Playwright, ruff, eslint y CI con puertas

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

Las métricas técnicas del charter se miden con tests automáticos: aislamiento de datos (NFR-06), exactitud fiscal
(NFR-03), validadores (NFR-07), cierre y recordatorios (NFR-09) y adaptación a móvil con Lighthouse (NFR-10). Los
umbrales deben ser ejecutables antes de la defensa.

## Decisión

- **Backend:** `pytest` (síncrono, ADR-0015), marcadores `rls`, `contract` y `slow`; `ruff` para lint y formato.
  Los tests de RLS e integración corren contra la **pila local de Supabase**, no contra mocks: la RLS solo vale si se
  prueba en Postgres con el esquema `auth` real.
- **Frontend:** `eslint` y `tsc --noEmit`; `playwright` para extremo a extremo en Chromium, Firefox y WebKit (NFR-10),
  con proyectos de 390 px y 1.440 px; Lighthouse CI para accesibilidad ≥ 90 (propuesto).
- **Guardas de deriva en CI:** (1) los esquemas de `contracts/` frente a los modelos Pydantic, (2) los ejemplos de
  contratos, (3) `openapi.json` frente a las rutas, (4) el cliente TypeScript frente a `openapi.json`.
- **Guardas de reglas del proyecto** como tests: sin `float` (ADR-0006), service key solo en `jobs` y `cli`, ninguna
  importación de SDK de modelos de lenguaje (ADR-0012), ninguna tabla de `public` sin RLS y sin registrar.
- **GitHub Actions:** un workflow con trabajos independientes por parte. El de RLS (`pytest -m rls`) es **requisito
  obligatorio** para fusionar (NFR-06 como puerta de despliegue).
- **Datos de prueba:** solo sintéticos (RES-07). Sin facturas reales en el repositorio, ni siquiera anonimizadas.
- **Specs:** cada una declara su comando de verificación; «hecho» significa que ese comando termina con código 0 y
  `tasks.json` está actualizado.

## Alternativas descartadas

- **Mocks de base de datos para la RLS.** Pasarían siempre y no probarían nada.
- **Cobertura mínima como objetivo.** Se miden criterios de aceptación, no porcentaje de líneas.
- **Cypress.** Playwright cubre los tres navegadores del NFR-10 con una sola herramienta.

## Consecuencias

- El CI necesita Docker en el runner para arrancar Supabase; el trabajo de RLS es el más lento y el más importante.
- Los tests de extremo a extremo comparten datos sembrados: cada spec crea y limpia los suyos.
