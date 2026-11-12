---
tipo: spec
id: SPEC-W-009
titulo: Modelo 130: borrador orientativo del pago fraccionado del IRPF, acumulado desde enero y con cada casilla enlazada a sus facturas y gastos
estado: hecha
prioridad: must
riesgo: medio
historias: [US-003]
requisitos: [RF-013]
nfr: [NFR-03, NFR-08]
restricciones: [RES-01, RES-02, RES-04]
adr: [0003, 0006, 0011, 0015, 0016]
depende_de: [SPEC-W-008]
bloquea: [SPEC-W-011, SPEC-W-014]
fecha: 2026-11-11
---

# SPEC-W-009 · Modelo 130

> Quinto paso de la cadena **perfil → clientes → facturas → modelo 303 → modelo 130**. Con lo que la persona ya tiene registrado (facturas emitidas en SPEC-W-007 y gastos en SPEC-W-003), la aplicación calcula **sola** el borrador del modelo 130 (IRPF, pago fraccionado en estimación directa) de un trimestre, **con importes acumulados desde el 1 de enero**, y enseña **cada casilla con las facturas y los gastos que la componen**, para que pueda revisarlo y presentarlo con confianza en la sede de la AEAT.
> Lo que **no** hace es presentar: el borrador es **orientativo** y no se envía nada a la AEAT (RES-04). Las minoraciones, el 5 % de gastos de difícil justificación, la deducción de la vivienda afectada (salvo que la persona decida lo contrario en P-01) y la compensación de resultados negativos quedan fuera (§4).

## 1. Contexto

**Situación de partida.** SPEC-W-008 dejó el 303 hecho y, con él, casi todo lo que el 130 necesita: `cuadre.tax.periods` (trimestres y plazos; el 130 se presenta en las mismas fechas que el 303), el patrón de un dominio puro cuyas casillas enlazan a los documentos que las componen, el paquete de lectura `cuadre.quarters` (consultas por rango `[inicio, fin)`, que sirven igual para «desde el 1 de enero»), `QuarterService`, la ruta `GET /api/tax/303` y la pantalla `/trimestres`, donde la pestaña «Modelo 130» sale ya reservada y desactivada («Próximamente»). Las facturas guardan `base_cents` e `irpf_cents` con **signo** (una rectificativa lleva la diferencia) y los gastos guardan `base_cents`, `vat_cents`, `deductible_vat`, `category` y `voided_at`; los gastos sin factura no llevan IVA. El prototipo (`docs/cuadre-interfaz.html`) fija las casillas y la pantalla. SPEC-W-005 dejó apuntado que `home_pct` (el porcentaje de la vivienda afectada) «solo se guarda» y que lo que se haga con él es de esta spec.

**Huecos que esta spec tiene que cerrar.** `InvoiceRow` no lleva `irpf_cents` ni `ExpenseRow` lleva el importe total (`base_cents`, `vat_cents`) de un gasto, y el repositorio hoy solo lee las líneas de IVA de un gasto: el 130 necesita la retención de cada factura y el coste de cada gasto, también el de los manuales.

**Por qué es de riesgo medio.** Igual que el 303, el riesgo es **de la regla fiscal, no del modelo** (US-003): un 130 mal sumado podría presentarse. Añade dos trampas propias: los importes son **acumulados** (un trimestre incluye los anteriores, y el pago ya ingresado se descuenta) y el 20 % es una **casilla derivada** (se redondea una vez, ADR-0006). Toda la regla vive en una función pura, determinista y con pruebas; NFR-03 exige coincidir al céntimo con casos resueltos a mano, y, como en SPEC-W-008, la exactitud se demostrará con **ejercicios simulados a mano** (Anexo B.1) mientras la validación externa de DEP-01 siga pendiente (P-05).

**Decisiones vigentes** (no se reabren aquí): ADR-0003 y ADR-0015 (SQL explícito, psycopg síncrono); ADR-0006 (céntimos enteros, `Decimal` con `ROUND_HALF_UP`, redondeo una vez por casilla derivada); ADR-0011 (cliente generado y `operation_id`); ADR-0016 (Vercel Function: sin trabajo posterior a la respuesta, 4,5 MB por petición); RES-01 (la lógica fiscal es determinista y no usa modelos de lenguaje); RES-04 (nada se envía a la AEAT); y de SPEC-W-008, D-02 (el periodo lo fija la fecha de expedición o la del gasto, en Europe/Madrid), D-08 (el servidor calcula todo; la interfaz no calcula nada fiscal) y D-09 (solo lectura, sin tablas nuevas).

**Decisiones que propone esta spec** (por defecto; la persona las confirma o corrige antes del hito 1):

| ID | Decisión | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Solo el 130 de la estimación directa**, con las casillas **01 a 07** del prototipo. Las demás del formulario (minoraciones, deducciones, compensaciones) no se calculan (§4) | Más casillas: más reglas y más casos a mano; cada una es un hito propio |
| D-02 | **Importes acumulados**: el borrador del trimestre *T* suma todo lo del año desde el **1 de enero** hasta el **último día del trimestre** (inclusive), por fecha de expedición de la factura y fecha del gasto, en Europe/Madrid. Una rectificativa cuenta, con su signo, en el periodo de **su** fecha | Fecha de cobro y de pago (P-02): otro criterio, fuera de alcance |
| D-03 | **01 · ingresos computables** = suma de `base_cents` de las facturas del periodo, de **todos los ámbitos** (nacional, UE y fuera de la UE) y con las rectificativas restando | Excluir los ingresos del extranjero: no es una regla del 130 |
| D-04 | **02 · gastos deducibles** = por cada gasto no anulado del periodo, su `base_cents` más el IVA que **no** se deduce (`vat_cents` si `deductible_vat = false`, nada si se deduce); los gastos sin factura valen su importe. Todas las categorías cuentan igual: la deducción de la vivienda afecta **no** se calcula (P-01, resuelta) | Contar solo ciertas categorías: no hay base legal en el PRD |
| D-05 | **03 · rendimiento neto** = 01 − 02 (puede ser negativo). **04 = 20 % de la 03 solo si la 03 es positiva**, con `Decimal` y `ROUND_HALF_UP`, **una vez** por casilla (ADR-0006); si no, 0 | Calcular el 20 % por documento: acumula céntimos de más |
| D-06 | **05 · pagos fraccionados anteriores** = suma de lo ingresado en los trimestres anteriores **del mismo año**; lo de cada uno es `max(0, 04 − 05 − 06)` **de ese trimestre**, calculado con la misma regla (recursivo, como el prototipo). Sus `items` son los propios trimestres | Leer pagos reales de una tabla: no existe; el borrador solo conoce lo que calcula |
| D-07 | **06 · retenciones soportadas** = suma de `irpf_cents` de las facturas del periodo, con signo. **07 · resultado** = 04 − 05 − 06. `result_kind`: `a_ingresar` (07 > 0), `nada_que_ingresar` (07 ≤ 0, un negativo ni se arrastra ni se compensa) y `sin_actividad` (ningún documento en todo el periodo acumulado) | Resultado negativo con compensación: fuera de alcance (P-04) |
| D-08 | **Cada casilla enlaza a sus documentos** (NFR-08, 100 %): la 01 y la 06 a facturas, la 02 a gastos, la 05 a los trimestres anteriores; la 03, la 04 y la 07 enumeran en `components` las casillas que las componen. **La suma de los `items` es el importe de la casilla** | Solo totales: no cumple NFR-08 |
| D-09 | **El servidor calcula todo**, también el plazo y su estado, que son **los del 303** (20 de abril, julio y octubre; 30 de enero), con el reloj inyectado; la interfaz no calcula nada fiscal | Calcular en el navegador: dos implementaciones de la regla |
| D-10 | **Solo lectura, sin tablas nuevas**: se calcula bajo demanda sobre `invoices` y `expenses` con la sesión de la persona (RLS), con las lecturas de `cuadre.quarters` por rango desde el 1 de enero. Una migración solo si el hito 2 demuestra que hace falta | Guardar borradores: histórico de lo calculado, con la duda de qué hacer cuando cambian los documentos |
| D-11 | **Información, no regla**: la respuesta lleva el **porcentaje de ingresos con retención** del año (sobre la 01, redondeado al entero) y un aviso fijo sobre la regla del 70 % del año anterior, que **no se calcula** (falta ese dato) | Calcular la regla del año anterior: necesita el año anterior completo y la fecha de alta |
| D-12 | **Lectura**: el 130 usa **tipos de entrada propios** (`IncomeRow` y `CostRow`, en `cuadre/tax/types_130.py`) y no amplía `InvoiceRow` ni `ExpenseRow`: el 303 no corre ningún riesgo. *(Resuelta en el hito 1; era «ampliar con campos opcionales o tipos propios».)* El hito 2 los rellena desde `invoices` y `expenses` | Ampliar las filas del 303 con campos opcionales: menos código, pero un cambio en lo que ya está hecho |
| D-13 | **Pantalla**: la pestaña «Modelo 130» de `/trimestres` pasa a enlace (`?model=130`; sin parámetro, el 303); misma hoja del prototipo, mismo selector de año y trimestre y mismo estado del plazo; sin JavaScript de cliente | Una pantalla aparte: dos rutas y dos menús |

**Preguntas resueltas el 2026-11-11** (las cinco, por la persona):

| ID | Pregunta | Respuesta |
|---|---|---|
| P-01 | **Vivienda afecta** (`home_pct`): SPEC-W-005 dejó para esta spec limitar la deducción de los suministros. ¿Se aplica ya? | **No**: no se calcula nada con `home_pct` (como el prototipo). Los avisos fijos dicen que el borrador **no incluye la deducción por vivienda afecta** y queda para una spec posterior; `home_pct` sigue guardándose sin usarse |
| P-02 | ¿Basta la fecha de expedición y la del gasto, o hace falta el criterio de cobro y pago? | **Fecha de expedición y del gasto** (D-02), como el 303 |
| P-03 | La retención que lleva un **gasto** (`withholding_cents`): ¿cuenta en algo? | **No**: la casilla 06 son las retenciones que la persona sufre en sus facturas |
| P-04 | Un resultado negativo (los gastos superan lo ingresado): ¿se arrastra o se compensa en trimestres posteriores? | **No**: «nada que ingresar», sin compensar; se anota como límite |
| P-05 | ¿Cómo se demuestra NFR-03 mientras DEP-01 esté pendiente? | **Cinco ejercicios simulados a mano** (Anexo B.1), calculados con cuentas escritas e independientes del código y marcados «simulados, no externos»; DEP-01 queda como mejora pendiente |

## 2. Objetivo

Que la persona abra **«Trimestres»**, elija un trimestre y la pestaña **«Modelo 130»** y vea su **borrador del pago fraccionado del IRPF**, acumulado desde enero, con las casillas 01 a 07, el resultado («a ingresar» o «nada que ingresar»), el plazo y, **bajo cada casilla, los documentos que la componen**, todo calculado por el servidor con reglas deterministas, en céntimos exactos, marcado como **orientativo** y sin enviar nada a la AEAT.

## 3. Alcance explícito

### 3.1 Dominio puro (`cuadre.tax.modelo_130`)
Función pura `build_modelo_130(year, quarter, invoices, expenses, today)` que recibe los documentos **del año hasta el fin del trimestre** ya leídos (tipos inmutables, sin base de datos ni reloj), calcula la 01 a la 07 con la regla de D-03 a D-07 (incluido el pago de cada trimestre anterior, para la 05), enlaza cada casilla a sus documentos y devuelve las casillas, el resultado, el porcentaje con retención, el plazo y el estado. Errores explícitos (`invalid_period`, `period_in_future`, `quarter_too_large`). Reutiliza `cuadre.tax.periods`; añade el inicio del año (`year_start`).

### 3.2 Base de datos
Sin migraciones previstas (D-10). Lecturas por rango `[1 de enero, fin del trimestre]` con las consultas de `cuadre.quarters`, ampliadas con las columnas que faltan (D-12).

### 3.3 Backend (FastAPI)
`GET /api/tax/130?year=&quarter=` (`operation_id: get_modelo_130`), solo rol `usuario`; método nuevo de `QuarterService`; modelos Pydantic de respuesta; errores `application/problem+json`; OpenAPI y cliente regenerados.

### 3.4 Frontend (Next.js)
La pestaña «Modelo 130» de `/trimestres` activa (`?model=130`), la hoja del 130 con el mismo diseño que la del 303, el mismo selector y el mismo estado del plazo, y el cliente generado.

### 3.5 Pruebas
Unitarias del dominio con los cinco ejercicios a mano y propiedades; lectura y API contra la base real; unitarias del frontend; Playwright `modelo-130.spec.ts` en Chromium, Firefox y WebKit a 390 y 1.440 px; mutaciones del dominio, de la API y de la interfaz.

## 4. Alcance excluido

- **El 5 % de gastos de difícil justificación**, las **minoraciones** por rendimientos bajos (casillas 12 y 13 y siguientes) y las **deducciones** por vivienda habitual o por otras causas.
- **La deducción de la vivienda afecta** (`home_pct`): no se calcula (P-01, resuelta); los avisos fijos lo dicen.
- **Compensación de resultados negativos** de trimestres anteriores y arrastre de saldos (P-04).
- **Estimación objetiva** (módulos), **criterio de caja**, actividades agrarias, ganaderas o forestales, Ceuta y Melilla.
- **Presentación o envío a la AEAT** (RES-04), **XLSX** de los libros registro (SPEC-W-019) y **recordatorios** de plazo (SPEC-W-014).
- La regla del **70 %** de retención del año anterior (D-11): solo se avisa.
- **Congelar o guardar borradores** (D-10) y cambiar facturas o gastos desde la pantalla: solo lee.
- El **303**, que no cambia: sigue siendo SPEC-W-008.

## 5. Contrato de interfaces

### 5.1 Campos y reglas

**Periodo.** `year` (2000-9998) y `quarter` (1-4), opcionales y con las mismas reglas que el 303 (por defecto, los de hoy en Europe/Madrid; el trimestre que aún no ha empezado da `period_in_future`; el que no existe, `invalid_period`). `period_start` es el **1 de enero**, `period_end` el primer día del trimestre siguiente (final exclusivo) y `deadline` y `deadline_status` los del 303.

**Casillas** (céntimos enteros con signo): `01`, `02`, `03`, `04`, `05`, `06` y `07`. Cada una lleva `code`, `label`, `group` (`rendimiento`, `pagos`, `resultado`), `amount_cents`, `items` y `components` (códigos, en las derivadas 03, 04 y 07).

| Casilla | Importe | Documentos (`items`) |
|---|---|---|
| `01` ingresos computables | suma de `base_cents` de las facturas del periodo | las facturas (con las rectificativas en negativo) |
| `02` gastos deducibles | suma de `base_cents` + el IVA no deducible de los gastos | los gastos no anulados |
| `03` rendimiento neto | `01 − 02` | derivada: `01`, `02` |
| `04` 20 % del rendimiento | `20 %` de la `03` si es positiva (una vez, `ROUND_HALF_UP`); si no, 0 | derivada: `03` |
| `05` pagos de trimestres anteriores | suma de `max(0, 07)` de cada trimestre anterior del año | **todos** los trimestres anteriores del año, también los que pagaron 0 (el T1 no tiene ninguno) |
| `06` retenciones soportadas | suma de `irpf_cents` de las facturas del periodo | las facturas con retención |
| `07` resultado | `04 − 05 − 06` | derivada: `04`, `05`, `06` |

**Item**: `kind` (`invoice` | `expense` | `quarter`), `id`, `label` (número de factura, proveedor del gasto o «T1 de 2026»), `date` (la de la factura o del gasto; la de fin de trimestre en un `quarter`) y `amount_cents`, **lo que ese documento aporta a esa casilla** (la base en la 01, la retención en la 06, el coste en la 02, el pago en la 05), con signo. El coste de un gasto es su base más el IVA no deducible.

**Resultado**: `result_cents` (= casilla 07) y `result_kind` (`a_ingresar` | `nada_que_ingresar` | `sin_actividad`).

**Información**: `withheld_share_percent` = `base de los documentos del periodo con retención distinta de cero × 100 / 01`, redondeado medio hacia arriba al entero; `null` si la 01 no es positiva. Se cuentan los documentos con retención **≠ 0** (no solo > 0) para que una rectificativa que devuelve retención reste de los dos lados (corregido en el hito 0, B.1).

**Avisos fijos** (`notes`, **siempre presentes**): borrador **orientativo** y sin presentar; lo que no incluye (§4: 5 % de difícil justificación, minoraciones y deducciones, vivienda afecta, compensación de negativos); y el de la regla del 70 % (D-11): «Si en el año anterior más del 70 % de tus ingresos llevó retención, no tienes obligación de presentar el 130. El porcentaje de este año que ves aquí es solo informativo.» (redactado sin género en el hito 1).

**Límite**: un periodo con más de **10.000 documentos** (facturas y gastos acumulados desde enero) da `quarter_too_large` (422, con texto propio) en vez de una respuesta que no cabría en 4,5 MB (ADR-0016).

### 5.2 Base de datos
Sin cambios (D-10). RLS ya limita `invoices` y `expenses` a `owner_id = auth.uid()`; el gestor con vínculo lee por las políticas existentes (su pantalla es SPEC-W-010); el administrador no ve ninguna fila.

### 5.3 API HTTP

| Operación | Ruta | Respuesta |
|---|---|---|
| `get_modelo_130` | `GET /api/tax/130?year=&quarter=` | `200` con `Modelo130` (periodo, plazo y estado, casillas con items, resultado, porcentaje con retención y avisos). `422` `invalid_period` / `period_in_future` / `quarter_too_large`; `401`; `403` (no es `usuario`) |

Los parámetros, los errores y el valor por defecto son los de `get_modelo_303`. `Cache-Control: private, no-store`. Solo lee: no crea ni cambia nada (T9-07).

### 5.4 Backend
`cuadre/tax/modelo_130.py` y `cuadre/tax/types_130.py` (puros, con `IncomeRow` y `CostRow` como entrada, D-12; `year_start` en `periods.py`); en `cuadre/quarters/`, la lectura de esas filas por rango desde enero, `QuarterService.modelo_130` y los modelos y errores del 130; `cuadre/api/routes_tax.py` con la ruta nueva. Los módulos nuevos de `cuadre.tax` se declaran como puros en `test_invoicing_boundary.py`.

### 5.5 Frontend
`lib/tax.ts` (puro, ampliado con lo del 130: dirección `?model=`, textos del resultado y del porcentaje, casillas por grupo), `lib/tax-api.ts` (`getModelo130`), `components/tax/modelo-130.tsx` y la pestaña de `quarter-picker.tsx`; `app/(app)/trimestres/page.tsx` elige la hoja según `?model=`. Server Components y HTML nativo: ninguna línea de JavaScript de cliente. Ninguna cuenta ni regla fiscal en el navegador (D-09).

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T9-01 | **Sin `float`** en importes: céntimos enteros o `Decimal` con `ROUND_HALF_UP` (RES-02); un test lo vigila en código y migraciones |
| T9-02 | **El dominio es puro**: no lee la base ni el reloj; recibe los documentos y el «hoy» (RES-01) |
| T9-03 | **Sin red ni modelos de lenguaje**: nada se envía a la AEAT ni a otro servicio (RES-04); sin dependencias nuevas |
| T9-04 | **Cada casilla se explica** (NFR-08): la suma de sus `items` es la casilla y las derivadas enumeran sus componentes; una prueba de propiedades lo cumple con documentos generados |
| T9-05 | **Solo `usuario`** lo lee por la API; el gestor, por RLS en su pantalla (SPEC-W-010); el administrador, nunca (D3) |
| T9-06 | **Sin datos personales en logs, trazas ni errores**: ni nombre de proveedor o cliente, ni NIF, ni concepto, ni importes; los errores dicen qué campo falla |
| T9-07 | **Una lectura no escribe**: ninguna fila nueva ni cambiada, ni siquiera `activity_log` |
| T9-08 | **Cabe en una Vercel Function** (ADR-0016): respuesta < 4,5 MB (de ahí el límite de 10.000 documentos de §5.1), sin trabajo posterior a la respuesta, `test_vercel_compat` en verde |
| T9-09 | **Borrador orientativo**: la API y la pantalla lo dicen siempre, junto con las exclusiones; la pantalla no ofrece «presentar» ni «descargar para la AEAT» |
| T9-10 | **Interfaz** como T8-10: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, desplegables nativos, sin scroll horizontal a 390 y 1.440 px en los tres motores |
| T9-11 | **El 303 no cambia de comportamiento**: sus pruebas (dominio, API, pantalla y E2E) siguen en verde **sin tocarlas** (D-12 se resolvió con tipos propios, así que no hizo falta ampliar sus filas) |
| T9-12 | **Datos sintéticos** (RES-07) y las pruebas E2E **no borran** facturas ni archivan gastos emitidos (T7-13): usan la cuenta de cada worker y comparan contra lo que dice el servidor |

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Ingresos de todos los ámbitos.** *Given* facturas del año a un cliente nacional, a uno de la UE y a uno de fuera de la UE; *When* se pide el 130; *Then* la 01 suma la base de las tres y cada una figura como item de la 01.

**AC-02 · Rectificativa.** *Given* una factura de 1.200,00 € de base y una rectificativa de −200,00 € del mismo año; *Then* la 01 cuenta 1.000,00 € desde el periodo de la rectificativa y la rectificativa es un item en negativo.

**AC-03 · Gastos.** *Given* un gasto con IVA deducible, otro con IVA no deducible y un gasto sin factura; *Then* la 02 suma de cada uno su base, su base más su IVA y su importe, respectivamente.

**AC-04 · Gasto anulado.** *Given* un gasto anulado; *Then* no cuenta ni figura.

**AC-05 · Rendimiento neto.** *Given* ingresos mayores y menores que los gastos; *Then* la 03 es 01 − 02 con su signo y la 04 es 0 cuando la 03 no es positiva.

**AC-06 · El 20 %.** *Given* un rendimiento neto con céntimos; *Then* la 04 es el 20 % de la 03 redondeado medio hacia arriba **una sola vez**, no la suma de los 20 % de cada documento.

**AC-07 · Acumulado.** *Given* documentos del T1 y del T2 del mismo año; *Then* el 130 del T1 solo cuenta los del T1 y el del T2 cuenta los dos; los documentos del T1 figuran en las casillas del T2.

**AC-08 · Pagos anteriores.** *Given* resultados del T1, T2 y T3 (positivos y no); *Then* la 05 del T4 suma, de cada trimestre anterior, `max(0, 07)` calculado con su propia 05, y sus items son esos trimestres.

**AC-09 · Retenciones.** *Given* facturas con retención y una rectificativa que la devuelve; *Then* la 06 suma las retenciones con su signo.

**AC-10 · Resultado.** *Given* un 07 positivo, uno cero, uno negativo y un periodo sin ningún documento; *Then* el resultado es «a ingresar», «nada que ingresar» (cero y negativo) y «sin actividad».

**AC-11 · Cada casilla se explica.** *Given* cualquier trimestre; *Then* la suma de los `items` de cada casilla con items es su importe y las derivadas (03, 04 y 07) enumeran sus componentes (NFR-08, 100 %).

**AC-12 · Fronteras.** *Given* documentos del 31/12 y del 01/01 y del último y el primer día de cada trimestre (Europe/Madrid); *Then* cada uno cuenta en el año y el trimestre de su fecha y el 130 de un año no incluye nada del anterior.

**AC-13 · Plazo y estado.** *Given* el reloj en distintas fechas; *Then* el plazo y su estado son los del 303.

**AC-14 · Periodo inválido o futuro.** *Given* `quarter=5`, un año fuera de rango o un trimestre que no ha empezado; *Then* `422` con `invalid_period` o `period_in_future` y el texto en español.

**AC-15 · Al céntimo.** *Given* los cinco ejercicios simulados del Anexo B.1 (resueltos a mano e independientes del código); *Then* todas las casillas y el resultado coinciden **al céntimo** en el dominio, desde la base de datos y por HTTP (NFR-03). Si llegan ejercicios externos (DEP-01), se añaden con la misma prueba.

**AC-16 · Aislamiento y roles.** *Given* dos usuarios con documentos; *Then* cada uno solo ve los suyos; el gestor (también con vínculo activo) y el administrador reciben `403`; sin sesión, `401`.

**AC-17 · Solo lectura y sin datos personales.** *Given* cualquier petición; *Then* no se escribe ninguna fila y ningún registro contiene números de factura, proveedores ni importes.

**AC-18 · Periodo demasiado grande.** *Given* más de 10.000 documentos acumulados; *Then* `422 quarter_too_large`.

**AC-19 · Pantalla.** *Given* la persona con facturas y gastos; *When* abre «Trimestres» y elige la pestaña «Modelo 130»; *Then* ve la hoja con las casillas 01 a 07, el resultado con texto, el plazo y su estado, el aviso «orientativo», el desplegable de documentos de cada casilla con enlaces a las facturas, y la dirección (`?model=130&year=&quarter=`) guarda lo elegido.

**AC-20 · El 303 sigue igual.** *Given* `/trimestres` sin `?model=` o con `?model=303`; *Then* se ve la hoja del 303 de siempre y todas sus pruebas siguen en verde.

**AC-21 · Adaptable y accesible.** *Given* 390 y 1.440 px en Chromium, Firefox y WebKit; *Then* no hay scroll horizontal, las pestañas y los desplegables tienen etiqueta y se usan con el teclado, el estado se entiende sin color y la consola no registra errores.

**AC-22 · Avisos fijos.** *Given* cualquier trimestre, también uno sin actividad; *Then* la API devuelve en `notes` el aviso de **orientativo**, la lista de lo que no incluye y el de la regla del 70 %, y la pantalla los enseña.

**AC-23 · Porcentaje con retención.** *Given* ingresos con y sin retención; *Then* `withheld_share_percent` es el porcentaje de la 01 que lleva retención, redondeado al entero, y es `null` cuando la 01 no es positiva; solo es informativo.

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-008 §8.1: pila de Supabase en marcha, puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 (o `E2E_AGENTS_PORT`) libres, sin red y con datos sintéticos.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                                  # migraciones + seed
pytest backend/tests/tax -k modelo_130 -q                              # AC-01 a AC-15 y AC-18, AC-22, AC-23 (dominio)
pytest backend/tests -m "not rls" -q                                   # incluye la lectura y la API (AC-14 a AC-18)
pytest backend/tests/rls -m rls -q                                     # AC-16
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/modelo-130.spec.ts   # AC-19 a AC-23 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/tax -k modelo_130` y `npm --prefix frontend exec -- playwright test e2e/modelo-130.spec.ts`, además de las secuencias completas de SPEC-W-001, 002, 003, 005, 006, 007 y 008.

### 8.3 Correspondencia criterio → prueba

| Criterio | Prueba |
|---|---|
| AC-01 a AC-06 | `backend/tests/tax/test_modelo_130.py` (casos pequeños y nombrados) |
| AC-07, AC-08, AC-09 | `test_modelo_130.py` (acumulado, pagos encadenados y retenciones) |
| AC-10, AC-11 | `test_modelo_130.py` y `test_modelo_130_properties.py` (documentos generados) |
| AC-12, AC-13, AC-14 | `test_modelo_130.py` (fronteras) y `test_modelo_130_api.py` |
| AC-15 | `test_modelo_130_cases.py` (los cinco ejercicios de B.1), `backend/tests/quarters/test_modelo_130_repository.py` (desde la base) y `test_modelo_130_api.py` (por HTTP) |
| AC-16, AC-17, AC-18 | `backend/tests/rls/`, `test_modelo_130_api.py` |
| AC-19, AC-20, AC-21, AC-22 | `frontend/e2e/modelo-130.spec.ts`, `roles.spec.ts`, `responsive.spec.ts`, `trimestres.spec.ts` (AC-20) y las unitarias de `lib/tax.test.ts` |
| AC-23 | `test_modelo_130.py` y `modelo-130.spec.ts` |

### 8.4 Definición de hecho

- [x] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005, 006, 007 y 008 §8.2 siguen en verde. *(Local, verificado el 2026-11-11 —Anexo B.6— con la batería completa en los tres motores; CI de GitHub en verde en `a4b0418`, confirmado por la persona el 2026-11-12.)*
- [x] Los **cinco ejercicios simulados** del Anexo B.1 coinciden al céntimo (NFR-03, P-05). La **validación externa de DEP-01** queda como mejora pendiente y se anota en el Anexo B al cerrar; si la persona la exige antes de cerrar, la spec no pasa de `en-revision`. *(Simulados, no externos: Anexo B.6.)*
- [x] El 100 % de las casillas con documentos enumera sus items y su suma es la casilla (NFR-08).
- [x] La pestaña «Modelo 130» de `/trimestres` está activa y hace todo lo de AC-19 a AC-23; el 303 no ha cambiado (AC-20).
- [x] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0006, 0011, 0015 y 0016 enlazados.
- [x] Las preguntas P-01 a P-05 están resueltas o anotadas en el Anexo B.
- [x] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

1. **Hito 0 · decisiones y cinco ejercicios simulados**: se confirman D-01 a D-13 y se resuelven P-01 a P-05; se redactan en el Anexo B.1 **cinco ejercicios resueltos a mano**, con las cuentas escritas paso a paso y sin ejecutar el código (con acumulado y pagos encadenados T1→T4, ingresos de los tres ámbitos, rectificativa, gastos con y sin IVA deducible y sin factura, retenciones, un rendimiento negativo, un 20 % con céntimos y la frontera de año), contrastados con un script independiente fuera del repositorio y marcados «simulados, no externos».
   **Hecho el 2026-11-11** (cinco ejercicios: T1 a T4 de 2025 con acumulado y pagos encadenados, y T1 de 2026 como frontera de año, más una comprobación adicional del T2 de 2026; los tres ámbitos, rectificativa, gastos con y sin IVA deducible, sin factura y anulados, retenciones con signo, un rendimiento negativo y un 20 % que sube y baja con céntimos; totales calculados a mano y contrastados al céntimo con un script independiente fuera del repositorio; D-01 a D-13 se confirman y P-01 a P-05 se resuelven; dos huecos de §5.1 corregidos; Anexo B.1).
2. **Hito 1 · dominio puro**: `modelo_130.py` y `types_130.py` con pruebas de los ejercicios a mano, propiedades de `items` y mutaciones.
   **Hecho el 2026-11-11** (`types_130.py` y `modelo_130.py` puros, `year_start` en `periods.py`; 69 pruebas nuevas y 3.897 sin RLS; los cinco ejercicios simulados y la comprobación adicional reproducidos al céntimo desde el bloque JSON de B.1; 63 mutaciones: 62 detectadas y 1 equivalente; D-12 resuelta con tipos propios; Anexo B.2).
3. **Hito 2 · lectura de datos**: lectura de `IncomeRow` y `CostRow` (D-12) y lectura por rango desde el 1 de enero, con la prueba del límite y las del 303 en verde.
   **Hecho el 2026-11-11** (`income_rows` y `cost_rows` en `cuadre/quarters/repository.py`, con `INCOME_SQL`, `COST_SQL` y `YEAR_DEFAULT_LIMIT`; los 23 documentos de B.1 sembrados en la base con las funciones `app.*`; 27 pruebas nuevas contra la base y 3.924 sin RLS; 1.561 RLS en verde; los cinco ejercicios y la comprobación adicional reproducidos al céntimo desde la base; 20 mutaciones detectadas; Anexo B.3). El servicio y los modelos van en el hito 3.
4. **Hito 3 · API**: `get_modelo_130`, modelos, errores, OpenAPI y cliente, con las pruebas de la API.
   **Hecho el 2026-11-11** (`QuarterService.modelo_130`, `Modelo130`/`Box130`/`Item130` y `present_130`, `period_too_large` con el código estable `quarter_too_large`, ruta `GET /api/tax/130` y OpenAPI y cliente regenerados; 36 pruebas nuevas por HTTP y 3.960 sin RLS; 1.561 RLS en verde; 27 mutaciones detectadas; respuesta máxima medida 2,51 MB; Anexo B.4).
5. **Hito 4 · frontend**: la pestaña, la hoja del 130, `lib/tax.ts` ampliado con sus unitarias y la comprobación visual en tres motores.
   **Hecho el 2026-11-11** (pestaña «Modelo 130» activa con `?model=130`, `Modelo130Sheet`, `BoxLine` compartido con el 303, `lib/tax.ts` y `lib/tax-api.ts` ampliados; 12 unitarias nuevas y 260 en verde; E2E del 303 en Chromium 14 de 14; comprobación visual desechable en tres motores y dos anchos; 41 mutaciones de la lógica detectadas; Anexo B.5).
6. **Hito 5 · E2E y cierre**: `modelo-130.spec.ts`, ajustes de `roles.spec.ts` y `responsive.spec.ts`, mutaciones de la interfaz, Anexo B, `tasks.json` y, si llegan, los ejercicios externos de DEP-01.
   **Hecho el 2026-11-11** (`modelo-130.spec.ts` con 12 pruebas por proyecto, oráculo `TaxApi.modelo130`, ajustes de `roles.spec.ts` y `responsive.spec.ts`; 21 mutaciones de los componentes detectadas; baterías completas: Chromium 305, Firefox 297 y WebKit 297 correctas, con 6 omitidas en los dos últimos; backend 3.960 y RLS 1.561; ningún defecto de producto; Anexo B.6).

## Anexo B · Decisiones que esta spec deja a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-011 (MCP).** La herramienta `borrador_trimestre` llama a las funciones de dominio de **los dos modelos** (`build_modelo_303` y `build_modelo_130`); no se reimplementa ninguna regla.
- **SPEC-W-014 (recordatorios).** El importe estimado del 130 que cita el correo sale de `build_modelo_130` con el mismo trimestre.
- **SPEC-W-010 (gestor).** Lee el mismo borrador con las políticas de lectura que ya existen; hace falta su pantalla y el registro de cada lectura.
- **SPEC-W-019 (XLSX).** Los libros registro salen de los mismos documentos.
- **Vivienda afecta.** P-01 se resolvió en contra de aplicarla ahora: queda una deuda visible en los avisos y apuntada para una spec posterior; `home_pct` sigue guardándose sin usarse.

### B.1 Hito 0 · cinco ejercicios simulados, resueltos a mano · 2026-11-11

**Estado: «simulados, no externos».** Cada ejercicio es un trimestre con sus importes **acumulados desde el 1 de enero**; los cuatro primeros son los trimestres de 2025 (un solo ejercicio fiscal, de modo que el T2 incluye al T1 y el T4 encadena los pagos de los tres anteriores) y el quinto es la frontera con 2026. Los totales se calcularon **a mano antes de ejecutar nada** y se contrastaron con un script desechable, **fuera del repositorio y sin importar `cuadre`**, con aritmética entera: **coinciden los cinco ejercicios y la comprobación adicional al céntimo** y la suma de los documentos de cada casilla es la casilla (NFR-08). Todos los importes están en **céntimos**.

**Límite de lo que demuestran.** Que el código reproducirá un cálculo manual hecho con la misma interpretación de las reglas (D-02 a D-07). No demuestran que esa interpretación sea la de la AEAT: eso daría la validación externa de DEP-01 (equipo docente o gestoría), que sigue **pendiente** como mejora.

**Convenciones.** Año 2025 (y 2026 para la frontera). Un gasto aporta a la 02 su **coste** = base + el IVA que no se deduce (`vat_cents` si no hay IVA deducible, 0 si lo hay); un gasto anulado no cuenta; un gasto sin factura no lleva IVA. La retención de una factura es el 15 % de su base (solo en las de empresa nacional; `ROUND_HALF_UP`), y la de una rectificativa es la **diferencia** de retención, con signo. El 20 % de la 04 se calcula **una sola vez** sobre la 03, solo si es positiva. La 05 de un trimestre es la suma de los pagos de los anteriores, y el pago de cada uno es `max(0, 07)`. El porcentaje con retención es `base de los documentos con retención ≠ 0 × 100 / 01`, redondeado al entero (hueco que este hito corrige en la spec, ver abajo).

#### Documentos

| Id | Fecha | Documento | Ámbito | Base | Retención | IVA | Cuenta |
|---|---|---|---|---|---|---|---|
| A1 | 2025-01-15 | factura | nacional | 300000 | 45000 | — | 15 % × 300000 = 45000 → 45000 |
| A2 | 2025-02-10 | factura | UE | 150000 | 0 | — | sin retención |
| A3 | 2025-03-05 | factura | fuera de la UE | 80000 | 0 | — | sin retención |
| A4 | 2025-03-28 | factura | nacional | 123459 | 18519 | — | 15 % × 123459 = 18518,85 → 18519 |
| B1 | 2025-04-10 | factura | nacional | 200000 | 30000 | — | 15 % × 200000 = 30000 → 30000 |
| B2 | 2025-05-12 | factura | UE | 60007 | 0 | — | sin retención |
| B3 | 2025-06-20 | rectificativa de A1, base corregida 250000 | nacional | -50000 | -7500 | — | base 250000 − vigente 300000 = −50000; retención 15 % × 250000 = 37500 − vigente 45000 = −7500 |
| C1 | 2025-07-15 | factura | nacional | 100000 | 15000 | — | 15 % × 100000 = 15000 → 15000 |
| D1 | 2025-10-10 | factura | nacional | 500000 | 75000 | — | 15 % × 500000 = 75000 → 75000 |
| D2 | 2025-12-31 | factura | UE | 1500000 | 0 | — | sin retención |
| X1 | 2026-04-01 | factura | nacional | 100000 | 15000 | — | 15 % × 100000 = 15000 → 15000 |
| G1 | 2025-01-20 | gasto, IVA deducible | — | 40000 | — | 8400 | coste = 40000 (el IVA se deduce en el 303) |
| G2 | 2025-02-15 | gasto, IVA no deducible | — | 25000 | — | 5250 | coste = 25000 + 5250 = 30250 |
| G3 | 2025-03-10 | gasto, sin factura (sin IVA) | — | 12000 | — | 0 | coste = 12000 |
| G4 | 2025-03-12 | gasto, anulado | — | 99999 | — | 21000 | no cuenta |
| G5 | 2025-04-18 | gasto, IVA deducible | — | 60000 | — | 12600 | coste = 60000 (el IVA se deduce en el 303) |
| G6 | 2025-05-30 | gasto, IVA no deducible | — | 15000 | — | 3150 | coste = 15000 + 3150 = 18150 |
| G7 | 2025-06-10 | gasto, sin factura (sin IVA) | — | 9999 | — | 0 | coste = 9999 |
| G8 | 2025-07-20 | gasto, IVA deducible | — | 900000 | — | 189000 | coste = 900000 (el IVA se deduce en el 303) |
| G9 | 2025-08-30 | gasto, IVA no deducible | — | 120000 | — | 25200 | coste = 120000 + 25200 = 145200 |
| G10 | 2025-09-12 | gasto, anulado | — | 50000 | — | 10500 | no cuenta |
| G11 | 2025-11-05 | gasto, IVA deducible | — | 70000 | — | 14700 | coste = 70000 (el IVA se deduce en el 303) |
| G12 | 2025-12-31 | gasto, sin factura (sin IVA) | — | 30001 | — | 0 | coste = 30001 |

#### E-1 · T1 de 2025 · los tres ámbitos, los cuatro tipos de gasto y un 20 % con céntimos que sube

Periodo: del 1 de enero de 2025 al 31 de marzo de 2025.

| Casilla | Cuenta | Importe | Documentos |
|---|---|---|---|
| 01 Ingresos computables | 300000 + 150000 + 80000 + 123459 | 653459 | A1, A2, A3, A4 |
| 02 Gastos deducibles | 40000 + 30250 + 12000 | 82250 | G1, G2, G3 |
| 03 Rendimiento neto | 01 − 02 = 653459 − 82250 | 571209 | derivada: 01, 02 |
| 04 20 % del rendimiento | 571209 × 20 % = 114241,8 → 114242 | 114242 | derivada: 03 |
| 05 Pagos de trimestres anteriores | 0 (cada pago es max(0, 07) del trimestre) | 0 | — |
| 06 Retenciones soportadas | 45000 + 18519 | 63519 | A1, A4 |
| 07 Resultado | 04 − 05 − 06 = 114242 − 0 − 63519 | 50723 | derivada: 04, 05, 06 |

**Resultado:** `a_ingresar` (507,23 €). **Porcentaje con retención:** 423459 × 100 / 653459 = 64,80 → **65 %**.

#### E-2 · T2 de 2025 · acumulado, pago anterior y una rectificativa que resta ingresos y retención

Periodo: del 1 de enero de 2025 al 30 de junio de 2025.

| Casilla | Cuenta | Importe | Documentos |
|---|---|---|---|
| 01 Ingresos computables | 300000 + 150000 + 80000 + 123459 + 200000 + 60007 − 50000 | 863466 | A1, A2, A3, A4, B1, B2, B3 |
| 02 Gastos deducibles | 40000 + 30250 + 12000 + 60000 + 18150 + 9999 | 170399 | G1, G2, G3, G5, G6, G7 |
| 03 Rendimiento neto | 01 − 02 = 863466 − 170399 | 693067 | derivada: 01, 02 |
| 04 20 % del rendimiento | 693067 × 20 % = 138613,4 → 138613 | 138613 | derivada: 03 |
| 05 Pagos de trimestres anteriores | T1: 50723 (cada pago es max(0, 07) del trimestre) | 50723 | T1 |
| 06 Retenciones soportadas | 45000 + 18519 + 30000 − 7500 | 86019 | A1, A4, B1, B3 |
| 07 Resultado | 04 − 05 − 06 = 138613 − 50723 − 86019 | 1871 | derivada: 04, 05, 06 |

**Resultado:** `a_ingresar` (18,71 €). **Porcentaje con retención:** 573459 × 100 / 863466 = 66,41 → **66 %**.

#### E-3 · T3 de 2025 · rendimiento neto negativo: «nada que ingresar» y pago cero para el siguiente

Periodo: del 1 de enero de 2025 al 30 de septiembre de 2025.

| Casilla | Cuenta | Importe | Documentos |
|---|---|---|---|
| 01 Ingresos computables | 300000 + 150000 + 80000 + 123459 + 200000 + 60007 − 50000 + 100000 | 963466 | A1, A2, A3, A4, B1, B2, B3, C1 |
| 02 Gastos deducibles | 40000 + 30250 + 12000 + 60000 + 18150 + 9999 + 900000 + 145200 | 1215599 | G1, G2, G3, G5, G6, G7, G8, G9 |
| 03 Rendimiento neto | 01 − 02 = 963466 − 1215599 | -252133 | derivada: 01, 02 |
| 04 20 % del rendimiento | la 03 no es positiva → 0 | 0 | derivada: 03 |
| 05 Pagos de trimestres anteriores | T1: 50723 + T2: 1871 (cada pago es max(0, 07) del trimestre) | 52594 | T1, T2 |
| 06 Retenciones soportadas | 45000 + 18519 + 30000 − 7500 + 15000 | 101019 | A1, A4, B1, B3, C1 |
| 07 Resultado | 04 − 05 − 06 = 0 − 52594 − 101019 | -153613 | derivada: 04, 05, 06 |

**Resultado:** `nada_que_ingresar` (−1.536,13 €). **Porcentaje con retención:** 673459 × 100 / 963466 = 69,89 → **70 %**.

#### E-4 · T4 de 2025 · pagos anteriores encadenados con `max(0, …)`, el 31/12 dentro y el porcentaje con retención

Periodo: del 1 de enero de 2025 al 31 de diciembre de 2025.

| Casilla | Cuenta | Importe | Documentos |
|---|---|---|---|
| 01 Ingresos computables | 300000 + 150000 + 80000 + 123459 + 200000 + 60007 − 50000 + 100000 + 500000 + 1500000 | 2963466 | A1, A2, A3, A4, B1, B2, B3, C1, D1, D2 |
| 02 Gastos deducibles | 40000 + 30250 + 12000 + 60000 + 18150 + 9999 + 900000 + 145200 + 70000 + 30001 | 1315600 | G1, G2, G3, G5, G6, G7, G8, G9, G11, G12 |
| 03 Rendimiento neto | 01 − 02 = 2963466 − 1315600 | 1647866 | derivada: 01, 02 |
| 04 20 % del rendimiento | 1647866 × 20 % = 329573,2 → 329573 | 329573 | derivada: 03 |
| 05 Pagos de trimestres anteriores | T1: 50723 + T2: 1871 + T3: 0 (cada pago es max(0, 07) del trimestre) | 52594 | T1, T2, T3 |
| 06 Retenciones soportadas | 45000 + 18519 + 30000 − 7500 + 15000 + 75000 | 176019 | A1, A4, B1, B3, C1, D1 |
| 07 Resultado | 04 − 05 − 06 = 329573 − 52594 − 176019 | 100960 | derivada: 04, 05, 06 |

**Resultado:** `a_ingresar` (1.009,60 €). **Porcentaje con retención:** 1173459 × 100 / 2963466 = 39,59 → **40 %**.

#### E-5 · T1 de 2026 · frontera de año: nada del 31/12/2025 cuenta y no hay ningún documento: «sin actividad»

Periodo: del 1 de enero de 2026 al 31 de marzo de 2026.

| Casilla | Cuenta | Importe | Documentos |
|---|---|---|---|
| 01 Ingresos computables | 0 | 0 | — |
| 02 Gastos deducibles | 0 | 0 | — |
| 03 Rendimiento neto | 01 − 02 = 0 − 0 | 0 | derivada: 01, 02 |
| 04 20 % del rendimiento | la 03 no es positiva → 0 | 0 | derivada: 03 |
| 05 Pagos de trimestres anteriores | 0 (cada pago es max(0, 07) del trimestre) | 0 | — |
| 06 Retenciones soportadas | 0 | 0 | — |
| 07 Resultado | 04 − 05 − 06 = 0 − 0 − 0 | 0 | derivada: 04, 05, 06 |

**Resultado:** `sin_actividad` (0,00 €). **Porcentaje con retención:** no se calcula (la 01 no es positiva).

#### E-5b · T2 de 2026 · comprobación adicional: el año nuevo empieza de cero (no arrastra nada de 2025)

Periodo: del 1 de enero de 2026 al 30 de junio de 2026.

| Casilla | Cuenta | Importe | Documentos |
|---|---|---|---|
| 01 Ingresos computables | 100000 | 100000 | X1 |
| 02 Gastos deducibles | 0 | 0 | — |
| 03 Rendimiento neto | 01 − 02 = 100000 − 0 | 100000 | derivada: 01, 02 |
| 04 20 % del rendimiento | 100000 × 20 % = 20000 → 20000 | 20000 | derivada: 03 |
| 05 Pagos de trimestres anteriores | T1: 0 (cada pago es max(0, 07) del trimestre) | 0 | T1 |
| 06 Retenciones soportadas | 15000 | 15000 | X1 |
| 07 Resultado | 04 − 05 − 06 = 20000 − 0 − 15000 | 5000 | derivada: 04, 05, 06 |

**Resultado:** `a_ingresar` (50,00 €). **Porcentaje con retención:** 100000 × 100 / 100000 = 100,00 → **100 %**.

**Lo que ejercita cada caso**

- **E-1.** Los tres ámbitos suman en la 01 (A1 a A4); los cuatro tipos de gasto: IVA deducible (G1, solo la base), IVA no deducible (G2, base más IVA), sin factura (G3) y **anulado** (G4, no cuenta). El 20 % de `571209` es `114241,8` y **sube** a `114242` (medio hacia arriba); G4 anulado dejaría un resultado distinto si contara.
- **E-2.** El T1 sigue dentro (acumulado) y la 05 trae su pago (`50723`); la rectificativa B3 resta `50000` de ingresos y `7500` de retención en el periodo de **su** fecha; el 20 % de `693067` es `138613,4` y baja a `138613`.
- **E-3.** Los gastos de G8 y G9 dejan el rendimiento neto en `−252133`: la 04 es **0** (no hay 20 % de un negativo), el 07 es `−153613` y el resultado «nada que ingresar»; su pago cuenta **0** para el T4 (`max(0, …)`). G10 está anulado.
- **E-4.** La 05 encadena T1 `50723`, T2 `1871` y T3 `0`; D2 y G12 son del **31/12** y cuentan en el T4; el 20 % de `1647866` es `329573,2` y baja a `329573`.
- **E-5.** Entre D2 y G12 (31/12/2025, del año anterior) y X1 (01/04/2026, del T2) el T1 de 2026 no tiene ningún documento: todas las casillas a cero y «sin actividad»; el porcentaje con retención no se calcula. **E-5b** pide el T2 de 2026: solo cuenta X1 (`100000`, retención `15000`), nada de 2025: `04 = 20000`, `07 = 5000`.
- **El redondeo por casilla no se ejerce con estos datos**: en ningún ejercicio sumar los 20 % de cada documento (redondeando uno a uno) da un resultado distinto del 20 % de la 03. Esa diferencia se fija con una prueba unitaria propia del hito 1 (documentos pequeños construidos para ello), no con estos ejercicios.

**Huecos de la spec que este hito corrige.**

- **Porcentaje con retención** (D-11, §5.1): se define con los documentos cuya retención **no es cero** (así una rectificativa que devuelve retención resta de los dos lados) y se redondea medio hacia arriba; `null` si la 01 no es positiva.
- **Casilla 05**: sus `items` son **todos** los trimestres anteriores del año, incluidos los que pagaron 0, para que se vea de dónde sale cada importe (T1 no tiene ninguno).

**Formato para las pruebas del hito 1** (los mismos datos, para no reescribirlos; `documentos` de cada caso son los ids que enlaza cada casilla, por fecha). Las pruebas pasan **todos los documentos juntos** y piden cada trimestre por separado, con un reloj posterior a 2026-04-01:

```json
{
 "nota": "simulados, no externos; importes en céntimos; las rectificativas llevan la diferencia ya calculada; los gastos llevan base e iva; la retención de una factura es la que lleva",
 "documentos": [
  {
   "id": "A1",
   "tipo": "factura",
   "fecha": "2025-01-15",
   "ambito": "national",
   "base": 300000,
   "retencion": 45000
  },
  {
   "id": "A2",
   "tipo": "factura",
   "fecha": "2025-02-10",
   "ambito": "eu",
   "base": 150000,
   "retencion": 0
  },
  {
   "id": "A3",
   "tipo": "factura",
   "fecha": "2025-03-05",
   "ambito": "non_eu",
   "base": 80000,
   "retencion": 0
  },
  {
   "id": "A4",
   "tipo": "factura",
   "fecha": "2025-03-28",
   "ambito": "national",
   "base": 123459,
   "retencion": 18519
  },
  {
   "id": "B1",
   "tipo": "factura",
   "fecha": "2025-04-10",
   "ambito": "national",
   "base": 200000,
   "retencion": 30000
  },
  {
   "id": "B2",
   "tipo": "factura",
   "fecha": "2025-05-12",
   "ambito": "eu",
   "base": 60007,
   "retencion": 0
  },
  {
   "id": "B3",
   "tipo": "rectificativa",
   "fecha": "2025-06-20",
   "ambito": "national",
   "base": -50000,
   "retencion": -7500,
   "rectifica": "A1"
  },
  {
   "id": "C1",
   "tipo": "factura",
   "fecha": "2025-07-15",
   "ambito": "national",
   "base": 100000,
   "retencion": 15000
  },
  {
   "id": "D1",
   "tipo": "factura",
   "fecha": "2025-10-10",
   "ambito": "national",
   "base": 500000,
   "retencion": 75000
  },
  {
   "id": "D2",
   "tipo": "factura",
   "fecha": "2025-12-31",
   "ambito": "eu",
   "base": 1500000,
   "retencion": 0
  },
  {
   "id": "X1",
   "tipo": "factura",
   "fecha": "2026-04-01",
   "ambito": "national",
   "base": 100000,
   "retencion": 15000
  },
  {
   "id": "G1",
   "tipo": "gasto",
   "fecha": "2025-01-20",
   "iva_deducible": true,
   "anulado": false,
   "base": 40000,
   "iva": 8400
  },
  {
   "id": "G2",
   "tipo": "gasto",
   "fecha": "2025-02-15",
   "iva_deducible": false,
   "anulado": false,
   "base": 25000,
   "iva": 5250
  },
  {
   "id": "G3",
   "tipo": "gasto",
   "fecha": "2025-03-10",
   "iva_deducible": false,
   "anulado": false,
   "base": 12000,
   "iva": 0
  },
  {
   "id": "G4",
   "tipo": "gasto",
   "fecha": "2025-03-12",
   "iva_deducible": true,
   "anulado": true,
   "base": 99999,
   "iva": 21000
  },
  {
   "id": "G5",
   "tipo": "gasto",
   "fecha": "2025-04-18",
   "iva_deducible": true,
   "anulado": false,
   "base": 60000,
   "iva": 12600
  },
  {
   "id": "G6",
   "tipo": "gasto",
   "fecha": "2025-05-30",
   "iva_deducible": false,
   "anulado": false,
   "base": 15000,
   "iva": 3150
  },
  {
   "id": "G7",
   "tipo": "gasto",
   "fecha": "2025-06-10",
   "iva_deducible": false,
   "anulado": false,
   "base": 9999,
   "iva": 0
  },
  {
   "id": "G8",
   "tipo": "gasto",
   "fecha": "2025-07-20",
   "iva_deducible": true,
   "anulado": false,
   "base": 900000,
   "iva": 189000
  },
  {
   "id": "G9",
   "tipo": "gasto",
   "fecha": "2025-08-30",
   "iva_deducible": false,
   "anulado": false,
   "base": 120000,
   "iva": 25200
  },
  {
   "id": "G10",
   "tipo": "gasto",
   "fecha": "2025-09-12",
   "iva_deducible": true,
   "anulado": true,
   "base": 50000,
   "iva": 10500
  },
  {
   "id": "G11",
   "tipo": "gasto",
   "fecha": "2025-11-05",
   "iva_deducible": true,
   "anulado": false,
   "base": 70000,
   "iva": 14700
  },
  {
   "id": "G12",
   "tipo": "gasto",
   "fecha": "2025-12-31",
   "iva_deducible": false,
   "anulado": false,
   "base": 30001,
   "iva": 0
  }
 ],
 "ejercicios": [
  {
   "caso": "E-1",
   "anio": 2025,
   "trimestre": 1,
   "casillas": {
    "01": 653459,
    "02": 82250,
    "03": 571209,
    "04": 114242,
    "05": 0,
    "06": 63519,
    "07": 50723
   },
   "resultado": "a_ingresar",
   "porcentaje_retencion": 65,
   "documentos": {
    "01": [
     "A1",
     "A2",
     "A3",
     "A4"
    ],
    "02": [
     "G1",
     "G2",
     "G3"
    ],
    "05": [],
    "06": [
     "A1",
     "A4"
    ]
   }
  },
  {
   "caso": "E-2",
   "anio": 2025,
   "trimestre": 2,
   "casillas": {
    "01": 863466,
    "02": 170399,
    "03": 693067,
    "04": 138613,
    "05": 50723,
    "06": 86019,
    "07": 1871
   },
   "resultado": "a_ingresar",
   "porcentaje_retencion": 66,
   "documentos": {
    "01": [
     "A1",
     "A2",
     "A3",
     "A4",
     "B1",
     "B2",
     "B3"
    ],
    "02": [
     "G1",
     "G2",
     "G3",
     "G5",
     "G6",
     "G7"
    ],
    "05": [
     "T1"
    ],
    "06": [
     "A1",
     "A4",
     "B1",
     "B3"
    ]
   }
  },
  {
   "caso": "E-3",
   "anio": 2025,
   "trimestre": 3,
   "casillas": {
    "01": 963466,
    "02": 1215599,
    "03": -252133,
    "04": 0,
    "05": 52594,
    "06": 101019,
    "07": -153613
   },
   "resultado": "nada_que_ingresar",
   "porcentaje_retencion": 70,
   "documentos": {
    "01": [
     "A1",
     "A2",
     "A3",
     "A4",
     "B1",
     "B2",
     "B3",
     "C1"
    ],
    "02": [
     "G1",
     "G2",
     "G3",
     "G5",
     "G6",
     "G7",
     "G8",
     "G9"
    ],
    "05": [
     "T1",
     "T2"
    ],
    "06": [
     "A1",
     "A4",
     "B1",
     "B3",
     "C1"
    ]
   }
  },
  {
   "caso": "E-4",
   "anio": 2025,
   "trimestre": 4,
   "casillas": {
    "01": 2963466,
    "02": 1315600,
    "03": 1647866,
    "04": 329573,
    "05": 52594,
    "06": 176019,
    "07": 100960
   },
   "resultado": "a_ingresar",
   "porcentaje_retencion": 40,
   "documentos": {
    "01": [
     "A1",
     "A2",
     "A3",
     "A4",
     "B1",
     "B2",
     "B3",
     "C1",
     "D1",
     "D2"
    ],
    "02": [
     "G1",
     "G2",
     "G3",
     "G5",
     "G6",
     "G7",
     "G8",
     "G9",
     "G11",
     "G12"
    ],
    "05": [
     "T1",
     "T2",
     "T3"
    ],
    "06": [
     "A1",
     "A4",
     "B1",
     "B3",
     "C1",
     "D1"
    ]
   }
  },
  {
   "caso": "E-5",
   "anio": 2026,
   "trimestre": 1,
   "casillas": {
    "01": 0,
    "02": 0,
    "03": 0,
    "04": 0,
    "05": 0,
    "06": 0,
    "07": 0
   },
   "resultado": "sin_actividad",
   "porcentaje_retencion": null,
   "documentos": {
    "01": [],
    "02": [],
    "05": [],
    "06": []
   }
  }
 ],
 "adicionales": [
  {
   "caso": "E-5b",
   "anio": 2026,
   "trimestre": 2,
   "casillas": {
    "01": 100000,
    "02": 0,
    "03": 100000,
    "04": 20000,
    "05": 0,
    "06": 15000,
    "07": 5000
   },
   "resultado": "a_ingresar",
   "porcentaje_retencion": 100,
   "documentos": {
    "01": [
     "X1"
    ],
    "02": [],
    "05": [
     "T1"
    ],
    "06": [
     "X1"
    ]
   }
  }
 ]
}
```

### B.2 Hito 1 · dominio puro del modelo 130 · 2026-11-11

**Qué hay.** Dos módulos puros nuevos en `backend/src/cuadre/tax/` (declarados en `PURE_TAX` de `test_invoicing_boundary.py`, que vigila que no importen base de datos, red, FastAPI, Pydantic ni reloj): `types_130.py` y `modelo_130.py`; `year_start` en `periods.py`; las constantes y los tres avisos en `limits.py`; todo exportado desde `cuadre.tax`. No hay base de datos, API ni pantalla todavía, y el 303 no se ha tocado.

| Pieza | Contenido |
|---|---|
| `types_130.py` | Dataclasses `frozen, slots`: entrada (`IncomeRow`: `base_cents` e `irpf_cents` con signo; `CostRow`: `base_cents`, `vat_cents`, `deductible_vat`, `voided`) y salida (`Item130`, `Box130`, `Modelo130`) |
| `modelo_130.py` | `build_modelo_130(year, quarter, incomes, costs, today)`: filtra del 1 de enero al fin del trimestre, calcula 01 a 07 por cada trimestre hasta el pedido (el pago de cada anterior alimenta la 05), enlaza cada casilla a sus documentos y devuelve resultado, porcentaje con retención, plazo y avisos |
| `limits.py` | `YEAR_MAX_DOCUMENTS = 10_000`, `IRPF_PAYMENT_RATE = Decimal(20)` y los avisos `NOTE_130_*` |
| `periods.py` | `year_start(year)`; plazo y estado son los de siempre |

**Decisiones tomadas al implementar** (completan o corrigen la spec, ya actualizada):

| Tema | Decisión |
|---|---|
| **D-12 resuelta** | **Tipos de entrada propios** (`IncomeRow`, `CostRow`) en lugar de ampliar `InvoiceRow` y `ExpenseRow`: el 303 no corre ningún riesgo y el hito 2 solo tiene que rellenar los nuevos |
| **Una sola cuenta** | Todo son sumas de céntimos enteros; el único redondeo es el 20 % de la 04 con `percentage_of` (`ROUND_HALF_UP`), **una vez** sobre la 03 y solo si es positiva |
| **Los pagos anteriores** | Se calculan trimestre a trimestre con la misma regla sobre lo acumulado hasta su fin: `max(0, 07)` de cada uno, con su propia 05. Los items de la 05 son **todos** los trimestres anteriores (id `T1`, etiqueta `T1 de 2025`, fecha = su último día), también los que pagaron 0 |
| **`sin_actividad`** | Solo si no hay ninguna factura ni gasto no anulado en el periodo acumulado. En un trimestre sin documentos a partir del T2, la 05 sigue listando los anteriores con pago 0: no contradice la regla (los items de la 05 no son documentos) |
| **Resultado** | `a_ingresar` (07 > 0) o `nada_que_ingresar` (07 ≤ 0, también el cero con documentos); el negativo no se arrastra |
| **Límite** | 10.000 documentos acumulados; reutiliza `QuarterTooLarge` de `modelo_303` (mismo `code` `quarter_too_large`) |
| **Porcentaje con retención** | Base de las facturas con retención ≠ 0 × 100 / 01, medio hacia arriba al entero (con `Decimal`; un empate como 12,5 sube a 13); `None` si la 01 no es positiva |
| **Avisos** | Tres, siempre: orientativo y acumulado; lo que no incluye (5 %, minoraciones y deducciones, vivienda afecta, compensación de negativos, y el plazo del calendario); y la regla del 70 % con el porcentaje como mera información. Redactados sin género («no tienes obligación de presentar el 130») |

**Pruebas.** **69 nuevas** (`pytest backend/tests/tax -k modelo_130`) y **3.897 en total** sin RLS (3.828 + 69); lo que no se toca (RLS, API, frontend) sigue como estaba:

| Archivo | Cubre |
|---|---|
| `test_modelo_130.py` (44) | AC-01 a AC-14, AC-18, AC-22 y AC-23: ingresos y rectificativa con signo; los cuatro tipos de gasto; el rendimiento negativo; el 20 % con redondeo (sube, baja y exactos); **el redondeo por casilla** (tres facturas de 12 céntimos: la 04 es 7, no 6); acumulado; pagos anteriores encadenados con `max(0, …)` y sus items; retenciones con signo; los tres resultados; fronteras de año y de trimestre; plazo y estado; periodo inválido y futuro; el límite; el porcentaje (empates, rectificativa que devuelve retención, 01 ≤ 0); avisos; determinismo |
| `test_modelo_130_cases.py` (18) | AC-15, AC-11, AC-12: **lee el bloque JSON de B.1** de `SPEC-W-009` y reproduce al céntimo los cinco ejercicios y la comprobación adicional (siete casillas, resultado, porcentaje y los documentos de cada casilla), con todos los documentos juntos |
| `test_modelo_130_properties.py` (7) | NFR-08 con 300 conjuntos al azar y semilla fija: suma de items = casilla, derivadas y regla del 20 %; la 05 de cada trimestre = lo que pagaron los anteriores calculados por separado; nada posterior al fin del trimestre cambia el resultado; aditividad de 01, 02 y 06; orden; otro año sin efecto; porcentaje frente a un oráculo con enteros |

**Mutaciones.** **63 mutaciones** de `modelo_130.py`, `limits.py` y `periods.py` con un ejecutor desechable fuera del repositorio (borra `__pycache__` antes y después de cada una): **62 detectadas y 1 equivalente** (K03: calcular el 20 % también con la 03 en cero, que da cero). La primera tanda dejó viva una cosa de verdad: el redondeo del porcentaje (el valor por defecto de `quantize` redondea al par y ninguna prueba tenía un empate exacto); ahora hay dos (12,5 y 37,5). Una propiedad mía estaba mal planteada (exigía que «sin actividad» no tuviera items en ninguna casilla, y la 05 lista los trimestres anteriores con pago 0); se corrigió la propiedad, no el dominio.

**Lo que no se ha comprobado:**
- **Contra la AEAT o una gestoría**: los cinco ejercicios son **simulados, no externos** (B.1); solo prueban que el código reproduce nuestro cálculo manual con las mismas reglas (D-02 a D-07).
- **Datos reales de la base**: `IncomeRow` y `CostRow` los rellena el hito 2; aquí no hay ninguna lectura.
- **Rendimiento con 10.000 documentos**: se prueba el límite, no el tiempo.

**Para el hito 2** (lectura de datos):
- Rellenar `IncomeRow` desde `public.invoices` (`id`, `{serie}-{NNN}` como `label` con `display_number`, `issue_date`, `base_cents`, `irpf_cents`; las rectificativas ya traen la diferencia con signo) y `CostRow` desde `public.expenses` (`id`, `supplier_name`, `expense_date`, `base_cents`, `vat_cents`, `deductible_vat`; los anulados se pueden dejar sin leer, `voided = False`).
- Leer por el rango `[year_start(year), fin del trimestre)` con la misma consulta por dueño y los mismos índices (`invoices_owner_date`, `expenses_by_owner_date`), con el límite de filas por consulta; los gastos manuales llegan sin IVA.
- Sembrar con los ayudantes de `tests/rls` los cinco ejercicios de B.1 y comprobar que, de la base de datos a la casilla, salen las mismas cifras (de paso, contrasta lo que calcula la base con las retenciones de B.1).

### B.3 Hito 2 · lectura de datos del modelo 130 · 2026-11-11

**Qué hay.** Solo se **añade** a `backend/src/cuadre/quarters/repository.py` (el 303 no se ha tocado y sus pruebas siguen igual): `INCOME_SQL` y `COST_SQL`, `income_rows` y `cost_rows`, y `YEAR_DEFAULT_LIMIT = YEAR_MAX_DOCUMENTS + 1`. Sin migración (D-10), sin servicio, sin modelos Pydantic y sin ruta: eso es el hito 3.

| Pieza | Contenido |
|---|---|
| `income_rows(conn, start, end, *, limit)` | Facturas de `public.invoices` con `owner_id = (SELECT auth.uid())` y `issue_date` en `[start, end)`: `id`, número que se enseña (`display_number`), fecha, `base_cents` e `irpf_cents`. Las rectificativas ya traen la diferencia con signo (B3: −50.000 y −7.500) |
| `cost_rows(conn, start, end, *, limit)` | Gastos no anulados de `public.expenses` en `[start, end)`: `id`, proveedor, fecha, `base_cents`, `vat_cents` y `deductible_vat`. Los manuales llegan con IVA 0 y no deducible (restricción de la tabla) |
| Límite | Cada consulta corta en 10.001 filas (`YEAR_DEFAULT_LIMIT`); el dominio decide `QuarterTooLarge`, como en el 303 |

**Decisiones al implementar:**

| Tema | Decisión |
|---|---|
| **No lee `tax_breakdown`** | El 130 solo necesita `base_cents` y `vat_cents` del gasto. Un tipo de IVA ilegible en las líneas (dato corrupto) rompe el 303 con `unsupported_vat_rate`, pero **no** el 130; hay una prueba que lo fija |
| **Rango, no trimestre** | Como las del 303, las funciones reciben `[start, end)`; el servicio del hito 3 pasará `year_start(year)` y el fin del trimestre |
| **Siembra de B.1** | Se emiten con las funciones `app.*` (la misma vía que la API): las ordinarias por orden cronológico en las series 2025 y 2026 (nacional con IVA 21 % y retención 15 %; UE y fuera de la UE sin retención); B3 rectifica A1 con la base vigente más la diferencia; los gastos con IVA, como documento con una línea al 21 %; los de IVA 0 sin deducir (G3, G7, G12), como **gastos manuales** (sin factura) |
| **Quién calcula qué** | Las retenciones y las diferencias de la rectificativa las calcula la base con `cuadre.tax`; la prueba las compara con las que la persona calculó a mano en B.1. Coinciden |

**Pruebas.** **27 nuevas** en `backend/tests/quarters/test_modelo_130_repository.py` (con la siembra `seed_130` en `conftest.py`); **3.924 sin RLS** (3.897 + 27) y **1.561 RLS**, todo en verde:
- AC-15: los cinco ejercicios y la comprobación adicional, de la base de datos a la casilla (siete casillas, resultado, porcentaje) y los documentos de cada casilla (ids de B.1 por el mapa de la siembra).
- Lo que guarda la base: base y retención de cada factura, base, IVA y deducibilidad de cada gasto, número y proveedor que se enseñan, los anulados nunca se leen y el orden de lectura (fecha, id).
- AC-12: primer día incluido, final exclusivo, 31/12 y 1/1, rango vacío o invertido, T1 de 2026 vacío.
- AC-16/T9-05: Beto, Gina (también con vínculo activo), Gus y Adán no leen nada de Alicia; cada persona solo lo suyo.
- Cada consulta respeta su `limit`; el valor por defecto es 10.001.
- T9-07: pedir los cuatro trimestres no cambia el recuento de facturas, gastos ni registro de actividad.
- Los índices `invoices_owner_date` y `expenses_by_owner_date` los usa el plan (`enable_seqscan = off`).

**Mutaciones.** **20 mutaciones** del SQL y de las funciones (dueño, anulados, cada frontera de fecha, columnas equivocadas, etiqueta, límite, orden, `voided`, IVA y deducibilidad) con un ejecutor desechable fuera del repositorio: la primera tanda dejó viva una (el orden de la consulta de ingresos, que el dominio reordena y por eso no cambiaba ningún resultado); se añadió una prueba del orden de lectura y **20 de 20 quedan detectadas**.

**Lo que no se ha comprobado:**
- **Contra la AEAT o una gestoría**: los ejercicios siguen siendo simulados (DEP-01 pendiente).
- **El límite con 10.001 filas reales**: se prueba el parámetro `limit` y la constante; el dominio ya cubre 10.000/10.001 y la API lo hará en el hito 3.
- **Rendimiento con un año grande**: se comprueba que los índices pueden usarse, no el tiempo.

**Para el hito 3** (API):
- `QuarterService.modelo_130(user, year, quarter)` como el del 303: validar el periodo antes de abrir transacción, leer `income_rows` y `cost_rows` en `[year_start(year), fin del trimestre)` con `user_transaction`, construir con `build_modelo_130` y presentar; `QuarterTooLarge` → `errors.quarter_too_large()` (con texto propio del 130 según §5.1).
- Modelos Pydantic del 130 en `cuadre/quarters/models.py` (casillas con `items` y `components`, `result_kind`, `withheld_share_percent`, `notes`), ruta `GET /api/tax/130` con `operation_id` `get_modelo_130` en `routes_tax.py`, `Cache-Control: private, no-store`, 401/403, y regenerar `backend/openapi.json` y `frontend/src/api/schema.d.ts` con sus scripts.
- `test_modelo_130_api.py` con la secuencia de B.1 por HTTP (AC-15), AC-13, AC-14, AC-16, AC-17 y AC-18 (el límite se puede probar bajando `YEAR_MAX_DOCUMENTS` con `monkeypatch`).

### B.4 Hito 3 · API del modelo 130 · 2026-11-11

**Qué hay.** `GET /api/tax/130?year=&quarter=` (`get_modelo_130`), solo para el rol `usuario`, con `Cache-Control: private, no-store`. Se añade, sin cambiar el comportamiento del 303:

| Archivo | Contenido |
|---|---|
| `quarters/models.py` | `Item130`, `Box130`, `Modelo130` y `present_130` (del dominio al modelo de la API; de ellos sale el cliente TypeScript) |
| `quarters/errors.py` | `period_too_large()`: `422` con el código estable `quarter_too_large` y el texto del periodo acumulado |
| `quarters/service.py` | `QuarterService.modelo_130` y el ayudante privado `_period`, compartido con el 303 |
| `api/routes_tax.py` | La ruta, con sus respuestas 401, 403 y 422 |
| `backend/openapi.json` y `frontend/src/api/schema.d.ts` | Regenerados con sus scripts (solo líneas añadidas; nada del 303 cambia) |

**Decisiones al implementar:**

| Tema | Decisión |
|---|---|
| **`id` es texto** | En `Item130`, `id` es `str`: UUID en facturas y gastos y `T1`, `T2`, `T3` en los trimestres anteriores de la casilla 05. El 303 mantiene `UUID` |
| **Mismo código, texto propio** | El límite responde `quarter_too_large` (el cliente no tiene que conocer otro código) con «El periodo acumulado desde el 1 de enero tiene más de 10.000 documentos…» |
| **`_period` compartido** | Se extrajo del 303 la resolución del periodo (por defecto el de hoy en Europe/Madrid, validación antes de abrir ninguna transacción) para no duplicarla. Las 59 pruebas del 303 y de su lectura siguen en verde sin tocarlas |
| **Sin `unsupported_vat_rate`** | El 130 no lee las líneas de IVA: una línea corrupta da `422` en el 303 y `200` en el 130 (hay una prueba que pide los dos a la vez) |
| **Solo lee** | Ninguna escritura, ni siquiera `activity_log`; ningún registro del servicio guarda números de factura, proveedores ni importes |

**Pruebas.** **36 nuevas** en `backend/tests/quarters/test_modelo_130_api.py` (aplicación y base reales, con `seeded_130`); **3.960 sin RLS**, **1.561 RLS**, frontend (typecheck, lint y 248 unitarias) y `export_openapi.py --check` y `gen:api --check`, todo en verde:
- AC-15 por HTTP: los cinco ejercicios y la comprobación adicional (siete casillas en orden, resultado, porcentaje y los documentos de cada casilla, con la suma de lo que aporta cada documento igual a la casilla).
- Forma de la respuesta (claves exactas, grupos, componentes, un item de factura, uno de gasto y uno de trimestre), plazo y estado según el reloj (los mismos que los del 303 del mismo trimestre, comparados por HTTP), valores por defecto (incluida la frontera de las 23:30 UTC) y avisos fijos, también en un periodo sin actividad.
- AC-14: periodo inexistente, no entero y futuro, y que el error de periodo se responde antes de leer la base.
- AC-18: con el límite bajado, 200 en el límite justo y `quarter_too_large` por encima, con el texto propio.
- AC-16: gestor (también con vínculo activo), administrador → `403`; sin sesión → `401`; otra persona ve `sin_actividad` y todo a cero.
- AC-17/T9-07: pedir los cuatro trimestres no cambia ningún recuento y los registros no contienen números de factura, proveedores ni importes.
- T9-08: el peor caso admisible (10.000 facturas, todas con retención, así que cada una sale en la 01 y en la 06) mide **2,51 MB** frente a los 4,5 MB de una Vercel Function: el límite de 10.000 se mantiene.

**Mutaciones.** **27 mutaciones** de `models.py` (campos del item, de la casilla y de la respuesta), `service.py` (inicio del rango, periodo por defecto, validación, error del límite, reloj), `errors.py` (código, estado, límite y texto) y de la ruta (rol, caché, parámetros): **27 de 27 detectadas**. Un patrón del ejecutor era ambiguo y se afinó.

**Lo que no se ha comprobado:**
- **Contra la AEAT o una gestoría**: los ejercicios siguen siendo simulados (DEP-01 pendiente).
- **La pantalla**: la dirección `?model=130` y la hoja son del hito 4; el cliente generado ya trae `get_modelo_130`.
- **Rendimiento**: se mide el tamaño de la respuesta, no el tiempo con 10.000 documentos.

**Para el hito 4** (frontend):
- `lib/tax-api.ts`: `getModelo130(query)` con el mismo patrón que `getModelo303` (Server Component, token de la sesión, sin caché).
- `lib/tax.ts` (puro, con unitarias): dirección `?model=303|130&year=&quarter=`, textos del resultado (`a_ingresar`, `nada_que_ingresar`, `sin_actividad`) y del porcentaje con retención («informativo»), casillas por grupo (`rendimiento`, `pagos`, `resultado`), y enlace de cada item (las facturas a su ficha, los gastos a su ficha; los items `quarter` no enlazan).
- `components/tax/modelo-130.tsx` y la pestaña «Modelo 130» activa en `quarter-picker.tsx`; `app/(app)/trimestres/page.tsx` elige la hoja según `?model=`; sin JavaScript de cliente; el 303 sin cambios (AC-20).

### B.5 Hito 4 · pestaña y hoja del modelo 130 · 2026-11-11

**Qué hay.** La pestaña «Modelo 130» de `/trimestres` deja de ser «Próximamente» y pasa a ser un enlace (`?model=130`; sin parámetro o con cualquier otro valor, el 303). La hoja sigue el prototipo (`docs/cuadre-interfaz.html`): cabecera oscura «IRPF, pago fraccionado · T2 de 2025, importes acumulados desde enero», las siete casillas en tres grupos, el resultado al pie y debajo el porcentaje con retención como texto pequeño de apoyo, más el mismo selector de año y trimestre y el mismo estado del plazo. Server Components y HTML nativo: ni una línea de JavaScript de cliente (`check:bundle` en verde). **La interfaz no calcula nada**: importes, resultado, porcentaje y avisos son los del servidor.

| Archivo | Cambio |
|---|---|
| `lib/tax.ts` | `ModelKey`, `parseModel`, `quarterHref(year, quarter, model)`; textos y agrupación del 130 (`resultText130`, `withheldShareText`, `groupBoxes130`, `componentsText130`, `itemSummary130`, `itemHref130`); la fila de cada casilla como dato (`boxView130` y `boxView303`, funciones puras) |
| `lib/tax-api.ts` | `getModelo130` y `TaxReading<M>` genérico, con el tratamiento de errores del 303 en una función común |
| `components/tax/box-row.tsx` | `BoxLine`: el marcado de una fila, único para los dos modelos; `BoxRow` (303) es un adaptador fino con las mismas clases |
| `components/tax/modelo-130.tsx` | `Modelo130Sheet` |
| `components/tax/quarter-picker.tsx` | Las dos pestañas son enlaces y conservan el año y el trimestre; los enlaces de trimestre y el formulario del año conservan el modelo (solo el 130 lleva `model`: las direcciones del 303 no cambian) |
| `components/tax/notes.tsx`, `deadline-status.tsx` | `avisos-${model}` (el del 303 sigue siendo `avisos-303`); el estado del plazo acepta los dos modelos |
| `app/(app)/trimestres/page.tsx` | Elige la lectura y la hoja según `?model=`; «Ir al trimestre actual» respeta el modelo |
| `e2e/trimestres.spec.ts` | Solo la afirmación obsoleta «130 desactivado con Próximamente» pasa a «130 es un enlace»; nada más del E2E del 303 cambia |

**Decisiones al implementar:**

| Tema | Decisión |
|---|---|
| **Una sola fila para los dos modelos** | En lugar de copiar el marcado de `BoxRow`, se extrae `BoxLine` y cada modelo le da su vista ya escrita. Es el único cambio sobre código del 303; lo vigilan las unitarias de `boxView303`, el E2E del 303 y la comparación visual |
| **Los trimestres anteriores enlazan** | En la casilla 05 cada trimestre anterior (`T1 de 2026…`) enlaza al 130 de ese trimestre (`/trimestres?model=130&year=&quarter=`): cumple NFR-08 enseñando de dónde sale cada pago. La nota de B.4 decía «no enlazan»; era una sugerencia y se corrige aquí. Un `id` que no sea `T1` a `T4` no enlaza |
| **Resultado negativo** | «Nada que ingresar este trimestre», sin repetir el signo; el importe con signo está en la casilla 07 (y el rendimiento negativo, en la 03). No se arrastra ni se compensa: los avisos del servidor lo dicen |
| **Regla del 70 %** | No se redacta en la interfaz: llega en `notes` (aviso fijo) y el porcentaje del año se enseña solo como información |
| **Grupos** | El prototipo agrupa 01 a 06 bajo un solo título; aquí son los tres grupos del servidor: «Rendimiento de la actividad (estimación directa)», «Pagos ya hechos y retenciones» y «Resultado» |
| **Gastos** | Un gasto no tiene detalle propio: se enseña su proveedor sin enlace y el desplegable cierra con «Ir a Gastos» (como en el 303) |

**Pruebas.**
- **12 unitarias nuevas** en `lib/tax.test.ts`; **260 en total**, todas en verde (las 248 anteriores, sin tocar): `parseModel` (ausente, `130`, `303`, valores raros, listas), la dirección (la del 303 idéntica), el plazo, los tres resultados, el porcentaje (incluido `null` y 0), las siete casillas siempre en tres grupos, los componentes de 03, 04 y 07, los resúmenes por tipo y por casilla, los enlaces de factura, trimestre y gasto, y las filas de los dos modelos.
- `lint`, `typecheck`, `build`, `check:bundle` y `gen:api --check`, con código 0; el backend no cambia (`pytest backend/tests/quarters`: 122 en verde; `ruff check`).
- **E2E del 303**: `e2e/trimestres.spec.ts` completo en Chromium a 1.440 px (un motor, un worker): **14 de 14** en verde con la afirmación del 130 actualizada.
- **Comprobación visual del 130** con una prueba **desechable** (no se commitea) en Chromium, Firefox y WebKit, a 390 y 1.440 px (6 de 6): las siete casillas con el importe del servidor, los tres grupos, el porcentaje y los tres avisos, pestaña activa y 303 sin `model`, los desplegables de la 01 y la 06 con el enlace a la factura y el de la 05 con enlace al trimestre anterior, trimestre y año conservan el modelo, T1 sin pagos anteriores, el periodo futuro se explica y «Ir al trimestre actual» conserva el 130; sin scroll horizontal, campos etiquetados y sin errores de consola. Las capturas se miraron a mano (escritorio y móvil).
- **Mutaciones de la lógica de la interfaz**: **41 de 41 detectadas** (dirección, `parseModel`, textos del resultado y del porcentaje, grupos, componentes, resúmenes, enlaces, importes y fechas, y la fila del 303), con un ejecutor desechable fuera del repositorio. Un patrón del ejecutor era ambiguo y se afinó. Las mutaciones de los componentes quedan para el hito 5.

**Lo que no se ha comprobado:**
- **La batería completa** (Chromium, Firefox y WebKit a 390 y 1.440 px) con los E2E propios del 130: es el hito 5. Aquí solo el E2E del 303 en un motor y la prueba visual desechable en los tres.
- **Roles y `responsive.spec.ts`** con el 130: sin tocar todavía (el gestor y el administrador siguen yendo a `/403` por la ruta de siempre).
- **Contra la AEAT o una gestoría**: los ejercicios siguen siendo simulados (DEP-01 pendiente).

**Para el hito 5** (E2E y cierre):
- `e2e/modelo-130.spec.ts` en los seis proyectos: lo que enseña la pantalla es lo que dice el servidor (casilla a casilla, resultado, porcentaje, avisos y documentos), emitiendo con las fixtures `gastosPage`, `biller` y `ledger`; un oráculo `TaxApi.modelo130` en `e2e/helpers/tax.ts` (tipos `Tax130` y `TaxItem130`, sin tocar los del 303) y la fixture `tax` ampliada.
- Cobertura de AC-19 a AC-23: pestaña y dirección (`?model=130&year=&quarter=`), enlaces de factura y de trimestre anterior, trimestre futuro, dirección ilegible, interfaz (sin scroll horizontal, etiquetas, teclado, foco y consola) y aislamiento por cuenta.
- Ajustes de `roles.spec.ts` (el gestor y el administrador no ven `/trimestres?model=130`, van a `/403`) y de `responsive.spec.ts` (también el 130).
- Mutaciones de los componentes (`box-row`, `modelo-130`, `quarter-picker`, `notes`, `page`), batería completa en tres motores y dos anchos, Anexo B final y cierre de `tasks.json`; si llegan ejercicios externos de DEP-01, se añaden.

### B.6 Hito 5 · E2E y cierre · 2026-11-11

**Qué hay.** `e2e/modelo-130.spec.ts` (12 pruebas por proyecto, seis proyectos), `TaxApi.modelo130(year?, quarter?)` y los tipos `Tax130`, `Tax130Box` y `TaxItem130` en `e2e/helpers/tax.ts` (el oráculo: lee el borrador por la API con el token de GoTrue de la cuenta, nunca la service key; `amountsOf` y `deltas` aceptan cualquier modelo). Tres pruebas nuevas en `roles.spec.ts` (el autónomo llega a la pestaña; el gestor y el administrador van a `/403` también con `?model=130`) y una en `responsive.spec.ts` (`/trimestres?model=130`). Ningún cambio de producción: las pruebas no encontraron ningún defecto.

**Decisiones.**
- Como en SPEC-W-008, **ninguna prueba espera cifras absolutas**: la cuenta del worker acumula facturas (RES-03). Cada una lee el oráculo (`tax.modelo130()`), comprueba que la pantalla enseña lo mismo y, si emite, que la **diferencia** es la esperada y que sus documentos salen en su casilla. La regla del 20 %, el acumulado y los pagos anteriores los fijan las pruebas del backend.
- Los gastos sin factura salen de `ledger.seed` (1 y 2 de enero de 2026, 10,01 € y 10,02 €) y se piden con `?year=2026&quarter=4`; el gasto con IVA deducible es el de ejemplo del servidor de agentes (`fixture:invoice_ok`, 28/10/2026). Ambas pruebas se omiten si hoy es anterior al 1/10/2026.
- Los avisos y fechas se buscan con `text()` (solo lo visible): Next conserva oculta la hoja del otro modelo al navegar con enlaces.

**Pruebas por proyecto:** la hoja (menú, pestaña, plazo y avisos); lo que enseña la pantalla frente al servidor (siete casillas, derivadas, resúmenes y filas de cada desplegable, resultado, porcentaje, ids de avisos); facturas y una rectificativa (01 +265.000 y 06 +30.000 exactos, enlaces, retención de la rectificativa); gastos (la 02 sube 2.003 y, anulados, baja); un gasto con IVA deducible suma solo su base (2.479); pagos de los trimestres anteriores (cada uno `max(0, 07)` y su enlace al 130 de ese trimestre); un periodo sin actividad; el selector (trimestre, año y pestañas conservan el modelo; el 303 sigue ahí; `?model=abc` enseña el 303); futuro y direcciones raras; interfaz (sin scroll horizontal, etiquetas, teclado, foco y consola); sin red; cada persona, lo suyo.

**Resultados** (`--workers=1`, un motor por invocación):

| Qué | Resultado |
|---|---|
| `modelo-130.spec.ts`, Chromium a 1.440 px | 15 correctas (12 y las 3 de inicio de sesión) |
| Batería completa, Chromium (390 y 1.440 px) | **305 correctas** |
| Batería completa, Firefox | **297 correctas**, 6 omitidas |
| Batería completa, WebKit | **297 correctas**, 6 omitidas |
| Backend sin RLS | 3.960 correctas |
| RLS (con la base recién reiniciada) | 1.561 correctas |
| `ruff`, `export_openapi --check`, `gen:api --check`, `lint`, `typecheck`, `build` y `check:bundle` | código 0 |
| Pruebas unitarias del frontend | 260 correctas |

La batería incluye W-001, 002, 003, 005, 006, 007 y 008. **Primera pasada con dos fallos intermitentes, ajenos al 130:** Chromium (restablecer contraseña a 390 px: dos 404 de recursos en consola) y WebKit (`gastos-registro`: campos de la revisión sin etiqueta asociada). Cada uno repitió 4 de 4 en verde aislado y las segundas pasadas de Chromium y WebKit salieron limpias; Firefox salió limpia a la primera. **RLS dio un fallo la primera vez** (`test_nobody_else_has_any_invoice_or_pdf`): la batería E2E deja PDFs a la Alicia sembrada y ese test exige que no tenga ninguno; con `supabase db reset` pasa, como en SPEC-W-008.

**Mutaciones de la interfaz.** **21 mutaciones** de `box-row`, `modelo-130`, `quarter-picker`, `notes`, la página y `tax-api` (con `next build` y `modelo-130.spec.ts` en Chromium a 1.440 px por mutante, restauración por huella): **21 detectadas, ninguna equivalente**. Dos no compilaron: una se rehízo (C02, detectada) y la del 303 leyendo otra cosa (C19) no es del 130 y la cubre `trimestres.spec.ts`. Se añadió una aserción (los avisos de cada modelo llevan su propio id) porque una mutación sobre ese id habría sobrevivido.

**Lo que no se ha comprobado:**
- **El CI de GitHub**: la verificación es local; la spec queda en `en-revision` hasta que la persona lo confirme.
- **Validación externa (DEP-01)**: los cinco ejercicios de B.1 son **simulados, no externos**; solo prueban que el código reproduce un cálculo manual con las mismas reglas (D-02 a D-07). Sigue siendo una mejora pendiente.
- **Los seis proyectos en paralelo**: un worker y un motor por vez, no la configuración del CI.
- **Lectores de pantalla reales** y **periodos con miles de documentos** en el navegador (la respuesta máxima mide 2,51 MB en la API).
- **Un 07 negativo en el E2E**: la cuenta del worker acumula facturas y no se puede garantizar; lo cubren el dominio, la API y los ejercicios de B.1.

**Estado de la spec.** Todos los hitos hechos, verificación local en verde y CI de GitHub en verde en `a4b0418`, confirmado por la persona el 2026-11-12: **`hecha`** (2026-11-12). Los ejercicios simulados del Anexo B.1 se dan por buenos por decisión de la persona del 2026-11-12; la validación externa de DEP-01 sigue como mejora pendiente (si llegan ejercicios externos, se añaden con la misma prueba).
