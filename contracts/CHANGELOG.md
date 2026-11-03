# Changelog de los contratos

Versionado semántico. Dentro de una versión mayor solo se añaden campos opcionales (los receptores ignoran los
que no conocen). Un cambio incompatible crea un directorio nuevo (`v2/`) y avisa a cuadre-agents antes de fusionarse.

## [1.0.0] · 2026-11-03

Primera versión.

- **C1 · Lectura de facturas** (`agents-api/v1`): `POST /v1/extract` → `ExtractedInvoice`.
- **C2 · Chatbot** (`agents-api/v1`): `POST /v1/chat` con respuesta SSE (`token`, `citation`, `tool_call`,
  `abstention`, `usage`, `done`, `error`).
- **C3 · Herramientas MCP de solo lectura** (`mcp/v1`): `buscar_facturas`, `resumen_mes`, `resumen_anio`,
  `borrador_trimestre`, `gastos_por_categoria`.
- Decisión D4: el servicio de agentes recibe un token derivado y acotado (`aud=cuadre-mcp`, `scope=mcp:read`,
  ≤ 5 min), no el JWT de Supabase del usuario.

Pendiente para 1.1: contrato de la base de conocimiento del chatbot (RF-019, SPEC-W-015).
