---
tipo: spec
id: SPEC-W-009
titulo: Modelo 130: borrador orientativo del pago fraccionado del IRPF, acumulado desde enero y con cada casilla enlazada a sus facturas y gastos
estado: propuesta
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
| D-04 | **02 · gastos deducibles** = por cada gasto no anulado del periodo, su `base_cents` más el IVA que **no** se deduce (`vat_cents` si `deductible_vat = false`, nada si se deduce); los gastos sin factura valen su importe. Todas las categorías cuentan igual (P-01 decide lo de la vivienda) | Contar solo ciertas categorías: no hay base legal en el PRD |
| D-05 | **03 · rendimiento neto** = 01 − 02 (puede ser negativo). **04 = 20 % de la 03 solo si la 03 es positiva**, con `Decimal` y `ROUND_HALF_UP`, **una vez** por casilla (ADR-0006); si no, 0 | Calcular el 20 % por documento: acumula céntimos de más |
| D-06 | **05 · pagos fraccionados anteriores** = suma de lo ingresado en los trimestres anteriores **del mismo año**; lo de cada uno es `max(0, 04 − 05 − 06)` **de ese trimestre**, calculado con la misma regla (recursivo, como el prototipo). Sus `items` son los propios trimestres | Leer pagos reales de una tabla: no existe; el borrador solo conoce lo que calcula |
| D-07 | **06 · retenciones soportadas** = suma de `irpf_cents` de las facturas del periodo, con signo. **07 · resultado** = 04 − 05 − 06. `result_kind`: `a_ingresar` (07 > 0), `nada_que_ingresar` (07 ≤ 0, un negativo ni se arrastra ni se compensa) y `sin_actividad` (ningún documento en todo el periodo acumulado) | Resultado negativo con compensación: fuera de alcance (P-04) |
| D-08 | **Cada casilla enlaza a sus documentos** (NFR-08, 100 %): la 01 y la 06 a facturas, la 02 a gastos, la 05 a los trimestres anteriores; la 03, la 04 y la 07 enumeran en `components` las casillas que las componen. **La suma de los `items` es el importe de la casilla** | Solo totales: no cumple NFR-08 |
| D-09 | **El servidor calcula todo**, también el plazo y su estado, que son **los del 303** (20 de abril, julio y octubre; 30 de enero), con el reloj inyectado; la interfaz no calcula nada fiscal | Calcular en el navegador: dos implementaciones de la regla |
| D-10 | **Solo lectura, sin tablas nuevas**: se calcula bajo demanda sobre `invoices` y `expenses` con la sesión de la persona (RLS), con las lecturas de `cuadre.quarters` por rango desde el 1 de enero. Una migración solo si el hito 2 demuestra que hace falta | Guardar borradores: histórico de lo calculado, con la duda de qué hacer cuando cambian los documentos |
| D-11 | **Información, no regla**: la respuesta lleva el **porcentaje de ingresos con retención** del año (sobre la 01, redondeado al entero) y un aviso fijo sobre la regla del 70 % del año anterior, que **no se calcula** (falta ese dato) | Calcular la regla del año anterior: necesita el año anterior completo y la fecha de alta |
| D-12 | **Lectura**: se amplían las filas de entrada con campos opcionales de valor 0 por defecto (`irpf_cents` en `InvoiceRow`; `base_cents` y `vat_cents` en `ExpenseRow`) para no romper el 303, o se crean tipos propios; lo decide el hito 2 con las pruebas del 303 en verde | Tipos propios: más código, pero ningún riesgo para el 303 |
| D-13 | **Pantalla**: la pestaña «Modelo 130» de `/trimestres` pasa a enlace (`?model=130`; sin parámetro, el 303); misma hoja del prototipo, mismo selector de año y trimestre y mismo estado del plazo; sin JavaScript de cliente | Una pantalla aparte: dos rutas y dos menús |

**Preguntas abiertas** (la persona las contesta antes del hito 1; hasta entonces rige la propuesta):

| ID | Pregunta | Propuesta por defecto |
|---|---|---|
| P-01 | **Vivienda afecta** (`home_pct`): SPEC-W-005 dejó para esta spec limitar la deducción de los suministros. ¿Se aplica ya? | **No** en esta spec (como el prototipo): se anota como exclusión visible («no incluye la deducción por vivienda afecta») y se deja para una spec posterior. Alternativa: aplicar `30 % × home_pct %` a los gastos de la categoría `utilities` desde el hito 1 |
| P-02 | ¿Basta la fecha de expedición y la del gasto, o hace falta el criterio de cobro y pago? | Fecha de expedición y del gasto (D-02), como el 303 |
| P-03 | La retención que lleva un **gasto** (`withholding_cents`): ¿cuenta en algo? | **No**: la casilla 06 son las retenciones que la persona sufre en sus facturas |
| P-04 | Un resultado negativo (los gastos superan lo ingresado): ¿se arrastra o se compensa en trimestres posteriores? | **No**: «nada que ingresar», sin compensar; se anota como límite |
| P-05 | ¿Cómo se demuestra NFR-03 mientras DEP-01 esté pendiente? | Cinco ejercicios **simulados a mano** (Anexo B.1), calculados con cuentas escritas e independientes del código y marcados «simulados, no externos»; DEP-01 queda como mejora pendiente |

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
- **La deducción de la vivienda afecta** (`home_pct`), salvo decisión contraria en P-01.
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
| `05` pagos de trimestres anteriores | suma de `max(0, 07)` de cada trimestre anterior del año | los trimestres anteriores |
| `06` retenciones soportadas | suma de `irpf_cents` de las facturas del periodo | las facturas con retención |
| `07` resultado | `04 − 05 − 06` | derivada: `04`, `05`, `06` |

**Item**: `kind` (`invoice` | `expense` | `quarter`), `id`, `label` (número de factura, proveedor del gasto o «T1 de 2026»), `date` (la de la factura o del gasto; la de fin de trimestre en un `quarter`) y `amount_cents`, **lo que ese documento aporta a esa casilla** (la base en la 01, la retención en la 06, el coste en la 02, el pago en la 05), con signo. El coste de un gasto es su base más el IVA no deducible.

**Resultado**: `result_cents` (= casilla 07) y `result_kind` (`a_ingresar` | `nada_que_ingresar` | `sin_actividad`).

**Información**: `withheld_share_percent` (entero, sobre la 01; `null` si la 01 no es positiva).

**Avisos fijos** (`notes`, **siempre presentes**): borrador **orientativo** y sin presentar; lo que no incluye (§4: 5 % de difícil justificación, minoraciones y deducciones, vivienda afecta, compensación de negativos); y el de la regla del 70 % (D-11): «Si en el año anterior más del 70 % de tus ingresos llevó retención, no estás obligada a presentar el 130.» El porcentaje del año en curso es solo informativo.

**Límite**: un periodo con más de **10.000 documentos** (facturas y gastos acumulados desde enero) da `quarter_too_large` (422, con texto propio) en vez de una respuesta que no cabría en 4,5 MB (ADR-0016).

### 5.2 Base de datos
Sin cambios (D-10). RLS ya limita `invoices` y `expenses` a `owner_id = auth.uid()`; el gestor con vínculo lee por las políticas existentes (su pantalla es SPEC-W-010); el administrador no ve ninguna fila.

### 5.3 API HTTP

| Operación | Ruta | Respuesta |
|---|---|---|
| `get_modelo_130` | `GET /api/tax/130?year=&quarter=` | `200` con `Modelo130` (periodo, plazo y estado, casillas con items, resultado, porcentaje con retención y avisos). `422` `invalid_period` / `period_in_future` / `quarter_too_large`; `401`; `403` (no es `usuario`) |

Los parámetros, los errores y el valor por defecto son los de `get_modelo_303`. `Cache-Control: private, no-store`. Solo lee: no crea ni cambia nada (T9-07).

### 5.4 Backend
`cuadre/tax/modelo_130.py` y `cuadre/tax/types_130.py` (puros); en `cuadre/quarters/`, el repositorio ampliado (D-12), `QuarterService.modelo_130` y los modelos y errores del 130; `cuadre/api/routes_tax.py` con la ruta nueva. Los módulos nuevos de `cuadre.tax` se declaran como puros en `test_invoicing_boundary.py`.

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
| T9-11 | **El 303 no cambia de comportamiento**: sus pruebas (dominio, API, pantalla y E2E) siguen en verde sin tocarlas más que para añadir los campos opcionales de D-12 |
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

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005, 006, 007 y 008 §8.2 siguen en verde.
- [ ] Los **cinco ejercicios simulados** del Anexo B.1 coinciden al céntimo (NFR-03, P-05). La **validación externa de DEP-01** queda como mejora pendiente y se anota en el Anexo B al cerrar; si la persona la exige antes de cerrar, la spec no pasa de `en-revision`.
- [ ] El 100 % de las casillas con documentos enumera sus items y su suma es la casilla (NFR-08).
- [ ] La pestaña «Modelo 130» de `/trimestres` está activa y hace todo lo de AC-19 a AC-23; el 303 no ha cambiado (AC-20).
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0006, 0011, 0015 y 0016 enlazados.
- [ ] Las preguntas P-01 a P-05 están resueltas o anotadas en el Anexo B.
- [ ] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

1. **Hito 0 · decisiones y cinco ejercicios simulados**: se confirman D-01 a D-13 y se resuelven P-01 a P-05; se redactan en el Anexo B.1 **cinco ejercicios resueltos a mano**, con las cuentas escritas paso a paso y sin ejecutar el código (con acumulado y pagos encadenados T1→T4, ingresos de los tres ámbitos, rectificativa, gastos con y sin IVA deducible y sin factura, retenciones, un rendimiento negativo, un 20 % con céntimos y la frontera de año), contrastados con un script independiente fuera del repositorio y marcados «simulados, no externos».
2. **Hito 1 · dominio puro**: `modelo_130.py` y `types_130.py` con pruebas de los ejercicios a mano, propiedades de `items` y mutaciones.
3. **Hito 2 · lectura de datos**: filas ampliadas (D-12) y lectura por rango desde el 1 de enero, con la prueba del límite y las del 303 en verde.
4. **Hito 3 · API**: `get_modelo_130`, modelos, errores, OpenAPI y cliente, con las pruebas de la API.
5. **Hito 4 · frontend**: la pestaña, la hoja del 130, `lib/tax.ts` ampliado con sus unitarias y la comprobación visual en tres motores.
6. **Hito 5 · E2E y cierre**: `modelo-130.spec.ts`, ajustes de `roles.spec.ts` y `responsive.spec.ts`, mutaciones de la interfaz, Anexo B, `tasks.json` y, si llegan, los ejercicios externos de DEP-01.

## Anexo B · Decisiones que esta spec deja a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-011 (MCP).** La herramienta `borrador_trimestre` llama a las funciones de dominio de **los dos modelos** (`build_modelo_303` y `build_modelo_130`); no se reimplementa ninguna regla.
- **SPEC-W-014 (recordatorios).** El importe estimado del 130 que cita el correo sale de `build_modelo_130` con el mismo trimestre.
- **SPEC-W-010 (gestor).** Lee el mismo borrador con las políticas de lectura que ya existen; hace falta su pantalla y el registro de cada lectura.
- **SPEC-W-019 (XLSX).** Los libros registro salen de los mismos documentos.
- **Vivienda afecta.** Si P-01 se resuelve en contra de aplicarla ahora, queda una deuda visible en los avisos y apuntada para una spec posterior; `home_pct` sigue guardándose sin usarse.

### B.1 Hito 0 · cinco ejercicios simulados, resueltos a mano · pendiente

**Estado: «simulados, no externos».** Se redactan en el hito 0 con una tabla por ejercicio (documento → importe → casilla), las cuentas escritas paso a paso y el bloque JSON para las pruebas del hito 1. Los cálculos son **manuales e independientes del código** y se contrastan con un script desechable fuera del repositorio. No demuestran que la interpretación de las reglas (D-02 a D-07) sea la de la AEAT: eso daría la validación externa de DEP-01, que sigue **pendiente** como mejora.
