# Changelog de los contratos

Versionado semántico. Dentro de una versión mayor solo se añaden campos opcionales (los receptores ignoran los
que no conocen). Un cambio incompatible crea un directorio nuevo (`v2/`) y avisa a cuadre-agents antes de fusionarse.

## [1.1.0] · 2026-11-16

Compatible hacia atrás para quien envía; **cuadre-agents debe aceptar la petición sin `X-User-Token` cuando `mcp_url` es `null`**.

- **C2 · `X-User-Token` condicional** (SPEC-W-004, P-01): obligatorio solo si `mcp_url` no es `null`. Sin herramientas de datos
  no hay token (el emisor llega con SPEC-W-011). Sin cambios en los modelos ni en los esquemas más allá de `x-contract-version`.
- **Ejemplos de C2:** `abstention_no_source.sse`, `abstention_out_of_scope.sse` (`referral: null`), `answer_length.sse`
  (`finish_reason: length`), `error_tool.sse` (`tool_error`) y `chat_no_tools.request.json` (`mcp_url: null`, con historial).

Pendiente para 1.2: contrato de la base de conocimiento del chatbot (RF-019, SPEC-W-015).

## [1.0.0] · 2026-11-03

Primera versión.

- **C1 · Lectura de facturas** (`agents-api/v1`): `POST /v1/extract` → `ExtractedInvoice`.
- **C2 · Chatbot** (`agents-api/v1`): `POST /v1/chat` con respuesta SSE (`token`, `citation`, `tool_call`,
  `abstention`, `usage`, `done`, `error`).
- **C3 · Herramientas MCP de solo lectura** (`mcp/v1`): `buscar_facturas`, `resumen_mes`, `resumen_anio`,
  `borrador_trimestre`, `gastos_por_categoria`.
- Decisión D4: el servicio de agentes recibe un token derivado y acotado (`aud=cuadre-mcp`, `scope=mcp:read`,
  ≤ 5 min), no el JWT de Supabase del usuario.

