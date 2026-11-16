---
tipo: spec
id: SPEC-W-013
titulo: Reporte mensual visual
estado: en-revision
prioridad: must
riesgo: bajo
historias: [US-008]
requisitos: [RF-014]
nfr: [NFR-06]
restricciones: [RES-02, RES-07]
adr: [0003, 0006, 0011, 0015]
depende_de: [SPEC-W-012]
bloquea: []
fecha: 2026-11-16
---

# SPEC-W-013 · Reporte mensual visual

> Para cada mes (cerrado o en curso), la persona ve **de dónde viene lo que ha facturado** (por ámbito y por cliente), **en qué se ha gastado** (por categoría), **cómo va frente al mes anterior** y **cómo ha evolucionado en los últimos 12 meses**, con gráficos sencillos que siempre llevan su tabla de texto. Todo se calcula en el servidor a partir del cierre mensual de SPEC-W-012; **no hay tabla, job ni migración nuevos**, y **no se calcula ningún importe a apartar**: el reporte orienta y enlaza al borrador del trimestre.

## 1. Contexto

**Situación de partida.** SPEC-W-012 cierra cada mes con sus totales por ámbito y por cliente y los enseña como tabla en `/mensual` (API `get_monthly_closings` y `get_monthly_closing`). Los gastos del cierre son un solo total (base + IVA no deducible): no hay desglose por categoría. Las ocho categorías de gasto existen (`cuadre.validators.categories`: `ExpenseCategory` y `LABELS`, única fuente) y cada gasto guarda la suya (`expenses.category`). La portada anuncia «Reporte mensual» como «Próximamente».

**Qué falta.** US-008 pide «un reporte visual de cada mes cerrado, para entender cuánto he ganado, de dónde viene y cuánto debo apartar» (RF-014: ingresos por cliente y ámbito, gastos por categoría, evolución y lo que conviene apartar). No hay gráficos, ni gastos por categoría, ni comparación con el mes anterior, ni evolución.

**Decisiones de la persona (2026-11-16).**
1. **Lo que conviene apartar, sin importe**: solo orientación y enlaces al borrador del 303 y del 130 del trimestre del mes. No se calcula un total a apartar ni hay lógica fiscal nueva.
2. **Gastos por categoría calculados al leer**: lectura sola, sin tocar `monthly_closings`, `close_month` ni la matriz de RLS. Si la suma no coincide con los gastos de la foto del cierre, el reporte lo dice.
3. **Gráficos propios en SVG/CSS desde componentes de servidor**: sin librería de gráficos ni JavaScript de cliente.
4. **Apartado propio `/reporte`**, con ítem «Reporte mensual» en el menú tras «Contabilidad mensual» y enlace desde cada mes de `/mensual`.

**Dependencia externa (Charter §8).** Qué cifras y gráficos consulta de verdad un autónomo cada mes **no está validado con usuarios**. Esta spec fija un conjunto mínimo y defendible (cuatro bloques, §5.5) y lo da por **provisional**: cambiarlo tras validarlo es una spec nueva, no un parche. Queda anotado como riesgo, no como bloqueo.

**Decisiones vigentes** (no se reabren): ADR-0003 (FastAPI y SQL explícito); ADR-0006 (importes en céntimos enteros, `Decimal` con `ROUND_HALF_UP`); ADR-0011 (cliente TypeScript generado); ADR-0015 (psycopg síncrono); RES-02, RES-07; los borradores y todo lo fiscal se marcan **orientativos**.

**Decisiones que propone esta spec** (la persona las confirma o corrige antes del hito 2):

| ID | Decisión | Alternativa y coste |
|---|---|---|
| D-01 | **Un endpoint de lectura** `GET /api/monthly-report/{year}/{month}` que devuelve todo lo del reporte, con el mes, la comparación, la tendencia, el desglose y los enlaces. La interfaz no suma ni compara | Varias llamadas a `/api/monthly-closings` y cálculo en el navegador: lógica de importes fuera del servidor (RES-02) |
| D-02 | **Reutilizar `MonthlyClosingService`** para el mes, el mes anterior y los 12 meses de la tendencia: las cifras salen de la misma foto que `/mensual`, y no pueden contradecirla | Recalcular aparte: dos fuentes de verdad |
| D-03 | **Gastos por categoría** = base + IVA no deducible de los gastos no anulados con `expense_date` en el mes, agrupados por `expenses.category`, con **la misma regla que el cierre**. Consulta propia en `cuadre.reports` (el cierre no se modifica). Solo salen las categorías con importe distinto de cero, de mayor a menor | Ampliar `monthly_closings` con el desglose: reabre una tabla ya cerrada (RLS, mutaciones); descartado por la persona |
| D-04 | **Descuadre**: si la suma por categoría ≠ `expenses_cents` del mes (típico: un gasto atrasado en un mes cerrado antes del siguiente recálculo), se devuelve `expenses_note` con un texto fijo y la interfaz lo enseña. Las categorías siempre son «al leer» | Esconderlo o forzar la igualdad: engaña |
| D-05 | **Comparación** con el mes anterior (si existe): importes anteriores, diferencia en céntimos y **variación en puntos básicos enteros** (`ROUND_HALF_UP`, 1 pb = 0,01 %), solo cuando el importe anterior es mayor que 0; si no, `null` y la interfaz dice «sin referencia». Nunca `float` | Porcentaje decimal: riesgo de `float` y de redondeos distintos entre servidor y navegador |
| D-06 | **Reparto por ámbito**: los tres ámbitos siempre en el orden nacional, UE, fuera de la UE, con su base y su cuota en puntos básicos del total; la cuota es `null` si el total del mes es ≤ 0 o la base del ámbito es negativa. Las cuotas redondeadas pueden no sumar 100 % y la tabla lo dice | Repartir el resto: números que no son los del cierre |
| D-07 | **Tendencia**: los 12 meses que terminan en el elegido, recortados al primer mes con actividad (D-05 de SPEC-W-012), con total, gastos y resultado de cada uno y su estado (`closed`, `in_progress`, `pending`) | Solo el año natural: no deja ver la continuidad entre enero y diciembre |
| D-08 | **Apartar**: la respuesta incluye el trimestre del mes (`quarter`, `quarter_year`); la interfaz enseña una nota fija («orientativo, no es dinero tuyo aunque esté en tu cuenta») y los enlaces `Ver borrador del 303` y `Ver borrador del 130` a esos trimestres. **Sin importe** | Calcular un total: lógica fiscal nueva y tres cifras que explicar |
| D-09 | **Gráficos de servidor, sin JavaScript de cliente**: barra segmentada (ámbitos), barras horizontales (clientes y categorías) y columnas pareadas ingresos/gastos (tendencia), como `<svg>` o `<div>` con anchos en `%`, cada uno en un `<figure>` con `role="img"`, `aria-label` y la `<table>` equivalente. La geometría se calcula con **enteros** (`Math.round(cents * 100 / max)`) | Recharts: dependencia, JS de cliente y `check:bundle` |
| D-10 | **Página `/reporte`** (`?anio=&mes=`, formulario `GET` de año y mes con etiquetas, como `/mensual`), mes por defecto el **último cerrado** (o el de alta si no hay ninguno). Ítem «Reporte mensual» en el menú del rol `usuario` tras «Contabilidad mensual»; sale de «Próximamente» en la portada; «Ver reporte» desde el detalle de `/mensual` | Dentro de `/mensual`: la pantalla crece y W-012 se vuelve a tocar |
| D-11 | **Sin RLS nueva ni migración**: las lecturas son las de SPEC-W-012 (`user_transaction`, `private.read_owner()`); el gestor y el administrador reciben `403`, como en `/mensual` | |

## 2. Objetivo

Que la persona vea, para cualquier mes con actividad, cuánto ha facturado y de quién (por ámbito y por cliente), cuánto ha gastado y en qué, cómo se compara con el mes anterior y cómo ha ido en el último año móvil, con cifras idénticas a las de `/mensual`, accesibles sin depender del color y sin calcular ningún impuesto nuevo.

## 3. Alcance explícito

### 3.1 Backend (FastAPI)
- Módulo `cuadre.reports`: reglas **puras** (comparación, puntos básicos, reparto por ámbito, agrupación por categoría, ventana de la tendencia, aviso de descuadre), repositorio de solo lectura de gastos por categoría y servicio que compone el reporte.
- `GET /api/monthly-report/{year}/{month}` (`get_monthly_report`).

### 3.2 Frontend (Next.js)
- Página `/reporte`, componentes de gráfico en `src/components/report/`, `src/lib/report.ts` (geometría con enteros y textos), lectura con el cliente generado, menú, portada y enlace desde `/mensual`.

### 3.3 Pruebas
- Reglas puras y propiedades con semilla; API con base real (roles, aislamiento, errores); unitarias de la geometría; E2E del reporte, roles y responsive.

## 4. Alcance excluido

- **Cualquier importe «a apartar»** y cualquier cálculo fiscal nuevo (IVA, IRPF, cuota de autónomos): el reporte enlaza a los borradores.
- Envío del reporte por correo o en PDF (RF-022, *Could*).
- Vista del gestor del reporte (la ficha del gestor no incluye `/mensual` hoy).
- Herramientas MCP `resumen_mes` y `gastos_por_categoria` (SPEC-W-011): podrán reutilizar `cuadre.reports`, pero no se crean aquí.
- Persistir categorías en el cierre, migraciones, jobs.
- Librería de gráficos, exportar imágenes, interacción (tooltips, zoom).
- Validación del contenido con usuarios (Charter §8): se anota como riesgo.

## 5. Contrato de interfaces

### 5.1 Reglas (`cuadre.reports.rules`, puras, sin base de datos ni reloj)
- **Gasto de un documento** = `base_cents + (0 si IVA deducible, `vat_cents` si no)`; los anulados no cuentan (idéntico a `closing.rules`).
- **Variación en puntos básicos** = `(actual − anterior) × 10 000 / anterior`, entero, `ROUND_HALF_UP` por el valor absoluto con el signo conservado; `null` si `anterior ≤ 0`.
- **Cuota por ámbito** = `base × 10 000 / total`, mismo redondeo; `null` si `total ≤ 0` o `base < 0`.
- **Categorías**: se agrupan por `ExpenseCategory`, se descartan las de importe 0 y se ordenan por importe descendente y, a igualdad, por la etiqueta.
- **Ventana de la tendencia**: los 12 meses que terminan en el elegido, sin pasar del primer mes con actividad; nunca meses futuros.
- **Descuadre**: `expenses_note` solo si `sum(categorías) ≠ expenses_cents` del mes.

### 5.2 Base de datos
Ninguna migración ni tabla. Consulta de solo lectura (con `private.read_owner()` y `user_transaction`):

```sql
SELECT category, base_cents, vat_cents, deductible_vat
  FROM public.expenses
 WHERE owner_id = (SELECT private.read_owner()) AND voided_at IS NULL
   AND expense_date >= %(start)s AND expense_date < %(end)s
 LIMIT %(limit)s
```

### 5.3 API HTTP

| `operation_id` | Ruta | Rol | Respuesta |
|---|---|---|---|
| `get_monthly_report` | `GET /api/monthly-report/{year}/{month}` | `usuario` | `MonthlyReport` |

`MonthlyReport` = `MonthlyClosing` de SPEC-W-012 (`year`, `month`, `status`, `invoice_count`, `national_cents`, `eu_cents`, `non_eu_cents`, `total_cents`, `expenses_cents`, `result_cents`, `ytd_cents`, `revision`, `closed_at`, `by_client`) más:

- `comparison`: `null` si no hay mes anterior con actividad; si no, `{previous_year, previous_month, previous_status, total_cents, expenses_cents, result_cents, total_delta_cents, expenses_delta_cents, result_delta_cents, total_variation_bp, expenses_variation_bp}` (los `*_variation_bp` pueden ser `null`, D-05).
- `scopes`: tres elementos `{scope, base_cents, share_bp}` en el orden nacional, UE, fuera de la UE.
- `expenses_by_category`: `[{category, label, expenses_cents, expense_count}]` (D-03).
- `expenses_by_category_total_cents` y `expenses_note` (`null` si cuadra; D-04).
- `trend`: `[{year, month, status, total_cents, expenses_cents, result_cents}]`, de más antiguo a más reciente (D-07).
- `quarter` y `quarter_year`: el trimestre natural del mes (D-08).

Errores como los de `/api/monthly-closings/{year}/{month}`: `422 invalid_period`, `422 period_in_future`, `404 closing_not_found` (mes anterior al primero con actividad); `401` sin sesión; `403` para `gestor` y `admin`. Cabecera `Cache-Control: private, no-store`. Todos los importes son céntimos enteros.

### 5.4 Backend
- `cuadre.reports.rules`: `expense_cost`, `variation_bp`, `share_bp`, `group_by_category`, `trend_window`, `build_comparison` (funciones puras sobre tipos propios).
- `cuadre.reports.repository.expenses_by_category(conn, start, end)` (lectura, con el `LIMIT` de `closing.limits`).
- `cuadre.reports.service.MonthlyReportService(pool, clock)`: reutiliza `MonthlyClosingService` (el mes, el anterior y los de la tendencia, con dos llamadas como mucho: el año del mes y el anterior) y compone el reporte; errores de `cuadre.closing.errors`.
- `cuadre.api.routes_report`: router con `operation_id` en `verbo_objeto`, registrado en `main.py`; `backend/openapi.json` y `frontend/src/api/schema.d.ts` se **regeneran**, no se editan.

### 5.5 Frontend
`/reporte` (componente de servidor, `requireRole("usuario")`, `export const instant = false` como `/mensual`):

1. **Cifras del mes**: ingresos, gastos y resultado, cada uno con su comparación en texto («+12,3 % frente a octubre», «sin referencia») además del color.
2. **De dónde viene**: barra segmentada por ámbito y barras horizontales por cliente, con su tabla.
3. **En qué se gasta**: barras horizontales por categoría, con su tabla y, si procede, la nota de descuadre.
4. **Evolución de 12 meses**: columnas pareadas de ingresos y gastos, con su tabla.
5. **Lo que conviene apartar**: nota fija «orientativo» y los dos enlaces a los borradores del trimestre (`/trimestres?year=…&quarter=…` y `…&model=130`).

Formato con `Intl.NumberFormat('es-ES')`; la variación se escribe a partir de los puntos básicos enteros del servidor. Tokens del prototipo, etiquetas en todos los controles, foco visible, sin scroll horizontal a 390 y 1.440 px, colores nunca como único canal (cada barra lleva su valor escrito). «Reporte mensual» en el menú de `usuario` tras «Contabilidad mensual» (también en `SECTIONS` de `lib/roles.ts`), fuera de «Próximamente» en `inicio/page.tsx`, y «Ver reporte» en el detalle de `/mensual`.

## 6. Restricciones técnicas
- Sin `float` en importes (RES-02), tampoco en las variaciones ni en las cuotas (puntos básicos enteros). En el frontend, la geometría de los gráficos usa enteros (`Math.round(cents * 100 / max)`) y el formato de dinero, `Intl.NumberFormat`; una prueba vigila que `cuadre.reports` no use `float`.
- Sin llamar a ninguna API de modelos; sin `service_transaction` ni `database_service_url` en la ruta (solo `user_transaction`).
- Límite de filas por consulta (el de `closing.limits`): si se supera, error controlado sin datos.
- Los logs llevan `request_id`, ruta, código y duración; nunca importes, nombres ni correos.
- Datos solo sintéticos (RES-07). Todo se marca como orientativo; el reporte no es una declaración.
- Sin JavaScript de cliente para los gráficos; `check:bundle` no crece por ellos.

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Reporte de un mes cerrado (US-008).** *Given* un usuario con facturas a clientes nacional, de la UE y de fuera de la UE y con gastos en septiembre y en agosto; *When* abre el reporte de septiembre; *Then* ve los importes por ámbito y por cliente del cierre, los gastos por categoría, la comparación con agosto y los 12 meses, con las mismas cifras que `/mensual`.

**AC-02 · Gastos por categoría.** *Given* gastos de varias categorías, uno anulado y uno con IVA no deducible; *Then* cada categoría suma base + IVA no deducible de sus gastos vivos, las de importe 0 no salen, el orden es de mayor a menor y la suma de las categorías es `expenses_cents`.

**AC-03 · Comparación.** *Given* agosto con 1.000,00 € y septiembre con 1.200,00 €; *Then* `total_delta_cents = 20 000` y `total_variation_bp = 2 000`; *Given* un mes anterior a 0; *Then* la variación es `null` y la interfaz dice «sin referencia».

**AC-04 · Primer mes.** *Given* el primer mes con actividad; *Then* `comparison` es `null` y la interfaz lo explica; *Given* un mes anterior a la actividad; *Then* `404 closing_not_found`.

**AC-05 · Reparto por ámbito.** *Then* los tres ámbitos salen siempre en orden nacional, UE y fuera de la UE con su base y su cuota en puntos básicos; con un total ≤ 0 o una base negativa, la cuota es `null`.

**AC-06 · Redondeo.** *Given* una variación de 1/3 (3 333,33…); *Then* 3 333 pb; con 0,5 pb exacto, redondeo `ROUND_HALF_UP` por el valor absoluto, con el signo del cambio, y sin `float`.

**AC-07 · Rectificativas.** *Given* una factura de agosto rectificada en septiembre; *Then* agosto conserva su importe, septiembre recoge la diferencia con su signo y el reparto por ámbito y por cliente lo refleja.

**AC-08 · Tendencia.** *Given* 20 meses de actividad; *Then* la tendencia trae los 12 que terminan en el elegido, de más antiguo a más reciente, también si cruzan de año; *Given* 5 meses de actividad; *Then* trae 5; nunca meses futuros.

**AC-09 · Mes en curso y mes pendiente.** *Then* el mes de hoy sale `in_progress` y un mes terminado sin cierre, `pending`, con cifras en vivo y el estado visible en el reporte.

**AC-10 · Descuadre.** *Given* septiembre cerrado y un gasto con fecha de septiembre registrado después y sin recálculo; *Then* `expenses_by_category_total_cents` ≠ `expenses_cents`, `expenses_note` explica la diferencia y la interfaz lo enseña; *Given* un mes que cuadra; *Then* `expenses_note` es `null`.

**AC-11 · Errores.** *Then* un año o mes que no existe da `422 invalid_period`, un mes futuro `422 period_in_future`; sin sesión `401`; el gestor y el administrador reciben `403`.

**AC-12 · Aislamiento (NFR-06).** *Given* dos usuarios con clientes y gastos distintos; *Then* el reporte de cada uno solo contiene lo suyo, también por categoría y tendencia.

**AC-13 · Apartar sin importe.** *Then* el reporte no contiene ningún importe «a apartar»; enseña la nota orientativa y los enlaces al 303 y al 130 del trimestre del mes (`quarter`, `quarter_year`), que llevan a la hoja de ese trimestre.

**AC-14 · Pantalla.** *Given* un usuario en `/reporte`; *Then* ve los cinco bloques, cambia de año y mes con un formulario con etiquetas, el mes por defecto es el último cerrado, cada gráfico tiene su `role="img"`, su `aria-label` y su tabla equivalente con las mismas cifras, nada se distingue solo por el color, no hay scroll horizontal a 390 y 1.440 px y no hay errores de consola.

**AC-15 · Menú y portada.** *Then* «Reporte mensual» está activo en el menú tras «Contabilidad mensual» solo para `usuario` (gestor y administrador no lo ven y `/reporte` los lleva a `/403`), ya no está en «Próximamente», y el detalle de `/mensual` lleva al reporte del mismo mes.

**AC-16 · Integridad.** *Then* `cuadre.reports` no usa `float`; las variaciones y cuotas son enteros; la respuesta no incluye ningún dato de otra cuenta ni sale en los registros.

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-012 §8.1: pila de Supabase en marcha, puertos 3100 (`E2E_WEB_PORT`), 8000 y 8765 libres, sin red, datos sintéticos y memoria suficiente para los E2E (1 worker).

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset
pytest backend/tests/reports -q                                   # AC-01 a AC-12, AC-16
pytest backend/tests/rls -m rls -q
pytest backend/tests -m "not rls" -q
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
E2E_WEB_PORT=3100 npm --prefix frontend exec -- playwright test e2e/reporte.spec.ts e2e/roles.spec.ts e2e/responsive.spec.ts e2e/mensual.spec.ts --workers=1   # AC-13 a AC-15
```

**Comando único de la spec** (el de `tasks.json`): `pytest backend/tests/reports`, además de `pytest backend/tests/rls -m rls` y `playwright test e2e/reporte.spec.ts`.

### 8.3 Correspondencia criterio → prueba (se completa en el hito 6)

| Criterio | Prueba prevista |
|---|---|
| AC-02, AC-03, AC-05, AC-06, AC-08 | `backend/tests/reports/test_reporte_rules.py` y `test_reporte_properties.py` (semilla fija) |
| AC-01, AC-04, AC-07, AC-09, AC-10, AC-11, AC-12, AC-13 | `backend/tests/reports/test_reporte_api.py` (base real, `FixedClock`, dos usuarios, roles) |
| AC-14 | `frontend/e2e/reporte.spec.ts` (con oráculo de la API) y `frontend/src/lib/report.test.ts` |
| AC-15 | `frontend/e2e/roles.spec.ts`, `responsive.spec.ts`, `mensual.spec.ts`, `lib/roles.test.ts` y `route-guard.test.ts` |
| AC-16 | `test_reporte_rules.py` (sin `float`) y la prueba de registros sin datos |

### 8.4 Definición de hecho
La secuencia termina con código 0 en local y en CI sobre el head empujado que contiene todos los hitos; `tasks.json` actualizado; ADR enlazados; sin secretos ni datos reales; el contenido del reporte queda anotado como **pendiente de validar con usuarios** (Charter §8).

## Anexo A · Orden de implementación (un commit por hito)

1. Spec y `tasks.json`. **Hecho** (2026-11-16).
2. Reglas puras de `cuadre.reports` y sus pruebas (unitarias y de propiedades). **Hecho** (B.1).
3. Repositorio, servicio y API `get_monthly_report`; `openapi.json` y `schema.d.ts` regenerados; pruebas de API.
4. Frontend: `lib/report.ts`, gráficos, página `/reporte`, menú, portada y enlace desde `/mensual`.
5. E2E del reporte, roles y responsive, con localizadores exactos (sin `hasText` parcial con números).
6. Mutaciones, matriz criterio → prueba, barrido de datos y cierre; `hecha` solo con el CI verde del head empujado con todos los hitos.

## Anexo B · Decisiones que esta spec deja a la implementación

Se rellena en cada hito (como en SPEC-W-012). Pendientes de partida:
- Forma exacta de los tipos Pydantic (`MonthlyReport` extiende `MonthlyClosing`) y nombres de los campos, que fija el hito 3 al generar el esquema.
- Si la tendencia reutiliza una o dos llamadas a `MonthlyClosingService` (año del mes y año anterior) y cómo se evita calcular dos veces el mismo año.
- Geometría exacta de los gráficos (alto de las columnas, ancho mínimo de las barras con importes pequeños, qué se hace con importes negativos de una rectificativa) y su texto alternativo; fija el hito 4 con pruebas unitarias.
- Texto de la nota «sin referencia» y de `expenses_note`, que no repiten importes de la persona.

### B.1 Hito 2 · Reglas puras · 2026-11-16

- **Paquete `cuadre.reports`** (`types.py`, `rules.py`, `__init__.py`), Python puro y solo con enteros: ni `float` ni `Decimal` ni `round(`. El redondeo *half-up* sobre el valor absoluto es aritmética entera `(2·|n| + d) // (2·d)` con el signo del cambio, así que no hay dependencia de `ROUND_HALF_UP`. Importa solo `cuadre.closing` (`YearMonth`, `SCOPES`, límites, `InvalidMonth`) y `cuadre.validators.categories` (`ExpenseCategory`, `LABELS`).
- **Funciones:** `expense_cost` (la regla del cierre), `variation_bp`, `share_bp`, `scope_shares`, `group_by_category`, `expenses_note`, `trend_window`, `build_comparison` y `quarter_of`. Errores con `code` estable: `ReportTooLarge` (`report_too_large`, más de `CLOSING_MAX_DOCUMENTS` gastos) y `PeriodBeforeActivity` (`closing_not_found`, el mes es anterior al primero con actividad: el servicio lo traducirá al `404` de §5.3).
- **Decisiones de forma:** (1) `trend_window` con `first = None` devuelve solo el mes elegido (una cuenta sin actividad); con `selected < first` falla en vez de devolver una ventana vacía. (2) `group_by_category` rechaza una categoría que no existe (no la manda a «Otros») y acepta el valor en texto de la enumeración. (3) Una categoría cuyo importe neto es 0 no sale aunque tenga gastos. (4) `EXPENSES_NOTE` es un texto fijo sin importes ni nombres. (5) `variation_bp` admite una cifra actual negativa (una rectificativa grande) frente a una referencia positiva: da más de −10 000 pb.
- **Pruebas** (`backend/tests/reports/`, sin base de datos; 75): `test_reporte_rules.py` (tabla de redondeo con 1/3, el medio exacto y negativos; sin referencia; cuotas; categorías; ventana; comparación; trimestre; el módulo sin `float`, `Decimal`, `locale` ni `round(`) y `test_reporte_properties.py` (semilla fija; las categorías suman lo mismo que `closing.build_month`; el orden de entrada no importa; un anulado no cambia nada; la variación y las cuotas coinciden con un oráculo exacto con `Fraction`).
- **Mutaciones manuales: 11, todas detectadas** (truncar el redondeo, perder el signo, no excluir anulados, contar el IVA deducible, invertir el desempate, no recortar a `first`, no descartar categorías a 0, referencia 0, cuota con base negativa, nota siempre y trimestre mal). La pasada completa es del hito 6.
- **Verificado en local:** `pytest backend/tests/reports` 75; `pytest backend/tests -m "not rls"` 4532; `ruff` limpio. Sin cambios en `closing/`, migraciones ni API.

