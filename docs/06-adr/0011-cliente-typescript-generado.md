# ADR-0011 · Cliente TypeScript generado desde `openapi.json`

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

El frontend consume la API FastAPI. Escribir a mano los tipos y las llamadas duplica el contrato y es la fuente más
habitual de desajustes entre pantalla y servidor. El prototipo ya anota el `operation_id` previsto de cada operación.

## Decisión

- **Cada ruta declara `operation_id` explícito** con la forma `verbo_objeto` en snake_case (`get_me`, `create_client`,
  `issue_invoice`, `upload_document`, `confirm_document`, `get_quarter_draft`…). Los nombres del prototipo se reutilizan.
  FastAPI se configura con `generate_unique_id_function` para usar ese valor, y un test falla si una ruta no lo define,
  si se repite o si no cumple el patrón.
- `backend/scripts/export_openapi.py` escribe `backend/openapi.json` (versionado, ordenado y estable) con un modo
  `--check` para el CI.
- `openapi-typescript` genera `frontend/src/api/schema.d.ts` y `openapi-fetch` aporta un cliente mínimo con tipos,
  al que se añade el `Authorization: Bearer` de la sesión. Script: `npm run gen:api`, con `--check` en CI.
- **Los importes son `*_cents: integer`** (ADR-0006): el tipo generado es `number`.
- **Errores** en `application/problem+json` con un campo `code` estable y un `detail` en español; el cliente los
  convierte a un tipo de error común.

## Alternativas descartadas

- **tRPC o GraphQL.** El backend es Python; no comparte tipos con el frontend.
- **Clientes generados con plantillas más pesadas (openapi-generator, orval).** Más código generado que revisar.
- **Tipos a mano.** Es lo que se pretende evitar.

## Consecuencias

- Cambiar una ruta o un modelo exige regenerar y comitear `openapi.json` y `schema.d.ts`; el CI lo vigila.
- Las rutas de streaming (`POST /api/chat`, SSE) y del MCP no se describen bien en OpenAPI: el chat se documenta con
  su esquema de eventos y el cliente lo consume con `fetch` directamente (SPEC-W-004).
