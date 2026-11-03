# ADR-0013 · Servidor MCP de solo lectura con token derivado y acotado

- **Estado:** Aceptado
- **Fecha:** 2026-11-03
- **Decisión de producto asociada:** D4 (sesión de arranque).

## Contexto

El chatbot responde sobre los datos del usuario con herramientas de solo lectura (RF-016, RES-06). El enunciado pide que
use «un token de acceso del usuario» para que la RLS se aplique también al agente, y nunca la service key. El JWT de
sesión de Supabase vale una hora y sirve para toda la API (también para operaciones de escritura), así que entregarlo
a otro servicio amplía mucho lo que ese servicio puede hacer en nombre del usuario.

## Decisión

- **El servidor MCP está en el propio backend FastAPI** (`/mcp`, transporte HTTP en streaming). Reutiliza la capa de datos
  y los servicios de cálculo (borradores, resúmenes), de modo que el chatbot y la pantalla muestran las mismas cifras.
- **Token derivado.** Por cada petición de chat, el backend emite un JWT propio, firmado con `MCP_TOKEN_SECRET`, con
  `iss=cuadre-web`, `aud=cuadre-mcp`, `scope=mcp:read`, `sub=<usuario>`, `conv=<conversation_id>` y `exp` ≤ 5 minutos. Lo
  recibe el agente en `X-User-Token` y lo reenvía al MCP como `Authorization: Bearer`.
- **El MCP solo acepta ese token.** Rechaza el JWT de Supabase, tokens caducados y los de otra audiencia o alcance.
- **RLS aplicada.** Con el token válido, el MCP abre una transacción `READ ONLY`, hace `SET LOCAL ROLE authenticated` y
  fija las claims con el `sub`, como en ADR-0003. El agente no ve nada que el usuario no vea.
- **Solo el rol `usuario` recibe herramientas de datos.** Para el gestor y el administrador, `mcp_url` va a `null`.
- **Herramientas con cifras agregadas** y sin IBAN, domicilios ni NIF de terceros (`contracts/mcp/v1/README.md`).
- **Auditoría:** cada llamada registra herramienta, parámetros y duración, sin el contenido devuelto.

## Alternativas descartadas

- **Reenviar el JWT de Supabase del usuario.** Más sencillo, pero si el servicio de agentes se compromete o filtra
  trazas, el atacante tiene una hora de acceso completo, con escritura, a la cuenta del usuario.
- **Token estático por servicio con parámetro `user_id`.** Rompería la garantía de que la RLS es la barrera: un fallo del
  agente permitiría pedir datos de otro usuario.
- **MCP como servicio separado.** Duplicaría la lógica de cálculo y las credenciales de base de datos.

## Consecuencias

- Hay que custodiar `MCP_TOKEN_SECRET` (rotación y entorno seguro). Es una clave de la web, no se comparte con agentes.
- Un chat muy largo puede superar los 5 minutos: el backend emite un token nuevo en cada petición, y cada petición es un
  turno, así que no hace falta renovación.
- El contrato C2 (`X-User-Token`) y C3 documentan este comportamiento; cuadre-agents no necesita saber cómo se firma.
