# ADR-0001 · Monorepo con `frontend/`, `backend/`, `supabase/` y `contracts/`

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

cuadre-web tiene una interfaz Next.js, una API FastAPI, el esquema de base de datos de Supabase y unos contratos que
comparte con otro repositorio (cuadre-agents). Trabaja una sola persona con Claude Code y desarrollo guiado por specs.
Una decisión de modelo de datos toca a la vez migración, API, cliente TypeScript y tests; separarlas en repositorios
distintos multiplicaría los cambios coordinados.

## Decisión

Un único repositorio con estas carpetas de primer nivel:

- `frontend/` · aplicación Next.js (con sus tests Playwright en `frontend/e2e/`).
- `backend/` · API FastAPI, lógica fiscal, jobs, servidor MCP y sus tests (`backend/src/cuadre/`).
- `supabase/` · migraciones SQL (única fuente del esquema), `config.toml` y datos de prueba sintéticos.
- `contracts/` · contratos versionados con cuadre-agents (se copian o se consumen como paquete).
- `docs/` · charter, PRD, specs (`04-specs/`) y ADRs (`06-adr/`).

El entorno virtual de Python vive en la raíz (`.venv/`) y lo comparten `backend/` y `contracts/tools/`. No hay gestor
de workspaces: `package.json` de la raíz solo orquesta la CLI de Supabase y scripts; `frontend/` tiene el suyo.

## Alternativas descartadas

- **Un repositorio por parte.** Aísla más, pero obliga a versionar y publicar el esquema y el cliente generado entre
  repos para cada cambio. Demasiada ceremonia para una persona.
- **Workspaces (pnpm/Turborepo/Nx).** Aportan caché de builds que aquí no hace falta; añaden una herramienta más.
- **Contratos en un repositorio propio.** Es lo correcto si hubiera varios consumidores. Hoy hay uno; `contracts/` es
  autocontenido y se puede extraer después sin cambiar su contenido.

## Consecuencias

- El CI se organiza en trabajos por carpeta con filtros de ruta, pero una sola definición de «hecho» por spec.
- Hay que cuidar que `contracts/` no importe nada de `backend/` (solo al revés), para poder extraerlo.
- Cada cambio de contrato exige avisar a cuadre-agents; el `CHANGELOG.md` de `contracts/` es el canal.
