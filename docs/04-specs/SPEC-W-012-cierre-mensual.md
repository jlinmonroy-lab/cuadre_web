---
tipo: spec
id: SPEC-W-012
titulo: Cierre mensual automático e idempotente y pantalla «Contabilidad mensual»
estado: en-revision
prioridad: must
riesgo: bajo
historias: [US-008]
requisitos: [RF-012]
nfr: [NFR-09, NFR-06]
restricciones: [RES-02, RES-07]
adr: [0003, 0005, 0007, 0015, 0016]
depende_de: [SPEC-W-003, SPEC-W-007]
bloquea: [SPEC-W-013]
fecha: 2026-11-13
---

# SPEC-W-012 · Cierre mensual automático e idempotente

> El día 1 de cada mes, el mes anterior queda **cerrado** con sus totales **por ámbito** (nacional, UE y fuera de la UE) y **por cliente**, el total del mes, los gastos y el acumulado del año. El cierre es un **job idempotente con reloj inyectado** (ADR-0007) que reutiliza la infraestructura de SPEC-W-014 (ruta interna del planificador, `run-job`, `service_transaction`). Si más tarde llega un documento con fecha de un mes ya cerrado, el mes **se reabre y se vuelve a cerrar**. La persona lo consulta en la pantalla «Contabilidad mensual», hoy «Próximamente» en el menú.

## 1. Contexto

**Situación de partida.** Existen las facturas (`invoices`: `issue_date`, `base_cents`, `client_id`, `client_name`, `client_scope`, `kind`, rectificativas con su diferencia y su signo) y los gastos (`expenses`: `expense_date`, `base_cents`, `vat_cents`, `deductible_vat`, `voided_at`); las lecturas por periodo de `cuadre.quarters`; los jobs de SPEC-W-014 (`cuadre.jobs.runner`, `GET /internal/jobs/{name}` con `CRON_SECRET`, `python -m cuadre.cli run-job`, `service_transaction`, el patrón «candidatos por función SQL, cifras con la identidad de cada persona»); y el prototipo `docs/cuadre-interfaz.html` con la pantalla «Contabilidad mensual» (`operation_id: get_monthly_closings`).

**Qué falta.** No hay tabla de cierres, ni job, ni API, ni pantalla. El apartado «Contabilidad mensual» del menú está desactivado.

**Decisiones de la persona (2026-11-13).** (1) El alcance es **job, API y pantalla**: ninguna otra spec cubre la pantalla (SPEC-W-013 es el reporte visual con gráficos). (2) La **reapertura** se detecta con un **recálculo diario de los últimos 12 meses cerrados**, sin disparadores en las tablas de facturas ni de gastos.

**Decisiones vigentes** (no se reabren): ADR-0007 (función Python con `now` inyectado, `INSERT … ON CONFLICT (owner_id, year, month)`, Europe/Madrid, repetir es seguro); ADR-0016 (el planificador hace GET en UTC; sin trabajo posterior a la respuesta); RES-02 (céntimos enteros, nunca `float`); T-04 (la clave de servicio solo en `cuadre.jobs` y `cuadre.cli`); `service_role` no lee datos financieros, así que las cifras se calculan con la identidad de cada persona, como las pantallas y como en SPEC-W-014.

**Decisiones que propone esta spec** (la persona las confirma o corrige antes del hito 2):

| ID | Decisión | Alternativa y coste |
|---|---|---|
| D-01 | **Tabla `public.monthly_closings`** con clave `(owner_id, year, month)`. Guarda la **foto** del cierre: número de facturas, importes por ámbito, total, gastos, desglose por cliente, `revision`, `first_closed_at` y `closed_at`. Importes en céntimos enteros. Sin datos de facturas sueltas | Guardar solo el último estado y recalcular al leer: no habría «cierre» ni constancia de reaperturas (NFR-09) |
| D-02 | **Ingresos = bases imponibles** (sin IVA) de todas las facturas del mes por `issue_date`, con las rectificativas contando su **diferencia en el mes de su fecha** (el mes de la original no cambia). **Gastos = base + IVA no deducible** de los gastos no anulados por `expense_date` (como el prototipo y como el coste del 130). **Nº de facturas = solo ordinarias** | Contar también las rectificativas: el número ya no sería «facturas emitidas» |
| D-03 | El **acumulado del año no se guarda**: la API lo suma de los cierres del año hasta cada mes. Así, si un mes antiguo se reabre, los siguientes no quedan desfasados | Guardarlo en cada fila: obliga a reescribir en cascada |
| D-04 | **Escritura solo por función** `private.close_month` (`SECURITY DEFINER`, `search_path = ''`, solo `service_role`): inserta, o reescribe con `revision + 1` si la foto cambia, o no hace nada si es idéntica. La tabla no se escribe directamente, ni el dueño ni `service_role` (que no tiene `DELETE`) | Escribir con `INSERT` directo desde Python: dos sitios para una regla de integridad |
| D-05 | **Ventana**: cada ejecución recalcula, por persona, los **últimos 12 meses ya terminados** en Europe/Madrid (del mes anterior al de «hoy» hacia atrás), sin pasar del **primer mes con actividad** (el más antiguo entre el del alta de la cuenta, el de su primera factura y el de su primer gasto). Dos consultas por persona (facturas y gastos de toda la ventana), agrupadas en Python. El día 1 se cierra el mes que acaba de terminar; el resto de los días el recálculo detecta documentos atrasados y **reabre y vuelve a cerrar** (`revision + 1`). Un documento atrasado se refleja como mucho en la siguiente ejecución | Disparador en las tablas: más inmediato pero toca facturas y gastos (descartado por la persona) |
| D-06 | **Meses sin actividad** dentro de la ventana se cierran **a cero**; los anteriores al primer mes con actividad no existen | Cerrar desde enero: filas vacías para cuentas nuevas |
| D-07 | **Job `monthly_closing`** en el mismo `JOB_NAMES`; `cli run-job monthly_closing [--now ISO] [--user UUID …] [--month AAAA-MM]`. `--month` recalcula un único mes aunque esté fuera de la ventana de 12 meses (operación manual, ADR-0007). Cron propuesto: `0 3 * * *` (UTC), el mismo día de Madrid en verano e invierno | Un job por mes concreto solo: no recogería los atrasados |
| D-08 | **API**: `GET /api/monthly-closings?year=AAAA` y `GET /api/monthly-closings/{year}/{month}`. Los meses terminados con cierre salen como `closed` (la foto); el **mes en curso** y los terminados aún sin cierre (antes de la primera ejecución) se calculan **en vivo** con la misma función pura y salen como `in_progress` o `pending`, sin guardarse | Mostrar solo cierres: el mes en curso quedaría vacío hasta el día 1 |
| D-09 | **Pantalla `/mensual`**: tabla de meses del año, panel con el detalle del mes elegido (ingresos por cliente con su ámbito y resultado = ingresos − gastos) y selector de año; solo lectura. Activa «Contabilidad mensual» en el menú del rol `usuario`, entre «Gastos» y «Trimestres» | Dejarla para SPEC-W-013 |
| D-10 | **RLS** del patrón del repositorio: `usuario` lee lo suyo; `gestor` lee solo con vínculo activo (sin pantalla en esta spec); `admin` ninguna política (D3) | |

## 2. Objetivo

Que cada mes terminado quede cerrado de forma automática, repetible y verificable con fechas simuladas, con sus totales por ámbito y por cliente; que un documento atrasado reabra y rehaga el cierre sin descuadrar el acumulado; y que la persona vea sus meses en «Contabilidad mensual».

## 3. Alcance explícito

### 3.1 Base de datos
- Migración con `public.monthly_closings` (RLS forzada, lectura del dueño y del gestor vinculado, claves y CHECK de coherencia), `private.close_month` y `private.closing_candidates`; registro en `rls_matrix.yaml`.

### 3.2 Backend (FastAPI)
- `cuadre.closing`: reglas puras (`build_month`, `closing_window`), lecturas por ventana, servicio de la API.
- `cuadre.jobs.closing_job.run_monthly_closing` y su registro en `cuadre.jobs.runner`; `run-job monthly_closing` en la CLI.
- `GET /api/monthly-closings` y `GET /api/monthly-closings/{year}/{month}`.

### 3.3 Frontend (Next.js)
- Página `/mensual`, activación del menú, lecturas con el cliente generado y pruebas unitarias del formateo.

### 3.4 Pruebas
- Reglas puras con fechas simuladas; job con base real (`FixedClock`); API; RLS; E2E de la pantalla.

## 4. Alcance excluido

- **Reporte visual** (gráficos, gastos por categoría, comparación con el mes anterior, «lo que conviene apartar»): SPEC-W-013.
- Envío del reporte por correo o en PDF (*Could*) y cualquier correo al cerrar.
- Pantalla del gestor para los cierres (la política de lectura existe; la pantalla, no).
- Meses con más de 12 de antigüedad: solo se recalculan a mano con `--month`.
- Disparadores en las tablas de facturas y de gastos.
- `vercel.json` y el despliegue (ADR-0016); el cron queda propuesto.
- Declaraciones o envío de nada a la AEAT (RES-04).

## 5. Contrato de interfaces

### 5.1 Reglas
- **Mes de un documento**: el de su `issue_date` (facturas, también rectificativas) o su `expense_date` (gastos), en calendario. No se convierte ninguna zona horaria: son fechas.
- **Ámbito** de un ingreso: el `client_scope` guardado en la factura (`national`, `eu`, `non_eu`), no el actual del cliente.
- **`total_cents`** = `national_cents + eu_cents + non_eu_cents` (puede ser negativo si hay más rectificaciones que facturas).
- **`expenses_cents`** = suma, de los gastos no anulados del mes, de `base_cents + (0 si deductible_vat, vat_cents si no)`.
- **Desglose por cliente** (`by_client`): una entrada por `client_id` con al menos una factura (ordinaria o rectificativa) en el mes: `{client_id, name, scope, base_cents, invoice_count}`; el nombre es el de la última factura del cliente en el mes; orden por `base_cents` descendente, después nombre y `client_id`. La suma de `base_cents` del desglose es igual a `total_cents`.
- **Primer mes con actividad** de una persona: el más antiguo entre el mes de `profiles.created_at` en Madrid, el de su primera factura y el de su primer gasto. Antes de él no hay cierres.
- **Ventana**: del mes anterior al de `hoy` (Madrid) hacia atrás, 12 meses como máximo y sin pasar del primer mes con actividad. Con `--month`, solo ese mes (tiene que haber terminado y no ser anterior a `2000-01`).
- **Idempotencia**: ejecutar el job con el mismo estado de los datos no cambia nada (`revision`, `closed_at` ni `first_closed_at`). Si la foto difiere de la guardada, se reescribe, `revision` sube en 1 y `closed_at` se actualiza; `first_closed_at` no cambia.
- **Estado de un mes en la API**: `closed` (hay cierre, se devuelve la foto), `pending` (terminó y aún no hay cierre: cifras en vivo), `in_progress` (es el mes de «hoy»: cifras en vivo). Los meses futuros no se listan.
- **Importes**: enteros en céntimos en la base y en la API; el cliente los formatea con `Intl.NumberFormat('es-ES')`. Ningún `float`.
- **Registros**: `user_id`, `period` (`AAAA-MM`), resultado y duración. Nunca nombres de clientes, importes ni correos.

### 5.2 Base de datos
```sql
create table public.monthly_closings (
  owner_id        uuid not null references public.profiles (id) on delete cascade,
  year            integer not null check (year between 2000 and 9998),
  month           integer not null check (month between 1 and 12),
  invoice_count   integer not null check (invoice_count >= 0),
  national_cents  bigint  not null,
  eu_cents        bigint  not null,
  non_eu_cents    bigint  not null,
  total_cents     bigint  not null,
  expenses_cents  bigint  not null,
  by_client       jsonb   not null default '[]',
  revision        integer not null default 1 check (revision >= 1),
  first_closed_at timestamptz not null default now(),
  closed_at       timestamptz not null default now(),
  primary key (owner_id, year, month),
  check (total_cents = national_cents + eu_cents + non_eu_cents),
  check (jsonb_typeof(by_client) = 'array')
);
```
- `private.close_month(p_owner uuid, p_year int, p_month int, p_payload jsonb) → text` (`'closed' | 'reopened' | 'unchanged'`): valida la forma y la coherencia del payload (`invalid_closing`, `P0001`) e inserta con `ON CONFLICT (owner_id, year, month) DO UPDATE … WHERE` la foto difiere. Solo `service_role`.
- `private.closing_candidates() → table (owner_id, created_at)`: cuentas `usuario` activas. Solo `service_role`. Sin nada financiero.
- Todas las funciones, `SECURITY DEFINER` con `set search_path = ''`.

### 5.3 API HTTP
| `operation_id` | Ruta | Rol | Respuesta |
|---|---|---|---|
| `get_monthly_closings` | `GET /api/monthly-closings?year=AAAA` | `usuario` | `{year, months: [{month, status, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, expenses_cents, ytd_cents, revision, closed_at}], totals}` |
| `get_monthly_closing` | `GET /api/monthly-closings/{year}/{month}` | `usuario` | lo mismo para un mes más `by_client` |
| (interna) | `GET /internal/jobs/monthly_closing` | planificador | `{closed, reopened, unchanged, failed}`, con las reglas de SPEC-W-014 (`401` sin secreto) |

`year` por defecto, el de hoy en Madrid. `422 invalid_period` si el año o el mes no existen y `422 period_in_future` si todavía no ha empezado. `gestor` y `admin` reciben `403`. Cabecera `Cache-Control: private, no-store`.

### 5.4 Backend
- `cuadre.closing.rules` (puro, sin base de datos ni reloj): `MonthTotals`, `ClientTotals`, `build_month(year, month, invoices, expenses)`, `closing_window(today, first_month, months=12)`, `previous_month`.
- `cuadre.jobs.closing_job.run_monthly_closing(service_pool, app_pool, now, only_owners=None, month=None) -> ClosingResult`; `cuadre.jobs.runner` pasa a registrar los jobs por nombre (el de recordatorios no cambia de comportamiento).
- Cifras con `user_transaction` y la consulta por ventana (`private.read_owner()`); la clave de servicio solo para listar candidatos y llamar a `close_month`.
- Un fallo con una persona (datos ilegibles, documentos de más: límite de filas) se cuenta como `failed`, se registra sin datos y no detiene a las demás.

### 5.5 Frontend
`/mensual`: tabla (Mes, Estado, Facturas, Nacional, UE, Fuera de la UE, Total del mes, Gastos, Acumulado del año; pie con el total del año), panel «Ingresos por cliente» con insignia de ámbito, panel «Resultado» y la nota de cierre y reapertura del prototipo; selector de año; el mes elegido se pasa por la URL (`?anio=2026&mes=9`). Tokens del prototipo, etiquetas en los controles, sin scroll horizontal a 390 y 1.440 px.

## 6. Restricciones técnicas
- Sin `float`. Sin llamar a ninguna API de modelos. `database_service_url` y `service_transaction` solo en `cuadre.jobs`/`cuadre.cli`; la ruta de la API no los toca.
- El job no abre más de una transacción de usuario por persona y ventana, y no retiene conexiones mientras calcula.
- Límite de filas por persona y consulta (facturas y gastos de la ventana): si se supera, esa persona falla (`failed`) sin afectar al resto.
- Datos solo sintéticos; el cron propuesto no se crea sin despliegue.

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Cierre del mes (US-008).** *Given* un usuario con facturas a clientes nacionales, de la UE y de fuera de la UE y con gastos en septiembre; *When* el job corre el 1 de octubre; *Then* septiembre queda cerrado con los totales por ámbito, el total, los gastos, el número de facturas y el desglose por cliente, con `revision = 1`.

**AC-02 · Mes sin actividad.** *Given* un usuario con actividad en agosto y octubre; *When* el job corre el 1 de noviembre; *Then* septiembre queda cerrado a cero y con `by_client` vacío.

**AC-03 · Idempotencia.** *Given* un mes cerrado; *When* el job corre otra vez (el mismo día o los siguientes); *Then* no cambia nada: una sola fila, misma `revision`, mismo `closed_at` y mismo `first_closed_at`.

**AC-04 · Ejecuciones simultáneas.** *Given* dos ejecuciones a la vez; *Then* queda una sola fila por mes con `revision = 1`.

**AC-05 · Reapertura por un documento atrasado.** *Given* septiembre cerrado; *When* se registra un gasto con fecha de septiembre (o se emite una factura con fecha de septiembre en otra serie) y el job corre; *Then* septiembre se reescribe con `revision = 2`, `closed_at` posterior y `first_closed_at` igual, y el acumulado de los meses siguientes refleja el cambio.

**AC-06 · Anulación posterior.** *Given* un mes cerrado con un gasto; *When* el gasto se anula y el job corre; *Then* el cierre baja los gastos y sube `revision`.

**AC-07 · Rectificativas.** *Given* una factura de agosto rectificada en septiembre; *Then* agosto conserva su importe y septiembre recoge la diferencia (con su signo) en el ámbito y el cliente de la factura.

**AC-08 · Primer mes con actividad.** *Given* una cuenta creada en octubre sin facturas anteriores; *Then* no hay cierres de enero a septiembre; *Given* una cuenta con una factura fechada en marzo; *Then* se cierran desde marzo (dentro de la ventana).

**AC-09 · Ventana.** *Given* una cuenta con actividad desde hace 20 meses; *Then* una ejecución recalcula los últimos 12 meses terminados; *When* se usa `--month` con un mes anterior; *Then* solo se recalcula ese mes.

**AC-10 · Día de Madrid y cambio de año.** *Given* `now` = 2026-12-31T23:30Z (ya es 1 de enero en Madrid); *Then* diciembre queda cerrado; con 2026-12-31T22:30Z (todavía 31) solo hasta noviembre.

**AC-11 · Acumulado y coherencia.** *Then* `ytd_cents` de cada mes es la suma de los totales de los cierres del año hasta ese mes y cambia si un mes anterior se reabre; la suma de `total_cents` de los meses de un trimestre es igual a la suma de las bases de las facturas de ese trimestre que usa el 130.

**AC-12 · Quién se cierra.** *Given* un gestor, un administrador y una cuenta suspendida; *Then* no tienen cierres.

**AC-13 · Un fallo no detiene a los demás.** *Given* una persona cuyos datos fallan; *Then* se cuenta `failed`, el resto se cierra y los registros no llevan nombres, importes ni correos.

**AC-14 · Aislamiento.** *Given* dos personas con clientes distintos; *Then* el desglose de cada una solo tiene los suyos.

**AC-15 · Ruta interna y CLI.** *Then* `GET /internal/jobs/monthly_closing` sin secreto o con otro responde `401`, con el correcto devuelve `{closed, reopened, unchanged, failed}`; `python -m cuadre.cli run-job monthly_closing --now … --user … [--month AAAA-MM]` imprime solo contadores y sale con 1 si algún cierre falló.

**AC-16 · API de la lista.** *Given* un año con meses cerrados, el mes en curso y uno terminado sin cierre; *Then* salen como `closed`, `in_progress` y `pending` con sus cifras; un año futuro o inexistente da `422`; el gestor y el administrador reciben `403`; sin cierres la lista está vacía.

**AC-17 · API del detalle.** *Then* el detalle de un mes trae el desglose por cliente ordenado; el mes en curso se calcula en vivo; un mes futuro da `422 period_in_future`.

**AC-18 · Pantalla.** *Given* un usuario en `/mensual`; *Then* ve la tabla de meses con su estado y el acumulado, elige un mes y ve sus clientes y su resultado, cambia de año, y «Contabilidad mensual» está activa en el menú entre «Gastos» y «Trimestres» solo para `usuario`; todos los campos tienen etiqueta y no hay scroll horizontal a 390 y 1.440 px.

**AC-19 · RLS (NFR-06).** *Then* `monthly_closings` está en la matriz con RLS forzada; el dueño lee lo suyo, el gestor solo con vínculo activo, el administrador nada; nadie (tampoco `service_role`) la escribe directamente.

**AC-20 · Integridad del cierre.** *Then* `close_month` rechaza un payload cuyo total no cuadra con los ámbitos o cuyo desglose no suma el total, y el módulo de cálculo no usa `float`.

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-014 §8.1: pila de Supabase en marcha, puertos 3100 (`E2E_WEB_PORT`), 8000 y 8765 libres, sin red, datos sintéticos y memoria libre suficiente para los E2E (1 worker).

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                              # aplica las migraciones de cierres
pytest backend/tests/rls -m rls -q
pytest backend/tests/jobs -k cierre_mensual -q                     # AC-01 a AC-15
pytest backend/tests/api -k monthly -q                             # AC-16 y AC-17
pytest backend/tests -m "not rls" -q
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
E2E_WEB_PORT=3100 npm --prefix frontend exec -- playwright test e2e/mensual.spec.ts e2e/roles.spec.ts --workers=1   # AC-18
```

**Comando único de la spec** (el de `tasks.json`): `pytest backend/tests/jobs -k cierre_mensual`, además de `pytest backend/tests/rls -m rls` y el E2E.

### 8.3 Correspondencia criterio → prueba

Se rellena con los archivos reales al cerrar el hito 6 (la de SPEC-W-014 citaba archivos que no existían). Previsto: `tests/jobs/test_cierre_mensual_{rules,job,runner,internal_route,cli}.py`, `tests/api/test_monthly_api.py`, `tests/rls/test_monthly_closings.py`, `frontend/src/lib/monthly-*.test.ts` y `frontend/e2e/mensual.spec.ts`.

### 8.4 Definición de hecho
La secuencia termina con código 0 en local y en CI; `tasks.json` actualizado; ADR-0007 y ADR-0016 enlazados; sin secretos ni datos reales; el cron propuesto queda anotado para el despliegue.

## Anexo A · Orden de implementación (un commit por hito, salvo que convenga agrupar)

1. Spec y `tasks.json`. **Hecho** (2026-11-13).
2. Migración, RLS y matriz. **Hecho** (B.1).
3. Reglas puras: `build_month` y `closing_window`.
4. Job, ruta interna y CLI.
5. API, cliente generado y pantalla `/mensual`.
6. Pruebas restantes, mutaciones y cierre (`hecha` solo con el CI de GitHub confirmado por la persona).

## Anexo B · Decisiones que esta spec deja a la implementación

- Forma exacta del `payload` de `close_month` y del `RETURNING` para distinguir inserción, reescritura y «sin cambios» en una sola sentencia.
- Valor del límite de filas por persona y consulta.
- Si la CLI acepta también el alias `close-month --month AAAA-MM` de ADR-0007 además de `run-job monthly_closing --month`.
- Que el servicio de la API reutilice las reglas puras para el mes en curso y los pendientes.

### B.1 Hito 2 · Base de datos · 2026-11-13

- Migraciones `20261113200000_monthly_closings.sql` (tabla con RLS forzada, política de lectura del dueño y del gestor vinculado, ninguna para el administrador, CHECK con nombre) y `20261113200100_monthly_closings_functions.sql` (`private.close_month` y `private.closing_candidates`, solo `service_role`). Nadie escribe la tabla directamente.
- `close_month` valida todo antes de escribir (`invalid_closing`, sin repetir datos): año y mes, seis importes enteros, `total = nacional + UE + fuera de la UE` y el desglose por cliente, que tiene que sumar **cada ámbito** y **el número de facturas** (más estricto que el §5.1: así una foto incoherente no llega a la base). Por eso, en `by_client`, `invoice_count` es el número de facturas **ordinarias** del cliente, igual que el del mes (D-02), y puede ser 0 si el cliente solo tiene rectificativas en el mes.
- Una sola sentencia `INSERT … ON CONFLICT … DO UPDATE … WHERE` la foto difiere, con `RETURNING (xmax = 0)`: devuelve `closed`, `reopened` o `unchanged`. El orden de `by_client` forma parte de la foto: cambiarlo reabre el mes, así que el job tiene que ordenar siempre igual. El mes **no** se compara con el reloj de la base de datos (lo decide el job).
- Verificado: `supabase db reset` limpio; `pytest backend/tests/rls/test_monthly_closings.py` 63 pasan (cierre, idempotencia, reapertura, dos ejecuciones a la vez con el mismo y con distinto contenido, 22 payloads incoherentes, escritura directa denegada a cinco personas y a `service_role`, privilegios, políticas, candidatos y CHECK por nombre); `pytest backend/tests/rls -m rls` 1799 pasan (con la tabla en la matriz).
