# Ejemplos de los contratos

Todo lo de esta carpeta es **sintético** (RES-07): NIF de relleno, empresas inventadas, URLs con
`example.test` o tokens de mentira, trazas `trc_synthetic_*`. Las URLs del BOE son ilustrativas del
formato de una cita, no una verificación jurídica.

Sirven para tres cosas:

1. **Documentar** cada contrato con casos reales de los escenarios del PRD.
2. **Probar los esquemas**: `contracts/tools/validate_examples.py` valida cada archivo contra su esquema JSON
   y contra el modelo Pydantic. Si un ejemplo deja de validar, el contrato ha cambiado.
3. **Alimentar el cliente simulado** de cuadre-web (`FakeAgentsClient`) mientras no exista `AGENTS_BASE_URL`,
   y servir de casos de partida a cuadre-agents.

| Carpeta / archivo | Contrato | Escenario que cubre |
|---|---|---|
| `extract/extract.request.json` | C1 · petición | URL firmada de corta duración |
| `extract/invoice_ok.response.json` | C1 | Lectura completa y consistente |
| `extract/invoice_doubtful_nif.response.json` | C1 | US-001: NIF ilegible → `null` + dudoso |
| `extract/invoice_sum_mismatch.response.json` | C1 | US-005: base 120,00 + cuota 25,20 ≠ total 147,00 |
| `extract/invoice_injection.response.json` | C1 | NFR-07: instrucciones ocultas; fuerza revisión manual |
| `extract/ticket_simplified.response.json` | C1 | Factura simplificada sin NIF del destinatario |
| `extract/unreadable.error.json` | C1 · error | 422 `unreadable` |
| `chat/chat.request.json` | C2 · petición | Historial + contexto de usuario |
| `chat/answer_with_citation.sse` | C2 | Respuesta con cita oficial |
| `chat/abstention_professional.sse` | C2 | US-002: criterio profesional → abstención y derivación al gestor |
| `chat/answer_with_tool.sse` | C2 + C3 | Respuesta apoyada en `buscar_facturas` |
| `chat/error_upstream.sse` | C2 | Error del servicio de lenguaje |
| `chat/chat_no_tools.request.json` | C2 · petición | Sin herramientas de datos (`mcp_url: null`, sin `X-User-Token`) y con historial de varios turnos |
| `chat/abstention_no_source.sse` | C2 | Sin fuente oficial: abstención y derivación a un asesor |
| `chat/abstention_out_of_scope.sse` | C2 | Fuera de alcance: abstención sin derivación (`referral: null`) |
| `chat/answer_length.sse` | C2 | Respuesta cortada por longitud (`finish_reason: length`) |
| `chat/error_tool.sse` | C2 + C3 | Falla una herramienta: `tool_call` fallido y `error` con `tool_error` |
| `mcp/*.example.json` | C3 | Una entrada y salida por herramienta (`{tool, input, output}`) |

Los datos de `mcp/` son dos ejercicios sintéticos independientes: `buscar_facturas`, `resumen_mes` y
`resumen_anio` comparten un mismo año de actividad, y `borrador_trimestre` y `gastos_por_categoria` comparten
un primer trimestre más pequeño. `validate_examples.py` comprueba que cada salida cuadra consigo misma al
céntimo (totales, ingresos por ámbito, casillas del 303 y del 130). No son datos de ningún usuario real.
