---
tipo: spec
id: SPEC-W-014
titulo: Recordatorios por correo antes de cada plazo trimestral
estado: en-revision
prioridad: must
riesgo: bajo
historias: [US-009]
requisitos: [RF-015]
nfr: [NFR-09, NFR-06]
restricciones: [RES-02, RES-04, RES-05, RES-07]
adr: [0003, 0007, 0008, 0015, 0016]
depende_de: [SPEC-W-009, SPEC-W-010]
bloquea: []
fecha: 2026-11-13
---

# SPEC-W-014 · Recordatorios por correo antes de cada plazo trimestral

> El autónomo recibe **un correo N días antes del plazo del 303 y el 130** con la fecha límite, el importe estimado de cada modelo y las facturas pendientes de revisar. El envío es un **job idempotente con reloj inyectado** (ADR-0007) detrás de la interfaz `EmailSender` (ADR-0008), de modo que se completa y se prueba entero sin proveedor real (DEP-05).

## 1. Contexto

**Situación de partida.** Existen el 303 y el 130 como funciones puras (`cuadre.tax`) con sus lecturas en `cuadre.quarters`; `cuadre.tax.periods.filing_deadline`; el reloj `cuadre.core.clock` (`today_in_madrid`); la interfaz `EmailSender` con `MemoryEmailSender` y `ConsoleEmailSender` (W-010); `db.service_transaction` y `DATABASE_SERVICE_URL` (solo jobs y CLI, T-04); y la cuenta de documentos en `review` que la cartera del gestor ya muestra.

**Qué falta.** No hay ajustes de recordatorio, ni `reminder_log`, ni código en `cuadre.jobs`, ni ruta interna del planificador, ni subcomando de CLI para jobs, ni `backend/tests/jobs/`. W-012 (cierre mensual) tampoco está hecha, así que esta spec crea la **infraestructura mínima de jobs** que W-012 reutilizará.

**Decisiones tomadas por la persona el 2026-11-13.** (1) El «resumen de cartera del gestor» de RF-015 se cumple con la **pantalla `/cartera`**, ya entregada en SPEC-W-010 (US-010); **no hay correo al gestor**. (2) La antelación es **configurable** por el usuario, con tabla, API y sección «Recordatorios» en `/perfil`.

**Decisiones vigentes** (no se reabren): ADR-0007 (job = función Python con `now` inyectado, idempotente, `reminder_log` único por `(owner_id, periodo, tipo)` escrito antes de enviar); ADR-0008 (plantillas en español, cifras ya calculadas por `cuadre.tax`, nunca IBAN, sin cuerpos de correo en los registros); ADR-0016 (el planificador hace `GET` en UTC con `CRON_SECRET`; sin trabajo posterior a la respuesta); RES-04 y RES-05 (todo es orientativo; nada se envía a la AEAT).

**Decisiones que propone esta spec** (la persona las confirma o corrige antes del hito 2):

| ID | Decisión | Alternativa y coste |
|---|---|---|
| D-01 | `public.reminder_settings(owner_id, enabled, lead_days)`; **sin fila = activado y 10 días**. `lead_days` entre 1 y 30 | Fila creada al registrarse: obliga a tocar el alta y a rellenar usuarios existentes |
| D-02 | **Ventana de envío**: se recuerda el trimestre cuyo plazo cae en `[hoy, hoy + lead_days]` (hoy en Madrid). Se envía **una sola vez** por `(owner_id, 'AAAA-Tn', 'quarter_deadline')` el primer día en que el job lo ve dentro de la ventana | Enviar solo el día exacto: un fallo de un día perdería el recordatorio, contra NFR-09 |
| D-03 | **Reserva antes de enviar** (`private.reminder_claim`): inserta la fila `pending` o, si ya existe, la reclama solo si está `failed` o `pending` desde hace más de 15 min (proceso caído). Si el envío falla, la fila pasa a `failed` y la siguiente ejecución la reclama. **Nunca se borra**: `service_role` no tiene `DELETE` (guard de RLS) | Marcar tras enviar: dos ejecuciones simultáneas duplicarían el correo. Borrar la reserva: prohibido a `service_role` |
| D-04 | Reciben correo solo cuentas `status = 'active'` con rol `usuario` y recordatorios activados. Con 303 y 130 a cero **se envía igualmente** (sigue habiendo plazo) | |
| D-05 | Las cifras se calculan con las mismas funciones que las pantallas (`QuarterService`/`build_modelo_303`/`build_modelo_130`) y **`owner_id` explícito en cada consulta** desde la transacción de servicio | Reimplementar sumas: dos sitios para una regla fiscal |
| D-06 | Ruta `GET /internal/jobs/{name}` (`reminders`), protegida con `CRON_SECRET`, fuera de `openapi.json`, más `python -m cuadre.cli run-job reminders [--now ISO]` | |
| D-07 | Un fallo de envío a un usuario no detiene el resto; el job devuelve `{sent, skipped, failed}` y registra solo `user_id`, `period` y código | |

## 2. Objetivo

Un job que, ejecutado cualquier día, envía a cada autónomo con recordatorios activados **un único correo por plazo trimestral** cuando falten como máximo `lead_days` días, con el plazo, el importe estimado del 303 y del 130 y el número de facturas pendientes de revisar; configurable desde el perfil; y repetible sin duplicar.

## 3. Alcance explícito

### 3.1 Base de datos
- Migración `…_reminders.sql`: `public.reminder_settings` y `public.reminder_log`, con RLS activada y forzada, registradas en `rls_matrix.yaml`.
- `reminder_settings`: `usuario` ALL sobre sus filas; `gestor` y `admin` sin política. `reminder_log`: `usuario` solo SELECT de lo suyo; la escritura es del rol de servicio; `gestor` y `admin` sin política. `UNIQUE (owner_id, period, kind)`.

### 3.2 Backend (FastAPI)
- `cuadre.jobs.reminders`: selección del trimestre a recordar, destinatarios, reserva, cálculo de cifras, redacción y envío; `run_reminders(pool, sender, now)`.
- `notifications/templates.py`: plantilla `quarter_reminder` en español.
- `GET/PUT /api/me/reminders` (`get_reminder_settings`, `update_reminder_settings`).
- `GET /internal/jobs/{name}` y subcomando `run-job` de la CLI; `Settings.cron_secret`.

### 3.3 Frontend (Next.js)
- Sección «Recordatorios» en `/perfil`: interruptor y antelación (1 a 30 días), con el cliente generado.

### 3.4 Pruebas
- `backend/tests/jobs/test_recordatorios_*.py` (ventana, destinatarios, plantilla, job, runner, ruta interna y CLI) con `FixedClock` y `MemoryEmailSender`; pruebas de API y RLS; unitarias del formulario y E2E de la sección.

## 4. Alcance excluido

- **Correo al gestor / resumen semanal de cartera.** La cartera es la pantalla de W-010 (decisión del 2026-11-13).
- **Proveedor real de correo, dominio verificado y contrato de encargado** (DEP-05, DEP-06): `EmailSender` simulado.
- **Cierre mensual** (W-012) y su reporte (W-013). Solo se comparte la infraestructura de jobs.
- Recordatorios de otros plazos (resumen anual, 390, 100…), por SMS o *push*, y baja con enlace sin sesión.
- Presentar o enviar nada a la AEAT (RES-04). Aviso legal más allá de «orientativo» (CONF-003).

## 5. Contrato de interfaces

### 5.1 Reglas
- **Trimestre a recordar.** Para `hoy` en Madrid, entre los trimestres del año anterior y del actual se elige el cuyo `filing_deadline(y, q)` cumple `hoy ≤ plazo ≤ hoy + lead_days`. Si ninguno, no se envía. El 4.º trimestre usa el plazo del 30 de enero del año siguiente.
- **Periodo** `AAAA-Tn` (`2026-Q4`); **tipo** `quarter_deadline`.
- **Contenido**: asunto con el trimestre y la fecha; cuerpo con plazo y días que faltan, `303` y `130` estimados (`Intl`-equivalente es-ES, p. ej. «1.234,56 €»; a ingresar o a devolver según el signo), número de facturas pendientes de revisar (`documents.status = 'review'`), enlace a la aplicación y la frase «Cifras orientativas, no se presentan solas ante la AEAT». **Nunca** IBAN, NIF completo ni datos de clientes.
- **Importes** en céntimos enteros y `Decimal` con `ROUND_HALF_UP` (RES-02); ningún `float`.
- **Idempotencia**: dos ejecuciones (o dos procesos a la vez) con el mismo `now` envían un solo correo por `(owner_id, periodo, tipo)`.
- **Fallo de envío** (`EmailDeliveryError`): la fila pasa a `failed` y se contabiliza `failed`; la siguiente ejecución dentro de la ventana la reclama y lo reintenta.
- **Registros**: `request_id`/`job`, `user_id`, `period`, resultado y duración. Nunca correo, asunto, cuerpo ni importes.

### 5.2 Base de datos
```sql
create table public.reminder_settings (
  owner_id   uuid primary key references public.profiles (id) on delete cascade,
  enabled    boolean not null default true,
  lead_days  integer not null default 10 check (lead_days between 1 and 30),
  updated_at timestamptz not null default now()
);
create table public.reminder_log (
  id        uuid primary key default gen_random_uuid(),
  owner_id  uuid not null references public.profiles (id) on delete cascade,
  period    text not null check (period ~ '^[0-9]{4}-Q[1-4]$'),
  kind      text not null check (kind in ('quarter_deadline')),
  status     text not null default 'pending' check (status in ('pending', 'sent', 'failed')),
  claimed_at timestamptz not null default now(),
  sent_at    timestamptz,
  unique (owner_id, period, kind)
);
```
Ninguna tabla se escribe directamente: `app.set_reminder_settings(p_enabled, p_lead_days)` (rol `usuario`), `private.reminder_claim(owner, period, kind) → boolean` y `private.reminder_mark(owner, period, kind, sent)` (solo `service_role`). Todas `SECURITY DEFINER` con `set search_path = ''`.

### 5.3 API HTTP
| `operation_id` | Ruta | Rol | Respuesta |
|---|---|---|---|
| `get_reminder_settings` | `GET /api/me/reminders` | `usuario` | `{enabled, lead_days}` (valores por defecto si no hay fila) |
| `update_reminder_settings` | `PUT /api/me/reminders` | `usuario` | los ajustes guardados; `422 invalid_lead_days` fuera de 1–30 |
| (interna) | `GET /internal/jobs/reminders` | planificador | `{sent, skipped, failed}`; `401` sin `Authorization: Bearer <CRON_SECRET>`; no sale en `openapi.json` |

`gestor` y `admin` reciben `403` en las rutas de usuario.

### 5.4 Backend
`run_reminders(pool, sender, now) -> ReminderResult`. `now` con zona; la fecha de Madrid se obtiene con `today_in_madrid`. Usa `service_transaction` y pasa `owner_id` explícito en cada consulta.

### 5.5 Frontend
Tarjeta «Recordatorios» en `/perfil`: interruptor «Avisarme por correo antes de cada plazo» y campo numérico «Días de antelación» con etiqueta, mensaje de error y confirmación al guardar. Tokens del prototipo; sin scroll horizontal a 390 y 1.440 px.

## 6. Restricciones técnicas
- Sin `float` para importes. Sin llamar a ninguna API de modelos. La service key solo en `cuadre.jobs` y `cuadre.cli`; las rutas de ajustes usan `user_transaction`.
- La ruta interna compara el secreto en tiempo constante y no se publica en el cliente generado.
- La hora UTC del cron se elige para caer en el mismo día de Madrid en verano e invierno (p. ej. 08:00 UTC); como el job es idempotente, adelantar o repetir es seguro.
- Sin trabajo tras la respuesta (ADR-0016): el job envía dentro de la petición; con volumen del piloto cabe en el límite de la función. Si algún día no cupiera, se evalúa en otra spec.
- Datos solo sintéticos; `.env.example` documenta `CRON_SECRET`.

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Recordatorio del cuarto trimestre (US-009).** *Given* un usuario con recordatorios activados y 10 días; *When* el job corre el 20 de enero de 2027; *Then* recibe un correo con el plazo del 30 de enero, el importe estimado del 303 y del 130 del 4.º trimestre de 2026 y el número de facturas pendientes de revisar.

**AC-02 · Fuera de ventana.** *Given* el mismo usuario; *When* el job corre el 19 de enero; *Then* no se envía nada; ni el 31 de enero.

**AC-03 · Idempotencia.** *Given* el correo del AC-01 enviado; *When* el job corre otra vez el 20, el 21 o dos veces a la vez; *Then* no se envía otro y `reminder_log` tiene una sola fila para `(owner, 2026-Q4, quarter_deadline)`.

**AC-04 · Recuperación de un día perdido.** *Given* que el job no corrió el 20; *When* corre el 22; *Then* se envía el recordatorio una vez.

**AC-05 · Antelación configurable.** *Given* un usuario con 5 días; *Then* el 24 de enero no recibe nada y el 25 sí; con el valor por defecto (sin fila) se comporta como 10 días.

**AC-06 · Desactivado.** *Given* un usuario con `enabled = false`; *Then* no recibe ningún recordatorio.

**AC-07 · Quién recibe.** *Given* una cuenta suspendida, un gestor y un administrador; *Then* ninguno recibe recordatorios.

**AC-08 · Fallo del envío.** *Given* un proveedor caído (`MemoryEmailSender(fail=True)`); *When* corre el job; *Then* el resultado cuenta `failed`, la fila de `reminder_log` queda `failed` y el resto de usuarios se procesan; *When* el proveedor vuelve y el job corre otra vez dentro de la ventana; *Then* la siguiente ejecución la reclama y se envía.

**AC-09 · Zona horaria.** *Given* `now` = 2027-01-19T23:30:00Z (ya es 20 de enero en Madrid); *Then* el recordatorio sale; con 2027-01-19T22:30:00Z (19 en Madrid, horario de invierno) no.

**AC-10 · Cifras iguales a las pantallas.** *Given* un usuario con facturas y gastos en el trimestre; *Then* los importes del correo coinciden al céntimo con `GET /api/tax/modelo-303` y `modelo-130` del mismo trimestre.

**AC-11 · Contenido seguro.** *Then* el correo y los registros del job no contienen IBAN, NIF completo ni clientes; los registros no llevan correo, asunto, cuerpo ni importes.

**AC-12 · Aislamiento.** *Given* dos usuarios; *Then* el correo de cada uno solo lleva sus cifras (cada consulta del job lleva `owner_id`).

**AC-13 · Ajustes.** *Given* un usuario; *When* hace `PUT /api/me/reminders` con `lead_days = 14`; *Then* `GET` lo devuelve y el job lo usa; `0` o `31` dan `422 invalid_lead_days`; un gestor o un administrador reciben `403`; un usuario no ve ni edita los ajustes de otro (RLS).

**AC-14 · Ruta interna.** *Given* el planificador; *Then* `GET /internal/jobs/reminders` sin secreto o con otro responde `401`, con el correcto ejecuta el job, y la ruta no aparece en `openapi.json`.

**AC-15 · Pantalla.** *Given* un usuario en `/perfil`; *When* desactiva el interruptor o cambia la antelación y guarda; *Then* ve la confirmación y, al recargar, los valores persisten; valores no válidos muestran un error asociado al campo; sin scroll horizontal a 390 y 1.440 px.

**AC-16 · RLS (NFR-06).** *Then* `reminder_settings` y `reminder_log` están en la matriz, con RLS forzada, el gestor y el administrador no leen ni escriben ninguna de las dos, y nadie (tampoco `service_role`) las escribe directamente: solo por las funciones.

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-010 §8.1: pila de Supabase en marcha, puertos 3100 (`E2E_WEB_PORT`), 8000 y 8765 libres, sin red y con datos sintéticos; memoria libre suficiente para los E2E (1 worker).

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                              # aplica las tres migraciones de recordatorios
pytest backend/tests/rls -m rls -q
pytest backend/tests/jobs -k recordatorios -q                      # AC-01 a AC-12 y AC-14
pytest backend/tests/api -k reminder -q                            # AC-13
pytest backend/tests -m "not rls" -q
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
E2E_WEB_PORT=3100 npm --prefix frontend exec -- playwright test e2e/recordatorios.spec.ts --workers=1   # AC-15 (E2E_WEB_PORT solo si el 3000 está ocupado)
```

**Comando único de la spec** (el de `tasks.json`): `pytest backend/tests/jobs -k recordatorios`, además de `pytest backend/tests/rls -m rls` y el E2E.

### 8.3 Correspondencia criterio → prueba

| Criterio | Prueba |
|---|---|
| AC-01, AC-02, AC-05, AC-09 (ventana y zona horaria) | `backend/tests/jobs/test_recordatorios_window.py` (puro) y `test_recordatorios_job.py` (con base de datos) |
| AC-03, AC-04, AC-06, AC-07 | `backend/tests/jobs/test_recordatorios_job.py` (repetición, dos ejecuciones a la vez, día sin ejecución, ajustes, cuentas que no reciben) y `test_recordatorios_recipients.py` |
| AC-08 | `backend/tests/jobs/test_recordatorios_job.py` (envío fallido en una cuenta, error inesperado, reintento) y `backend/tests/rls/test_reminders.py` (reservar, cerrar y reclamar) |
| AC-10, AC-11, AC-12 | `test_recordatorios_job.py` (cifras iguales a `QuarterService`, registros sin datos, cifras de cada dueño) y `test_recordatorios_template.py` (contenido y formato) |
| AC-13 | `backend/tests/api/test_reminders_api.py` y `frontend/src/lib/reminders-form.test.ts` |
| AC-14 | `backend/tests/jobs/test_recordatorios_internal_route.py`, `test_recordatorios_runner.py` y `test_recordatorios_cli.py` |
| AC-15 | `frontend/e2e/recordatorios.spec.ts` (Chromium, Firefox, WebKit; 390 y 1.440 px) |
| AC-16 | `backend/tests/rls/` (matriz, `test_rls_guard.py`) y `backend/tests/rls/test_reminders.py` |

### 8.4 Definición de hecho
La secuencia termina con código 0 en local y en CI; `tasks.json` actualizado; ADR-0007, 0008 y 0016 enlazados; sin secretos ni datos reales; DEP-05 anotada como pendiente para el piloto.

## Anexo A · Orden de implementación (un commit por hito)

1. Spec y `tasks.json`. **Hecho** (2026-11-13).
2. Migración, RLS y matriz. **Hecho** (B.1).
3. Dominio puro: ventana, plantilla y selección. **Hecho** (B.2).
4. Job, ruta interna y CLI. **Hecho** (B.3).
5. API de ajustes, cliente generado y sección de `/perfil`. **Hecho** (B.4).
6. Pruebas restantes, E2E y cierre. **Hecho en local** (B.5); `hecha` cuando la persona confirme el CI de GitHub sobre el head empujado.

## Anexo B · Decisiones que esta spec deja a la implementación

- Cálculo de las cifras: si `QuarterService` exige `CurrentUser`, se extrae la parte que lee con una conexión dada para no duplicar reglas.
- Enlace del correo: `FRONTEND_ORIGIN` + `/trimestres`.
- `vercel.json` con el cron solo si ya existe despliegue (ADR-0016); si no, se documenta la expresión.
- Las cifras del job se calculan con `QuarterService` por `user_transaction` (misma ruta que las pantallas) y no con `service_role`, que no tiene `SELECT` sobre facturas ni gastos ni ejecuta `private.read_owner()`; el job usa `service_transaction` solo para listar destinatarios y reclamar/marcar (hito 4).

### B.1 Hito 2 · Base de datos · 2026-11-13

- Migraciones `20261113100000_reminders.sql` (tablas, RLS forzada, lectura solo del dueño, CHECK `status`/`sent_at`) y `20261113100100_reminders_functions.sql` (`app.set_reminder_settings`, `private.reminder_claim`, `private.reminder_mark`). Ninguna tabla se escribe directamente; `service_role` solo ejecuta las dos funciones `private.*`.
- La reserva no borra nunca (el guard prohíbe `DELETE` a `service_role`): `failed` y `pending` abandonada hace más de 15 min se reclaman de nuevo. No hizo falta cerrojo asesor: la concurrencia de dos reclamaciones la resuelve el `unique` + `on conflict` (probado con dos hilos).
- Verificado: `supabase db reset` limpio; `pytest backend/tests/rls -m rls` 1719 pasan (39 nuevos en `test_reminders.py`); `pytest backend/tests -m "not rls"` 4135 pasan; `ruff check` y `ruff format --check` limpios.

### B.2 Hito 3 · Dominio puro · 2026-11-13

- `cuadre.jobs.reminders` (puro): `due_quarter(today, lead_days)` (ventana `[hoy, hoy + lead_days]` sobre los plazos del año anterior y el actual), `effective_settings` (valores por defecto, D-01), `is_recipient` (D-04) y `DueQuarter.period` (`2026-Q4`).
- `cuadre.notifications.templates.quarter_reminder`: recibe primitivos (año, trimestre, plazo, días, cifras `(céntimos, kind)`, pendientes) y reutiliza `format_euros` y `long_date` de `cuadre.invoicing.texts`. No hay `ReminderFigures` ni `render_reminder` en `jobs`: el job (hito 4) llama directamente a la plantilla. Un importe negativo se muestra en positivo y el texto dice el sentido («a compensar»).
- Verificado: `pytest backend/tests/jobs -k recordatorios` 55 pasan (ventana, zona horaria Madrid, plantilla, destinatarios); `pytest backend/tests -m "not rls"` sin regresiones; ruff limpio.

### B.3 Hito 4 · Job, ruta interna y CLI · 2026-11-13

- Migración `20261113100200_reminders_candidates.sql`: `private.reminder_candidates()` (solo `service_role`) lista las cuentas `usuario` activas con su correo, nombre y ajustes (por defecto, activado y 10 días). `service_role` sigue sin leer `reminder_settings` ni nada financiero.
- `cuadre.jobs.reminders_job.run_reminders`: candidato -> ventana -> `reminder_claim` -> cifras con la identidad de la persona (`QuarterService` y la cuenta de documentos en `review` por `user_transaction` con el pool de la app: mismas funciones que las pantallas) -> envío -> `reminder_mark`. Un fallo (envío o cálculo) deja la fila `failed` y no detiene a los demás; el cierre se reintenta una vez. Solo se registran `user_id`, periodo, resultado y duración. `only_owners` limita a unas cuentas (CLI `--user` y pruebas).
- `cuadre.jobs.runner.run_named_job` es el único punto que abre el pool de servicio (la ruta de `api/` no toca `DATABASE_SERVICE_URL`: lo vigila `test_service_key_scope`). `GET /internal/jobs/{name}` (`include_in_schema=False`) exige `Authorization: Bearer <CRON_SECRET>` con comparación en tiempo constante; sin `CRON_SECRET` configurado responde siempre 401; `404 job_not_found`, `503 job_unavailable`. `python -m cuadre.cli run-job reminders [--now ISO] [--user UUID]` imprime solo contadores y sale con 1 si algún envío falló.
- **Cron (aún sin `vercel.json`: el despliegue no está hecho):** `0 8 * * *` en UTC, es decir 09:00 en invierno y 10:00 en verano, siempre el mismo día de Madrid. Al ser idempotente, repetirlo o adelantarlo es seguro.
- Verificado: `pytest backend/tests/jobs -k recordatorios` 88 pasan (dominio puro, job con base real, ruta interna y CLI); `pytest backend/tests/rls -m rls` 1722; `pytest backend/tests -m "not rls"` 4223; ruff limpio; `export_openapi.py --check` OK (la ruta interna no entra en el contrato).

### B.4 Hito 5 · Ajustes por la API y sección de `/perfil` · 2026-11-13

- `GET/PUT /api/me/reminders` (`get_reminder_settings`, `update_reminder_settings`), solo `usuario`, `Cache-Control: private, no-store`. Sin ajustes guardados, el GET devuelve `{enabled: true, lead_days: 10}` (D-01). El cuerpo es estricto en el tipo (`StrictBool`, `StrictInt`, sin campos extra: forma incorrecta -> `422 validation_error`), pero el rango (1 a 30) lo decide el servicio (`check_lead_days`, la misma regla que el job) para responder `422 invalid_lead_days` con `field: "lead_days"` y un `detail` fijo que no repite lo enviado. La función SQL tiene la última palabra.
- Frontend: tarjeta «Recordatorios» en `/perfil`, entre el formulario del perfil y el logo, con su propio botón «Guardar recordatorios» (escritura distinta de la del perfil) y confirmación «Recordatorios guardados.» (distinta de «Cambios guardados.» para no confundirse con el otro formulario). La interfaz solo cruza texto con entero y no decide el rango; el error del servidor sale junto al campo y no se pierde lo tecleado.
- `ProfileApi.restore()` de los E2E también restaura los recordatorios (activados, 10 días): la cuenta `gastosUser` es del worker.
- Verificado: `pytest backend/tests/api -k reminder` 29 pasan; `export_openapi.py --check` y `gen:api -- --check` OK; `npm run test:unit` 326, `lint` y `typecheck` limpios; `playwright test e2e/recordatorios.spec.ts` 72 pasan (3 navegadores x 390/1.440 px, 1 worker, `E2E_WEB_PORT=3100`).

### B.5 Hito 6 · Cierre · 2026-11-13

- **Matriz criterio -> prueba** corregida en §8.3 con los archivos reales (la primera versión citaba tres que no existen) y `E2E_WEB_PORT` en §8.2.
- **Mutaciones** (cambios deliberados con las pruebas lanzadas después; cada archivo se restauró y se comprobó): 15 en Python y 6 en SQL. Detectadas 19 de 21. Las dos que sobreviven son equivalentes y se dejan: M15 (la API no pre-valida el rango de la antelación: lo rechaza la función SQL con el mismo `invalid_lead_days`) y M14 (el runner no exige zona horaria: lo exige igualmente `today_in_madrid`, con el mismo error). Cubren los extremos de la ventana, la reserva previa, el cierre `sent`/`failed`, el día de Madrid, el trimestre de las cifras, el estado de los pendientes, el filtro de cuentas, el secreto del cron (cualquiera y vacío), el rol de la ruta, los valores por defecto, el destinatario activo, la RLS forzada, una política de lectura ajena, reclamar fallidas, los candidatos suspendidos, el rol de `set_reminder_settings` y el cierre de reservas no pendientes. Se añadió `test_recordatorios_runner.py` (job desconocido, hora sin zona, sin base de servicio).
- **Prueba intermitente corregida** (ajena a W-014, pero bloqueaba el CI): `e2e/roles.spec.ts` «Mi gestor ... menú» leía el menú con `allInnerTexts()` sin esperar y fallaba hacia la mitad de las veces a 390 px. Ahora espera a que el enlace «Perfil» esté en el DOM; 8 de 8 repeticiones pasan.
- **Verificado en local:** `supabase db reset` con las tres migraciones; `pytest backend/tests/rls -m rls` 1722; `pytest backend/tests/jobs -k recordatorios` 91; `pytest backend/tests/api -k reminder` 29; `pytest backend/tests -m "not rls"` 4252 (antes de añadir el test del runner); `ruff` limpio; `export_openapi.py --check` y `gen:api -- --check` al día; `test:unit` 326, `lint`, `typecheck`, `build` y `check:bundle` en verde; E2E `recordatorios` 72 (3 navegadores x 2 anchos); `perfil`, `roles` y `responsive` sin fallos salvo la intermitente ya corregida.
- **Barrido de datos:** sin claves ni IBAN en lo nuevo; `CRON_SECRET` solo como nombre en `.env.example` y en el código; los registros del job no llevan correo, asunto, cuerpo ni importes (probado).
- **Pendiente para el piloto (no de esta spec):** DEP-05 (proveedor de correo real; ADR-0008 sigue «Propuesto»), `vercel.json` con el cron `0 8 * * *` (UTC) cuando exista el despliegue (ADR-0016) y fijar `CRON_SECRET` en el entorno.
- **Estado:** `en-revision` hasta que la persona confirme el CI de GitHub sobre el head empujado; entonces `hecha`.
