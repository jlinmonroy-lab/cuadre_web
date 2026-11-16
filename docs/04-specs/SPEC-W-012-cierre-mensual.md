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
- **Desglose por cliente** (`by_client`): una entrada por cliente **y ámbito** con al menos una factura (ordinaria o rectificativa) en el mes (lo normal es una por cliente: solo hay dos si sus facturas cambiaron de ámbito dentro del mes): `{client_id, name, scope, base_cents, invoice_count}`, donde `invoice_count` cuenta solo las ordinarias; el nombre es el de la última factura del cliente en el mes; orden por `base_cents` descendente, después nombre y `client_id`. El desglose suma `total_cents`, cada ámbito y el `invoice_count` del mes.
- **Primer mes con actividad** de una persona: el más antiguo entre el mes de `profiles.created_at` en Madrid, el de su primera factura y el de su primer gasto. Antes de él no hay cierres.
- **Ventana**: del mes anterior al de `hoy` (Madrid) hacia atrás, 12 meses como máximo y sin pasar del primer mes con actividad. Con `--month`, solo ese mes (tiene que haber terminado y no ser anterior a `2000-01`).
- **Idempotencia**: ejecutar el job con el mismo estado de los datos no cambia nada (`revision`, `closed_at` ni `first_closed_at`). Si la foto difiere de la guardada, se reescribe, `revision` sube en 1 y `closed_at` se actualiza; `first_closed_at` no cambia.
- **Estado de un mes en la API**: `closed` (hay cierre, se devuelve la foto), `pending` (terminó y aún no hay cierre: cifras en vivo), `in_progress` (es el mes de «hoy»: cifras en vivo). Los meses futuros no se listan. Un mes antiguo sin cierre (anterior a los 12 meses que recalcula el job) también es `pending`. La lista empieza en el primer mes con actividad (un año anterior da `months: []`), pero un cierre que ya existe sale siempre.
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
| `get_monthly_closings` | `GET /api/monthly-closings?year=AAAA` | `usuario` | `{year, months: [{month, status, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, expenses_cents, result_cents, ytd_cents, revision, closed_at}], totals}` |
| `get_monthly_closing` | `GET /api/monthly-closings/{year}/{month}` | `usuario` | lo mismo para un mes más `by_client` |
| (interna) | `GET /internal/jobs/monthly_closing` | planificador | `{closed, reopened, unchanged, failed}`, con las reglas de SPEC-W-014 (`401` sin secreto) |

`year` por defecto, el de hoy en Madrid. `result_cents` es ingresos menos gastos del mes. `422 invalid_period` si el año o el mes no existen, `422 period_in_future` si todavía no ha empezado y, en el detalle, `404 closing_not_found` para un mes anterior al primero con actividad. `gestor` y `admin` reciben `403`. Cabecera `Cache-Control: private, no-store`.

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

**AC-16 · API de la lista.** *Given* un año con meses cerrados, el mes en curso y uno terminado sin cierre; *Then* salen como `closed`, `in_progress` y `pending` con sus cifras; un año futuro o inexistente da `422`; el gestor y el administrador reciben `403`; una cuenta nueva ve su mes de alta como `in_progress` y un año anterior a su actividad da una lista vacía.

**AC-17 · API del detalle.** *Then* el detalle de un mes trae el desglose por cliente ordenado; el mes en curso se calcula en vivo; un mes futuro da `422 period_in_future` y un mes anterior al primero con actividad, `404 closing_not_found`.

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
E2E_WEB_PORT=3100 npm --prefix frontend exec -- playwright test e2e/mensual.spec.ts e2e/roles.spec.ts e2e/responsive.spec.ts --workers=1   # AC-18 (E2E_WEB_PORT solo si el 3000 está ocupado)
```

**Comando único de la spec** (el de `tasks.json`): `pytest backend/tests/jobs -k cierre_mensual`, además de `pytest backend/tests/rls -m rls` y el E2E.

### 8.3 Correspondencia criterio → prueba

| Criterio | Prueba |
|---|---|
| AC-01, AC-02, AC-03, AC-04 | `backend/tests/jobs/test_cierre_mensual_job.py` (cierre, mes a cero, repetir, dos ejecuciones a la vez) y `test_cierre_mensual_rules.py` |
| AC-05, AC-06, AC-07 | `test_cierre_mensual_job.py` (gasto atrasado, factura en otra serie, anulación posterior, rectificativa) y `tests/api/test_monthly_api.py` (la foto no cambia hasta que corre el job) |
| AC-08, AC-09, AC-10 | `test_cierre_mensual_job.py`, `test_cierre_mensual_window.py` (ventana, primer mes, mes pedido, día de Madrid y cambio de año), con el alta de la cuenta desplazada para no depender del reloj real |
| AC-11 | `test_cierre_mensual_properties.py` (casilla 01 y gastos del 130 con documentos aleatorios) y `test_cierre_mensual_job.py` (130 por trimestre con base real) |
| AC-12, AC-13, AC-14 | `test_cierre_mensual_job.py` (quién se cierra, fallo aislado y registros sin datos, aislamiento) |
| AC-15 | `test_cierre_mensual_internal_route.py`, `test_cierre_mensual_runner.py` y `test_cierre_mensual_cli.py` |
| AC-16, AC-17 | `backend/tests/api/test_monthly_api.py` |
| AC-18 | `frontend/e2e/mensual.spec.ts`, `roles.spec.ts`, `responsive.spec.ts` y `frontend/src/lib/monthly.test.ts` |
| AC-19 | `backend/tests/rls/test_monthly_closings.py`, la matriz de RLS y `test_rls_guard.py` |
| AC-20 | `test_monthly_closings.py` (22 payloads incoherentes y las CHECK), `test_cierre_mensual_payload.py` (deriva contra la base) y `test_cierre_mensual_rules.py` (sin `float`) |

### 8.4 Definición de hecho
La secuencia termina con código 0 en local y en CI; `tasks.json` actualizado; ADR-0007 y ADR-0016 enlazados; sin secretos ni datos reales; el cron propuesto queda anotado para el despliegue.

## Anexo A · Orden de implementación (un commit por hito, salvo que convenga agrupar)

1. Spec y `tasks.json`. **Hecho** (2026-11-13).
2. Migración, RLS y matriz. **Hecho** (B.1).
3. Reglas puras: `build_month` y `closing_window`. **Hecho** (B.2).
4. Job, ruta interna y CLI. **Hecho** (B.3).
5. API, cliente generado y pantalla `/mensual`. **Hecho** (B.4).
6. Pruebas restantes, mutaciones y cierre. **Hecho en local** (B.5); `hecha` cuando la persona confirme el CI de GitHub sobre el head empujado.

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

### B.2 Hito 3 · Reglas puras · 2026-11-13

- Paquete `cuadre.closing` (puro: sin base de datos, red ni reloj): `limits.py` (`WINDOW_MONTHS = 12`, `CLOSING_MAX_DOCUMENTS = 20 000`), `types.py` (`YearMonth` con calendario, `MonthInvoice`, `MonthExpense`, `ClientTotals`, `MonthTotals`) y `rules.py` (`closing_window`, `explicit_window`, `first_active_month`, `month_bounds`, `window_bounds`, `build_month`, `build_months`, `payload_of`). El ámbito se redefine en `types.py` para no importar el paquete de clientes.
- **Precisión sobre §5.1:** el desglose lleva una entrada por **cliente y ámbito**, no solo por cliente. Si las facturas de un cliente cambian de ámbito dentro del mes (el ámbito es el guardado en cada factura), aparece una entrada por ámbito; así el desglose sigue sumando cada ámbito, que es lo que exige `private.close_month` (B.1). Lo normal sigue siendo una entrada por cliente.
- **Orden del desglose** (forma parte de la foto): `base_cents` descendente, después `name` (orden por código de carácter) y `client_id`. El nombre es el de la última factura del cliente en el mes (por fecha y, a igualdad, por id).
- `build_months` agrupa los documentos una sola vez para toda la ventana (dos consultas por persona) y rechaza con `TypeError` cualquier importe que no sea un entero (ni `bool`) y con `ClosingTooLarge` (`closing_too_large`) más de 20 000 documentos; `InvalidMonth` usa el código `invalid_period` y `PeriodInFuture` el de siempre.
- **Coherencia con el 130 comprobada:** para cualquier conjunto de documentos aleatorios, la suma de los meses de enero al fin de cada trimestre es la casilla 01 del 130 y su casilla 02 coincide con los gastos del cierre.
- Verificado: `pytest backend/tests/jobs -k cierre_mensual` 119 pasan (70 de reglas y ventana, 6 propiedades de 300 ejecuciones con semilla fija y 43 de deriva contra `private.close_month`, incluida la reapertura de punta a punta); `pytest backend/tests/jobs` 210; `ruff` limpio; el módulo no contiene `float`, `Decimal`, `locale` ni `round(`. Dos cambios deliberados (ignorar el `voided` de los gastos y sumar todo al ámbito nacional) los detectan las pruebas.

### B.3 Hito 4 · Job, ruta interna y CLI · 2026-11-13

- `cuadre.jobs.closing_job.run_monthly_closing` y `cuadre.closing.repository` (lecturas con la identidad de la persona: `invoices_between`, `expenses_between`, `first_dates`). Por persona, una transacción corta de lectura (primer mes, ventana y dos consultas para toda la ventana) y, después, **una transacción de servicio por mes** con `private.close_month`: un fallo a medias deja lo ya guardado y la siguiente ejecución sigue desde ahí.
- **Contadores:** `closed`, `reopened` y `unchanged` cuentan **meses**; `failed` cuenta **personas** cuyo cierre falló (la spec solo fijaba los cuatro nombres). Un fallo (documentos de más, error de base) se registra con `user_id` y el nombre del tipo de error y no detiene a las demás. Los registros no llevan nombres de clientes, importes ni correos.
- **`--month` / `month`:** se valida antes de tocar a nadie (`InvalidMonth` o `PeriodInFuture` suben al llamante; la CLI las traduce a un error en español). Para cada persona, un mes anterior a su primer mes con actividad **no hace nada** (coherente con «antes no hay cierres»). Los gastos anulados se excluyen en SQL y el primer gasto para el «primer mes» es el primer gasto no anulado.
- `cuadre.jobs.runner` pasa a un registro por nombre (`JOBS`, `JOB_NAMES`, `MONTHLY_JOBS`, `JobContext`); `run_named_job` gana el parámetro opcional `month` (con un job que no trabaja por meses es un `ValueError`). El job de recordatorios no cambia y `routes_internal.py` no se tocó: `GET /internal/jobs/monthly_closing` aparece al registrar el job.
- CLI: `run-job monthly_closing [--now] [--user] [--month AAAA-MM]` imprime `Listo: N cerrados, N reabiertos, N sin cambios, N fallidos.` (sale con 1 si algún cierre falló) y el alias de ADR-0007 `close-month --month AAAA-MM`.
- **Prueba de la ruta:** la base de pruebas acumula miles de cuentas de otras pruebas y la ruta no admite `only_owners`, así que `test_cierre_mensual_internal_route.py` registra un envoltorio que limita el job a las cuentas de la prueba; el 401 y el resto de reglas de acceso son las de `test_recordatorios_internal_route.py`.
- **Cron propuesto** (sin `vercel.json`, no hay despliegue): `0 3 * * *` (UTC), el mismo día de Madrid en verano e invierno. Nuevo job, misma ruta interna y mismo `CRON_SECRET`.
- Verificado: `pytest backend/tests/jobs -k cierre_mensual` 165 pasan (22 del job con base real: cierre, a cero, repetir, dos ejecuciones a la vez, reapertura por gasto, por factura de otra serie y por anulación, rectificativa, primer mes, ventana, mes pedido, cambio de año en Madrid, coherencia con el 130 por trimestre, quién se cierra, fallo aislado, aislamiento y registros); `pytest backend/tests/jobs` 256 y `tests/rules` 119 sin regresiones; `ruff` limpio; `export_openapi.py --check` OK.

### B.4 Hito 5 · API y pantalla `/mensual` · 2026-11-13

- `GET /api/monthly-closings?year=` y `GET /api/monthly-closings/{year}/{month}` (`get_monthly_closings`, `get_monthly_closing`), solo `usuario`, `Cache-Control: private, no-store`. Lista y detalle comparten **un único cálculo del año** (`cuadre.closing.service`): con una transacción de la persona se leen el alta, las primeras fechas, los cierres guardados del año y, solo para los meses sin cierre, las facturas y los gastos.
- **Tres estados:** `closed` (foto guardada, con `revision` y `closed_at`), `in_progress` (el mes de hoy en Madrid, en vivo) y `pending` (terminó y aún no hay cierre, en vivo). Un mes muy antiguo sin cierre (anterior a los 12 meses que recalcula el job) también sale `pending` con sus cifras en vivo; se recalcula a mano con `close-month`. La foto **no se refresca al leer**: un documento atrasado se ve tras la siguiente ejecución del job.
- **Precisiones sobre §5.3:** (1) la lista empieza en el **primer mes con actividad**; un año anterior a la actividad devuelve `months: []` y una cuenta nueva ve su mes de alta como `in_progress` (la spec decía «sin cierres la lista está vacía»); (2) el detalle de un mes anterior al primero con actividad responde `404 closing_not_found` (código nuevo); (3) cada mes lleva también `result_cents` (ingresos menos gastos), para que la interfaz no reste; (4) `year` y `month` fuera de 2000-9998 o 1-12 dan `422 invalid_period` y los que no han empezado `422 period_in_future`; un `year` que no es un número, el error de validación de siempre.
- Frontend: página `/mensual` (selector de año como formulario `GET`, `?anio=&mes=` en la dirección, mes por defecto el último cerrado), tarjetas por debajo de 1.280 px y tabla desde ahí (el patrón de la lista de facturas, sin scroll horizontal a 390 ni a 1.440 px), detalle con ingresos por cliente y su ámbito, resultado y la nota de cierre y reapertura. La interfaz no suma ni resta: usa `ytd_cents`, `total_cents`, `result_cents` y `by_client` tal cual. «Contabilidad mensual» pasa a enlace activo del menú (entre Gastos y Trimestres), entra en las secciones del autónomo y sale de «Próximamente» en la portada, donde queda «Reporte mensual» (SPEC-W-013).
- **E2E:** la cuenta del worker acumula facturas que no se pueden borrar, así que `mensual.spec.ts` usa un oráculo por la API (`helpers/monthly.ts`). Prepara el mes anterior con una serie nueva (`createSeries`), una factura y un gasto con fecha de ese mes y lo cierra con `python -m cuadre.cli close-month --user …` (la ruta interna recorre todas las cuentas, que en la base de pruebas son miles). Cubre mes cerrado con sus clientes, mes en curso, cambio de mes, reapertura por un gasto atrasado, selector de año, año futuro y maqueta; `roles.spec.ts` y `responsive.spec.ts` incluyen el apartado.
- Verificado: `pytest backend/tests/api -k monthly` 25 pasan; `pytest backend/tests -m "not rls"` 4446 y `rls` 1799; `npm run test:unit` 333 (7 nuevas); `lint`, `typecheck`, `build` y `check:bundle` en verde; `gen:api -- --check` y `export_openapi.py --check` al día; `playwright e2e/mensual.spec.ts` 42 pasan (3 navegadores x 390/1.440, 1 worker); `roles.spec.ts` y `responsive.spec.ts` 309 pasan. Revisión visual a 390 y 1.440 px con capturas desechables (sin errores de maqueta).

### B.5 Hito 6 · Cierre · 2026-11-13

- **Matriz criterio -> prueba** escrita en §8.3 con los archivos reales; §5.1, §5.3, AC-16 y AC-17 puestos al día con lo decidido en los hitos 3 a 5 (una entrada por cliente y ámbito, `result_cents`, `closing_not_found`, lista vacía solo antes de la actividad, cierres existentes siempre visibles) y `E2E_WEB_PORT` en §8.2.
- **Pruebas atadas al reloj real, corregidas.** Varias pruebas daban por hecho que la cuenta de prueba «nació en noviembre de 2026»: el primer mes de una cuenta sin documentos es el de su alta y la cuenta se crea con la hora real. Habrían fallado el 1 de diciembre. Ahora leen el mes de alta de la base (`tests/jobs/closing_support.py`: `signup_month`, `now_to_close`, `iso_to_close`) y construyen el reloj a partir de él; las que cuentan con una cuenta nueva se repiten además con el alta desplazada a marzo de 2031 (`SHIFTS`) para demostrar que no dependen del mes real. Las pruebas con facturas fechadas en 2026 no dependen del alta (el primer mes lo fija la factura).
- **Mutaciones: 49 (15 en las reglas, 6 en el job, 9 en el servicio y la API, 5 en la interfaz y 14 en SQL), todas detectadas al final.** Cubren el signo y el ámbito de los ingresos, los gastos anulados y el IVA no deducible, el recuento de facturas, el nombre y el orden del desglose, el desglose sin ámbito, la ventana (11, 12 y 13 meses), el mes en curso, el mes pedido, el día de Madrid, el límite de documentos y la validación de entradas; el primer mes con actividad, el aislamiento de fallos y los contadores del job; el acumulado, los estados, el primer mes visible, `result_cents`, los años y meses futuros, el 404 y el rol de la ruta; el mes por defecto, la nota de reapertura y las etiquetas de la pantalla; y en SQL la cláusula de «foto distinta», la revisión, `first_closed_at`, la validación de importes, ámbito y sumas, los candidatos, la RLS forzada, una política abierta, los permisos y la comprobación del total. **Dos sobrevivieron y se cubrieron con una prueba nueva:** (1) la lista no enseñaba un cierre guardado si el documento que fijaba el primer mes se anulaba después (`test_a_closing_that_exists_is_listed_even_if_its_month_is_no_longer_the_first_with_activity`); (2) `close_month` no distinguía un ámbito inventado cuyas sumas cuadraban como «fuera de la UE» (caso `ámbito desconocido que cuadra con otro` en `test_monthly_closings.py`). Cuatro mutaciones de la primera pasada no se aplicaron por un fallo de la herramienta con los finales de línea y se repitieron después: detectadas. Cada archivo se restauró y la base se reinició al terminar.
- **Verificado en local:** `supabase db reset`; `pytest backend/tests/rls -m rls` 1800; `pytest backend/tests/jobs -k cierre_mensual` 173; `pytest backend/tests/api -k monthly` 28; `pytest backend/tests -m "not rls"` 4457; `ruff` limpio; `export_openapi.py --check` y `gen:api -- --check` al día; `test:unit` 333, `lint`, `typecheck`, `build` y `check:bundle` en verde; E2E `mensual`, `roles` y `responsive` 351 pasan sin fallos (1 worker, `E2E_WEB_PORT=3100`).
- **Barrido de datos:** sin claves, IBAN ni NIF reales en lo nuevo; el E2E y el frontend no mencionan credenciales de servicio; los registros del job solo llevan ids, periodos y contadores; `.env.example` sin cambios.
- **Pendiente para el piloto (no es de esta spec):** `vercel.json` con los crons de `reminders` y de `monthly_closing` (`0 3 * * *` en UTC el segundo), `CRON_SECRET` en el entorno y DEP-05 (proveedor de correo real).
- **CI de `593522a` en rojo (2026-11-16).** Un fallo duro en el E2E de `chromium-390`: `modelo-130.spec.ts` buscaba la fila de una factura por texto parcial y `2026-001` casa con `R-2026-001`; en una cuenta nueva las series de facturas y de rectificativas coinciden. No era un fallo de la aplicación. Reproducido en local tras `supabase db reset`, corregido con un localizador por enlace exacto (también en `trimestres.spec.ts`) en `d9f46ff`, y pasa con cuenta nueva y con historial. Tres pruebas flaky pasaron al reintento: `factura.spec.ts` (rectificar, carrera del envío; anterior a esta spec) y dos de `auth.spec.ts` con `console.error: Failed to load resource: 404` sin ruta, **no reproducido en local** en 32 repeticiones; `watchBrowserErrors` ahora añade la ruta del recurso para identificarlo si vuelve a salir. No se ha demostrado que sea de W-012 ni que no lo sea.
- **Estado:** `en-revision` hasta que la persona confirme el CI de GitHub sobre el head empujado tras `d9f46ff`; entonces `hecha`.

