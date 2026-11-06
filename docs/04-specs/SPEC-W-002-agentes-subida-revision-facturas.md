---
tipo: spec
id: SPEC-W-002
titulo: Cliente de agentes, subida de factura de compra y pantalla de revisión
estado: en-progreso
prioridad: must
riesgo: alto
historias: [US-001, US-011]
requisitos: [RF-008, RF-009]
nfr: [NFR-01, NFR-07, NFR-10, NFR-11]
restricciones: [RES-01, RES-02, RES-06, RES-07]
adr: [0003, 0004, 0006, 0012, 0015, 0016]
depende_de: [SPEC-W-001]
bloquea: [SPEC-W-003, SPEC-W-016]
fecha: 2026-11-04
---

# SPEC-W-002 · Cliente de agentes, subida de factura de compra y pantalla de revisión

> Primera spec con datos financieros reales del usuario y primera que cruza la frontera con cuadre-agents. Entrega el camino
> **archivo o foto → Storage privado → lectura por el agente → pantalla de revisión**. Lo que **no** hace es decidir si un gasto
> es correcto ni registrarlo: eso es SPEC-W-003 (RES-01: el modelo lee, el código valida).

## 1. Contexto

**Situación de partida.** SPEC-W-001 deja identidad, tres roles, RLS demostrada, API con JWKS, frontend con portadas, E2E y CI. No existe
ninguna tabla de documentos ni de gastos, ni cliente de agentes, ni bucket de Storage. `contracts/` (v1.0.0) ya define el contrato C1
(`POST {AGENTS_BASE_URL}/v1/extract`) con sus modelos Pydantic, esquemas JSON y seis ejemplos sintéticos. El prototipo
(`docs/cuadre-interfaz.html`, pantalla Gastos) fija el flujo: subir → «leyendo» → «para revisar» con los campos dudosos marcados.

**Por qué es de riesgo alto.** (1) Cruza datos fiscales a un servicio externo con una URL firmada: si se filtra o dura de más, es una fuga
(NFR-11). (2) La respuesta de un modelo es entrada no confiable: puede traer instrucciones ocultas (NFR-07) o importes mal formados
(RES-02). (3) Es la primera tabla con archivos, y el aislamiento de Storage no lo cubre la matriz de RLS de tablas.

**Decisiones vigentes** (no se reabren aquí): ADR-0012 (el repositorio no llama a ningún modelo; todo pasa por `AgentsClient` con
`FakeAgentsClient` y `HttpAgentsClient`, que se activa solo si existe `AGENTS_BASE_URL`); ADR-0004 (bucket privado `documents`,
ruta `{owner_id}/{document_id}.{ext}`, subida con URL firmada, lectura del agente con URL firmada de ≈120 s emitida con el token del
usuario); ADR-0006 (importes en céntimos; el contrato manda cadenas `"120.00"` y la web las convierte en el borde); CONF-001 (a) y D3
(el gestor no escribe; el administrador no ve datos financieros).

**Decisiones de diseño que esta spec propone y que quedan a tu visto bueno** (cada una trae su recomendación y qué cambia si la rechazas):

| ID | Decisión propuesta | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Subida directa del navegador a Storage** con URL firmada (ADR-0004), y comprobación de la firma del archivo en el servidor al completar | Subir a través de la API: valida antes de guardar, pero **ya no es una alternativa**: Vercel limita el cuerpo de una petición a 4,5 MB y aquí el límite es de 15 MiB (ADR-0016). Si el spike del hito 0 muestra que Storage no admite la subida desde el navegador (`localhost:3000`), se reabre esta decisión y, con ella, el límite de D-03 |
| D-02 | **La lectura ocurre dentro de la petición**: `complete` y `retry` esperan al agente (hasta 45 s) y responden con el estado final. El estado vive en la base de datos y el sondeo de la pantalla solo cubre recargas y lecturas interrumpidas. Sin `BackgroundTasks`, cola ni worker | `BackgroundTasks` (propuesta anterior): en Vercel no se puede contar con trabajo posterior a la respuesta (ADR-0016). Cola (Vercel Queues): fiable, pero un servicio más que no hace falta para una persona y 5 lecturas simultáneas. Si la petición se interrumpe, el documento queda en «No se pudo leer» pasados 120 s y se reintenta a mano |
| D-03 | **Límites: 15 MiB por archivo; PDF, JPG, PNG, HEIC y WebP; 5 lecturas simultáneas por usuario** | Subirlos exige tocar tres sitios a la vez (CHECK, bucket y API) y un test que comprueba que coinciden |
| D-04 | **Vista previa del original** en la pantalla de revisión con URL firmada de 60 s (PDF e imágenes; HEIC solo descarga). **Descartar borra el archivo**; lo ya registrado se conservará (SPEC-W-003, CONF-004) | No mostrar el original: la persona no podría verificar un NIF ilegible contra el documento |
| D-05 | **La cámara móvil entra ya** (`<input capture="environment">`); US-011 es *Must* y no cuesta más | Aplazarla a SPEC-W-016: se pierde la prueba temprana en 390 px |
| D-06 | **`FakeAgentsClient` recorre los fixtures en orden fijo** (completa, NIF dudoso, suma que no cuadra, ticket, instrucciones ocultas, ilegible). Con `APP_ENV=production` y sin `AGENTS_BASE_URL`, **la API no arranca**: nunca un simulacro silencioso en producción | Cliente simulado también en producción: peligroso, nadie lo notaría |
| D-07 | **Se guarda la extracción normalizada** (céntimos y textos acotados), no la respuesta cruda del agente, y las correcciones de la persona en un campo aparte (`review`) | Guardar la cruda: más fiel, pero conserva texto sin acotar de una fuente no confiable |

*Revisión del 2026-11-04 (ADR-0016): al decidir que el backend se despliega en Vercel Functions, D-01 y D-02 se reescribieron. Siguen siendo propuestas a tu visto bueno, igual que D-03 a D-07.*

*Visto bueno del 2026-11-05: la persona revisó ADR-0016 y D-01 a D-07 y pidió seguir con la fase siguiente; se tratan como aprobadas y la spec pasa a `en-progreso`. El spike del hito 0 comprobó el supuesto de D-01 (subida directa del navegador a Storage, sin plan B): funciona en local, ver Anexo B.*

## 2. Objetivo

Al terminar esta spec:

1. Una persona con rol `usuario` puede **subir una o varias facturas de compra** (PDF, JPG, PNG, HEIC o WebP) desde un archivo o con la
   **cámara del móvil**, y ver cómo cada una pasa a «Leyendo…» y luego a «Para revisar» (RF-008, US-011).
2. La web **pide la lectura a cuadre-agents a través de `AgentsClient`** (simulado o HTTP), con una URL firmada de unos 120 s, y guarda el
   resultado **normalizado** (importes en céntimos, textos acotados), marcando los campos dudosos y las sospechas de inyección (RF-009, US-001).
3. La **pantalla de revisión** muestra lo leído junto al original, marca los campos dudosos, deja corregirlos y guardar el borrador, volver a
   leer si falló o descartar. **No registra ningún gasto**: el botón llega desactivado hasta SPEC-W-003.
4. Los archivos están **aislados por Storage y por RLS**: el dueño ve los suyos, el gestor con vínculo activo puede leerlos, el administrador
   y cualquier otra cuenta no (NFR-06), y esto lo prueba una batería, no una promesa.
5. Ni las URLs firmadas, ni los tokens, ni el contenido de los documentos, ni los nombres de archivo salen en logs (NFR-11).

## 3. Alcance explícito

### 3.1 Cliente de agentes (`cuadre.agents`)
- Interfaz `AgentsClient` (`typing.Protocol`) con `extract_invoice(...)`. (`stream_chat` lo añade SPEC-W-004; añadir un método no rompe a nadie.)
- `FakeAgentsClient` con los fixtures de `contracts/examples/extract/` (D-06) y errores simulables; en los tests se inyecta un guion exacto.
- `HttpAgentsClient` (`httpx2`): `Authorization: Bearer <AGENTS_API_KEY>`, `X-Cuadre-Contract-Version: 1`, `X-Request-Id`, tiempo máximo de 45 s
  en total, reintento acotado, validación de la respuesta con los modelos de `cuadre_contracts` y mapeo de errores.
- Selección por entorno (`get_agents_client(settings)`) y dependencia `cuadre-contracts` del backend.
- **Normalización** de la respuesta: cadenas decimales → céntimos enteros, textos acotados y limpios (§5.3). Es lo único que se guarda.

### 3.2 Base de datos y Storage (migraciones)
- Enums `document_status` y `upload_source`; tabla `documents` con RLS activada y forzada; funciones `app.*` para cada transición y un trigger
  que impide transiciones inválidas; eventos en `activity_log`.
- Bucket privado `documents` (tamaño y tipos limitados) con políticas sobre `storage.objects`; funciones auxiliares `private.document_*`.
- `documents` registrada en `backend/tests/rls/rls_matrix.yaml`.

### 3.3 Backend (FastAPI)
- Rutas `upload_document`, `complete_document_upload`, `list_documents`, `get_document`, `get_document_preview`, `save_document_review`,
  `retry_document_extraction` y `discard_document` (§5.1), solo para el rol `usuario`.
- Módulo de Storage (`cuadre.documents`): emite URL firmada de subida, lee la cabecera del archivo, emite URL firmada de lectura de ≈120 s para el
  agente y de 60 s para la vista previa, y borra el archivo; **siempre con el JWT del usuario, nunca con la service key**.
- Lectura dentro de la petición `complete` / `retry` (D-02; sin trabajo posterior a la respuesta), límite de lecturas simultáneas, errores `problem+json` nuevos (§5.1) y registro sin datos sensibles.

### 3.4 Frontend (Next.js)
- Apartado **Gastos** (`/gastos`) activo para `usuario`: zona de subida (archivos y «Hacer una foto»), lista de documentos con su estado y recarga
  mientras alguno se lee.
- Pantalla de revisión (`/gastos/[id]`): formulario de lo leído con los dudosos marcados (texto e icono, no solo color), original al lado, guardar,
  volver a leer, descartar y «Registrar gasto» desactivado.
- `parseCents` / `formatCents` (ADR-0006) en `src/lib/money.ts`, con pruebas unitarias.
- Tokens de diseño del prototipo, etiqueta en cada campo, foco visible, sin scroll horizontal a 390 y 1.440 px.

### 3.5 Pruebas
- `backend/tests/agents/`, `backend/tests/documents/`, `backend/tests/rules/test_vercel_compat.py` (T2-13 y T2-14), ampliación de `backend/tests/rls/` (tabla y `storage.objects`), unitarias del frontend y
  `frontend/e2e/gastos-subida.spec.ts` en los tres motores y los dos anchos.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Validar NIF, fecha, cuota, suma y duplicados; **confirmar y registrar** el gasto; categorías; gastos sin factura | SPEC-W-003 |
| Que `injection_suspected` **obligue** a revisar antes de registrar (aquí solo se guarda y se muestra) | SPEC-W-003 (NFR-07) |
| Pantalla del gestor para ver los documentos de sus usuarios | SPEC-W-010 (aquí solo la política de Storage y de la tabla) |
| Chatbot y servidor MCP | SPEC-W-004 y W-011 |
| Activar el `HttpAgentsClient` contra el servicio real | Depende de la SPEC-A de lectura de facturas en cuadre-agents; aquí se prueba contra un servidor simulado |
| Borrado de archivos huérfanos (`uploading` abandonados), exportación y cierre de cuenta | Tarea de mantenimiento futura y SPEC-W-017 (CONF-004) |
| Contador de pendientes en la navegación, arrastrar y soltar, subida por correo | Fuera de la v1 (el reenvío por correo está en *Won't have*) |
| Lectura local sin agente (OCR propio) | Fuera de la v1 (ADR-0012) |

## 5. Contrato de interfaces

### 5.1 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador). Errores en `application/problem+json` como en SPEC-W-001.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `upload_document` | `POST /api/documents` | Cuerpo `{ "filename": string, "mime_type": enum, "size_bytes": int, "source": "file"\|"camera" }`. **201** `{ "id": uuid, "status": "uploading", "upload": { "url": string, "method": "PUT", "headers": { "Content-Type": string } }, "max_bytes": int }`. `upload.url` es la URL completa de Storage (`{SUPABASE_URL}/storage/v1/object/upload/sign/documents/{ruta}?token=…`; Storage la devuelve relativa y la API la compone); vale 2 h y admite **una sola** subida (Anexo B). `headers["Content-Type"]` es el tipo declarado |
| `complete_document_upload` | `POST /api/documents/{id}/complete` | Sin cuerpo. Comprueba, con el JWT del usuario, que el archivo existe, que su tamaño y el tipo que Storage registró son los declarados y que su **firma** (primeros 32 bytes, con `Range`; nunca se descarga el archivo entero) coincide con el tipo; pasa a `processing` y **lee el documento dentro de esta misma petición** (hasta 45 s, D-02). **200** `{ "id", "status" }` con el estado final: `review` o `extraction_failed`. Idempotente: en `processing` (otra petición lo está leyendo), `review` o `extraction_failed` responde con el estado actual sin lanzar otra lectura |
| `list_documents` | `GET /api/documents` | Los documentos de la persona que no están `uploading` ni `discarded`, del más reciente al más antiguo: `[{ id, status, original_filename, mime_type, created_at, doc_type, supplier_name, total_cents, doubtful_count, injection_suspected, error }]` |
| `get_document` | `GET /api/documents/{id}` | El documento completo (§5.3). Un `processing` con más de 120 s sin cambios se presenta como `extraction_failed` con `error.code = "timeout"` (sin escribir nada en un GET); es lo que se ve si se interrumpió la petición que lo leía |
| `get_document_preview` | `GET /api/documents/{id}/preview` | `{ "url": string, "expires_in": 60, "previewable": bool }`; `previewable` es `false` para HEIC |
| `save_document_review` | `PUT /api/documents/{id}/review` | Cuerpo = lo editable de §5.3 (`review`). Valida **la forma** (tipos, fechas ISO, importes en céntimos, longitudes), no la fiscalidad. **200** con el documento. Solo en `review` o `extraction_failed` (relleno a mano) |
| `retry_document_extraction` | `POST /api/documents/{id}/retry` | Solo en `extraction_failed` o `processing` caducado. Reutiliza el mismo `document_id` (la lectura es idempotente por él) y, como `complete`, **lee dentro de la petición**: **200** `{ "id", "status" }` con `review` o `extraction_failed` |
| `discard_document` | `DELETE /api/documents/{id}` | **204**. Pasa a `discarded` y borra el archivo. Estados `uploading`, `processing`, `review`, `extraction_failed` |

`operation_id` del prototipo reservados para SPEC-W-003: `validate_extraction`, `confirm_document`, `create_expense`.

**Códigos de error nuevos** (`code`, HTTP): `unsupported_file_type` 415 · `file_too_large` 413 · `file_type_mismatch` 422 (la firma del archivo no es la del tipo declarado; el documento queda
`discarded` y no se llama al agente) · `upload_missing` 409 (se completó sin haber subido) · `upload_size_mismatch` 422 · `document_not_found` 404 (también si es de otra persona: no se distingue) ·
`document_wrong_state` 409 · `too_many_processing` 429 (5 lecturas simultáneas, con `Retry-After`) · `storage_unavailable` 503.

**Detalle fijado en el hito 3** (Anexo B.5):
- `upload_size_mismatch` **también descarta el documento y borra el archivo**, igual que `file_type_mismatch`: una URL de subida admite una sola subida, así que el archivo no se puede reemplazar. `upload_missing` deja el documento en `uploading` y se puede volver a completar.
  El tipo que Storage registró (cabecera `Content-Type` del `PUT`, sin parámetros y sin distinguir mayúsculas) también debe ser el declarado; si no, `file_type_mismatch`.
- Para la persona un documento `discarded` ya no existe: `get_document` y `get_document_preview` responden `404 document_not_found`. La vista previa de un `uploading` es `409 document_wrong_state`.
- `Retry-After`: 10 s en `429 too_many_processing`, 5 s en `503 storage_unavailable`. `list_documents` devuelve como mucho 200 documentos (la paginación llegará con SPEC-W-003, cuando haya `registered`).
- `error` es `{ "code", "message" }` con uno de los ocho motivos de abajo; `get_document` y `list_documents` no exponen la ruta de Storage, la traza del agente ni su coste.
- Si la reserva se hizo pero Storage no puede firmar la subida, el documento se descarta y la respuesta es `503 storage_unavailable`. Un fallo de Storage al firmar la lectura deja el documento en `extraction_failed` con motivo `internal` (200), no en `processing`.
- Si el documento se descarta mientras se está leyendo, `complete` responde `200` con `status: "discarded"` y no guarda la lectura.

**Estados.** `uploading` → `processing` → `review` | `extraction_failed`; `extraction_failed` → `processing` (reintento); `uploading`, `processing`, `review`, `extraction_failed` → `discarded`.
`registered` existe en el enum pero **ninguna ruta de esta spec lleva a él** (lo introduce SPEC-W-003 ampliando el trigger).

**Motivos de fallo (`error.code`)** y su texto en español: `unreadable` «No hemos podido leer el documento. Prueba con una foto más nítida o rellena los datos a mano.» · `unsupported_media_type` «Este tipo de
archivo no se puede leer.» · `payload_too_large` «El archivo es demasiado grande para leerlo.» · `timeout` «La lectura ha tardado demasiado.» · `upstream_error` y `agents_unavailable` «El servicio de lectura no está
disponible ahora. Puedes reintentarlo o rellenar los datos a mano.» · `invalid_response` «La lectura ha devuelto datos que no se pueden usar.» · `internal` «No se ha podido completar la lectura.» El texto nunca incluye la respuesta del agente.

### 5.2 Base de datos y Storage

Migraciones nuevas (nombre `YYYYMMDDHHMMSS_descripcion.sql`, sin migraciones destructivas). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`.

```
CREATE TYPE document_status AS ENUM ('uploading','processing','review','extraction_failed','discarded','registered');
CREATE TYPE upload_source   AS ENUM ('file','camera');

documents                                                   -- tabla financiera
  id                  uuid PK DEFAULT gen_random_uuid()
  owner_id            uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE
  status              document_status NOT NULL DEFAULT 'uploading'
  source              upload_source NOT NULL
  original_filename   text NOT NULL CHECK (char_length(original_filename) BETWEEN 1 AND 255)
  mime_type           text NOT NULL CHECK (mime_type IN ('application/pdf','image/jpeg','image/png','image/heic','image/webp'))
  size_bytes          bigint NOT NULL CHECK (size_bytes BETWEEN 1 AND 15728640)            -- 15 MiB
  storage_path        text NOT NULL UNIQUE                                                   -- '{owner_id}/{id}.{ext}'
  extraction          jsonb                       -- ExtractedInvoice normalizado (§5.3); NULL hasta que haya lectura
  review              jsonb                       -- correcciones de la persona; NULL hasta que guarda
  injection_suspected boolean NOT NULL DEFAULT false
  error_code          text                        -- motivo de extraction_failed
  agent_trace_id      text
  agent_cost_eur      numeric(9,6)
  created_at, uploaded_at, extracted_at, updated_at   timestamptz
  CHECK (status <> 'review' OR extraction IS NOT NULL)
  CHECK (status <> 'extraction_failed' OR error_code IS NOT NULL)
```

La ruta de Storage **nunca** contiene el nombre de archivo de la persona: solo `owner_id`, `id` y la extensión del tipo. Los 15 MiB aparecen en la CHECK, en el bucket y en la API; un test comprueba que coinciden.

**CHECK añadidas en el hito 1** (la base no se fía de que la API haya validado; CLAUDE.md: las reglas críticas van en la base):
- `storage_path = owner_id/id.ext`, con `ext` ∈ `pdf`, `jpg`, `png`, `heic`, `webp` según `mime_type`: no hay forma de reservar otra ruta ni de meter el nombre del archivo (T2-07).
- `error_code` ∈ `unreadable`, `unsupported_media_type`, `payload_too_large`, `timeout`, `upstream_error`, `agents_unavailable`, `invalid_response`, `internal` (§5.1).
- **Importes enteros** en `extraction` y `review` (RES-02, T2-02): ambos son objetos JSON y `total_cents`, `tax_breakdown[*].base_cents`, `tax_breakdown[*].vat_cents` y `withholding.amount_cents` son enteros JSON o nulos (no `12.5`, ni `12.0`, ni `"120.00"`, ni más de 15 cifras). AC-03 queda garantizado también si la API fallara.

**Privilegios.** `authenticated`: `SELECT` y nada más. Ninguna escritura directa: todo por funciones.

**Políticas de `documents`:**

| Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|
| SELECT | las suyas | las de usuarios con vínculo activo (`private.gestor_has_access(owner_id)`) | **ninguna** |
| INSERT / UPDATE / DELETE | denegado (solo `app.*`) | denegado | denegado |

**Funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`, verifican `auth.uid()` y `private.app_role() = 'usuario'`, escriben `activity_log` en la misma transacción; error `P0001` con código estable, `42501` si el rol no basta):

| Función | Efecto |
|---|---|
| `app.create_document(p_filename, p_mime, p_size, p_source)` | Crea la fila en `uploading` con su `storage_path` y devuelve `(document_id, object_path)`. Falla con `too_many_processing` si ya hay 5 lecturas en curso (aviso rápido, AC-12). No registra actividad: aún no hay nada subido |
| `app.mark_document_uploaded(p_id)` | `uploading` → `processing`; `uploaded_at = now()`. Registra `document.uploaded`. **Aquí se impone el límite de 5 lecturas simultáneas** (empieza la lectura), con un cerrojo asesor por persona para que dos peticiones a la vez no lo superen; si no cabe, falla con `too_many_processing` y el documento sigue en `uploading` |
| `app.record_extraction(p_id, p_extraction, p_injection, p_trace, p_cost)` | `processing` → `review`; guarda la extracción normalizada, la marca de inyección, la traza y el coste. Registra `document.extracted` |
| `app.fail_extraction(p_id, p_code)` | `processing` → `extraction_failed`. Registra `document.extraction_failed` |
| `app.retry_document(p_id)` | `extraction_failed` (o `processing` con más de 120 s) → `processing`, limpia `error_code`; cuenta para el límite como `mark_document_uploaded` |
| `app.save_document_review(p_id, p_review)` | Guarda `review` en `review` o `extraction_failed`; el estado no cambia. `p_review` nulo: `invalid_review` |
| `app.discard_document(p_id)` | → `discarded`. Registra `document.discarded` con `{from_status}` |

**Lecturas en curso.** Para el límite no cuentan los `processing` con más de 120 s sin cambios (§5.1 ya los presenta como fallidos): una lectura interrumpida no ocupa un sitio para siempre. El 5 y los 120 s viven en SQL (`private.document_max_processing()` y `private.document_processing_timeout()`); en el hito 3 se decide si `MAX_PROCESSING_PER_USER` sigue siendo una variable de la API o se retira.

Códigos: `document_not_found` (también para un documento ajeno), `document_wrong_state`, `too_many_processing`, `invalid_review`. **Trigger** `BEFORE UPDATE` (`documents_guard`):
- solo permite las transiciones de §5.1 (`uploading` → `processing` | `discarded`; `processing` → `review` | `extraction_failed` | `discarded`; `review` → `discarded`; `extraction_failed` → `processing` | `discarded`), más las actualizaciones sin cambio de estado en `processing` (reintento), `review` y `extraction_failed` (correcciones); `discarded` y `registered` son terminales;
- impide cambiar `id`, `owner_id`, `source`, `original_filename`, `mime_type`, `size_bytes`, `storage_path` y `created_at`;
- **congela la lectura original**: `extraction`, `injection_suspected`, `agent_trace_id` y `agent_cost_eur` solo cambian al pasar de `processing` a `review` (AC-14);
- mantiene `updated_at` (salvo que la sentencia lo fije a propósito, lo que permite a los tests envejecer filas).

Errores del trigger (red de seguridad; las funciones fallan antes con `document_wrong_state`): `document_invalid_transition`, `document_immutable_column`, `document_extraction_frozen`.

**`activity_log`** (categoría `data`, `owner_id` = la persona): `document.uploaded` `{document_id, mime_type, size_bytes, source}`, `document.extracted` `{document_id, injection_suspected, doubtful_count}`,
`document.extraction_failed` `{document_id, error_code}`, `document.discarded` `{document_id, from_status}`. **Nunca** nombres de archivo, NIF ni importes.

**Storage.** Bucket privado `documents` (`file_size_limit` 15 MiB, tipos permitidos = los cinco). Políticas sobre `storage.objects`, con funciones `private.document_*` (`SECURITY DEFINER`, `STABLE`):

| Operación | Quién |
|---|---|
| INSERT | `usuario` dueño de la carpeta **y** existe una fila `documents` suya en `uploading` con esa ruta (no se sube nada a rutas que la API no ha reservado). Sin `upsert`. Storage la evalúa **al firmar** la URL, no al subir (Anexo B) |
| SELECT | el dueño, y el `gestor` con vínculo activo sobre el dueño. Administrador: nada |
| UPDATE | denegado (los archivos no se sobrescriben) |
| DELETE | el dueño de la carpeta, mientras ninguna fila `registered` use esa ruta. Sin fila (archivo huérfano) también puede borrarlo |

Las rutas válidas tienen exactamente la forma `{uuid}/{archivo}`. Las funciones `private.document_*` **nunca lanzan**: una ruta rara (sin carpeta, con una carpeta de más, carpeta que no es un uuid, mayúsculas) se deniega, no es un error 500.

Las políticas de `storage.objects` no entran en `rls_matrix.yaml` (que cubre `public`); las prueban `test_storage_policies.py` (por SQL, con la misma tabla de cinco personas y los cinco estados del vínculo, `declined` incluido) y `test_storage_live.py` (contra la API real de Storage, con tokens ES256 de GoTrue).

**Comportamiento de Storage comprobado en el spike** (detalle y fuentes en el Anexo B): la URL de subida caduca a las 2 h, admite una sola subida (un segundo `PUT` recibe 409) y no se puede acortar; Storage **no inspecciona el contenido** ni cruza la extensión de la ruta con el tipo; los errores llegan con HTTP 400 y el código real en el cuerpo (`statusCode`), y un objeto ajeno responde igual que uno inexistente. El bucket lo crea `20261105100000_documents_bucket.sql` (hito 0); la tabla, las funciones y las políticas, `20261105100100`, `…200` y `…300` (hito 1).

### 5.3 Datos de la lectura

**Respuesta del agente → forma guardada.** `HttpAgentsClient` valida con `ExtractResponse` (`cuadre_contracts`) **en modo estricto** (ni un número donde va una cadena, ni una fecha como entero, ni `"true"` como booleano); cualquier fallo de validación es `invalid_response`. Después, `normalize_extraction` (`cuadre.agents.normalize`) la normaliza —y vuelve a comprobar todo lo que protege a la base, por si un cliente se saltara la validación—:

```
extraction (jsonb)
  doc_type            full_invoice | simplified_invoice | ticket | receipt | other | not_an_invoice
  supplier_name       string ≤ 200 | null          supplier_tax_id, recipient_tax_id   string ≤ 32 | null
  invoice_number      string ≤ 64 | null           issue_date   "YYYY-MM-DD" | null      currency   "EUR" | otra | null
  tax_breakdown       [ { vat_rate: "21", base_cents: 12000, vat_cents: 2520 } ]          -- ≤ 10 líneas; importes nulos si no se leen
  withholding         null | { rate: "15", amount_cents: 1800 }
  total_cents         int | null
  doubtful_fields     [ { field, line_index, reason, raw_text ≤ 200 } ]
  warnings            [ string ≤ 300 ]             -- ≤ 5
```

- **Importes (RES-02, ADR-0006).** Cada cadena debe cumplir `-?[0-9]{1,12}\.[0-9]{2}` **completa** (`fullmatch`, solo dígitos ASCII: `\d` casa dígitos de cualquier alfabeto —el modelo del contrato los deja pasar— y `$` admite un salto de línea final); se convierte con `Decimal` a céntimos enteros. Cualquier otra cosa invalida la respuesta entera. Los tipos (`vat_rate`, `rate`) quedan como cadenas decimales
  (`[0-9]{1,3}(\.[0-9]{1,2})?`). No hay `float` en ningún punto del camino.
- **Cotas.** Más de 10 líneas de IVA o más de 50 dudosos invalidan la respuesta entera (no se trunca dinero en silencio); `warnings` se recorta a los 5 primeros no vacíos; `line_index` fuera de `tax_breakdown` pasa a `null` (la duda se conserva en el campo); el coste del agente debe ser `< 1000` (`agent_cost_eur` es `numeric(9,6)`); `trace_id` se limpia y se recorta a 200.
- **Textos de una fuente no confiable.** Se normalizan a NFC, se eliminan los caracteres de control (Cc), de formato (Cf: ancho cero y **controles bidireccionales**, que sirven para suplantar texto) y los sustitutos sueltos (Cs: PostgreSQL no los admite en `jsonb`), se colapsan espacios y saltos de línea, se recorta a la longitud indicada y lo que queda vacío pasa a `null`. Se muestran siempre como texto (nunca HTML). No se interpretan, no se siguen enlaces ni se ejecuta nada.
- `injection_suspected` se guarda en su columna y se muestra como aviso; **no** cambia ninguna otra regla en esta spec.
- `review` tiene la forma de `extraction` sin `doubtful_fields` ni `warnings`: lo que la persona corrige. La interfaz muestra `review` si existe y `extraction` si no.

### 5.4 Cliente de agentes

```
class AgentsClient(Protocol):
    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse: ...   # lanza AgentsError(code, http_status, trace_id)
```

- `HttpAgentsClient`: presupuesto total de **45 s** (incluye el reintento); un reintento solo ante error de conexión, `429` (con `Retry-After` ≤ 5 s) o `502`; nunca ante un `4xx` ni un tiempo agotado. Mapeo: `422 unreadable` → `unreadable`, `413` → `payload_too_large`, `415` →
  `unsupported_media_type`, `401` → `agents_unavailable` (error de configuración: se registra, la persona ve el mensaje genérico), `502`/error de red → `upstream_error`/`agents_unavailable`, 45 s → `timeout`.
  Detalle fijado en el hito 2 (Anexo B.4): `5xx` y `429` sin reintento posible → `upstream_error`; error de conexión (tras su único reintento), `401`, `403`, `404` y redirecciones (no se siguen) → `agents_unavailable`;
  `400` y `422` con otro `code` (la petición que hemos enviado es la errónea) → `internal`; JSON roto, cuerpo de más de 1 MiB o respuesta que no cumple `ExtractResponse` → `invalid_response`. El `message` del agente no se usa nunca.
  El reintento solo se hace si, tras la pausa, quedan al menos 5 s de presupuesto; la pausa es `Retry-After` en segundos enteros (una fecha HTTP cuenta como ausente) o 500 ms ante un `502` o un error de conexión.
  Una conexión por llamada, sin redirecciones y sin proxies del entorno (la clave del servicio solo va a la URL configurada).
- `FakeAgentsClient`: recorre los seis fixtures en orden fijo y **cíclico** (cada llamada avanza, aunque sea el mismo documento: reintentar un ilegible en una demo da otra lectura); con un guion inyectado, lo sirve exacto y **falla si se agota**
  (`FakeScriptExhausted`: así se prueba que completar dos veces no lee dos veces). Los fixtures se cargan al primer uso y se validan con los mismos modelos.
- `document_url` la **genera siempre la API** con el JWT del usuario y `expiresIn ≤ 120`; nunca viene de una entrada de la persona. `AGENTS_BASE_URL` debe ser `https` salvo `APP_ENV=local`, y sin usuario, contraseña, consulta ni fragmento.
- Variables nuevas: `AGENTS_BASE_URL` (opcional; una cadena vacía cuenta como ausente), `AGENTS_API_KEY` (obligatoria si hay URL), `AGENTS_TIMEOUT_SECONDS` (45; de 1 a 120). Con `APP_ENV=production` y sin `AGENTS_BASE_URL`, `create_app` lanza y **la API no arranca** (D-06); en `staging` sin URL se usa el simulado y se avisa en el registro.
  `MAX_UPLOAD_BYTES` (15728640) y `MAX_PROCESSING_PER_USER` **no son variables de entorno**: el 5 vive en SQL desde el hito 1 (Anexo B.3) y los 15 MiB son una constante de `cuadre.documents.limits`, igual que en la CHECK y en el bucket (subirlos exige migración; una variable solo podría bajarlos y dejaría dos fuentes de verdad). `test_limits.py` compara los tres sitios.
  Dependencia nueva del backend: `cuadre-contracts==1.0.0` (no está en PyPI: se instala antes, `pip install -e contracts/python`; un test comprueba que el pin, `contracts/python/pyproject.toml` y `contracts/VERSION` coinciden y que README, CI y SPEC-W-001 §8.2 respetan el orden).
- **Storage** (`cuadre.documents`, `httpx2` contra `{SUPABASE_URL}/storage/v1`): basta `Authorization: Bearer <JWT del usuario>`; **no** hace falta `apikey` ni una variable nueva (la clave publicable sola actúa como `anon` y se deniega). Las respuestas de error traen HTTP 400 con `{"statusCode": "403"|"404"|"409"|"413"|"415", "error", "message", "code"}`: se interpreta el `statusCode` del cuerpo, no el de HTTP, y el texto de Storage no llega a la persona. Las rutas devueltas por Storage (`url`, `signedURL`) son relativas a `/storage/v1`.

### 5.5 Frontend

| Ruta | Quién | Contenido |
|---|---|---|
| `/gastos` | `usuario` | Subir archivos (`<input type=file multiple accept=".pdf,.jpg,.jpeg,.png,.heic,.webp">`) y «Hacer una foto» (`accept="image/*" capture="environment"`); lista de documentos con estado «Leyendo…», «Para revisar» o «No se pudo leer»; se actualiza sola mientras alguno se lee |
| `/gastos/[id]` | `usuario` | Revisión: original (vista previa o descarga), formulario, aviso de dudosos y de sospecha de inyección, «Guardar cambios», «Volver a leer», «Descartar» y «Registrar gasto» desactivado con «Próximamente» |

El flujo de subida lo orquesta un componente de cliente: acción de servidor `upload_document` → `PUT` del archivo a la URL firmada (el navegador nunca tiene el JWT) → acción de servidor `complete_document_upload`, que **espera la lectura** (hasta 45 s): mientras tanto la fila muestra «Leyendo…». El estado se
refresca con `router.refresh()` cada 2 s mientras haya algún documento en `processing`, para cubrir recargas de la página y lecturas interrumpidas. Un fallo en cualquier paso se muestra en la fila del archivo, con su motivo y la opción de reintentar, sin perder los demás.

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T2-01 | **Sin modelos de lenguaje en este repositorio** (RES-01, ADR-0012). Se mantienen `test_no_llm_sdk` y el resto de guardas de W-001; `cuadre.agents` solo habla con `cuadre-agents` por HTTP |
| T2-02 | **Sin `float`** en código, migraciones ni jsonb: importes en céntimos enteros; `Decimal` solo en la conversión. `test_no_float` sigue verde |
| T2-03 | **La service key no interviene**: la URL firmada de subida, la de lectura, la vista previa y el borrado usan el JWT del usuario. `test_service_key_scope` sigue verde |
| T2-04 | **Ni URLs firmadas, ni tokens, ni nombres de archivo, ni contenido en logs ni trazas** (NFR-11). Un test captura los registros de todo el flujo y busca `token=`, la URL firmada, el nombre del archivo y el NIF del fixture |
| T2-05 | **Toda respuesta del agente es dato no confiable**: se valida con los modelos del contrato, se normaliza y se acota; `injection_suspected` no valida ni deja de validar nada |
| T2-06 | **Solo `usuario` escribe documentos**; el gestor y el administrador reciben 403, y a nivel de base de datos no tienen política de escritura. El gestor solo lee con vínculo activo (revocar corta el acceso en la petición siguiente, también a Storage) |
| T2-07 | **Ruta de Storage sin datos de la persona** y solo reservada por `app.create_document`; sin sobrescritura |
| T2-08 | **La firma del archivo se comprueba en el servidor** (`%PDF-`, `FFD8FF`, `89504E47`, `ftyp` en el desplazamiento 4, `RIFF…WEBP`) antes de llamar al agente, junto con el tipo que Storage registró: Storage no mira el contenido ni la extensión (Anexo B) |
| T2-09 | **Una sola vez por documento**: la lectura es idempotente por `document_id`; completar dos veces no lanza dos lecturas |
| T2-10 | **Tiempo**: la web no añade latencia apreciable (NFR-01 es del agente, p95 ≤ 30 s): con el cliente simulado, de «completar» a «Para revisar» pasa menos de 3 s |
| T2-11 | **Interfaz**: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, anuncios con `aria-live`, sin scroll horizontal a 390 y 1.440 px en Chromium, Firefox y WebKit |
| T2-12 | **Migraciones sin datos reales**: el seed no añade documentos; los archivos de prueba son sintéticos (RES-07) y se generan en el test |
| T2-13 | **Sin trabajo posterior a la respuesta** (ADR-0016): las rutas no usan `BackgroundTasks` ni hilos que sobrevivan a la petición; la lectura ocurre dentro de `complete` y `retry`. Un test recorre `backend/src/cuadre` buscándolos |
| T2-14 | **Ningún archivo pasa por la API** (límite de 4,5 MB por petición en Vercel, ADR-0016): la subida va del navegador a Storage y el agente lee con otra URL firmada. Un test comprueba que el OpenAPI no declara `multipart/form-data` ni `application/octet-stream` |

## 7. Criterios de aceptación (Given-When-Then)

```gherkin
AC-01  Subida y lectura (US-001)
  Given una persona con rol usuario y una factura PDF de 200 KB
  When pide subirla, sube el archivo a la URL firmada y completa la subida
  Then el documento pasa a "processing" y después a "review" con los campos leídos
    And los importes están en céntimos enteros
    And se registra "document.uploaded" y "document.extracted" sin nombre de archivo ni importes

AC-02  Dato ilegible (US-001, fixture invoice_doubtful_nif)
  Given una lectura con el NIF del proveedor ilegible
  Then supplier_tax_id es null y figura en doubtful_fields con motivo "illegible"
    And la pantalla de revisión lo marca con texto e icono y avisa de que hay datos dudosos
    And "Registrar gasto" está desactivado y no existe ninguna ruta que registre un gasto

AC-03  Importes mal formados (RES-02)
  Given una respuesta del agente con "120,5", "1e3", "12.345" o un número JSON como importe
  Then la respuesta se rechaza entera como "invalid_response", no se guarda nada de ella
    And el documento queda "extraction_failed" y la persona puede reintentar o rellenar a mano

AC-04  Tipo y tamaño
  Given un archivo de tipo no permitido, de más de 15 MiB, o un PDF cuyo contenido es otro tipo
  When se intenta subir o completar
  Then se rechaza con "unsupported_file_type", "file_too_large" o "file_type_mismatch"
    And en el último caso el documento queda "discarded", el archivo se borra y no se llama al agente

AC-05  Fallos del agente (ADR-0012)
  Given un servicio que responde "unreadable", "upstream_error", no responde en 45 s o devuelve 502 una vez
  Then los dos primeros dejan el documento en "extraction_failed" con su mensaje; el tercero en "timeout"; el cuarto se reintenta una vez y termina bien
    And el apartado Gastos sigue funcionando y se puede rellenar a mano

AC-06  Instrucciones ocultas (NFR-07, fixture invoice_injection)
  Given una lectura con injection_suspected = true
  Then se guarda la marca, la pantalla muestra un aviso y el texto sospechoso se ve como texto
    And ningún campo se interpreta como orden ni se sigue ningún enlace

AC-07  Aislamiento de documentos y archivos (NFR-06)
  Given Alicia con un documento, Beto, Gina (gestor) y Adán (admin)
  Then Beto no ve el documento ni puede firmar una URL de su ruta (404 "document_not_found")
    And Gina lo lee solo con vínculo activo; con vínculo pendiente, revocado o rechazado, no
    And Gina no puede crear, modificar ni borrar documentos ni archivos
    And Adán no ve ninguno, y la matriz de RLS y test_storage_policies lo prueban

AC-08  Cliente de agentes: selección y contrato (ADR-0012)
  Given AGENTS_BASE_URL ausente, presente, o ausente con APP_ENV=production
  Then se usa FakeAgentsClient, HttpAgentsClient, o la API no arranca
    And HttpAgentsClient envía Authorization con AGENTS_API_KEY, X-Cuadre-Contract-Version: 1 y X-Request-Id, y una petición que cumple extract_request.schema.json
    And nunca envía la service key ni el JWT de la persona, y acepta los seis ejemplos de contracts/examples/extract/

AC-09  Sin datos sensibles en los registros (NFR-11)
  Given el flujo completo de subida, lectura, fallo y descarte
  Then ningún registro contiene la URL firmada, "token=", el JWT, el nombre del archivo ni datos del documento

AC-10  Móvil (US-011, NFR-10)
  Given un viewport de 390 px
  When la persona pulsa "Hacer una foto" (entrada con capture="environment") y se adjunta una imagen
  Then la imagen entra en la misma lectura que un archivo y aparece en la lista
    And ninguna pantalla de Gastos necesita scroll horizontal a 390 ni a 1.440 px en los tres navegadores

AC-11  Estados y recuperación
  Given un documento en processing sin cambios desde hace más de 120 s (por ejemplo, porque se interrumpió la petición que lo leía)
  Then GET lo presenta como extraction_failed con "timeout" y "Volver a leer" lo relanza con el mismo document_id
    And completar dos veces la misma subida no lanza dos lecturas

AC-12  Límites
  Given una persona con 5 documentos en "processing"
  When pide subir otro
  Then recibe 429 "too_many_processing" con Retry-After y no se crea ninguna fila

AC-13  Descarte
  Given un documento en review
  When la persona lo descarta
  Then pasa a "discarded", el archivo desaparece de Storage y se registra "document.discarded"
    And descartar de nuevo devuelve 409 "document_wrong_state"

AC-14  Revisión editable
  Given un documento en review con campos dudosos
  When la persona corrige el NIF y un importe y guarda
  Then se guarda review en céntimos, la lectura original no cambia y al recargar se ven las correcciones
    And un importe que no se puede interpretar se señala junto al campo y no se guarda

AC-15  Guardas del proyecto
  Then documents figura en rls_matrix.yaml con RLS forzada; test_rls_guard, test_no_float, test_no_llm_sdk, test_service_key_scope,
       test_operation_ids, test_openapi_drift y gen:api --check siguen en verde
```

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-001 §8.1, con la pila de Supabase en marcha (`npx supabase start`; Storage incluido) y los puertos 3000 y 8000 libres. Sin red hacia cuadre-agents: todo corre con el cliente simulado y un servidor de prueba local.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"      # el backend depende ahora de cuadre-contracts
npx supabase db reset                                                 # migraciones + seed + bucket
pytest backend/tests/agents backend/tests/documents -q                # AC-01 a AC-06, AC-08, AC-09, AC-11 a AC-14
pytest backend/tests/rls -m rls -q                                    # AC-07, AC-15 (documents y storage.objects)
pytest backend/tests -m "not rls" -q
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/gastos-subida.spec.ts     # AC-01, AC-02, AC-10 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/agents backend/tests/documents` y `npm --prefix frontend exec -- playwright test e2e/gastos-subida.spec.ts`, además de la secuencia completa
de SPEC-W-001 §8.2, que debe seguir en verde.

### 8.3 Correspondencia criterio → prueba

| AC | Prueba |
|---|---|
| AC-01 | `backend/tests/documents/test_upload_flow.py` y `test_documents_live.py` (Storage y GoTrue reales); `frontend/e2e/gastos-subida.spec.ts` · «subida y lectura» |
| AC-02 | `backend/tests/agents/test_fake_client.py`; `frontend/e2e/gastos-subida.spec.ts` · «dato dudoso» |
| AC-03 | `backend/tests/agents/test_normalize.py` (parametrizada con importes inválidos; de punta a punta en `test_http_client.py`) |
| AC-04 | `backend/tests/documents/test_file_validation.py` (tabla de firmas de los cinco tipos) y `test_storage_client.py` (cliente de Storage contra un servidor guionado) |
| AC-05 | `backend/tests/agents/test_http_client.py` (servidor simulado: 422, 502 único, tiempo agotado, 401, 413, 415) |
| AC-06 | `backend/tests/agents/test_normalize.py`; `frontend/e2e/gastos-subida.spec.ts` · «instrucciones ocultas» |
| AC-07 | `backend/tests/rls/test_documents.py`, `test_storage_policies.py` (reparto de cinco y estados del vínculo) y `test_storage_live.py` (API real de Storage); `rls_matrix.yaml`. Lado API: `backend/tests/documents/test_roles.py` (403 a gestores y administradores en las ocho rutas, ajeno = inexistente) |
| AC-08 | `backend/tests/agents/test_selection.py`, `test_http_client.py`, `test_contract_examples.py`; `backend/tests/rules/test_agents_boundary.py` (el paquete no puede importar la base de datos ni el JWT) y `test_contracts_dependency.py` |
| AC-09 | `backend/tests/documents/test_no_sensitive_logs.py` |
| AC-10 | `frontend/e2e/gastos-subida.spec.ts` · «cámara y sin scroll» (seis proyectos) |
| AC-11 a AC-14 | `backend/tests/documents/test_states.py` (incluye la concurrencia), `test_limits.py` (AC-12 y coherencia con SQL), `test_discard.py`, `test_review.py`, `test_errors_mapping.py`; `frontend/src/lib/money.test.ts`. En la base de datos (hito 1): `backend/tests/rls/test_documents_states.py` (estados, trigger, límites, caducidad, descarte, correcciones y las CHECK de importes de AC-03) |
| AC-15 | `backend/tests/rls/test_rls_guard.py` y las guardas de `backend/tests/rules/` |
| T2-10 | `backend/tests/documents/test_upload_flow.py::test_t210_the_web_adds_no_noticeable_latency` |
| T2-13, T2-14 | `backend/tests/rules/test_vercel_compat.py` |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y la de SPEC-W-001 §8.2 sigue en verde.
- [ ] `pytest backend/tests/rls -m rls` incluye `documents` y `storage.objects`.
- [ ] §8.2 de SPEC-W-001, `README.md` y la acción `python-env` del CI instalan `contracts/python` antes que el backend (en el mismo cambio).
- [ ] `frontend/e2e/roles.spec.ts` y la navegación reflejan que Gastos ya no es «Próximamente» para `usuario`.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0012, 0015 y 0016 enlazados.
- [ ] Sin secretos ni documentos reales en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike de Storage** (CLI 3.0, ES256): URL firmada de subida y de lectura con el JWT del usuario; que Storage acepte esa subida desde `http://localhost:3000` (CORS; si no, se reabre D-01: no hay plan B por la API, ADR-0016); políticas sobre `storage.objects` con funciones
   `private.document_*`; borrar con el token del usuario; bucket y límites declarados en una migración. Resultado al Anexo B.
   **Hecho el 2026-11-05.** El bucket está en `supabase/migrations/20261105100000_documents_bucket.sql` (con `test_storage_bucket.py`); las políticas sobre `storage.objects` y las funciones `private.document_*` pasan al hito 1 porque dependen de la tabla `documents`.
1. **Base de datos**: enums, `documents`, funciones `app.*`, trigger, bucket y políticas, matriz y `test_documents` / `test_storage_policies`, con mutaciones.
   **Hecho el 2026-11-05** (migraciones `20261105100100` a `…300`; decisiones y mutaciones en el Anexo B.3).
2. **`cuadre.agents`**: Protocol, Fake, Http, normalización, errores y selección por entorno; pruebas de contrato con los seis ejemplos; dependencia `cuadre-contracts` (README, CI y SPEC-W-001 §8.2 en el mismo commit).
   **Hecho el 2026-11-06** (paquete `backend/src/cuadre/agents/`; decisiones, pruebas y mutaciones en el Anexo B.4).
3. **API de documentos**: rutas, módulo de Storage, lectura dentro de la petición `complete` / `retry`, límites y registro sin datos sensibles; `openapi.json` y `schema.d.ts` regenerados.
   **Hecho el 2026-11-06** (paquete `backend/src/cuadre/documents/` y `api/routes_documents.py`; decisiones, pruebas y mutaciones en el Anexo B.5).
4. **Frontend**: `money.ts`, `/gastos` y `/gastos/[id]`, subida y cámara, refresco, estados; navegación activa para `usuario`.
5. **E2E y cierre**: `gastos-subida.spec.ts` (tres motores, dos anchos), `roles.spec.ts` actualizado, mutaciones, Anexo B, `tasks.json` y commit.

## Anexo B · Decisiones que esta spec dejó a la implementación

*(Se rellena al implementar.)*

### B.1 Spike de Storage · hito 0 · 2026-11-05

Entorno: Supabase CLI 3.0.0, `storage-api v1.88.0`, Kong 2.8.1, tokens ES256 reales de GoTrue para alicia, beto, gina (gestor) y adán (admin). Script desechable, no commiteado: usa una tabla provisional en un esquema `spike` y políticas provisionales sobre `storage.objects`, y lo retira todo al terminar (comprobado: ni esquema, ni políticas, ni objetos, ni vínculos). Todo lo de abajo es lo observado, no lo leído en documentación.

| Pregunta | Resultado |
|---|---|
| **¿Una migración puede crear el bucket?** | Sí. Con `npx supabase start -x studio` sobre una base nueva (el orden del CI) y con `npx supabase db reset`, la migración se aplica y el bucket queda creado. Las tablas de Storage existen cuando corren las migraciones. Crear las políticas sobre `storage.objects` con el rol `postgres` (el de las migraciones) también funciona |
| **¿Autenticación contra Storage?** | Storage acepta el JWT ES256 del usuario. **Basta `Authorization: Bearer`**; no hace falta `apikey`. Con la clave publicable sola actúa como `anon` y se deniega; sin cabeceras, `Invalid Compact JWS`. No hace falta ninguna variable nueva en el backend |
| **Firma de la subida** (`POST /storage/v1/object/upload/sign/documents/{ruta}`) | Responde `{ "url", "token" }`. La `url` es **relativa** (`/object/upload/sign/documents/{ruta}?token=…`, sin el prefijo `/storage/v1`: la API lo compone). El token caduca a las **2 h** (7.200 s) y lleva `url`, `owner`, `scope`, `upsert`. La política de INSERT se evalúa **al firmar**, con la identidad del usuario: se deniega a beto, a gina, a adán, a alicia sobre una ruta sin fila `documents` y a alicia sobre la ruta de beto. La política puede consultar la fila de `documents` |
| **CORS y subida desde `http://localhost:3000`** | El preflight responde 200 con `Access-Control-Allow-Origin: *`, métodos con `PUT` y las cabeceras pedidas (`content-type`). Un `PUT` con **solo `Content-Type`** (sin `Authorization` ni `apikey`, como hará el navegador) guarda el archivo y devuelve `Access-Control-Allow-Origin: *`. Un segundo `PUT` a la misma ruta con el mismo token responde 409 `Duplicate` y el archivo no cambia |
| **Límites del bucket** | 15 MiB exactos se aceptan; 15 MiB + 1 byte, 413 `EntityTooLarge` y no se guarda; `text/plain`, 415 `InvalidMimeType`. Un `Content-Type` con parámetros (`application/pdf; charset=binary`) se acepta |
| **¿Storage mira el contenido?** | **No.** Un texto de 27 bytes subido como `application/pdf` se acepta; unos bytes con forma de WebP subidos a una ruta `.pdf` con `image/webp`, también. Storage registra el tipo de la cabecera del `PUT` y no lo cruza con la extensión. La firma del archivo y la coherencia con lo declarado las comprueba la API (T2-08) |
| **Firma de la lectura** (`POST /storage/v1/object/sign/documents/{ruta}`, `{"expiresIn": n}`) | Responde `{ "signedURL" }`, también relativa a `/storage/v1`. Caduca exactamente a `expiresIn` (120 s y 2 s comprobados); pasado el tiempo, `InvalidJWT` («exp claim timestamp check failed»). **Un `GET` de esa URL sin ninguna cabecera** devuelve el archivo con su `Content-Type` y CORS `*`: es lo único que necesita el agente |
| **Quién puede firmar la lectura** | Alicia sí. Beto, adán, gina sin vínculo, gina con vínculo **pendiente**, gina con vínculo **revocado** y gus (sin vínculo): no. Gina con vínculo **activo**: sí. Un objeto ajeno responde exactamente igual que uno inexistente (404 `NoSuchKey`): no hay forma de saber si existe |
| **Comprobar tamaño y firma sin descargar** | `GET /storage/v1/object/authenticated/documents/{ruta}` con `Authorization` y `Range: bytes=0-7` devuelve 206 con `Content-Range: bytes 0-7/246` (el total sale de ahí) y solo esos bytes; la API pedirá `0-31`. `GET /storage/v1/object/info/authenticated/documents/{ruta}` devuelve JSON con `size` y `content_type`. `HEAD` con `Authorization` devuelve `Content-Length` y `Content-Type`, y el `Range` también funciona sobre la URL firmada |
| **Borrado con el JWT del usuario** (`DELETE /storage/v1/object/documents/{ruta}`) | Alicia borra cuando su fila no está `registered`; con la fila `registered` se deniega, de modo que la política sí puede mirar la tabla. Beto, gina (con vínculo activo) y adán: denegado y el archivo sigue ahí (comprobado en la base) |
| **URL de subida ya emitida y documento descartado antes de subir** | Sigue valiendo: el `PUT` se acepta y deja un archivo sin fila viva. La autorización ocurre solo al firmar |
| **Forma de los errores** | HTTP **400** con `{ "statusCode": "403"\|"404"\|"409"\|"413"\|"415", "error", "message", "code" }` para casi todo. El código real está en el cuerpo, no en el estado HTTP |

**Consecuencias para los hitos siguientes** (ya reflejadas en §5.1, §5.2, §5.4 y T2-08):
- D-01 se mantiene y **no hace falta plan B**: el navegador sube directamente. El límite de 15 MiB lo hace cumplir Storage (413) además de la CHECK y la API.
- El cliente de Storage de `cuadre.documents` se apoya solo en el JWT del usuario, compone las URL con `{SUPABASE_URL}/storage/v1` y decide por el `statusCode` del cuerpo.
- `complete` compara tamaño y tipo registrados (`object/info`) con lo declarado y lee los primeros 32 bytes con `Range`; nunca descarga el archivo entero (T2-08, 4,5 MB de Vercel).
- Una URL de subida es un secreto portador de 2 h y de un solo uso: nunca en registros ni trazas (T2-04, ya cubierto).
- Quedan huérfanos posibles (archivos subidos tras descartar, o `uploading` abandonados): ya está excluido en §4 como tarea de mantenimiento.
- Hito 1: las funciones `private.document_*` no pueden lanzar excepción con una carpeta que no sea un uuid (convertir de forma segura y devolver `false`), porque una excepción dentro de una política es un 500 y no una denegación. Falta probar en `test_storage_policies.py` el estado de vínculo `declined`, que el spike no cubrió.

### B.3 Hito 1 · base de datos de documentos · 2026-11-05

Tres migraciones: `20261105100100_documents_table.sql` (enums, `documents`, CHECK, políticas, trigger), `…200_documents_functions.sql` (las siete funciones `app.*` y sus ayudantes) y `…300_documents_storage_policies.sql` (las tres políticas de `storage.objects`). Se aplican igual con `supabase start` sobre una base nueva (el orden del CI) y con `db reset`.

**Decisiones tomadas al implementar** (ya reflejadas en §5.2):
- El límite de 5 lecturas se impone **también donde empieza la lectura** (`mark_document_uploaded` y `retry_document`), con un cerrojo asesor por persona; `create_document` solo avisa antes. Sin esto, 10 subidas reservadas y completadas a la vez habrían pasado el límite. Las lecturas con más de 120 s sin cambios no cuentan.
- Las CHECK de ruta, de motivos de fallo y de **importes enteros** viven en la tabla: la API (hito 2 y 3) las repetirá, pero la base no depende de ella.
- El trigger congela la lectura original y las columnas de identidad, y deja `updated_at` fijable a propósito para que los tests envejezcan filas sin desactivar nada.
- La política de borrado de Storage permite al dueño borrar un archivo huérfano (sin fila `documents`) y le prohíbe borrar uno cuya fila esté `registered`. La forma de la ruta es estricta (`{uuid}/{archivo}`): una carpeta de más o de menos se deniega.
- La matriz de RLS tiene una clave nueva, `seed`, para tablas que no se rellenan solas: sin filas de ejemplo, «nadie ve nada» es una afirmación vacía.
- `MAX_PROCESSING_PER_USER` sigue en §5.4, pero el 5 vive en SQL; el hito 3 decide si se retira la variable.

**Pruebas** (173 nuevas en `backend/tests/rls/`, 289 en total): `test_documents.py` (quién llama a qué), `test_documents_states.py` (transiciones, trigger, CHECK, límites con una prueba de concurrencia determinista, caducidad, descarte y correcciones), `test_storage_policies.py` (SQL, cinco personas × cinco estados del vínculo) y `test_storage_live.py` (API real de Storage, siete casos).

**Mutaciones** (28; método de SPEC-W-001 hito 1: se rompe a propósito la base local, se comprueba que la suite falla y se revierte; un ejecutor desechable compara una huella del esquema antes y después): lectura abierta, gestor sin mirar el vínculo, política extra para el admin, `INSERT/UPDATE/DELETE` concedidos, `FORCE RLS` retirada, trigger eliminado, transiciones ilegales permitidas, lectura descongelada, identidad modificable, CHECK de importes eliminada, CHECK de ruta eliminada, función sin comprobar el rol, sin comprobar el dueño, límite eliminado al empezar la lectura, `mark_document_uploaded` sin comprobar el estado, reintento sin exigir caducidad, marca de inyección perdida, nombre de archivo en el registro de actividad, `search_path` sin fijar, INSERT de Storage sin la fila reservada, SELECT de Storage abierto, DELETE de Storage sin mirar `registered`, política para `anon`, UPDATE permitido, cualquier gestor lee los archivos, subida aunque el documento ya no esté en `uploading`, carpetas que no son uuid que lanzan excepción y cerrojo asesor eliminado. **Las 28 hacen fallar la suite**; tras revertirlas, vuelve a verde y la huella del esquema es idéntica. Lecciones: una mutación que quita una CHECK deja filas que impiden volver a ponerla (el revertir debe borrarlas), y las funciones releídas con `pg_get_functiondef` cambian en espacios en blanco (la huella los normaliza).

**Para el hito 3** (API): traducir los errores de la base a `problem+json`: `document_not_found` → 404, `document_wrong_state` → 409, `too_many_processing` → 429 con `Retry-After`, `42501` → 403; `invalid_review` y las CHECK (`23514`) solo pueden aparecer si la validación de forma falló antes, y son un error interno.

### B.4 Hito 2 · `cuadre.agents` · 2026-11-06

Paquete `backend/src/cuadre/agents/`: `errors.py` (`FailureCode`, `AgentsError`, `AgentsConfigurationError`), `client.py` (Protocol), `text.py` (limpieza de textos), `normalize.py`, `fake.py`, `http.py` y `selection.py`. `create_app` elige el cliente y lo guarda en `app.state.agents_client`; la dependencia `Depends(...)` que lo entrega a las rutas es del hito 3. No hay rutas nuevas: `openapi.json` y `schema.d.ts` no cambian, y `contracts/` tampoco (el contrato C1 se cumple tal cual).

**Decisiones tomadas al implementar** (ya reflejadas en §5.3 y §5.4):
- El modelo del contrato **deja pasar dígitos de otros alfabetos** (`\d` casa `٣` y `Decimal` los lee) y la validación Pydantic por defecto acepta una fecha como entero y `"true"` como booleano. Por eso el cliente HTTP valida en modo estricto y `normalize_extraction` repite sus comprobaciones con dígitos ASCII y `fullmatch` (un `$` admitiría `"120.00\n"`): doble cerco, probado saltándose la validación con `model_copy`.
- Cotas: más de 10 líneas de IVA o 50 dudosos invalidan la respuesta entera (no se trunca dinero); `warnings` se recorta a 5; una duda que apunta a una línea inexistente pierde el índice pero se conserva; el coste debe ser `< 1000` porque `agent_cost_eur` es `numeric(9,6)` y el contrato admite más.
- Textos: además de control, se eliminan los caracteres de formato (controles bidireccionales: suplantación de texto) y los sustitutos sueltos (PostgreSQL no los admite en `jsonb`).
- Mapeo de errores completado (ver §5.4). Un `400` o un `422` con otro código son **nuestros** (la petición enviada es la errónea) y dan `internal`, no `unreadable`: el documento no tiene la culpa.
- Una conexión por llamada, sin redirecciones y sin proxies del entorno (`trust_env=False`): la clave del servicio solo va a la URL configurada. Las excepciones de validación se lanzan `from None` y no se registran: su texto lleva los datos recibidos.
- `FakeAgentsClient` cíclico y que falla al agotarse el guion; en `staging` sin URL se usa y se avisa; en `production` la API no arranca. Un test antiguo (`test_the_interactive_docs_are_off_in_production`) tuvo que declarar el servicio de agentes por esa misma regla.
- Solo tres variables nuevas (`AGENTS_BASE_URL`, `AGENTS_API_KEY`, `AGENTS_TIMEOUT_SECONDS`); una cadena vacía cuenta como ausente porque `.env.example` las trae vacías. `MAX_UPLOAD_BYTES` pasa al hito 3 y `MAX_PROCESSING_PER_USER` se retira.
- `cuadre-contracts==1.0.0` en el backend (y `jsonschema` en `dev`). Orden de instalación: `contracts/requirements.txt` → `contracts/python` → `backend[dev]`, en la acción `python-env`, el README, `CLAUDE.md` y SPEC-W-001 §8.2. Se comprobó en un entorno virtual **limpio** con esa secuencia exacta.

**Pruebas** (277 en `backend/tests/agents/` y 9 en `backend/tests/rules/`; el conjunto «no rls» pasa de 123 a 409, y las 289 de RLS siguen igual): servidor HTTP local de verdad (puerto efímero, guion por petición, registra lo recibido) para probar tiempos agotados, conexión rechazada, reintentos y cabeceras por el cable; los cinco ejemplos de respuesta y el de error por Fake y por HTTP; importes con «trampas» de coma flotante (`0.29`, `1.15`, `4.35`); la normalización contra la base real (`app.record_extraction` y la CHECK de importes de los cinco ejemplos); `FailureCode` = CHECK de `error_code`, y cada código pasa por `app.fail_extraction`; registros sin URL firmada, `token=`, clave, NIF ni nombre; el paquete no puede importar la base de datos, la autenticación ni el JWT (`test_agents_boundary`); y el pin de `cuadre-contracts` coincide con `contracts/` y con el orden de instalación (`test_contracts_dependency`).

**Mutaciones** (48, mismo método que en los hitos anteriores, ejecutor desechable fuera del repositorio): importe vía `float`, formato sin comprobar, `match` en vez de `fullmatch`, `\d` Unicode, sin quitar control / formato / sustitutos, sin recorte ni colapso de espacios, sin los cuatro topes, línea de duda fuera de rango, marca de inyección perdida, traza sin acotar, sin cada una de las tres cabeceras, reintento ante cualquier `4xx`, tras tiempo agotado o sin límite, `Retry-After` sin tope, 401/403/404 como `unreadable`, redirecciones y proxies admitidos, sin tope de cuerpo, plazo sin comprobar entre trozos, reintento sin presupuesto, la clave en los registros, validación no estricta, producción con simulacro, sin `https`, sin clave, URL con credenciales, cadena vacía como valor, tiempo sin rango, Fake desordenado / compartido / sin detectar el guion agotado, API sin selección, pin distinto, acción y README en orden inverso, `422` y `413` mal mapeados, e importar `psycopg` o leer `supabase_url` dentro del paquete. **Las 48 hacen fallar la suite.** Una sobrevivió en la primera pasada (el tope de 1 MiB: la prueba mandaba basura, que se rechaza igual por no ser JSON); ahora la prueba manda una respuesta *válida* rellena de espacios y distingue 1 MiB exactos (se acepta) de 1 MiB + 1 (se rechaza).

**Lo que no se puede garantizar o no se ha comprobado:**
- El presupuesto de 45 s se aplica a la conexión, la espera de cabeceras y entre trozos del cuerpo (acotado a 1 MiB), pero los tiempos de `httpx2` son **por lectura de socket**: un servidor que gotee el cuerpo a propósito podría estirar la espera hasta ~2× el presupuesto. El tope duro lo pone la función de Vercel (`maxDuration`, spec de despliegue). El servicio de agentes es infraestructura propia, así que se acepta.
- `HttpAgentsClient` nunca ha hablado con el servicio real (depende de la SPEC-A de lectura de facturas en cuadre-agents): solo con el servidor local de pruebas.
- En Windows una conexión rechazada tarda ~2 s en fallar, así que la prueba del reintento tras error de conexión dura unos 4 s; es la más lenta del paquete.
- `FakeAgentsClient` lee los fixtures de `contracts/examples/`, fuera de `backend/`. Si el despliegue de Vercel no los incluye, el simulado falla con `AgentsConfigurationError` (no con un documento ilegible); no afecta a producción, donde no existe, pero sí a un `staging` sin URL. Va con el resto de lo de `contracts/` a la spec de despliegue (B.2).

**Para los hitos siguientes:**
- **Hito 3:** el Storage de `cuadre.documents` es el único que fabrica `document_url` (≤ 120 s, con el JWT de la persona). Pasar `AgentsError.code.value` a `app.fail_extraction`; los textos en español de cada motivo (§5.1) viven allí. Añadir `MAX_UPLOAD_BYTES`, retirar `MAX_PROCESSING_PER_USER` y exponer `app.state.agents_client` con una dependencia. Pasar el `request_id` de la petición al cliente (`X-Request-Id`). `test_vercel_compat` no debe confundir `itertools.count` (el Fake) con un hilo.
- **Hito 5:** el Fake recorre sus fixtures en orden cíclico, así que un E2E que necesite un fixture concreto depende del orden de llegada. El constructor ya acepta un guion; falta decidir cómo llega desde el entorno de la prueba (variable solo con `APP_ENV=local`, o un cliente inyectado).

### B.5 Hito 3 · API de documentos · 2026-11-06

Paquete `backend/src/cuadre/documents/` (`limits`, `signature`, `storage`, `repository`, `models`, `presentation`, `service`, `errors`) y `api/routes_documents.py` con las ocho rutas de §5.1. `create_app` guarda `app.state.storage` (`HttpStorage`) junto a `app.state.agents_client` (hito 2) y monta el router. `backend/openapi.json` y `frontend/src/api/schema.d.ts` están regenerados; `typecheck` y `lint` del frontend siguen limpios con el cliente nuevo.

**Decisiones tomadas al implementar** (las de comportamiento ya están en §5.1 y §5.4):
- **Una ruta larga no puede retener una conexión.** `Tx` mantiene una conexión del pool durante toda la ruta; `complete` y `retry` esperan al agente hasta 45 s y el pool es de 10. `core/auth.py` gana `get_verified_token`, `get_current_user_detached` y `require_role_detached`: leen el perfil en su propia transacción corta y la sueltan, y el servicio abre transacciones cortas por paso. Una prueba comprueba, con el agente retenido, que el pool no tiene ninguna conexión en uso durante la espera. El rol se vuelve a comprobar dentro de cada función SQL, así que leerlo antes no abre ningún hueco.
- `upload_size_mismatch` también descarta y borra el archivo; `upload_missing` no. Un documento atascado en `uploading` no sale en la lista ni se puede descartar desde la interfaz, y una URL de subida admite una sola subida.
- `MAX_UPLOAD_BYTES` y los 120 s son constantes, no variables de entorno (ver §5.4); `test_limits.py` las compara con la CHECK, el bucket y `private.document_processing_timeout()`.
- El orden de `complete` es la seguridad: existencia, tamaño, tipo registrado y firma ANTES de pasar a `processing` y de llamar al agente. Si otra petición gana `mark_document_uploaded`, la perdedora no da 409: responde el estado actual (la lectura es idempotente por documento).
- Las consultas filtran por `owner_id = auth.uid()` además de la RLS. Una prueba lo comprueba leyendo como un gestor con vínculo activo, para el que la RLS sí dejaría pasar.
- `Review` es `extra="forbid"` con enteros estrictos en céntimos y los textos pasan por `clean_text` (un NUL rompería el `jsonb`); `issue_date` solo admite `AAAA-MM-DD`. Un tipo no permitido es un 415 propio, no el 422 genérico de una enumeración.
- Storage se llama siempre con el JWT de la persona; nunca descarga el archivo entero (en *stream*, corta a los 32 bytes aunque Storage ignorase `Range`: una prueba mide cuánto llegó a escribir el servidor); rechaza URL devueltas que no sean de nuestro bucket; no sigue redirecciones ni usa proxies del entorno. `httpx2` y `httpcore2` pasan a `WARNING` en `configure_logging`.
- `test_operation_ids` admite ahora los verbos `complete`, `retry`, `save` y `discard`, que fija §5.1.

**Pruebas** (306 en `backend/tests/documents/`, 7 guardas nuevas en `backend/tests/rules/test_vercel_compat.py`; el conjunto «no rls» pasa de 409 a 722 y las 289 de RLS siguen igual): la aplicación real con base de datos real, un Storage en memoria que anota el JWT de cada llamada y el agente simulado; flujo completo y su registro de actividad; las 20 parejas tipo declarado × firma real; archivo ausente, tamaño y tipo registrado distintos; matriz de cinco estados × seis acciones; concurrencia con hilos (lectura en curso, dos `complete` a la vez con una barrera, descarte durante la lectura); `GatedAgents` y `BrokenAgents` para lo que ocurre *mientras* se lee; 403 a gestores y administradores en las ocho rutas, también con vínculo activo; ajeno = inexistente con el mismo cuerpo; cada error real de la base traducido a su `problem+json`; el cliente de Storage contra un servidor local guionado; el flujo completo de AC-09 con todos los registros capturados; y `test_documents_live.py` contra **Storage y GoTrue reales** (reservar, `PUT` solo con `Content-Type`, `complete`, vista previa abierta sin cabeceras, URL de lectura del agente, archivo falso, tipo y tamaño distintos, los cuatro tipos de imagen, descarte que borra el objeto). Sin objetos sueltos en Storage al terminar.

**Mutaciones** (52, mismo método que en los hitos anteriores): comprobaciones de tamaño / tipo registrado / firma quitadas una a una; rechazo sin descartar o sin borrar; `complete` sin idempotencia o con la carrera dando 409; lectura sin marcar la subida; URL de lectura o de vista previa de una hora; fallo del agente o lectura buena sin guardar; excepción inesperada que deja `processing`; reserva sin descartar si falla la firma; descarte sin borrar el archivo o que falla si el borrado falla; un descartado que se puede ver; HEIC previsualizable; `Content-Type` de subida cambiado; nombre sin limpiar; tipo o tamaño no validados; Storage sin JWT, con el archivo entero, ignorando `statusCode`, aceptando URL ajenas, siguiendo redirecciones o con proxies; 403 mal traducido; gestores dentro; ruta que retiene la conexión; caducidad sin presentar; consultas sin filtro de propietario o sin tope; 15 MiB desalineado con SQL; 429 sin `Retry-After`; corrección con campos extra, céntimos no estrictos, textos sin limpiar, fecha sin forma o IVA sin patrón; nombre de archivo o JWT en un registro; `201` cambiado; `request_id` que no llega al agente; JWT en bruto distinto; `complete` que rechaza un fallido; descarte durante la lectura que da error; motivo de caducidad distinto de `timeout`. **Las 52 hacen fallar la suite.** Una sobrevivió en la primera pasada (la caducidad de 60 s de la vista previa no se comprobaba) y al preparar las mutaciones vi que mi prueba de redirecciones no distinguía seguirla de no seguirla (apuntaba a un puerto muerto): ahora apunta al mismo servidor y cuenta las peticiones.

**Lo que no se ha comprobado:**
- **Navegador real.** `test_documents_live.py` sube con `httpx` y las cabeceras que enviaría un navegador, no desde uno: el CORS real queda para el E2E del hito 5 (B.2).
- **Hilos.** Las rutas son síncronas: una lectura ocupa un hilo del *threadpool* de FastAPI (40 por defecto) hasta 45 s. Con 5 lecturas simultáneas por persona, el límite lo marca el número de personas leyendo a la vez; sobra para la v1, pero no se ha medido bajo carga.
- **Vercel.** Qué pasa con `complete` si el navegador cierra la conexión antes de que acabe la lectura (el documento queda en `processing` y a los 120 s se presenta como fallido, AC-11, pero no se ha visto en una función real), y el Storage de Supabase alojado, siguen para la spec de despliegue.
- **Servicio real de agentes.** Las rutas solo se han ejecutado con `FakeAgentsClient`; `HttpAgentsClient` no ha leído nunca una factura de verdad (depende de la SPEC-A de lectura en cuadre-agents).

**Para los hitos siguientes:**
- **Hito 4:** el cliente generado ya trae `Document`, `DocumentSummary`, `DocumentState`, `Review`, `UploadResponse` y `PreviewResponse`. Orden del flujo de subida: acción de servidor `upload_document` → `PUT` a `upload.url` con `upload.headers` (el navegador nunca tiene el JWT) → acción de servidor `complete_document_upload`, que tarda hasta 45 s. Los documentos en `uploading` no salen en la lista: los errores de subida se muestran en la fila del archivo. Comprobar tipo y tamaño en el cliente antes de reservar (`415`/`413` existen, pero evitan un viaje). `429` trae `Retry-After`. Un `complete` puede responder `status: "discarded"` si se descartó mientras se leía. `doubtful_fields[].field` usa `total`, no `total_cents`. El refresco cada 2 s debe llamar a `list_documents`/`get_document` (la caducidad de 120 s se presenta ahí, sin escribir).
- **Hito 5:** decidir cómo fija el E2E qué fixture lee el simulado (sigue siendo cíclico) y confirmar el CORS en los tres navegadores.

### B.2 Sin comprobar todavía

- **Navegador real.** El CORS se comprobó a nivel de cabeceras (preflight y `PUT` con `Origin: http://localhost:3000`); el E2E del hito 5 lo confirma en Chromium, Firefox y WebKit. Si fallara ahí, se reabre D-01.
- Si una URL de lectura ya emitida sigue valiendo tras revocar el vínculo: por construcción vale hasta que caduca (≤ 120 s); no se probó.
- El Storage de Supabase alojado (versión, CORS, caducidad de 2 h): queda para la spec de despliegue.
- Con el backend en Vercel (ADR-0016), también para la spec de despliegue: qué pasa con `complete` si el navegador cierra la conexión antes de que acabe la lectura, y que `cuadre-contracts`, que está fuera de `backend/`, se instale en el despliegue.
