---
tipo: spec
id: SPEC-W-010
titulo: Acceso del gestor: invitar, aceptar, revocar, cartera, lectura registrada, anotaciones y registro de actividad
estado: en-progreso
prioridad: must
riesgo: medio
historias: [US-004, US-010]
requisitos: [RF-002, RF-003]
nfr: [NFR-06]
restricciones: [RES-03, RES-07]
adr: [0003, 0005, 0008, 0011, 0015, 0016]
depende_de: [SPEC-W-001, SPEC-W-003]
bloquea: [SPEC-W-014, SPEC-W-016]
fecha: 2026-11-12
---

# SPEC-W-010 · Acceso del gestor

> Sexto paso de la cadena y primera spec que **abre la contabilidad de una persona a otra**: el autónomo **invita a su gestor por correo y puede retirarle el acceso cuando quiera**; el gestor **ve a quién da servicio, con sus pendientes, y consulta (solo lee) lo que cada autónomo le ha permitido**; cada lectura queda **registrada** y el autónomo la ve; el gestor puede dejar **anotaciones** que el autónomo lee. CONF-001 opción (a): el gestor consulta, revisa y descarga, **nunca emite ni registra**.
> Casi toda la parte difícil (la tabla `gestor_access`, las funciones de aceptar, rechazar y revocar, la función que decide si hay vínculo y las políticas de lectura de cada tabla) existe desde SPEC-W-001 a 009. Esta spec añade lo que falta: rutas, correo, cartera, lectura con registro, anotaciones y las dos pantallas.

## 1. Contexto

**Situación de partida.** SPEC-W-001 dejó en la base de datos: `public.gestor_access` (estados `pending`, `active`, `revoked` y `declined`; caducidad de 14 días; una invitación abierta por pareja dueño-gestor), `private.gestor_has_access(owner)` (se evalúa en **cada consulta**: revocar corta el acceso al instante), `app.accept_gestor_access`, `app.decline_gestor_access` y `app.revoke_gestor_access` (con su entrada en `activity_log` en la misma transacción), el registro `activity_log` (solo de añadir; el dueño y el actor lo leen) y `private.log_activity` (que **no** puede llamar `authenticated`). SPEC-W-002 a 009 añadieron las políticas de **lectura del gestor** de `profiles`, `business_profiles`, `invoice_series`, `clients`, `invoices`, `invoice_files`, `documents`, `expenses` y de los buckets de Storage; el administrador no tiene ninguna sobre datos financieros (D3). La portada `/cartera` del gestor existe, vacía («Próximamente»). El 303 y el 130 son funciones de dominio puras y sus lecturas están en `cuadre.quarters`.

**Qué falta.** No hay ninguna ruta HTTP ni pantalla para invitar, aceptar, rechazar ni revocar; no hay correo (solo los de Auth de Supabase); el gestor no tiene cartera ni lee nada por la API; las lecturas del gestor no se registran; no existe `gestor_notes` (la «revisión» de CONF-001 a); y el autónomo no tiene dónde ver quién tiene acceso ni qué ha leído.

**Por qué es de riesgo medio.** El riesgo es **de seguridad, no de cálculo** (R-04, NFR-06): una lectura que se cuele sin vínculo, que sobreviva a una revocación o que revele si una persona existe sería una fuga. Por eso las reglas críticas siguen en SQL (política y función de registro) y no solo en la API, y la cobertura de roles y de revocación es la de NFR-06. El registro de cada lectura es la contrapartida de la confianza que da el autónomo.

**Decisiones vigentes** (no se reabren aquí): CONF-001 (a) y D1 (el registro libre crea `usuario`; el administrador promueve gestores; el autónomo invita por correo y el gestor acepta dentro de la aplicación, **sin tokens de invitación**); D3 (el administrador no ve datos financieros); ADR-0003 y ADR-0015 (SQL explícito, psycopg síncrono); ADR-0005 (rol de `profiles.role` vía `private.app_role()`, nunca de claims del JWT; vínculo evaluado en cada consulta); ADR-0008 (correo detrás de la interfaz `EmailSender`, sin proveedor real todavía); ADR-0011 (cliente generado y `operation_id` en `verbo_objeto`); ADR-0016 (Vercel Function: respuestas < 4,5 MB, sin trabajo tras la respuesta, sin archivos por la API).

**Decisiones de producto tomadas por la persona el 2026-11-12:** (1) alcance de lectura **completo de consulta**: cartera con pendientes y, por autónomo, facturas (con PDF), gastos, documentos para revisar, perfil y clientes, **borradores 303 y 130** y anotaciones; (2) la pantalla del autónomo es una **sección nueva «Mi gestor»** del menú (`/gestor`); (3) **una spec y seis hitos**.

**Decisiones que propone esta spec** (por defecto; la persona las confirma o corrige antes del hito 1):

| ID | Decisión | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Invitar**: el autónomo escribe el correo del gestor; la ruta inserta en `gestor_access` (la política ya fija el resto) y envía un correo con `EmailSender`. **No revela** si el correo es de un gestor, de un usuario o de nadie: la respuesta y el correo son los mismos. Sin tokens: el gestor acepta dentro de la aplicación (D1) | Mensaje distinto según exista o no la cuenta: enumeración de cuentas (descartado) |
| D-02 | **Aceptar, rechazar y revocar** son rutas finas sobre las funciones SQL que ya existen (`app.*`), con sus códigos de error. Revocar vale también para retirar una invitación pendiente. La invitación caduca a los 14 días (ya en la tabla) | Reimplementar la lógica en Python: dos sitios para una regla de seguridad |
| D-03 | **`gestor_notes`**: tabla nueva, RLS forzada y registrada en `rls_matrix.yaml`. El gestor con vínculo activo **inserta y lee** las suyas; el autónomo **lee** todas las de su cuenta; **solo se añaden** (no se editan ni se borran); texto de 1 a 2.000 caracteres; ligadas opcionalmente a una factura, un gasto o un documento por su id; el administrador, nada | Anotaciones editables: obliga a un historial para que el autónomo no vea cambios silenciosos |
| D-04 | **Cartera**: `GET /api/gestor/cartera` lista a los autónomos con acceso **activo** (nombre y correo) con sus **pendientes** = documentos en estado `review` del autónomo (US-010: «marcado con su número»). Un autónomo sin pendientes sale sin marca. Orden: con pendientes primero, por nombre | Más indicadores (facturas sin cobrar, trimestre próximo): SPEC-W-014 |
| D-05 | **`owner_scope`**: una dependencia de FastAPI para `/api/gestor/autonomos/{owner_id}/…` que exige rol `gestor`, comprueba el vínculo activo **con la identidad del propio gestor** (RLS y `private.gestor_has_access`; sin service key y sin claims del JWT) y **registra cada lectura**. Sin vínculo, con vínculo revocado, caducado o de otro gestor, la respuesta es **la misma `404`**: no se filtra que el autónomo exista | `403` distinto de `404`: permite saber qué ids son autónomos |
| D-06 | **Registrar la lectura** con una función SQL nueva `app.log_gestor_read(owner, entity_type, entity_id)` (`SECURITY DEFINER`, `search_path = ''`) que comprueba el vínculo y escribe en `activity_log` (`category = 'access'`, `action = 'gestor.read'`, **solo ids y tipo**, nunca importes, nombres, NIF ni IBAN). `authenticated` no puede escribir en `activity_log` por otra vía. **Una entrada por petición de datos del gestor** | Registrar desde Python con la service key: prohibido (prohibición 6) |
| D-07 | **Lecturas por autónomo** (solo lectura): facturas (lista, detalle y descarga del PDF por URL firmada de corta vida), gastos (los anulados se ven rotulados «Anulado»), documentos (los de estado `review` y `extraction_failed`, y el original por URL firmada), perfil del negocio y series, clientes, y los **borradores del 303 y del 130** con los mismos servicios y funciones de dominio. Las lecturas de `cuadre.quarters` y de facturas pasan a recibir el dueño explícito (hoy filtran por `auth.uid()`) y siguen apoyándose en la RLS | Un segundo juego de consultas para el gestor: dos sitios para cada regla de cálculo |
| D-08 | **Registro de actividad del autónomo**: `GET /api/gestor/actividad` pagina las entradas `access` de su cuenta (invitar, aceptar, rechazar, revocar, lecturas del gestor) con fecha, quién (correo del gestor) y qué leyó (tipo e id), sin datos financieros. La política de lectura de `activity_log` ya existe | Un visor completo con filtros: mejora posterior |
| D-09 | **Pantallas**: autónomo `/gestor` («Mi gestor»: invitar con correo, estado de las invitaciones con texto, revocar con confirmación, anotaciones recibidas y registro de actividad); gestor `/cartera` (invitaciones recibidas con aceptar y rechazar, y la cartera con los pendientes marcados) y `/cartera/{ownerId}` (ficha con pestañas **Facturas, Gastos, Documentos, Trimestres, Perfil y clientes y Anotaciones**). Server Components y HTML nativo; JavaScript de cliente solo para formularios si hiciera falta | Una pantalla aparte por cada lectura: más rutas y más menú |
| D-10 | **Nombres de ruta**: las del gestor van bajo `/api/gestor/autonomos/{owner_id}/…` (la nota de `tasks.json` decía `/clientes/{owner_id}`, que se confunde con los clientes del autónomo); los clientes del autónomo son `/api/gestor/autonomos/{owner_id}/clientes` | Mantener `/clientes/{owner_id}`: ambigüedad en las dos pantallas |

**Preguntas abiertas** (con propuesta; la persona las resuelve en el hito 0):

| ID | Pregunta | Propuesta |
|---|---|---|
| P-01 | ¿Se **oculta el IBAN** al gestor? (la política de `business_profiles` ya lo deja leer) | **No**: le sirve para domiciliaciones; se anota en las exclusiones |
| P-02 | ¿Puede el gestor **descargar** el PDF de una factura y el original de un gasto? | **Sí**, por URL firmada, solo lectura y registrado |
| P-03 | ¿Se pueden **borrar o editar** las anotaciones? | **No**: solo de añadir (D-03) |
| P-04 | **Límite de invitaciones abiertas** por autónomo (pendientes + activas) | **5** |
| P-05 | ¿Cuántas **lecturas** se registran? | **Una entrada por petición de datos del gestor**; sin deduplicar |

## 2. Objetivo

Que el **autónomo** invite a su gestor, vea el estado de la invitación, la revoque cuando quiera y sepa **qué ha leído su gestor y cuándo**; que el **gestor** acepte o rechace invitaciones, vea a sus autónomos con los pendientes de cada uno y **consulte** su contabilidad (facturas, gastos, documentos, perfil, clientes y los borradores del 303 y del 130) y deje **anotaciones**; que **ninguna lectura sin vínculo vigente prospere** (tampoco tras revocar) y que **cada lectura quede registrada**, sin escribir nunca en la contabilidad del autónomo (CONF-001 a).

## 3. Alcance explícito

### 3.1 Base de datos
- Migración de `public.gestor_notes` (RLS activada y forzada, política por rol, privilegios mínimos) y su alta en `backend/tests/rls/rls_matrix.yaml`.
- Función `app.log_gestor_read` (§5.2) y los índices que necesiten el registro de actividad y las anotaciones.

### 3.2 Backend (FastAPI)
- Rutas del autónomo: invitar, listar accesos, revocar, listar anotaciones y listar actividad. Rutas del gestor: invitaciones recibidas, aceptar, rechazar, cartera y las lecturas por autónomo con `owner_scope`; crear y listar anotaciones.
- `cuadre.notifications` (`EmailSender`: `ConsoleEmailSender`, `MemoryEmailSender`; el proveedor real se activa con `EMAIL_PROVIDER` y queda sin implementar) y la plantilla del correo de invitación.
- Lecturas de `cuadre.quarters`, de facturas, gastos, documentos, clientes y perfil con **dueño explícito**.
- OpenAPI y cliente TypeScript regenerados (`operation_id` en `verbo_objeto`).

### 3.3 Frontend (Next.js)
- `/gestor` (autónomo), `/cartera` y `/cartera/{ownerId}` (gestor), el menú y `lib/roles.ts`, `lib/gestor.ts` (puro, con unitarias), `lib/gestor-api.ts` y los componentes de las pantallas; reutiliza las hojas del 303 y del 130 y las listas ya hechas.

### 3.4 Pruebas
- `backend/tests/gestor/` (rutas, `owner_scope`, correo, registro y anotaciones), `backend/tests/rls/` (matriz de `gestor_notes` y aislamiento tras revocar), unitarias del frontend y `e2e/gestor.spec.ts` en tres motores y dos anchos.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Que el gestor **emita, registre, edite o anule** nada del autónomo (facturas, gastos, perfil, clientes) | Decisión CONF-001 (a): no en la v1 |
| **Proveedor real de correo**, dominio verificado y contrato de encargado | DEP-05, DEP-06 y ADR-0008 (antes del piloto) |
| **Recordatorios** al autónomo y resumen de cartera del gestor por correo | SPEC-W-014 |
| **Exportación de datos** y cierre de cuenta (RGPD); qué pasa con el acceso del gestor al borrar una cuenta | SPEC-W-017 (bloqueada por CONF-004) |
| **Pantallas del administrador** (alta y promoción de gestores) | SPEC-W-015 |
| **Cierre mensual y reporte** visibles al gestor | SPEC-W-012 y SPEC-W-013 |
| **Chatbot** del gestor y herramientas MCP de cartera | SPEC-W-004 y SPEC-W-011 (solo el rol `usuario` recibe herramientas de datos) |
| Anotaciones **editables, borrables o con respuesta** del autónomo | Mejora posterior |
| **Notificar** al autónomo de cada lectura (aviso en tiempo real) | Mejora posterior (el registro ya existe) |
| Filtros, exportación y búsqueda en el registro de actividad | Mejora posterior |

## 5. Contrato de interfaces

### 5.1 Reglas

**Acceso.** Una invitación nace `pending` con caducidad a 14 días, dirigida a un correo en minúsculas; no puede ser el del propio autónomo; solo hay una abierta (pendiente o activa) por pareja; el autónomo no puede tener más de 5 abiertas (P-04). Aceptar o rechazar solo lo hace un `gestor` cuyo correo es el de la invitación (o ya la había aceptado como `gestor_id`); revocar solo lo hace el dueño, y vale para una invitación pendiente o activa. Una vez `revoked`, `declined` o caducada, no se reabre: se invita de nuevo.

**Sin enumeración.** `invite_gestor_access` responde igual (mismo estado y mismo cuerpo, y un correo equivalente) si el correo es de un gestor, de un autónomo, del administrador o de nadie. El correo dice «te han invitado a dar acceso a su contabilidad en Cuadre; entra y acéptalo», sin ningún dato financiero. No incluye enlace con token.

**Vínculo y lectura.** Toda ruta `/api/gestor/autonomos/{owner_id}/…` pasa por `owner_scope`: rol `gestor` (en caso contrario `403`, como el resto de rutas por rol); vínculo `active` con `gestor_id = el gestor` y no caducado; si no, `404` con el mismo cuerpo. La lectura corre con la identidad del gestor (RLS); nunca con la service key ni con el JWT del autónomo. **Cómo se elige a quién se mira (decidido en el hito 2):** en vez de un parámetro `owner` en cada consulta, las lecturas del autónomo filtran por `private.read_owner()` (= el ajuste local `cuadre.read_owner` si existe, y si no `auth.uid()`); `owner_scope` lo fija con `set_config(..., true)` (local a la transacción) **solo después** de que `app.log_gestor_read` haya comprobado el vínculo. El camino del autónomo no lo fija nunca y queda idéntico; la RLS sigue siendo la que decide qué filas se ven.

**Registro de lecturas.** Cada petición de datos de `owner_scope` escribe **una** entrada: `category = 'access'`, `actor_id`/`actor_role = gestor`, `owner_id`, `action = 'gestor.read'`, `entity_type` (`portfolio`, `invoices`, `invoice`, `invoice_pdf`, `expenses`, `documents`, `document_original`, `profile`, `clients`, `modelo_303`, `modelo_130`, `notes`) y `entity_id` (id del recurso o `null` en las listas); `metadata` solo con identificadores y el periodo pedido, **nunca** importes, nombres, NIF, IBAN, conceptos ni URLs firmadas. Se escribe en la **misma transacción** que la lectura: si el registro falla, no se entrega el dato.

**Anotaciones.** `gestor_notes(id, owner_id, gestor_id, body 1..2000, entity_type?, entity_id?, created_at)`; solo `insert` (por el gestor con vínculo activo, con `gestor_id = auth.uid()` y `owner_id` del vínculo) y `select` (el gestor las suyas con vínculo activo; el autónomo las de su cuenta); ni `update` ni `delete`. Crear una anotación se registra (`gestor.note_added`, solo ids).

**Cartera.** Un autónomo aparece mientras el vínculo esté `active`. Sus pendientes son los documentos con `status = 'review'` del autónomo; en la respuesta, `pending_count` (entero ≥ 0) y el nombre a mostrar. Los autónomos sin vínculo activo no aparecen. Leer la cartera (y abrir la ficha de un autónomo) deja `gestor.read` con `entity_type = 'portfolio'`: **una entrada por cada autónomo cuyo nombre y pendientes se enseñan** (la función de SQL registra por dueño; corregido en el hito 2, la spec decía «no se registra por autónomo»). Una cartera sin autónomos no registra nada.

**Registro de actividad (autónomo).** Devuelve, más reciente primero y con paginación por cursor (el `id` de la última entrada, páginas de 50), las entradas `access` donde `owner_id` es el autónomo: `action`, `occurred_at`, `actor_role`, `actor_email` (el del gestor que actuó; `null` si actuó el propio autónomo), `entity_type`, `entity_id` y el periodo (`year`, `quarter`) de los borradores. Nunca devuelve el texto de una anotación ni datos financieros. Las entradas de lectura se describen con texto («Tu gestor consultó tus facturas») en la interfaz, no en la API.

### 5.2 Base de datos

**`public.gestor_notes`** (en su propia migración): `RLS` activada y forzada; `revoke all` a todos los roles y `grant select` a `authenticated`; políticas: `select` del dueño (`owner_id = auth.uid()`) y `select` del gestor (`private.gestor_has_access(owner_id) and gestor_id = auth.uid()`); **ninguna** de escritura y **ninguna** del administrador. **Se escribe solo por `app.add_gestor_note`** (decidido en el hito 1: así el vínculo, que lo anotado es del autónomo y el registro van en una sola transacción). Un trigger la hace **solo de añadir** aunque venga de una función `SECURITY DEFINER`. Sin claves foráneas a `profiles` (sobrevive al borrado de una cuenta). Índices por (`owner_id`, `created_at desc`) y (`gestor_id`, `created_at desc`). Se registra en `rls_matrix.yaml` (`test_rls_guard`).

**`app.log_gestor_read(p_owner uuid, p_entity_type text, p_entity_id text, p_metadata jsonb default null)`**: `SECURITY DEFINER`, `search_path = ''`; comprueba `private.app_role() = 'gestor'` y `private.gestor_has_access(p_owner)` (si no, `42501`); `entity_type` entre los de §5.1 y `metadata` solo con `year` y `quarter` numéricos (si no, `invalid_read`); escribe la entrada de §5.1 con `private.log_activity`. Es ejecutable solo por `authenticated`.

**`app.add_gestor_note(p_owner uuid, p_body text, p_entity_type text, p_entity_id uuid) returns uuid`**: solo `gestor` con vínculo activo (`42501`); texto recortado de 1 a 2.000 (`invalid_note`, `detail = body`); si se liga a algo, el tipo (`invoice`, `expense` o `document`) y el id van juntos y la entidad **existe y es de ese autónomo** (`invalid_note`, `detail = entity`); inserta y registra `gestor.note_added` (solo ids, nunca el texto) en la misma transacción.

**`app.invite_gestor_access(p_email text) returns uuid`** (añadida en el hito 1): solo `usuario`; recorta y pasa a minúsculas; `invalid_email`, `cannot_invite_self`; **retira** (a `revoked`) las invitaciones pendientes caducadas de esa pareja (el índice parcial único las cuenta como abiertas y bloquearía volver a invitar para siempre); `gestor_access_already_open`; `too_many_open_invitations` (5 abiertas no caducadas, P-04) con un cerrojo asesor por persona; inserta y registra `gestor_access.invited` en la misma transacción. **`app.list_gestor_invitations()`** (añadida en el hito 1): solo `gestor`; las pendientes no caducadas dirigidas a su correo, con `id`, nombre de quien invita, `invited_at` y `expires_at` (antes de aceptar, el gestor no puede leer el perfil del autónomo). La política de inserción directa de `gestor_access` de SPEC-W-001 se mantiene (sus pruebas la usan); la API solo usa `app.invite_gestor_access` y retirar la directa queda como endurecimiento posterior.

### 5.3 API HTTP

| Operación | Ruta | Quién | Respuesta |
|---|---|---|---|
| `invite_gestor_access` | `POST /api/gestor/accesos` `{email}` | `usuario` | `201` con el acceso (`id`, `gestor_email`, `status`, `invited_at`, `expires_at`) y `email_sent` (`false` si el correo no se pudo entregar: la invitación existe y queda pendiente); `409 invitation_already_open`; `422 cannot_invite_self` / `invalid_email`; `422 too_many_open_invitations` |
| `list_gestor_accesses` | `GET /api/gestor/accesos` | `usuario` | `200` con sus accesos (más reciente primero; los caducados salen como `expired`) |
| `revoke_gestor_access` | `POST /api/gestor/accesos/{id}/revocar` | `usuario` | `204`; `404 gestor_access_not_found`; `409 gestor_access_not_open` |
| `list_gestor_notes` | `GET /api/gestor/anotaciones` | `usuario` | `200`, las anotaciones de su cuenta |
| `list_gestor_activity` | `GET /api/gestor/actividad?cursor=` | `usuario` | `200` paginado (§5.1) |
| `list_gestor_invitations` | `GET /api/gestor/invitaciones` | `gestor` | `200` con las pendientes dirigidas a su correo (nombre del autónomo y caducidad) |
| `accept_gestor_invitation` / `decline_gestor_invitation` | `POST /api/gestor/invitaciones/{id}/aceptar` · `/rechazar` | `gestor` | `204`; `404 gestor_access_not_found`; `409 gestor_access_not_pending`; `409 gestor_access_expired` (solo al aceptar) |
| `get_gestor_portfolio` | `GET /api/gestor/cartera` | `gestor` | `200` con los autónomos activos y sus pendientes |
| `get_gestor_autonomo` | `GET /api/gestor/autonomos/{owner_id}` | `gestor` + vínculo | `200` con nombre, pendientes y los contadores de la ficha |
| `list_gestor_autonomo_invoices` · `get_gestor_autonomo_invoice` · `get_gestor_autonomo_invoice_pdf` | `…/facturas?year=&scope=&paid=&limit=&offset=`, `…/facturas/{id}`, `…/facturas/{id}/pdf` | `gestor` + vínculo | `200` (lista **paginada**: `limit` 1–200, por defecto 100, y `offset`; AC-23); el PDF, por **URL firmada** de ≈ 60 s (`{url, expires_in}`; `409 invoice_pdf_pending` si aún no hay PDF) |
| `list_gestor_autonomo_expenses` | `…/gastos?page=&limit=&year=&month=` | `gestor` + vínculo | `200` `{items, next_cursor}` con cursor como el del autónomo, hasta 100 por página (los anulados llevan `voided_at`) |
| `list_gestor_autonomo_documents` · `get_gestor_autonomo_document_original` | `…/documentos`, `…/documentos/{id}/original` | `gestor` + vínculo | `200`; el original, por URL firmada |
| `get_gestor_autonomo_profile` · `list_gestor_autonomo_clients` | `…/perfil`, `…/clientes` | `gestor` + vínculo | `200` |
| `get_gestor_autonomo_modelo_303` · `get_gestor_autonomo_modelo_130` | `…/trimestres/303?year=&quarter=` · `…/trimestres/130?…` | `gestor` + vínculo | `200` con **el mismo cuerpo** que `get_modelo_303` y `get_modelo_130`; los mismos `422` de periodo |
| `create_gestor_note` · `list_gestor_autonomo_notes` | `POST/GET …/anotaciones` | `gestor` + vínculo | `201` / `200` |

Errores en `application/problem+json` con `code` estable y `detail` en español, sin repetir lo enviado ni datos del autónomo. `Cache-Control: private, no-store` en todas. Sin vínculo vigente: `404` uniforme (`code: not_found`). Rol equivocado: `403 forbidden`; sin sesión: `401`.

### 5.4 Backend
`cuadre/gestor/` (servicio, repositorio, modelos y errores), `cuadre/notifications/` (`EmailSender` y sus implementaciones), `cuadre/api/routes_gestor.py`, `cuadre/gestor/scope.py` (`owner_scope`: registro y dueño de la lectura en una transacción), `cuadre/gestor/reads.py` y `cuadre/api/routes_gestor_reads.py` (hito 2), y las lecturas con `private.read_owner()` en `cuadre/quarters/`, `cuadre/invoicing/`, `cuadre/expenses/`, `cuadre/documents/`, `cuadre/clients/` y `cuadre/profile/`. Ninguna conexión a la base fuera de `cuadre.db`; ninguna service key en estas rutas.

### 5.5 Frontend
`app/(app)/gestor/page.tsx` (autónomo), `app/(app)/cartera/page.tsx` y `app/(app)/cartera/[ownerId]/page.tsx` (gestor, con la pestaña elegida por `?tab=`), `lib/gestor.ts` (puro: textos de estado, marca de pendientes, agrupación y direcciones), `lib/gestor-api.ts` (lecturas de servidor y acciones), componentes en `components/gestor/`. `lib/roles.ts`: «Mi gestor» (`/gestor`) para `usuario` y las rutas `/cartera/…` como sección del gestor. Ninguna regla de acceso en el navegador: el servidor decide y la interfaz solo enseña.

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T10-01 | **El vínculo se evalúa en cada consulta** (ADR-0005): revocar corta el acceso al instante; ninguna caché de vínculo |
| T10-02 | **Sin service key** (prohibición 6) ni claims del JWT para el rol: todo con la identidad del gestor y `private.gestor_has_access` |
| T10-03 | **El gestor nunca escribe** en la contabilidad (CONF-001 a): ni rutas ni políticas de escritura salvo `gestor_notes`; una prueba intenta cada escritura y falla |
| T10-04 | **Sin enumeración de cuentas**: invitar y `owner_scope` responden igual exista o no la persona; `404` uniforme |
| T10-05 | **El registro es parte de la lectura**: misma transacción; si no se puede registrar, no se devuelve el dato; `activity_log` solo se escribe por funciones `app.*` |
| T10-06 | **Sin datos personales ni financieros** en el registro, en logs, trazas, errores ni en el cuerpo del correo (sin importes, NIF, IBAN, conceptos ni URLs firmadas) |
| T10-07 | **RLS**: `gestor_notes` activada y forzada, registrada en la matriz y con el patrón de CLAUDE.md; el administrador, ninguna política; `test_rls_guard` en verde |
| T10-08 | **Cabe en una Vercel Function** (ADR-0016): respuestas < 4,5 MB (las listas se paginan), sin trabajo tras la respuesta, sin archivos por la API: PDF y originales por URL firmada de corta vida; `test_vercel_compat` en verde |
| T10-09 | **Sin float** en importes (RES-02): lo que enseña el gestor es lo que enseña el autónomo (céntimos enteros y las funciones de dominio existentes) |
| T10-10 | **Correo detrás de `EmailSender`** (ADR-0008): sin proveedor real; en desarrollo a consola, en pruebas a memoria; sin cuerpos de correo en los logs |
| T10-11 | **Interfaz** como T8-10 y T9-10: tokens del prototipo, etiquetas en cada campo, foco visible, estado con texto además de color, confirmación antes de revocar, sin scroll horizontal a 390 y 1.440 px en los tres motores |
| T10-12 | **Datos sintéticos** (RES-07) y los E2E **no borran** facturas ni archivan gastos emitidos: usan cuentas propias de cada worker |

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Invitar.** *Given* un autónomo; *When* escribe el correo de su gestor y envía; *Then* se crea una invitación `pending` que caduca a los 14 días, se envía un correo a esa dirección sin ningún dato financiero ni token, y queda la entrada de actividad.

**AC-02 · Sin enumeración.** *Given* un correo de un gestor, otro de un autónomo y otro que no existe; *When* el autónomo invita a cada uno; *Then* la respuesta (estado y cuerpo) y el correo enviado son equivalentes en los tres casos.

**AC-03 · Límites de la invitación.** *Given* un autónomo; *Then* invitarse a sí mismo da `422 cannot_invite_self`, repetir una invitación abierta da `409 invitation_already_open`, un correo mal formado da `422 invalid_email` y la sexta abierta da `422 too_many_open_invitations`.

**AC-04 · Aceptar y rechazar.** *Given* un gestor con una invitación dirigida a su correo; *When* la acepta; *Then* pasa a `active` con su `gestor_id` y queda registrado; *When* la rechaza, pasa a `declined`; una caducada responde `409 gestor_access_expired`; una dirigida a otro correo responde `404`; un autónomo o el administrador reciben `403`.

**AC-05 · Revocar (US-004).** *Given* un autónomo que ha invitado a un gestor con acceso activo; *When* revoca; *Then* el gestor **deja de verlo en su cartera**, **cualquier petición suya a sus datos se rechaza al instante** (`404`) y la revocación queda en el registro de actividad. También retira una invitación pendiente.

**AC-06 · Solo el dueño revoca.** *Given* un acceso; *Then* otro autónomo, el gestor y el administrador no pueden revocarlo (`404` o `403`) y el acceso no cambia.

**AC-07 · Cartera (US-010).** *Given* un gestor con acceso a tres autónomos, uno con cuatro documentos en `review`; *When* abre su cartera; *Then* ve a los tres y el que tiene pendientes aparece marcado con el **número 4** (también escrito con texto); los otros, sin marca.

**AC-08 · Quién sale en la cartera.** *Given* invitaciones pendientes, rechazadas, revocadas y caducadas y un acceso activo; *Then* solo sale el activo; un autónomo de otro gestor no sale.

**AC-09 · `owner_scope`.** *Given* un gestor; *When* pide los datos de un autónomo sin vínculo, con vínculo revocado, caducado o de otro gestor, o de un id que no existe; *Then* recibe la **misma `404`**; un autónomo o el administrador reciben `403`; sin sesión, `401`.

**AC-10 · Cada lectura queda registrada.** *Given* un gestor con acceso; *When* consulta facturas, gastos, documentos, perfil, clientes o un borrador; *Then* cada petición deja una entrada `gestor.read` con el autónomo, el gestor, el tipo y el id, **sin ningún importe, nombre, NIF, IBAN ni URL firmada**, y si el registro falla, no se devuelve el dato.

**AC-11 · Facturas.** *Given* un autónomo con facturas y una rectificativa; *When* el gestor las consulta; *Then* la lista y el detalle coinciden con lo que ve el autónomo, y el PDF se descarga por una URL firmada de corta vida (registrado).

**AC-12 · Gastos, documentos, perfil y clientes.** *Given* un autónomo con gastos (uno anulado), documentos en `review` y clientes; *Then* el gestor ve lo mismo que el autónomo (el anulado, rotulado), puede descargar el original de un documento por URL firmada y lee el perfil y las series.

**AC-13 · Borradores 303 y 130.** *Given* los ejercicios simulados de B.1 de SPEC-W-008 y SPEC-W-009 sembrados en una cuenta con gestor; *When* el gestor pide el 303 y el 130 de un periodo; *Then* el cuerpo coincide **al céntimo** con el que obtiene el autónomo (mismo dominio, mismos `422` de periodo).

**AC-14 · Solo lectura (CONF-001 a).** *Given* un gestor con acceso activo; *When* intenta emitir, registrar, editar o anular algo del autónomo, o escribir en cualquier tabla distinta de `gestor_notes`; *Then* no existe la ruta o la base de datos lo rechaza, y el autónomo no ve ningún cambio.

**AC-15 · Anotaciones.** *Given* un gestor con acceso; *When* crea una anotación (1 a 2.000 caracteres, opcionalmente ligada a una factura, un gasto o un documento); *Then* la ve en la ficha, el autónomo la ve en «Mi gestor», no se puede editar ni borrar, otro gestor no la ve, y tras revocar el gestor ya no puede crear ni leer anotaciones del autónomo (el autónomo las conserva).

**AC-16 · Registro de actividad del autónomo.** *Given* un autónomo con un gestor que ha leído datos; *When* abre «Mi gestor»; *Then* ve, paginado y más reciente primero, cuándo se invitó, aceptó, rechazó o revocó y **qué leyó su gestor y cuándo**; otro autónomo, el gestor y el administrador no pueden leer ese registro por la API.

**AC-17 · Aislamiento y matriz.** *Given* la matriz de RLS; *Then* `gestor_notes` está registrada, el administrador no tiene ninguna política sobre ella ni sobre el resto de datos financieros, y `test_rls_guard` y los tests de roles pasan.

**AC-18 · Sin service key y sin datos en logs.** *Given* cualquier petición de estas rutas; *Then* no se usa la service key y ningún registro (logs, trazas, errores, correo) contiene importes, nombres, NIF, IBAN, conceptos ni URLs firmadas.

**AC-19 · Pantalla del autónomo.** *Given* un autónomo; *When* abre «Mi gestor»; *Then* puede invitar (campo de correo con etiqueta y errores junto al campo), ve el estado de cada invitación **con texto** (pendiente, activa, rechazada, revocada, caducada), revoca con una confirmación previa, lee las anotaciones recibidas y el registro de actividad.

**AC-20 · Pantalla del gestor.** *Given* un gestor; *When* abre «Cartera»; *Then* ve las invitaciones recibidas con aceptar y rechazar, y su cartera con los pendientes marcados con su número y con texto; al elegir un autónomo, ve su ficha con pestañas Facturas, Gastos, Documentos, Trimestres, Perfil y clientes y Anotaciones, **sin ningún botón de emitir, registrar o editar**; la pestaña y el autónomo elegido viven en la dirección.

**AC-21 · Menú y roles.** *Given* cada rol; *Then* el autónomo ve «Mi gestor» activo y no «Cartera»; el gestor ve «Cartera» y no «Mi gestor»; el administrador, ninguno de los dos; y las rutas del otro rol llevan a `/403`.

**AC-22 · Adaptable y accesible.** *Given* 390 y 1.440 px en Chromium, Firefox y WebKit; *Then* ninguna pantalla nueva tiene scroll horizontal, todos los campos tienen etiqueta, los desplegables, pestañas y confirmaciones se usan con teclado, el estado se entiende sin color y la consola no registra errores.

**AC-23 · Cabe en una Vercel Function.** *Given* el mayor listado admisible de facturas, gastos o documentos de un autónomo; *Then* cada respuesta mide < 4,5 MB (las listas se paginan) y las descargas van por URL firmada.

**AC-24 · Revocar a mitad (NFR-06).** *Given* un gestor con una petición en curso y un autónomo que revoca; *Then* toda petición que empiece después de la revocación se rechaza, sin ninguna lectura residual (sin caché de vínculo).

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-009 §8.1: pila de Supabase en marcha, puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 (o `E2E_AGENTS_PORT`) libres, sin red y con datos sintéticos.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                                  # migraciones + seed
pytest backend/tests/rls -m rls -q                                     # NFR-06 (con gestor_notes en la matriz)
pytest backend/tests/gestor -q                                         # AC-01 a AC-16 y AC-18, AC-23, AC-24
pytest backend/tests -m "not rls" -q
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/gestor.spec.ts       # AC-19 a AC-22 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/rls backend/tests/gestor` y `npm --prefix frontend exec -- playwright test e2e/gestor.spec.ts`, además de las secuencias completas de SPEC-W-001, 002, 003, 005, 006, 007, 008 y 009.

### 8.3 Correspondencia criterio → prueba

| Criterio | Prueba |
|---|---|
| AC-01 a AC-04 | `backend/tests/gestor/test_invitations.py` (rutas, correo con `MemoryEmailSender`, límites, aceptar y rechazar) |
| AC-05, AC-06, AC-24 | `backend/tests/gestor/test_revocation.py` y `backend/tests/rls/` (revocar corta al instante; solo el dueño) |
| AC-07, AC-08 | `backend/tests/gestor/test_portfolio.py` |
| AC-09, AC-10 | `backend/tests/gestor/test_owner_scope.py` y `test_read_log.py` |
| AC-11, AC-12, AC-13 | `backend/tests/gestor/test_reads.py` (con los ejercicios de B.1 de W-008 y W-009 sembrados) |
| AC-14 | `backend/tests/gestor/test_read_only.py` y `backend/tests/rls/` |
| AC-15 | `backend/tests/gestor/test_notes.py` |
| AC-16 | `backend/tests/gestor/test_activity.py` |
| AC-17 | `backend/tests/rls/` (`rls_matrix.yaml`, `test_rls_guard`, roles) |
| AC-18, AC-23 | `backend/tests/gestor/test_privacy.py` y `backend/tests/rules/test_vercel_compat.py` |
| AC-19 a AC-22 | `frontend/e2e/gestor.spec.ts`, `roles.spec.ts`, `responsive.spec.ts` y las unitarias de `lib/gestor.test.ts` y `lib/roles.test.ts` |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005, 006, 007, 008 y 009 §8.2 siguen en verde.
- [ ] **Cero accesos indebidos** del gestor (sin vínculo, tras revocar, de otro gestor) y del administrador (NFR-06), con cada lectura registrada.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0005, 0008, 0011, 0015 y 0016 enlazados.
- [ ] Las preguntas P-01 a P-05 están resueltas o anotadas en el Anexo B.
- [ ] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

1. **Hito 0 · la spec y las decisiones**: se redacta esta spec; D-01 a D-10 y P-01 a P-05 se confirman o se corrigen.
2. **Hito 1 · SQL y acceso**: migración de `gestor_notes` y `app.log_gestor_read` (con `app.add_gestor_note`), matriz de RLS, `cuadre.notifications` y las rutas de invitar, listar, aceptar, rechazar y revocar, con sus pruebas.
   **Hecho el 2026-11-12** (migraciones `gestor_notes` y funciones `app.*`; `cuadre.notifications`; `cuadre.gestor` y las seis rutas de acceso; OpenAPI y cliente regenerados; Anexo B.2).
3. **Hito 2 · API de lectura del gestor**: `owner_scope`, cartera, lecturas por autónomo con dueño explícito (también 303 y 130), anotaciones, registro de lecturas y de actividad; OpenAPI y cliente.
   **Hecho el 2026-11-12** (migración `read_owner`; `cuadre.gestor.scope` y `reads`; 16 rutas; OpenAPI y cliente regenerados; Anexo B.3).
4. **Hito 3 · pantalla del autónomo** `/gestor`: invitar, estados, revocar, anotaciones y registro de actividad; menú y roles; unitarias y comprobación visual en tres motores.
5. **Hito 4 · pantallas del gestor** `/cartera` y `/cartera/{ownerId}`: invitaciones, cartera con pendientes, ficha con pestañas y descargas; unitarias y comprobación visual.
6. **Hito 5 · E2E y cierre**: `e2e/gestor.spec.ts`, ajustes de `roles.spec.ts` y `responsive.spec.ts`, mutaciones de la interfaz, batería completa, Anexo B final, `tasks.json` y `en-revision`.

## Anexo B · Decisiones que esta spec deja a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-014 (recordatorios y resumen de cartera).** Reutiliza `EmailSender` y la definición de pendientes de D-04; el resumen de cartera por correo no existe aquí.
- **SPEC-W-016 (adaptable y accesible).** Las tres pantallas nuevas entran en su revisión de 390 y 1.440 px y de Lighthouse.
- **SPEC-W-017 (exportación y cierre de cuenta).** Debe decidir qué pasa con `gestor_access` y `gestor_notes` al borrar una cuenta (CONF-004); `gestor_notes` y `activity_log` no llevan claves foráneas a `profiles` para sobrevivir al borrado, como el registro de actividad.
- **SPEC-W-015 (administración).** El alta y la promoción de gestores es del administrador; esta spec no crea gestores.

### B.1 Notas del hito 0

- **La nota de `tasks.json` hablaba de `/api/gestor/clientes/{owner_id}`:** se renombra a `/api/gestor/autonomos/{owner_id}` (D-10) para no confundirla con los clientes del autónomo. Se corrige en el mismo cambio.
- **Estado de SPEC-W-001, 002 y 003:** siguen en `en-revision` en `tasks.json` aunque su verificación está en verde y todo lo posterior depende de ellas; no se tocan aquí.
- **Sin prototipo.** `docs/cuadre-interfaz.html` no trae pantallas de gestor ni de «Mi gestor»; el diseño sale de los tokens y de componentes ya hechos (hoja del 303 y del 130, listas de facturas y de gastos). Lo que el prototipo no fija lo decide la skill de diseño sin cambiar los tokens.
- **El IBAN** que la política de `business_profiles` deja leer al gestor se enseña tal cual (P-01); si se decide ocultarlo, es una columna menos en la lectura del perfil del gestor, no un cambio de política.

### B.2 Hito 1 · SQL, correo y acceso · 2026-11-12

**Qué hay.** Dos migraciones nuevas (`20261112100000_gestor_notes.sql` y `20261112100100_gestor_functions.sql`), el paquete `cuadre/notifications/` (correo detrás de `EmailSender`), el paquete `cuadre/gestor/` y `api/routes_gestor.py` con las seis rutas de acceso, y `gestor_notes` en `rls_matrix.yaml`. Sin pantallas y sin lecturas del gestor (hitos 2 a 4).

| Pieza | Contenido |
|---|---|
| `public.gestor_notes` | Solo de añadir (trigger, también para funciones `SECURITY DEFINER`), sin claves foráneas, RLS forzada: el dueño lee las de su cuenta, el gestor las suyas con vínculo activo, el administrador ninguna; **sin escritura directa** |
| `app.invite_gestor_access` | Minúsculas, formato, no a uno mismo, retira las caducadas de esa pareja, límite de 5 con cerrojo asesor, registra `gestor_access.invited` |
| `app.list_gestor_invitations` | Las pendientes no caducadas del gestor con el nombre de quien invita |
| `app.log_gestor_read` | `gestor.read` solo con vínculo activo; tipos cerrados y `metadata` solo con `year` y `quarter` numéricos |
| `app.add_gestor_note` | Vínculo activo, texto 1 a 2.000, entidad existente **y del autónomo**; registra `gestor.note_added` sin el texto |
| `cuadre/notifications/` | `EmailMessage`, `EmailSender`, `ConsoleEmailSender` (dirección enmascarada y tipo; nunca asunto ni cuerpo), `MemoryEmailSender` (con `fail`), `UnavailableEmailSender`, `get_email_sender` y la plantilla de la invitación |
| `cuadre/gestor/` y rutas | `invite_gestor_access`, `list_gestor_accesses`, `revoke_gestor_access` (`usuario`) y `list_gestor_invitations`, `accept_gestor_invitation`, `decline_gestor_invitation` (`gestor`), con errores en problem+json |

**Decisiones al implementar** (corrigen o completan la spec, ya actualizada en §5.2 y §5.3):

| Tema | Decisión |
|---|---|
| **`gestor_notes` sin `INSERT` directo** | Se escribe solo por `app.add_gestor_note` (la spec decía `grant insert` y una política): así el vínculo, que lo anotado es del autónomo y el registro van en una sola transacción |
| **Invitar es una función** | La política de inserción directa de SPEC-W-001 se **mantiene** (sus pruebas la usan); la API solo usa `app.invite_gestor_access`. Retirar la directa queda anotado como endurecimiento posterior |
| **Caducadas** | El índice único parcial cuenta una invitación pendiente caducada como abierta; la función la retira (a `revoked`) al volver a invitar y la API la muestra como `expired` (derivado, no es un estado de la base) |
| **Correo después del commit** | Se envía en la misma petición, tras confirmar la transacción (ADR-0016); si falla, la invitación sigue pendiente y la respuesta lleva `email_sent: false` (se registra solo el id) |
| **Producción sin proveedor** | Una primera versión hacía fallar el arranque de la API; rompía dos pruebas que construyen la aplicación en producción y bloqueaba todo por una sola ruta. Ahora se avisa al arrancar (`email_provider_missing`) y `UnavailableEmailSender` hace fallar cada envío de forma explícita |
| **`not_the_owner`** | Se traduce a `404` igual que «no encontrado»; en la práctica la API no lo alcanza (revocar exige el rol `usuario`), pero una prueba directa fija la tabla de traducciones |
| **Función de tabla** | `app.list_gestor_invitations()` se consulta con `SELECT * FROM`; el gestor no puede leer el perfil del autónomo antes de aceptar |

**Pruebas.** **70 de API y correo** (`backend/tests/gestor`, 57, y `backend/tests/notifications`, 13) y **77 de SQL** (`test_gestor_functions.py`, 71, y `test_gestor_functions_extra.py`, 6) más la fila nueva de la matriz de RLS; 16 de ellas (las 6 extra y las 10 de `test_error_mapping.py`) nacieron de las mutaciones. Lo que cubren: invitar y su correo; **sin enumeración** (misma respuesta y mismo correo para un gestor, un autónomo, el administrador y nadie); límites (a uno mismo, duplicado, 5 abiertas, con una **carrera real** de dos transacciones); aceptar, rechazar y revocar (revocar corta el acceso a la petición siguiente) y quién puede cada cosa; registro de lecturas y de anotaciones sin datos; privacidad en los registros (consola enmascarada); contrato.

**Resultados medidos:**

| Qué | Resultado |
|---|---|
| `backend/tests/gestor`, `backend/tests/notifications` y `agents/test_selection.py` y `api/test_errors.py` (los dos que rompió la primera versión del guardia de producción) | **125 correctas** (tras el arreglo) |
| RLS completa, con la base recién reiniciada, **antes** de añadir las 6 pruebas extra | **1.652 correctas** (1.561 + 91); las 6 extra pasan por separado |
| Backend sin RLS completo, **antes** del arreglo de producción | 4.028 correctas y 2 fallos (los de arriba); los 2 pasan ya por separado |
| `ruff`, `export_openapi --check`, `gen:api --check`, `lint`, `typecheck` y 260 unitarias del frontend | código 0 |

**Pendiente de repetir (resuelto en el hito 2):** la pasada completa del backend sin RLS tras el arreglo (4.133 correctas) y la de RLS (1.652 correctas, con la base reiniciada) se repitieron el 2026-11-12; ver B.3.

**Mutaciones.** **45 mutaciones** (27 de las funciones SQL aplicadas con `create or replace` y restauradas, 18 de Python), con un ejecutor desechable fuera del repositorio: **45 detectadas, ninguna equivalente** (la del guardia de producción se rehízo tras el arreglo: detectada). La primera tanda dejó cinco vivas: el cerrojo asesor (la prueba con hilos no forzaba la carrera: ahora una transacción abierta retiene el límite para la siguiente), una factura y un documento de otro autónomo (solo se probaba un gasto), un tipo de entidad libre (el id coincidía con un documento) y el `403` por SQL (no es alcanzable por la API: se fijó con una prueba de la tabla de traducciones).

**Lo que no se ha comprobado:**
- **Un proveedor de correo real**: solo consola, memoria y el «no disponible» de producción (DEP-05).
- **El `INSERT` directo de `gestor_access`**: sigue vivo y se salta el límite y el registro de `gestor_access.invited`; no es alcanzable por la API (Data API desactivada).
- **Pantallas y lecturas del gestor**: hitos 2 a 4.

**Para el hito 2** (API de lectura del gestor):
- `owner_scope` con `app.log_gestor_read` en la **misma transacción** que la lectura (si falla el registro, no se devuelve el dato), `404` uniforme sin vínculo vigente, cartera con pendientes (`documents.status = 'review'`) y las lecturas por autónomo con dueño explícito (también el 303 y el 130), descargas por URL firmada y rutas de anotaciones (`app.add_gestor_note`) y de actividad (`activity_log` por cursor).
- Lecturas de `cuadre.quarters`, facturas, gastos, documentos, clientes y perfil: hoy filtran por `auth.uid()`; pasan a recibir el dueño y siguen apoyándose en la RLS.

### B.3 Hito 2 · API de lectura del gestor · 2026-11-12

**Qué hay.** Una migración (`20261112100200_read_owner.sql`), `cuadre/gestor/scope.py` (`owner_scope`), `cuadre/gestor/reads.py` (`GestorReadService`), `api/routes_gestor_reads.py` con 16 rutas (la cartera, la ficha, facturas con su PDF, gastos, documentos con su original, perfil, clientes, 303, 130, anotaciones del gestor, anotaciones del autónomo y actividad) y cambios mínimos en los repositorios de facturas, gastos, documentos, perfil, clientes y trimestres. `backend/openapi.json` y `frontend/src/api/schema.d.ts` regenerados. Sin pantallas.

**Decisiones al implementar** (corrigen o completan la spec, ya actualizada en §5.1, §5.3 y §5.4):

| Tema | Decisión |
|---|---|
| **Dueño de la lectura** | En lugar de un parámetro `owner` en cada consulta (el plan), las lecturas filtran por `private.read_owner()`, que devuelve el ajuste local `cuadre.read_owner` o, si no existe, `auth.uid()`. Se fija con `set_config(..., true)` solo **después** de que `app.log_gestor_read` haya comprobado el vínculo. El camino del autónomo no lo fija nunca: sus consultas devuelven lo mismo y su suite entera sigue en verde sin tocarla. Menos superficie que añadir un parámetro a una decena de funciones |
| **404 uniforme** | El `42501` de `app.log_gestor_read` se traduce a un único `404` (`not_found`): sin vínculo, revocado, caducado, de otro gestor o inexistente son indistinguibles |
| **Registro y lectura, una transacción** | Si la lectura falla después del registro (p. ej. una factura que no existe), tampoco queda la entrada; un periodo rechazado (`422`) no abre nada ni registra nada |
| **Cartera** | Una entrada `portfolio` **por autónomo enseñado** (la spec decía que no se registraba por autónomo); sin autónomos, nada |
| **Paginación** | Facturas: `limit` 1–200 y `offset`; gastos: cursor y hasta 100; actividad: cursor por `id`, de 50 en 50. Las del autónomo no cambian (AC-23) |
| **Descargas** | URL firmada de ≈ 60 s con el JWT **del gestor** (RLS del Storage), después del commit; se registra el recurso, nunca la URL |
| **Gastos anulados** | El gestor los ve con `voided_at`; el autónomo no (parámetro `include_voided` solo en el camino del gestor) |
| **Documentos** | Solo `review` y `extraction_failed`; el original de un descartado o en subida es `404` |
| **Periodo de los borradores** | Va en `metadata` (`year`, `quarter`), ya resuelto si no se pidió; se registra solo si el periodo es válido |

**Pruebas.** `backend/tests/gestor` tiene **160 pruebas**: 57 del hito 1 y **103 de este** — cartera (14), aislamiento y revocación (14), lecturas contra los 303 y 130 de B.1 de SPEC-W-008 y SPEC-W-009 comparadas **cuerpo a cuerpo** con las del propio autónomo (31), registro de lecturas (8), anotaciones (9), actividad (5), solo lectura (15, con todas las tablas financieras), privacidad y tamaños (3) y extras nacidos de las mutaciones (4). Las 2.602 pruebas de SPEC-W-005 a 009 siguieron en verde tras tocar sus repositorios.

**Resultados medidos (2026-11-12, todos con código 0):**

| Qué | Resultado |
|---|---|
| Backend sin RLS completo (incluye la pasada pendiente del hito 1) | **4.133 correctas**, 1.652 deseleccionadas (RLS) |
| RLS completa, con la base recién reiniciada (`supabase db reset`; aplica `read_owner` desde cero) | **1.652 correctas** |
| `ruff check`, `ruff format --check`, `export_openapi --check`, `gen:api --check` | código 0 |
| Frontend: `lint`, `typecheck` y `test:unit` con el esquema nuevo | código 0; **260 de 260** unitarias |

**Mutaciones.** Ejecutor desechable fuera del repositorio, **37 mutantes** (2 de `private.read_owner`, 5 de `scope.py`, 30 de `reads.py` y de las rutas): **35 detectadas y 2 equivalentes**. Los dos equivalentes son P03 (cartera que admite también `pending`) y P04 (cartera sin filtrar por gestor): los cubre otra capa, no la consulta — la RLS de `gestor_access` limita al gestor a sus filas y la de `profiles` solo le deja leer el perfil con vínculo **activo**, así que la unión descarta cualquier otra fila (se comprobó con una fila pendiente que ya nombra al gestor). **Un hueco real:** P15 (el gestor sin los clientes archivados) sobrevivió porque ninguna prueba tenía un cliente archivado; se añadió la prueba y ahora se detecta. Una tanda previa cortada por falta de memoria dejó P15 aplicado en `reads.py`; se detectó, se restauró y se comprobó.

**Lo que no se ha comprobado:**
- **Tamaño de respuesta a escala:** AC-23 está cubierto por construcción y con la siembra de B.1, no con 5.000 autónomos ni 200 facturas reales.
- **Descargas con Storage real:** las URL firmadas se prueban con un Storage de mentira que apunta lo que se le pide (ruta, JWT del gestor y vida de 60 s); no se ha firmado contra el Storage local ni el de producción.
- **Pantallas y E2E:** hitos 3 a 5.

**Para los hitos 3 y 4.** Las pantallas piden las listas del gestor por páginas (facturas con `offset`, gastos con `next_cursor`, actividad con `next_cursor`); la ficha usa `get_gestor_autonomo` y las descargas devuelven `{url, expires_in}`, no bytes.
