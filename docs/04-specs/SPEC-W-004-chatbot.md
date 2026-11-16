---
tipo: spec
id: SPEC-W-004
titulo: Chatbot en la web (proxy SSE, historial, valoración y aviso de no asesoramiento)
estado: en-progreso
prioridad: must
riesgo: alto
historias: [US-002]
requisitos: [RF-016, RF-017, RF-018]
nfr: [NFR-01, NFR-05, NFR-06, NFR-08, NFR-11]
restricciones: [RES-05, RES-06, RES-07]
adr: [0002, 0003, 0005, 0011, 0012, 0013, 0015, 0016]
depende_de: [SPEC-W-001]
bloquea: [SPEC-W-011, SPEC-W-015]
fecha: 2026-11-16
---

# SPEC-W-004 · Chatbot en la web

> La persona pregunta en lenguaje natural sobre la aplicación o sobre fiscalidad general y recibe una respuesta **con fuente oficial citada** o un **aviso claro de que no puede responder** y a quién acudir. La web recibe el flujo del agente (`cuadre-agents`, contrato C2), lo valida, lo guarda y lo reenvía al navegador sin que este vea nunca el JWT. El chat **orienta, no asesora**, y lo dice en la interfaz. Las herramientas de datos del usuario llegan con SPEC-W-011; aquí el agente trabaja sin ellas.

## 1. Contexto

**Situación de partida.** `cuadre.agents` tiene `AgentsClient` con solo `extract_invoice` (SPEC-W-002); su docstring deja `stream_chat` para esta spec. Los contratos C2 (`POST /v1/chat`, SSE) y sus ejemplos ya existen en `contracts/` (versión 1.0.0). No hay tablas `chat_*`, ni ruta de chat, ni streaming en el cliente de agentes, ni emisor del token MCP, ni pantalla (el prototipo `docs/cuadre-interfaz.html` no tiene apartado de chat: solo aporta tokens y patrones).

**Qué falta.** US-002 pide respuesta con fuente oficial o aviso de que no puede responder y, ante un caso personal que exige criterio profesional, no dar recomendación ni cifra y derivar al gestor (si lo hay) o a un asesor (RF-016, RF-017). RF-018 pide valorar cada respuesta. RES-05 exige que la interfaz diga que orienta pero no asesora. NFR-08 exige que el 100 % de las respuestas fiscales citen fuente, con «aserción por código».

**Decisiones de la persona (2026-11-16).**
1. **Solo el rol `usuario`** usa el chat en la v1.
2. **Route Handler de Next → FastAPI** para el stream: el navegador nunca ve el JWT.
3. **Varias conversaciones, con borrado.**
4. **Valoración local, con lista cerrada de motivos**, sin cambio de contrato por ella.

**Dependencias externas.** DEP-03 (corpus del chatbot) y la `SPEC-A-*` del agente del chatbot son de `cuadre-agents`. Con `FakeAgentsClient` y los ejemplos de `contracts/examples/chat/` se construye y se prueba todo aquí. La evaluación NFR-05 (40 preguntas, 10 trampa, juez de otro modelo) es del repositorio de agentes. CONF-003 (límite legal del chatbot) sigue **abierto**: el texto del aviso es provisional. Qué preguntas hacen de verdad los autónomos y cómo se valora el chat **no está validado con usuarios** (Charter §8): la pantalla es un mínimo defendible y provisional.

**Decisiones vigentes** (no se reabren): ADR-0012 (la web no llama a modelos; toda respuesta del agente es dato no confiable); ADR-0013 (token MCP derivado; en esta spec `mcp_url` va a `null`); ADR-0016 (Vercel Functions: sin proceso persistente ni trabajo posterior a la respuesta); ADR-0003 (SQL explícito) y ADR-0015 (psycopg síncrono: el SSE usa `run_in_threadpool`); ADR-0005 (rol desde `profiles.role`); RES-05, RES-06, RES-07.

**Decisiones que propone esta spec** (la persona las confirma o corrige antes del hito 2; D-01 a D-04 ya están decididas):

| ID | Decisión | Alternativa y coste |
|---|---|---|
| D-01 | **Solo `usuario`**. Gestor y administrador reciben `403 forbidden` en todas las rutas y no ven el apartado. El chat del gestor sería otra spec | Chat del gestor sin herramientas de datos: añade el rol a rutas, tablas y pruebas de RLS |
| D-02 | **Route Handler de Next** (`app/(app)/asistente/enviar/route.ts`) con comprobación de mismo origen y `sessionToken()` en el servidor, que reenvía el stream a FastAPI `POST /api/chat` | `fetch` directo del navegador a la API: expone el JWT al JS del cliente y obliga a CORS y `expose_headers` |
| D-03 | **Varias conversaciones**: la conversación nace con el primer mensaje (no hay ruta de «crear»), se lista por última actividad, se abre y se borra (con sus mensajes y valoraciones). Sin retención automática en la v1 | Un hilo único: crece sin límite y el contexto enviado se recorta |
| D-04 | **Valoración local**: pulgar arriba o abajo por mensaje del asistente; abajo exige un motivo de la lista cerrada (`incorrect`, `no_source`, `not_helpful`, `other`); editable; una por mensaje. Sin texto libre | Texto libre: dato personal posible en logs y exportación. Enviarla al agente: cambia el contrato (1.1) |
| D-05 | **Contrato**: C2 declara `X-User-Token` obligatorio, pero el emisor llega con W-011. W-004 envía `mcp_url: null` y **no** emite token. **Confirmado el 2026-11-16 (P-01): se relaja el contrato a 1.1.0** (`X-User-Token` obligatorio solo si `mcp_url` no es `null`; `CHANGELOG.md`, `VERSION`, `export_schemas.py`, `validate_examples.py`) y coordinarlo con `cuadre-agents`. P-01 resuelta | Emitir ya un token mínimo (adelanta trabajo de W-011) o enviar uno ficticio (rompe ADR-0013) |
| D-06 | **`message_id` y eventos propios hacia el navegador**: la web asigna el UUID del mensaje del asistente y lo añade al `done` que reenvía, como dice el contrato; además emite un evento inicial `start` con `conversation_id`, `user_message_id` y `message_id`. Ninguno de los dos entra en C2 | Que el navegador pregunte los ids después: dos llamadas y estados intermedios |
| D-07 | **Persistencia sin trabajo posterior**: el mensaje del usuario se guarda **antes** de llamar al agente (con el tope por hora); el del asistente se inserta **una vez, al final**, desde el propio generador, en un `finally` (estados `complete`, `abstained`, `error` e `interrupted` si el navegador cortó, con lo recibido hasta entonces). Transacciones cortas y `require_role_detached`: ninguna conexión se retiene durante el stream. Sin `BackgroundTasks` | Guardar al vuelo en cada `token`: muchas escrituras y mensajes que cambian |
| D-08 | **«Sin fuente» por código (NFR-08)**: una respuesta que termina en `stop` sin ninguna `citation`, sin `tool_call` terminada y sin `abstention` se guarda con `has_source = false` y se enseña con una nota visible. La web no clasifica si la pregunta era fiscal; mide y avisa | Clasificar en la web: lógica de lenguaje fuera de `cuadre-agents` |
| D-09 | **Aviso de no asesoramiento (RES-05)**: permanente bajo el campo de entrada y repetido en cada abstención. Texto provisional: «Cuadre orienta, no asesora. Para decidir sobre tu caso, consulta a tu gestor o a un asesor.» P-02 resuelta (texto provisional) | Solo en la primera pantalla: se pierde en cuanto hay hilo |
| D-10 | **Contenido no confiable**: el texto del agente se pinta como texto plano (sin HTML ni Markdown con enlaces); una cita solo es enlace si su URL es `https`, con `rel="noopener noreferrer"`; los frames desconocidos o fuera de orden se descartan; se acotan el tamaño de línea y de frame | Renderizar Markdown: superficie de inyección |
| D-11 | **Derivación coherente**: si el agente deriva a `gestor` pero la persona no tiene un gestor vinculado (SPEC-W-010), la web muestra «asesor»; la web decide `has_gestor`, no el agente | Fiarse del agente: puede mandar a alguien que no existe |
| D-12 | **Límites provisionales** (P-03 resuelta: se aplican tal cual): mensaje ≤ 2.000 caracteres (el contrato admite 8.000); contexto enviado = últimos 50 mensajes; **20 mensajes de usuario por hora** (`429 chat_rate_limited` con `Retry-After`, contado en base de datos con un bloqueo asesor por persona para que dos peticiones simultáneas no se lo salten); plazo al primer frame 15 s y total 90 s | Sin tope: coste sin control (NFR-04) |
| D-13 | **Logs**: `request_id`, `user_id`, `conversation_id`, ruta, código, duración, `finish_reason` y los tokens de `usage`; **nunca** el texto del usuario ni el del agente, ni la URL firmada, ni `AGENTS_API_KEY` | |
| D-14 | **Pantalla `/asistente`**: lista de conversaciones y hilo; en 390 px la lista va plegada; `aria-live="polite"` en la respuesta que se escribe; botón «Detener» mientras llega. Menú «Asistente» solo para el rol `usuario`. Nombre y textos **provisionales** | |
| D-15 | **Sin RLS nueva fuera de `chat_*`** y sin acceso para gestor ni administrador: no se añade la política `private.gestor_has_access` | |

*Visto bueno (2026-11-16): la persona confirma P-01, P-02 y P-03, es decir, **D-05** (contrato 1.1.0), **D-09** (texto del aviso, provisional) y **D-12** (límites, provisionales). **D-06 a D-08, D-10, D-11 y D-13 a D-15 siguen pendientes de visto bueno** y se confirman o corrigen antes del hito 2.*

**Preguntas abiertas**

| ID | Pregunta | Estado |
|---|---|---|
| P-01 | ¿Se relaja C2 a 1.1.0 (`X-User-Token` solo con `mcp_url`)? Toca el repositorio hermano | **Resuelta (2026-11-16): sí.** El hito 3 cambia `contracts/` (`python`, `export_schemas.py`, `validate_examples.py`, `CHANGELOG.md`, `VERSION`) y se avisa a `cuadre-agents` en el mismo cambio |
| P-02 | Texto definitivo del aviso y límite legal del chat (CONF-003, «con asesoría legal si hay piloto») | **Resuelta (2026-11-16): se mantiene el texto de D-09 como provisional.** CONF-003 sigue abierto; el texto vive en una constante única para cambiarlo sin tocar la interfaz |
| P-03 | ¿Son razonables 2.000 caracteres, 20 mensajes por hora y los plazos de 15 s y 90 s? Sin datos de uso real | **Resuelta (2026-11-16): se aplican tal cual**, como constantes en un solo módulo (`cuadre.chat.limits`) para ajustarlos con datos reales |

## 2. Objetivo

Que una persona con la cuenta de `usuario` pueda hacer preguntas, ver cómo se escribe la respuesta, ver sus fuentes o su abstención, valorar cada respuesta, volver a sus conversaciones y borrarlas, con la garantía de que (1) nada del agente se trata como cierto ni como código, (2) ninguna respuesta fiscal se presenta como asesoramiento, (3) solo ella ve su historial y (4) un corte del navegador, del agente o de la red no deja el historial a medias ni expone datos.

## 3. Alcance explícito

### 3.1 Backend (FastAPI)
- `AgentsClient.stream_chat(...)`: `Protocol`, `FakeAgentsClient` (sirve `contracts/examples/chat/*.sse`), `HttpAgentsClient` con streaming de verdad.
- Paquete `cuadre.chat` (`rules`, `models`, `repository`, `service`, `errors`): reglas puras, persistencia, límite por hora y orquestación del stream.
- Rutas bajo `/api/chat` (solo `usuario`, todas con `operation_id`): `stream_chat` (`POST /api/chat`, SSE), `list_chat_conversations`, `get_chat_conversation`, `delete_chat_conversation` y `rate_chat_message`.
- Errores `application/problem+json` con `code` estable: `chat_rate_limited` (429), `conversation_not_found` (404), `message_too_long` (422), `agent_unavailable` (503, solo antes del primer byte).

### 3.2 Base de datos
- Migraciones propias: `chat_conversations`, `chat_messages`, `chat_feedback`, funciones `app.*` de escritura, RLS forzada, entradas en `rls_matrix.yaml`.

### 3.3 Frontend (Next.js)
- `/asistente`, Route Handler de envío, lector del stream (`fetch` + `ReadableStream`), aviso permanente, nota de «sin fuente», valoración, estados vacío, cargando, error, abstención e interrumpido; ítem de menú, portada y `lib/roles.ts`.

### 3.4 Pruebas
- Reglas y API (`backend/tests/chat/`), cliente de agentes con servidor SSE real, RLS, unitarias de `lib/chat.ts` y E2E `chat.spec.ts` en tres motores y dos anchos.

## 4. Alcance excluido
- **Herramientas de datos del usuario y emisor del token MCP**: SPEC-W-011. Aquí `mcp_url` es `null` y nunca se envía token.
- **Base de conocimiento y su administración**: SPEC-W-015 y `cuadre-agents`. **Evaluación NFR-05** (40 preguntas y 10 trampa): `cuadre-agents`.
- **Chat del gestor o del administrador.**
- Enviar la valoración al agente; texto libre en la valoración; retención automática; búsqueda dentro del historial; compartir conversaciones; voz, imágenes o adjuntos.
- Verificar el streaming en un despliegue real de Vercel (no hay despliegue ni `vercel.json`): queda como pendiente documentado.
- Validar con usuarios el contenido y los textos (Charter §8).

## 5. Contrato de interfaces

### 5.1 Reglas (`cuadre.chat.rules`, puras, sin base de datos, sin red y sin reloj)
- **Contexto**: los últimos 50 mensajes de la conversación más el nuevo, en orden; cada `content` ≤ 8.000 (el del usuario ≤ 2.000, D-12).
- **Título** de la conversación: los primeros 60 caracteres del primer mensaje, sin saltos de línea, recortado por palabra.
- **`has_source`** (D-08): `finish_reason = stop` y existe alguna `citation` o alguna `tool_call` con `status = finished`; las abstenciones y los errores no se evalúan (`null`).
- **Derivación** (D-11): `gestor` solo si hay vínculo activo; si no, `asesor`.
- **Validación de frames**: un frame `token` con texto vacío se ignora; el orden `token`* → `citation`* → `abstention`? → `usage` → `done`/`error` se tolera con frames intercalados pero un frame después de `done` o `error` se descarta; cualquier `event` fuera de los siete conocidos se descarta; tamaño máximo de línea y de frame; `cost_eur` se conserva como cadena (nunca `float`).
- **Cita enlazable**: URL con esquema `https` y host; el resto se enseña como texto sin enlace.
- **Estado final del mensaje del asistente**: `complete` (`stop` o `length`), `abstained` (`abstained`), `error` (`error` o un frame `error`), `interrupted` (el navegador cortó o el generador se canceló).

### 5.2 Base de datos
Tres tablas en `public`, cada una en su migración: RLS activada y forzada, `revoke all` a `public`, `anon`, `authenticated` y `service_role` salvo lo que se diga, políticas `usuario` (`owner_id = auth.uid()`), **ninguna para gestor ni administrador**, y registro en `rls_matrix.yaml`.

- `chat_conversations(id uuid pk, owner_id, title text ≤ 80, created_at, last_message_at)`. Solo `SELECT` directo; las altas y los borrados, por funciones.
- `chat_messages(id uuid pk, conversation_id → chat_conversations on delete cascade, owner_id, role in ('user','assistant'), content text, status in ('complete','abstained','error','interrupted'), finish_reason, trace_id, has_source boolean null, citations jsonb, abstention jsonb null, created_at)`. **Inmutable**: se inserta una sola vez (el del usuario antes de llamar al agente, el del asistente al final) y no se actualiza ni se borra salvo por la cascada del borrado de la conversación. Un trigger lo hace cumplir.
- `chat_feedback(message_id pk → chat_messages on delete cascade, owner_id, rating in ('up','down'), reason null | in ('incorrect','no_source','not_helpful','other'), updated_at)`; `reason` obligatorio con `down` y nulo con `up` (CHECK). Solo del mensaje del asistente de la propia persona.
- Funciones (`SECURITY DEFINER`, `set search_path = ''`, errores con `errcode 'P0001'` y códigos estables, dueño siempre `auth.uid()`): `app.append_chat_user_message(conversation_id | null, content, now)` (crea la conversación si hace falta, comprueba el tope por hora tras `pg_advisory_xact_lock` por persona y devuelve ids), `app.append_chat_assistant_message(...)`, `app.delete_chat_conversation(id)` y `app.rate_chat_message(message_id, rating, reason)`.
- Sin `float` ni `numeric` de importes en `chat_*` (RES-02): el `cost_eur` de `usage` no se guarda; solo se registran los tokens en el log.

### 5.3 API HTTP (todas `Cache-Control: private, no-store`)

| `operation_id` | Ruta | Respuesta |
|---|---|---|
| `stream_chat` | `POST /api/chat` con `{conversation_id: uuid \| null, content}` | `200 text/event-stream` |
| `list_chat_conversations` | `GET /api/chat/conversations` | `200` lista `{id, title, last_message_at}` por última actividad, máx. 200 |
| `get_chat_conversation` | `GET /api/chat/conversations/{conversation_id}` | `200` conversación con mensajes, citas, abstención y valoración |
| `delete_chat_conversation` | `DELETE /api/chat/conversations/{conversation_id}` | `204` |
| `rate_chat_message` | `PUT /api/chat/messages/{message_id}/feedback` con `{rating, reason}` | `200` |

Eventos que ve el navegador en `stream_chat`: `start` (`conversation_id`, `user_message_id`, `message_id`), los de C2 validados (`token`, `citation`, `tool_call`, `abstention`, `usage`) y `done` (`finish_reason`, `trace_id`, `message_id`, `has_source`, `status`) o `error` (`code`, `message` en español, sin trazas). Cualquier fallo **antes** de enviar `start` es un `problem+json` normal; después, un evento `error` dentro del stream. `ADR-0011`: el stream no se describe bien en OpenAPI; el cliente usa `fetch` directo y los tipos de los eventos viven en `frontend/src/lib/chat.ts`.

Errores: `401`, `403 forbidden` (gestor o administrador), `403 account_suspended`, `404 conversation_not_found` (también la de otra persona), `422 message_too_long` y de validación, `429 chat_rate_limited`, `503 agent_unavailable`.

### 5.4 Backend
- `AgentsClient.stream_chat(request: ChatRequest, *, request_id) -> AsyncIterator[ChatStreamFrame]`. `HttpAgentsClient`: `Authorization: Bearer AGENTS_API_KEY`, `X-Cuadre-Contract-Version: 1`, `X-Request-Id`, sin seguir redirecciones ni usar proxies del entorno; lee el cuerpo por líneas **sin bufferizarlo**, con plazo al primer frame (15 s) y total (90 s), un tope de línea y de frame, y **sin reintento tras el primer byte**; `FakeAgentsClient` elige el ejemplo por un marcador en el último mensaje (`[fixture:<nombre>]`) y, sin marcador, por turnos.
- `cuadre.chat.service`: guarda el mensaje del usuario (con el tope), llama a `stream_chat`, valida y reenvía frame a frame y, en un `finally`, guarda el del asistente. Las operaciones de base de datos usan `run_in_threadpool` y transacciones cortas; la conexión no se retiene mientras llega el stream (`require_role_detached`).
- `user_context`: `role = "usuario"`, `has_gestor` del vínculo activo, `current_date` del reloj inyectado; `locale = "es-ES"`; `mcp_url = null`.

### 5.5 Frontend
- `/asistente` (componente de servidor con la lista y el hilo; un componente de cliente mínimo para el campo, el stream y la valoración), `app/(app)/asistente/enviar/route.ts`, `lib/chat.ts` (puro y probado: lector de frames, acumulado de texto, derivación, citas, estados), `lib/roles.ts` (ítem «Asistente» solo para `usuario`) y la portada.
- Pantalla: lista de conversaciones con «Nueva conversación» y «Borrar» (con confirmación), hilo con mensajes de la persona y del asistente, citas como lista con título, editorial y fecha de vigencia, abstención con la derivación y el aviso, nota de «sin fuente», valoración con motivo, campo con etiqueta y contador, «Detener», aviso permanente de no asesoramiento. Tokens del prototipo en el tema de Tailwind.

## 6. Restricciones técnicas
- **T-01** Este repositorio no llama a ninguna API de modelos ni usa SDKs (ADR-0012); las pruebas de `backend/tests/rules/test_no_llm_sdk.py` siguen verdes. `AGENTS_API_KEY` nunca llega al navegador ni a los logs.
- **T-02** El JWT de Supabase no llega al navegador: el Route Handler lo lee en el servidor y llama a FastAPI con él. Nunca se usa la service key en estas rutas.
- **T-03** Toda respuesta del agente es dato no confiable: se valida contra `cuadre_contracts` en modo estricto, se acota y se pinta como texto (D-10). `injection_suspected` no existe en C2; si llega un frame desconocido, se descarta.
- **T-04** Sin `BackgroundTasks` ni trabajo tras la respuesta (ADR-0016); sin `float` en tokens ni en costes; `cost_eur` es cadena y no se guarda.
- **T-05** Ninguna conexión a la base de datos se retiene mientras llega el stream; psycopg síncrono con `run_in_threadpool` (ADR-0015); pool con `max_size = 10`.
- **T-06** Logs sin contenido (D-13). Los eventos `error` hacia el navegador no llevan trazas ni texto del agente: mensaje fijo en español.
- **T-07** Sin RLS ni acceso para gestor ni administrador sobre `chat_*`; el rol sale de `profiles.role`, nunca de claims; `SECURITY DEFINER` solo con `search_path = ''`.
- **T-08** Datos solo sintéticos (RES-07). El chat se marca como orientativo (RES-05) y no sustituye a un asesor.
- **T-09** Todo el texto de interfaz y los errores, en español; identificadores en inglés; interfaz sin scroll horizontal a 390 y 1.440 px, foco visible y etiquetas en cada campo.
- **T-10** Cambiar un contrato (P-01, hito 3): `contracts/python`, `export_schemas.py`, `CHANGELOG.md` y `VERSION`; nunca a mano `contracts/**/schemas/*.json`.

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Pregunta con fuente (US-002).** *Given* un usuario con el agente simulado; *When* escribe «¿Qué mención lleva una factura a una empresa alemana?»; *Then* ve la respuesta escribirse, la cita (título, editorial, fecha de vigencia y enlace `https`), el aviso de no asesoramiento y la conversación aparece en su lista con ese título.

**AC-02 · Streaming incremental.** *Given* un agente que trocea la respuesta con retardo; *Then* el navegador recibe el primer `token` antes de que el agente envíe `done` (no se bufferiza) y `done` llega con `message_id`, `trace_id` y `has_source`.

**AC-03 · Abstención por criterio profesional (RF-017).** *Given* una pregunta personal con efectos fiscales; *Then* no aparece cifra ni recomendación, se enseña la abstención con la derivación y el aviso, el mensaje queda `abstained` y `has_source` es `null`.

**AC-04 · Derivación coherente (D-11).** *Given* una abstención que deriva a `gestor`; *When* la persona no tiene gestor vinculado; *Then* la interfaz dice «asesor»; con un gestor vinculado dice «tu gestor».

**AC-05 · Respuesta sin fuente (NFR-08).** *Given* una respuesta que termina en `stop` sin citas ni herramientas; *Then* el mensaje se guarda con `has_source = false` y se enseña con la nota de «sin fuente oficial».

**AC-06 · Estado de herramienta.** *Given* frames `tool_call` (`started`, `finished`, `failed`); *Then* se enseña «Consultando…» mientras dure y desaparece al terminar; `failed` no rompe la respuesta. (W-004 no ofrece herramientas; esto prueba el tratamiento del frame.)

**AC-07 · Aviso permanente (RES-05).** *Given* cualquier estado de `/asistente` (vacío, con hilo, cargando, error); *Then* el aviso de no asesoramiento es visible bajo el campo, y se repite en cada abstención.

**AC-08 · Valoración (RF-018).** *Given* una respuesta del asistente; *When* pulsa «útil»; *Then* queda `up`; *When* pulsa «no útil»; *Then* debe elegir un motivo de la lista cerrada antes de guardarse; puede cambiarla, y siempre hay una sola por mensaje. No se puede valorar un mensaje propio ni uno ajeno.

**AC-09 · Historial.** *Given* tres conversaciones; *Then* la lista va por última actividad, el título son los primeros 60 caracteres del primer mensaje, y abrir una enseña sus mensajes, citas, abstenciones y valoraciones tal como se guardaron.

**AC-10 · Borrado.** *Given* dos conversaciones; *When* borra una; *Then* desaparecen sus mensajes y valoraciones, la otra sigue intacta y abrir la borrada da `404 conversation_not_found`.

**AC-11 · Aislamiento (NFR-06).** *Given* dos usuarios; *Then* uno no ve, abre, valora ni borra las conversaciones del otro (404), y por RLS ni el gestor vinculado ni el administrador leen ninguna fila de `chat_*`.

**AC-12 · Roles (D-01).** *Given* un gestor, un administrador o una cuenta suspendida; *Then* toda ruta de chat responde `403` (`forbidden` o `account_suspended`), el menú no muestra «Asistente» y `/asistente` redirige.

**AC-13 · Corte del navegador.** *Given* una respuesta a medias; *When* el navegador cierra la conexión; *Then* el mensaje del asistente se guarda con lo recibido y estado `interrupted`, el del usuario no se pierde, y al reabrir la conversación se ven ambos con la marca de interrumpida.

**AC-14 · Fallos del agente.** *Given* un agente caído o que responde `error`; *Then* antes del primer byte la API responde `503 agent_unavailable` y el mensaje de la persona queda guardado y se ofrece «Reintentar»; durante el stream llega un evento `error` con mensaje fijo y el mensaje queda `error`. Nunca se enseña texto ni traza del agente.

**AC-15 · Plazos.** *Given* un agente que no responde; *Then* a los 15 s sin primer frame la respuesta es `503 agent_unavailable`; un flujo que pasa de 90 s se corta con `timeout`, se guarda `error` y no se reintenta tras el primer byte.

**AC-16 · Tope por hora (D-12).** *Given* una persona con 20 mensajes de usuario en la última hora; *When* envía el 21.º; *Then* responde `429 chat_rate_limited` con `Retry-After`, sin llamar al agente y sin guardar el mensaje; dos envíos simultáneos en el límite no lo superan.

**AC-17 · Validación.** *Given* un mensaje vacío, solo con espacios o de más de 2.000 caracteres; *Then* `422` sin llamar al agente ni guardar nada; un `conversation_id` ajeno o inexistente da `404`.

**AC-18 · Contenido no confiable (D-10).** *Given* una respuesta con HTML, un enlace `javascript:` o `http:`, un frame desconocido, uno posterior a `done` o una línea gigante; *Then* el HTML se ve como texto, solo las citas `https` son enlaces, lo desconocido se descarta y lo desmesurado termina en un error controlado.

**AC-19 · Petición al agente.** *Given* una conversación de 80 mensajes; *Then* el agente recibe los últimos 50, `user_context` con `role = usuario`, `has_gestor` correcto y `current_date` del reloj, `mcp_url = null` y ninguna cabecera `X-User-Token`; `AGENTS_API_KEY` solo va en `Authorization` hacia el agente.

**AC-20 · Frontera (ADR-0012).** *Given* el repositorio; *Then* no hay SDKs ni claves de modelos, el JWT de Supabase y `AGENTS_API_KEY` no aparecen en el HTML, en el JS del cliente ni en las respuestas al navegador, y el Route Handler rechaza orígenes distintos.

**AC-21 · Logs sin contenido (D-13).** *Given* un envío con frases reconocibles; *Then* los registros llevan `request_id`, `user_id`, `conversation_id`, código, duración, `finish_reason` y tokens, y no contienen el texto del usuario ni el de la respuesta.

**AC-22 · Pantalla.** *Given* `/asistente` a 390 y 1.440 px; *Then* no hay scroll horizontal, el campo tiene etiqueta y contador, el foco se ve, la respuesta se anuncia con `aria-live="polite"`, «Detener» corta el stream (queda `interrupted`) y existen los estados vacío, cargando, error, abstención e interrumpido.

**AC-23 · Contrato y cliente de agentes.** *Given* el `FakeAgentsClient`; *Then* sirve todos los ejemplos de `contracts/examples/chat/` (los cuatro de hoy más abstención `no_source` y `out_of_scope`, `length` y `tool_error`), `validate_examples.py` los valida, `openapi.json` y `schema.d.ts` están al día y los `operation_id` son los de §5.3.

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Pila de Supabase en marcha, puertos 3100 (`E2E_WEB_PORT`), 8000 y 8765 libres, sin red, datos sintéticos y memoria suficiente para los E2E.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -r contracts/requirements.txt ; pip install -e contracts/python ; pip install -e "backend[dev]"
python contracts/tools/export_schemas.py --check ; python contracts/tools/validate_examples.py
npx supabase db reset
pytest backend/tests/chat -q                                      # AC-01 a AC-21, AC-23
pytest backend/tests/agents -q                                    # cliente de agentes: Fake y Http con servidor SSE real
pytest backend/tests/rls -m rls -q                                # AC-11
pytest backend/tests -m "not rls" -q
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
E2E_WEB_PORT=3100 npm --prefix frontend exec -- playwright test e2e/chat.spec.ts e2e/roles.spec.ts e2e/responsive.spec.ts --workers=2   # AC-07, AC-12, AC-22; en frío y con historial
```

**Comando único de la spec** (el de `tasks.json`): `pytest backend/tests/chat` y `playwright test e2e/chat.spec.ts`, además de `pytest backend/tests/rls -m rls`.

### 8.3 Correspondencia criterio → prueba
Se escribe en el hito 7 con los nombres reales de las pruebas. Previsto: AC-01 a AC-06, AC-08, AC-09, AC-10, AC-13 a AC-19 y AC-21 en `backend/tests/chat/`; AC-02, AC-14, AC-15, AC-18 y AC-19 también en `backend/tests/agents/` con un servidor SSE real; AC-11 en `backend/tests/rls/`; AC-12, AC-20 y AC-22 en `chat.spec.ts`, `roles.spec.ts`, `responsive.spec.ts` y `lib/chat.test.ts`; AC-23 en `backend/tests/agents` y `contracts/tools/validate_examples.py`.

### 8.4 Definición de hecho
La secuencia termina con código 0 en local y en CI sobre el head empujado que contiene todos los hitos; `tasks.json` actualizado; ADR enlazados; sin secretos ni datos reales; el contenido y los textos del chat quedan anotados como **pendientes de validar con usuarios** (Charter §8) y el texto del aviso como **provisional hasta cerrar CONF-003**.

## Anexo A · Orden de implementación (un commit por hito)

1. Spec y `tasks.json`. **Hecho** (2026-11-16).
2. Migraciones de `chat_*`, funciones `app.*`, `rls_matrix.yaml` y pruebas de RLS.
3. `AgentsClient.stream_chat` (Protocol, Fake, Http en streaming), ejemplos nuevos, contrato 1.1.0 (P-01), pruebas con un servidor SSE real.
4. Servicio y API del chat (SSE, conversaciones, valoración, tope por hora); `openapi.json` y `schema.d.ts` regenerados; `backend/tests/chat`.
5. Frontend: `lib/chat.ts`, `/asistente`, Route Handler de envío, menú, portada.
6. E2E `chat.spec.ts`, roles y responsive, con localizadores exactos (sin `hasText` parcial con números ni nombres) y el agente de E2E con `/v1/chat` y un guion por marcador.
7. Mutaciones, matriz criterio → prueba, barrido de datos y cierre; `hecha` solo con el CI verde del head empujado con todos los hitos.

## Anexo B · Decisiones que esta spec deja a la implementación

Se rellena en cada hito (como en SPEC-W-012 y SPEC-W-013). Pendientes de partida:
- Forma exacta de los tipos Pydantic de los eventos que ve el navegador (`start`, `done` ampliado, `error`) y su ubicación (`cuadre.chat.models`; no en `cuadre_contracts`).
- Cómo se cancela el generador cuando el navegador corta (cierre de `StreamingResponse`, `asyncio.CancelledError`) y cómo se garantiza el `finally` sin trabajo posterior; prueba con un servidor real que corta.
- Cómo el Route Handler reenvía el cuerpo sin bufferizar con `cacheComponents` activo, y `maxDuration` acorde a los 90 s.
- De dónde sale `has_gestor` (consulta del vínculo activo de SPEC-W-010) y su coste.
- Guion por marcador del agente de E2E para tres navegadores en paralelo.
- Textos exactos de estados, abstención y errores (provisionales) y el orden del menú.
