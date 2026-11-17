---
tipo: spec
id: SPEC-W-013
titulo: Reporte mensual visual
estado: hecha
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
E2E_WEB_PORT=3100 npm --prefix frontend exec -- playwright test e2e/reporte.spec.ts e2e/roles.spec.ts e2e/responsive.spec.ts e2e/mensual.spec.ts --workers=2   # AC-13 a AC-15; en frío (tras `supabase db reset`) y otra vez con historial
```

**Comando único de la spec** (el de `tasks.json`): `pytest backend/tests/reports`, además de `pytest backend/tests/rls -m rls` y `playwright test e2e/reporte.spec.ts`.

### 8.3 Correspondencia criterio → prueba

Los nombres de prueba son los reales; las de `backend/tests/reports/test_reporte_api.py` corren con la aplicación y la base de datos reales.

| Criterio | Prueba |
|---|---|
| AC-01 · mes cerrado | `test_a_closed_month_has_the_figures_of_the_monthly_closings_and_everything_the_report_draws` (cifras idénticas a `/api/monthly-closings`, ámbitos y trimestre) y `reporte.spec.ts` «un mes cerrado enseña lo que dice el servidor…» (cifras y las cuatro tablas contra el oráculo) |
| AC-02 · gastos por categoría | `test_the_expenses_by_category_exclude_the_voided_and_count_the_non_deductible_vat`, `test_the_first_and_the_last_day_belong_to_their_month_and_the_next_first_does_not`, `test_reporte_rules.py` (anulado fuera, IVA, importe 0, orden y desempate) y `test_the_categories_add_up_to_the_expenses_of_the_closing` (propiedades, semilla fija) |
| AC-03 · comparación | `test_the_comparison_has_the_previous_month_deltas_and_variations`, `test_variation_rounds_half_up_on_the_absolute_value_with_its_sign`, `test_variation_is_the_exact_ratio_rounded_half_up` y las comparaciones de `reporte.spec.ts` (1) |
| AC-04 · primer mes | `test_the_first_month_has_no_comparison_and_the_months_before_it_are_not_found` y `reporte.spec.ts` «una cuenta nueva ve su mes en curso sin referencia…» |
| AC-05 · ámbitos | `test_the_three_scopes_come_in_order_with_their_shares`, `test_there_is_no_share_when_the_total_is_not_positive`, `test_each_share_is_within_one_basis_point_of_the_exact_one`, y el `flex-grow` de los tramos en `reporte.spec.ts` (1) |
| AC-06 · redondeo | los casos de redondeo de `test_reporte_rules.py` (1/3, el medio exacto, negativos) y los oráculos con `Fraction` de `test_reporte_properties.py` |
| AC-07 · rectificativas | `test_a_rectification_counts_in_its_own_month_with_its_sign_and_leaves_no_share` |
| AC-08 · tendencia | `test_the_trend_has_twelve_months_across_the_year_boundary`, los `trend_window_*` de `test_reporte_rules.py` y las columnas y la tabla de evolución de `reporte.spec.ts` (1) |
| AC-09 · mes en curso y pendiente | `test_a_pending_and_an_in_progress_month_are_calculated_live_with_their_trend` |
| AC-10 · descuadre | `test_a_late_expense_in_a_closed_month_is_flagged_until_the_job_runs_again` y `reporte.spec.ts` «un gasto atrasado en un mes cerrado se avisa…» |
| AC-11 · errores y acceso | `test_a_period_that_does_not_exist_or_has_not_started_is_refused`, `test_a_month_that_is_not_a_number_is_a_validation_error`, `test_too_many_expenses_are_refused_without_any_data`, `test_without_a_session_the_answer_is_401`, `test_gestores_and_admins_cannot_use_it`, `test_a_suspended_account_cannot_use_it` y `reporte.spec.ts` «el selector cambia de mes y de año…» |
| AC-12 · aislamiento | `test_one_person_never_sees_the_figures_categories_or_trend_of_another` |
| AC-13 · apartar sin importe | `reporte.spec.ts` «lo que conviene apartar no lleva ningún importe…», `report.test.ts` (`SET_ASIDE_NOTE`, `quarterLinks`) y la ausencia de campos de importe en `test_a_closed_month_has_the_figures…` |
| AC-14 · pantalla | `reporte.spec.ts` («maqueta: cada gráfico tiene su texto alternativo…», «sin red…», el selector y las tablas), `responsive.spec.ts` (`/reporte`) y `report.test.ts` (porcentajes, geometría y textos) |
| AC-15 · menú, portada y enlace | `roles.spec.ts` («Reporte mensual · …» para el autónomo, el gestor y el administrador; la portada sin «Próximamente»), `reporte.spec.ts` «el detalle de /mensual enlaza al reporte del mismo mes», `roles.test.ts` y `route-guard.test.ts` |
| AC-16 · integridad | `test_no_float.py` (todo `cuadre.reports`), `test_the_module_never_uses_decimals`, `test_the_logs_carry_no_amounts_names_or_emails`, `test_the_route_is_in_the_public_contract` y `report.test.ts` (sin `parseFloat`, `toFixed` ni `Number(`) |

### 8.4 Definición de hecho
La secuencia termina con código 0 en local y en CI sobre el head empujado que contiene todos los hitos; `tasks.json` actualizado; ADR enlazados; sin secretos ni datos reales; el contenido del reporte queda anotado como **pendiente de validar con usuarios** (Charter §8). **Excepción del cierre (2026-11-16):** la persona cerró la spec como `hecha` **sin** el CI de GitHub en verde (ver Anexo A, hito 6); el criterio de CI no se verificó al cerrar. **Actualización 2026-11-17:** el CI de GitHub, lanzado a mano sobre `9d44b88` (run `44032402643`, que contiene todos los hitos), terminó en verde con los cinco trabajos; el criterio de CI que faltaba al cerrar queda verificado.

## Anexo A · Orden de implementación (un commit por hito)

1. Spec y `tasks.json`. **Hecho** (2026-11-16).
2. Reglas puras de `cuadre.reports` y sus pruebas (unitarias y de propiedades). **Hecho** (B.1).
3. Repositorio, servicio y API `get_monthly_report`; `openapi.json` y `schema.d.ts` regenerados; pruebas de API. **Hecho** (B.2).
4. Frontend: `lib/report.ts`, gráficos, página `/reporte`, menú, portada y enlace desde `/mensual`. **Hecho** (B.3).
5. E2E del reporte, roles y responsive, con localizadores exactos (sin `hasText` parcial con números). **Hecho** (B.4).
6. Mutaciones, matriz criterio → prueba, barrido de datos y verificación completa. **Hecho en local** (B.5). **Cerrada como `hecha`** por decisión de la persona el 2026-11-16, **sin** confirmación del CI de GitHub: no consta ningún resultado de CI sobre `6d844ee` ni sobre lo posterior, y la verificación completa es la local de B.5.

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

### B.2 Hito 3 · Servicio y API · 2026-11-16

- **`GET /api/monthly-report/{year}/{month}`** (`get_monthly_report`, rol `usuario`, `Cache-Control: private, no-store`): `MonthlyReport` extiende `MonthlyClosing` (el mes, con su `by_client`) y añade `comparison`, `scopes`, `expenses_by_category`, `expenses_by_category_total_cents`, `expenses_note`, `trend`, `quarter` y `quarter_year`, como en §5.3. Nombres y tipos en `cuadre.reports.models`; `backend/openapi.json` y `frontend/src/api/schema.d.ts` se regeneraron con sus scripts.
- **Único cambio en `closing/`, aditivo:** `MonthlyClosingService.months_of(user, year)` devuelve los meses de un año con su desglose por cliente, y `month()` pasa a leer de la misma función interna. Mismo resultado y mismos errores (las 28 pruebas de API de W-012 y las del job siguen en verde). Permite que el reporte haga **como mucho dos cálculos de año** y que sus cifras sean las de `/mensual`.
- **Año anterior:** se pide solo si `month ≤ 11` (la tendencia o la comparación pueden llegar a él) y `year − 1 ≥ 2000`. El primer mes con actividad es el más antiguo de los meses listados; un mes pedido que no aparece en la lista da `404 closing_not_found`, igual que `/mensual`.
- **`422 report_too_large`:** más gastos de los que caben (`CLOSING_MAX_DOCUMENTS`) se traduce a un error controlado y sin datos (en W-012 el exceso del cierre no tiene traducción; aquí sí, por §6). La consulta pide una fila más del tope, y una prueba fija esa relación.
- **Gastos por categoría:** consulta propia en `cuadre.reports.repository` (`expense_date` en `[primer día, primer día del mes siguiente)`, `voided_at IS NULL`, `category::text`) con la identidad de la persona y su RLS; sin migraciones ni cambios en la matriz de RLS.
- **Límite conocido:** los dos cálculos de año y la lectura de categorías son transacciones distintas (es una lectura); un documento que llegue entre medias se ve en `expenses_note`.
- **Pruebas** (`backend/tests/reports/`, 26 nuevas de API con la aplicación y la base reales): historia de agosto a noviembre con dos meses cerrados por el job; cifras idénticas a `/api/monthly-closings`; categorías (anulado fuera, IVA no deducible dentro, primer y último día del mes); comparación y primer mes; mes pendiente y en curso; rectificativa con su signo y sin cuotas; tendencia de 12 meses a través del cambio de año; descuadre y su desaparición tras el job; errores y roles; aislamiento entre dos personas; registros sin importes ni nombres; contrato público. Las fechas de la tendencia son pasadas porque la base rechaza facturas con fecha futura.
- **Mutaciones manuales: 15 sobre el servicio, el repositorio y `months_of`; 2 sobrevivieron** (el límite superior del mes y el tope de filas) y se cubrieron con dos pruebas nuevas; ahora todas se detectan.
- **Verificado en local:** `pytest backend/tests/reports` 101; `pytest backend/tests -m "not rls"` 4558; `pytest backend/tests/rls -m rls` 1800; `ruff` limpio; `export_openapi.py --check` y `gen:api -- --check` al día; `typecheck`, `lint` y `test:unit` (333) en verde.

### B.3 Hito 4 · Frontend `/reporte` · 2026-11-16

- **`/reporte`** (`app/(app)/reporte/page.tsx`, componente de servidor, `requireRole("usuario")`, `?anio=&mes=` como `/mensual`): formulario `GET` con **Mes** y **Año** etiquetados (los doce meses siempre; un mes sin datos lo explica el servidor con su texto), cifras del mes, ingresos por ámbito y por cliente, gastos por categoría, evolución y «Lo que conviene apartar». La lista de `/api/monthly-closings` solo sirve para elegir el mes por defecto (el último cerrado); todas las cifras vienen de `get_monthly_report`. `reading` de `monthly-api.ts` se exporta y lo reutiliza `report-api.ts`.
- **`lib/report.ts`** (puro, probado con `node --test`): `formatBp` (puntos básicos → `20,0 %` con enteros y arrastre), `variationText` y `deltaText` (siempre con signo y con palabras; «sin referencia» si el servidor da `null`), `barPercent`/`columnPercents` (porcentajes enteros, mínimo 1 si hay algo, nada para ceros y negativos), los resúmenes de `aria-label` y `SET_ASIDE_NOTE`. Una prueba vigila que el módulo no use `parseFloat`, `toFixed` ni `Number(`.
- **Gráficos de servidor, sin JavaScript de cliente** (`components/report/`): barra segmentada por ámbito (el ancho de cada tramo es su base en céntimos, con `flex-grow`), barras horizontales por cliente y por categoría, y columnas pareadas ingresos/gastos de la tendencia. Cada uno va en un `<figure>` con `role="img"` y `aria-label`, con **su importe escrito en cada fila** y su **tabla equivalente** en un `<details>` «Ver como tabla». Los colores son los tokens existentes (el ámbito conserva el color que tiene en el resto de la app); nada se distingue solo por el color. Los importes negativos no dibujan barra.
- **Decisiones de forma:** (1) la tabla de la tendencia lleva el estado del mes debajo del nombre (con una columna propia, a 390 px el mes se partía letra a letra: se vio en la revisión visual y se corrigió); (2) el color de gastos es `scope-non-eu`; (3) el mes elegido se marca en la tendencia con un marco y con «(mes del reporte)» para lectores de pantalla; (4) abreviatura de septiembre: `sept.`.
- **Menú, portada y enlace:** «Reporte mensual» en el menú del autónomo tras «Contabilidad mensual» y en las secciones que exigen rol; la portada omite la sección «Próximamente» cuando no hay nada (el autónomo ya no tiene nada próximo; el administrador sí); «Ver el reporte de …» en el detalle de `/mensual`.
- **Revisión visual** a 390 y 1.440 px con datos sintéticos de cinco meses, siete categorías y clientes de los tres ámbitos (capturas en el scratchpad, sin commitear): sin scroll horizontal a ningún ancho; la corrección de la tabla de la tendencia salió de ahí. No se consultó la skill `frontend-design`: el prototipo no define gráficos y se aplicaron sus tokens sin añadir otros.
- **E2E existentes actualizados** (por el menú y la portada nuevos, no son los del reporte, que son del hito 5): `helpers/env.ts` (la navegación esperada), `roles.spec.ts` (el orden del menú y la portada del autónomo sin «Próximamente») y su efecto en `responsive.spec.ts`.
- **Verificado en local:** `test:unit` 344 (11 nuevas de `report.test.ts` y las de `roles` y `route-guard` actualizadas), `lint`, `typecheck`, `build` (`/reporte` en la salida), `check:bundle`, `pytest backend/tests/rules` 119; E2E `roles`, `responsive` y `mensual` en Chromium a 390 y 1.440 px sin fallos (con 1 worker, `E2E_WEB_PORT=3100`).

### B.4 Hito 5 · E2E del reporte, roles y responsive · 2026-11-16

- **`frontend/e2e/reporte.spec.ts`** (8 pruebas por proyecto, en Chromium, Firefox y WebKit a 390 y 1.440 px): (1) un mes cerrado enseña lo que dice el servidor: las tres cifras, la comparación con el mes anterior, y las tablas de ámbitos, clientes, categorías y evolución, fila a fila y celda a celda contra el oráculo; (2) lo que conviene apartar sin ningún importe en euros y con los dos enlaces al trimestre del mes, que llevan a `/trimestres`; (3) el aviso de descuadre tras un gasto atrasado, y su desaparición al volver a cerrar; (4) una cuenta recién registrada: mes en curso, «sin mes anterior» y textos vacíos; (5) el selector y los errores del servidor (mes anterior a la actividad, año futuro con «Ir al año en curso»); (6) maqueta: cuatro gráficos con `role="img"` y `aria-label`, cuatro tablas abiertas, sin scroll horizontal y con todos los campos etiquetados; (7) sin peticiones fuera de localhost; (8) el enlace «Ver el reporte de …» desde `/mensual`.
- **Ayudas:** `MonthlyApi.report` (el oráculo), `Ledger.create(…, category)` (con `"other"` por defecto) y `helpers/report.ts` (`prepareReportMonths`: el mes anterior con una factura a cada ámbito y tres gastos de categorías distintas, el anterior a ese con una factura y un gasto, ambos cerrados con la CLI del job para esa cuenta). `roles.spec.ts` (el autónomo ve «Reporte mensual» tras «Contabilidad mensual»; gestor y administrador no lo ven y `/reporte` los lleva a `/403`) y `responsive.spec.ts` (`/reporte`).
- **Lección (la misma que destapó el CI de W-012, ahora de una cuenta con historial):** el fixture `biller` archiva los clientes y crea otros con el mismo nombre en cada prueba, así que el mes anterior de una cuenta que ya ha pasado por otras pruebas trae **dos filas «Estudio Norte S.L. · Nacional»** con distinto `client_id`. La primera versión de la prueba 1 solo pasaba con la base recién creada: con historial mezclaba las celdas de las dos filas y fallaba en los seis proyectos. Ahora los clientes del oráculo se agrupan por (nombre, ámbito, base) y la tabla debe traer exactamente tantas filas como cada grupo, con celdas exactas. Los importes y los nombres se comparan siempre con cabecera de fila y celda exactas, no con texto parcial.
- **Verificación local** (`E2E_WEB_PORT=3100`, 2 workers como el CI): `reporte`, `roles`, `responsive` y `mensual` en los seis proyectos, **en frío (tras `supabase db reset`): 423 de 423; con historial (sin reset): 423 de 423**, sin *flaky*. `lint` y `typecheck` en verde.
- **Mutaciones de la interfaz (5, todas detectadas por `reporte.spec.ts`):** signo de la variación invertido, ámbitos UE y fuera de la UE intercambiados en la tabla, mes elegido sin marcar en la evolución, enlace del 303 con el trimestre equivocado y aviso de descuadre omitido. Una se repitió a mano para comprobar que el fallo era una aserción (el `href` del 303) y no un error de compilación. Cada archivo se restauró.

### B.5 Hito 6 · Mutaciones, matriz de criterios y cierre · 2026-11-16

- **Mutaciones nuevas: 40, todas detectadas** (con las 31 de los hitos 2, 3 y 5, **71 en total**). Cada una edita un único archivo en el sitio, lanza las pruebas y restaura el original en un `finally`; antes de empezar cada lote el script comprueba que la línea base es verde y al acabar `git status` de `backend/src` y `frontend/src` queda limpio. Familias: **A, reglas** (13: ventana de 11 y de 13 meses, sin tope superior, redondeo sin el doble, variación sobre el mes actual, `previous_status`, deltas de ingresos y del resultado, tope de gastos con `>=`, coste solo con la base, trimestres de cuatro meses, ámbitos en orden inverso, cuota con total 0); **B, servicio, modelos y ruta** (5: `PeriodBeforeActivity` sin traducir, `min` por `max` del primer mes, `Cache-Control` quitado, `comparison` y `share_bp` obligatorios); **C, `lib/report.ts`** (14, con `node --test`: arrastre y `+4` de `formatBp`, el caso 0 y el signo de `variationText`, mínimo de 1, tope de 100 y `floor` de `barPercent`, escala separada de las columnas, enlaces 303/130 cambiados, signo de `deltaText`, «sept.», ámbito del cliente y cuota en los resúmenes); **D, componentes** (8, con el E2E: `flex-grow` de los tramos, ancho de las barras, altura de las columnas, `role="img"` sin `aria-label`, texto del desplegable de la tabla, «Próximamente» vacío, orden del menú y texto del enlace desde `/mensual`).
- **Incidente de proceso (sin supervivientes):** en la primera ejecución de la familia A, `rules.py` quedó mutado (la mutación «sin tope superior» figuraba como «no aplica» porque el archivo ya la contenía, lo que indica que venía de un intento anterior interrumpido; no está confirmado) y esa pasada no tenía comprobación de línea base, así que **sus resultados no se cuentan**. Se detectó porque `pytest` fallaba tras restaurar, se recuperó con `git checkout` y se repitió todo con un script que comprueba antes que la línea base es verde y restaura siempre desde la copia en memoria: las 18 de A y B salen detectadas.
- **Prueba reforzada en este hito:** `reporte.spec.ts` (1) no comprobaba el cableado de la geometría (ancho de los tramos por ámbito, ancho de las barras por categoría, altura de las columnas de ingresos y gastos); se añadió con un cálculo del porcentaje escrito aparte de la aplicación (`barPct`). Las tres mutaciones D de geometría se lanzaron **después** de reforzarla, así que no sabemos si la prueba anterior las habría visto.
- **Detección por tiempo de espera:** dos mutaciones de la familia D (el texto del desplegable y el del enlace desde `/mensual`) las ve el E2E porque `locator.click` no encuentra el texto y la prueba agota el tiempo («Target page… has been closed»), no por una aserción. Es una detección real pero lenta; se deja así.
- **No detectable:** los colores de cada ámbito (`SCOPE_BAR`): ningún test mira el color, solo la leyenda con texto. Se revisaron en las capturas del hito 4 y no se simulan. Tampoco se comprueba el tamaño real de la barra a 1.440 px frente a 390 px más allá de «no hay scroll horizontal».
- **Barrido de datos:** sin claves, correos fuera de `@example.test`, NIF, IBAN ni URLs de base de datos en `backend/src/cuadre/reports`, `routes_report.py`, `backend/tests/reports`, `lib/report*`, `components/report`, `app/(app)/reporte`, `e2e/reporte.spec.ts` ni `helpers/report.ts` (solo nombres de variables de entorno en el `conftest`, como el resto de pruebas); `.env.example` sin cambios; los registros de la API no llevan importes, nombres ni correos (`test_the_logs_carry_no_amounts_names_or_emails`).
- **Verificación local:** tras `supabase db reset`: `pytest backend/tests/reports` 101; `api -k monthly` 28; `jobs -k cierre_mensual` 173; `pytest backend/tests -m "not rls"` 4558; `pytest backend/tests/rls -m rls` 1800; `ruff check` y `ruff format --check` limpios; `export_openapi.py --check`, `export_schemas.py --check` y `gen:api -- --check` al día; `lint`, `typecheck`, `build` (con `/reporte`) y `check:bundle` en verde; `test:unit` 344. E2E de `reporte`, `roles`, `responsive` y `mensual` en los seis proyectos con 2 workers y sin reintentos: **en frío (tras `supabase db reset`) 423 de 423**; **con historial 422 de 423**: falló `reporte.spec.ts` «una cuenta nueva ve su mes en curso…» en `firefox-390` con `browserContext.close: Protocol error (Browser.removeBrowserContext)`, un error interno de Firefox al cerrar el contexto, no una aserción; repetida nueve veces en Firefox 390 y 1.440 pasó 9 de 9. Se anota como inestabilidad de infraestructura, no se corrige.
- **Pendiente para el piloto (no es de esta spec):** validar con usuarios qué cifras y gráficos consultan de verdad (Charter §8: el contenido del reporte es provisional); `vercel.json` con los crons, `CRON_SECRET` y el proveedor de correo (DEP-05); el reporte por correo o PDF (RF-022, *Could*); y los dos tests inestables de W-012 (404 de `auth` y «rectificar» de factura) si vuelven a aparecer en el CI.
