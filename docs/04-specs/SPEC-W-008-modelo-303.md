---
tipo: spec
id: SPEC-W-008
titulo: Modelo 303 casilla a casilla: borrador orientativo del IVA trimestral con cada casilla enlazada a sus facturas y gastos
estado: en-revision
prioridad: must
riesgo: medio
historias: [US-003]
requisitos: [RF-013]
nfr: [NFR-03, NFR-08]
restricciones: [RES-01, RES-02, RES-04]
adr: [0003, 0006, 0011, 0015, 0016]
depende_de: [SPEC-W-003, SPEC-W-007]
bloquea: [SPEC-W-009, SPEC-W-011]
fecha: 2026-11-11
---

# SPEC-W-008 · Modelo 303 casilla a casilla

> Cuarto paso de la cadena **perfil → clientes → facturas → trimestre**. Con lo que la persona ya tiene registrado (facturas emitidas en SPEC-W-007 y gastos en SPEC-W-003), la aplicación calcula **sola** el borrador del modelo 303 (IVA, autoliquidación) de un trimestre y enseña **cada casilla con las facturas y los gastos que la componen**, para que pueda revisarlo y presentarlo con confianza en la sede de la AEAT.
> Lo que **no** hace es presentar: el borrador es **orientativo** y no se envía nada a la AEAT (RES-04). El modelo 130 es SPEC-W-009; el 349, la compensación de periodos anteriores y los regímenes especiales quedan fuera (§4).

## 1. Contexto

**Situación de partida.** Las facturas emitidas ya guardan, factura a factura, el dato que el 303 necesita: `tax_treatment` (`national_vat`, `eu_reverse_charge`, `eu_consumer_vat`, `non_eu_consumer_vat`, `non_eu_not_subject`), `base_cents`, `vat_rate` y `vat_cents`, con **signo** en las rectificativas (SPEC-W-007 §5.1.3 y B.0). Los gastos registrados (SPEC-W-003) guardan `expense_date`, `deductible_vat`, `base_cents`, `vat_cents` y las líneas validadas de `tax_breakdown` (tipo, base y cuota), y los anulados llevan `voided_at`. En el menú del autónomo «Trimestres» sale desactivado («Próximamente»). El prototipo (`docs/cuadre-interfaz.html`) fija las casillas y la pantalla.

**Por qué es de riesgo medio.** El riesgo es **de la regla fiscal, no del modelo** (US-003, INVEST): una casilla mal sumada da un borrador equivocado que la persona podría presentar (R-03). Por eso toda la regla vive en una función **pura, determinista y con pruebas**, sin lectura de la base ni del reloj, y NFR-03 exige que coincida **al céntimo** con cinco trimestres resueltos a mano (DEP-01). La persona decidió el 2026-11-11 (P-03) que, en lugar de esperar a DEP-01, se **simulen cinco trimestres de referencia resueltos a mano** (Anexo B.1): se calculan con cuentas escritas paso a paso, **independientes del código**, y quedan marcados como **«simulados, no externos»**. Eso demuestra que el código reproduce un cálculo manual, pero **no es la validación externa que pide NFR-03** (equipo docente o gestoría): esa sigue siendo una mejora pendiente y se anota como tal al cerrar.

**Decisiones vigentes** (no se reabren aquí): ADR-0003 y ADR-0015 (SQL explícito, psycopg síncrono); ADR-0006 (céntimos enteros, `Decimal` con `ROUND_HALF_UP`, redondeo por documento y tipo y una vez por casilla derivada); ADR-0011 (cliente TypeScript generado y `operation_id`); ADR-0016 (Vercel Function: sin trabajo posterior a la respuesta, 4,5 MB por petición); RES-01 (la lógica fiscal es determinista y no usa modelos de lenguaje); RES-04 (nada se envía a la AEAT).

**Decisiones que propone esta spec** (por defecto; **P-01 a P-05 las resolvió la persona el 2026-11-11**; D-01 a D-10 se tratan como aprobadas salvo que las corrija antes del hito 1):

| ID | Decisión | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Solo el 303 y solo el régimen general.** Casillas 01-09 (devengado por tipo del 4, 10 y 21 %), 27, 28, 29, 45, 46, 59 y 120, las del prototipo. Las demás casillas del formulario (compensaciones, prorrata, resultado de la liquidación, 349…) no se calculan (§4) | Más casillas: más reglas y más casos a mano; cada una es un hito propio |
| D-02 | **El trimestre lo fija la fecha de expedición** de la factura (`issue_date`) y la **fecha del gasto** (`expense_date`), en trimestres naturales de **Europe/Madrid**. Una rectificativa cuenta, con su signo, en el trimestre de **su propia** fecha de expedición (SPEC-W-007 B.0) | Criterio de caja (fecha de cobro): es otro régimen y queda fuera (P-01, resuelta) |
| D-03 | **Devengado**: `national_vat`, `eu_consumer_vat` y `non_eu_consumer_vat` suman base y cuota en la casilla de **su tipo** (`vat_rate` 4, 10 o 21); `eu_reverse_charge` suma su **base** en la **59**; `non_eu_not_subject` suma su base en la **120**. Un tipo distinto de 4, 10 o 21 no se esconde: error explícito (`unsupported_vat_rate`) | Una casilla «otros tipos»: no existe en el modelo |
| D-04 | **Deducible**: gastos **no anulados** con `deductible_vat = true`, sumados por **línea de `tax_breakdown` con cuota** (tipo > 0): base en la **28** y cuota en la **29**. Las líneas con tipo 0 no tienen cuota y no entran; los gastos con IVA no deducible no entran (y la pantalla no los lista) | Sumar la base de todo gasto deducible, como el prototipo: infla la 28 con operaciones sin cuota (P-02, resuelta: no entran) |
| D-05 | **Sumas en céntimos enteros**: la cuota de cada documento ya está redondeada al céntimo (al emitir o registrar); las casillas **suman**, sin volver a redondear. Solo una casilla derivada se redondea, una vez, con `ROUND_HALF_UP` (en el 303 no hay ninguna: 27 = suma de cuotas, 45 = 29 y 46 = 27 − 45) | Recalcular la cuota desde la base y el tipo: puede diferir un céntimo de lo facturado |
| D-06 | **Resultado 46 = 27 − 45** en céntimos con signo: positivo = «a ingresar»; negativo = «a compensar» en próximos trimestres (sin compensar nada, D-01); **cero con documentos en el trimestre = «a cero»** (27 = 45, o una factura anulada del todo) y **«sin actividad» solo si el trimestre no tiene ningún documento** (corregido en el hito 1, B.2) | Calcular el resultado final con compensaciones: fuera de alcance |
| D-07 | **Cada casilla enlaza a sus documentos** (NFR-08, 100 %): la API devuelve, por casilla, los `items` (factura o gasto) que la componen, con su identificador, número o proveedor, fecha, base y cuota, y la **suma de los items es igual a la casilla** (propiedad que se comprueba en las pruebas). Las casillas derivadas (27, 45, 46) enlazan a las casillas que las componen | Solo totales: no cumple NFR-08 |
| D-08 | **El servidor calcula todo**: el trimestre, el plazo de presentación y su estado (`en_curso`, `plazo_abierto`, `plazo_cerrado`) salen de la API con el reloj inyectado; la interfaz **no calcula nada fiscal** (como D-14 de SPEC-W-007) | Calcular en el navegador: dos implementaciones de la regla |
| D-09 | **Solo lectura, sin tablas nuevas**: el borrador se calcula bajo demanda sobre `invoices` y `expenses` con la sesión de la persona (RLS). Nada se guarda ni se congela: un borrador no es un documento legal. Una migración solo si el hito 2 demuestra que la consulta lo necesita, y entonces entra en la matriz RLS | Guardar borradores: histórico de lo calculado, pero hay que decidir qué pasa cuando cambian las facturas |
| D-10 | **Pantalla `/trimestres`** nace aquí con el 303 (el 130 se añade en SPEC-W-009): selector de trimestre del año, casillas agrupadas como el prototipo (IVA devengado, IVA deducible, resultado, información adicional), detalle desplegable por casilla, resultado y plazo con texto además de color, y el aviso «orientativo» | Una pantalla por modelo: dos rutas y dos menús |

**Preguntas resueltas el 2026-11-11** (las cinco, por la persona):

| ID | Pregunta | Respuesta |
|---|---|---|
| P-01 | ¿Se necesita el **criterio de caja** (IVA al cobro) o basta la fecha de expedición? | **Fecha de expedición** (D-02); el criterio de caja no está en el PRD |
| P-02 | Un gasto deducible con líneas al 0 %: ¿entra su base en la 28? | **No** (D-04) |
| P-03 | **DEP-01**: ¿quién entrega los cinco trimestres resueltos a mano y cuándo? | **No se espera a nadie: los simula el asistente** (Anexo B.1), calculados a mano e independientes del código y marcados «simulados, no externos». NFR-03 se da por cubierta con esos casos **por decisión de la persona**; la validación externa real sigue pendiente como mejora y DEP-01 se conserva en `external` |
| P-04 | Canarias, Ceuta y Melilla (heredada de SPEC-W-007 P-02): `ES` es nacional con IVA | **Se queda como nacional, con un aviso fijo** en la API y en la pantalla (§5.1, AC-21); no hay IGIC |
| P-05 | ¿«Trimestres» muestra desde ya la pestaña del 130 desactivada («Próximamente»)? | **Sí**, desactivada y con el texto «Próximamente», como el menú (la propuesta era «Disponible con SPEC-W-009», pero un identificador interno no le dice nada a quien usa la aplicación; corregido en el hito 4, B.5) |

## 2. Objetivo

Que la persona abra **«Trimestres»**, elija un trimestre y vea su **borrador del modelo 303** con las casillas del régimen general, el resultado («a ingresar», «a compensar», «a cero» o «sin actividad»), el plazo de presentación y, **bajo cada casilla, las facturas y los gastos que la componen**, todo calculado por el servidor con reglas deterministas, en céntimos exactos, marcado como **orientativo** y sin enviar nada a la AEAT.

## 3. Alcance explícito

### 3.1 Dominio puro (`cuadre.tax.modelo_303`)
Función pura `build_modelo_303(year, quarter, invoices, expenses, today)` que recibe documentos ya leídos (tipos inmutables, sin base de datos ni reloj), clasifica cada factura por `tax_treatment` y tipo y cada gasto por línea con cuota, suma en céntimos enteros y devuelve las casillas con sus `items`, el resultado, el plazo y el estado. Errores explícitos (`unsupported_vat_rate`, `quarter_too_large`, `invalid_period`, `period_in_future`). Módulos puros: `periods.py`, `types_303.py` y `modelo_303.py`. Funciones de periodo: inicio y fin de cada trimestre natural, trimestre de una fecha y plazo de presentación (1-20 de abril, julio y octubre; 1-30 de enero).

### 3.2 Base de datos
**Sin migraciones** (D-09; confirmado en el hito 2: los índices `invoices_owner_date` y `expenses_by_owner_date` cubren la consulta). Una consulta por tabla con el rango `[inicio, fin)` del trimestre y `voided_at is null` en gastos. Si un hito posterior añade una función SQL o un índice, va en su propia migración, entra en `rls_matrix.yaml` y tiene sus pruebas de RLS.

### 3.3 Backend (FastAPI)
`GET /api/tax/303?year=&quarter=` (`operation_id: get_modelo_303`), solo rol `usuario`; servicio y repositorio de lectura; modelos Pydantic estrictos; errores `application/problem+json`; OpenAPI regenerado; sin registro de datos personales.

### 3.4 Frontend (Next.js)
Ruta `/trimestres` (Server Components), «Trimestres» activo en el menú del autónomo, selector de trimestre en la dirección (`?año=&trimestre=`), casillas con detalle desplegable y enlaces a `/facturas/[id]` y a `/gastos`, estados vacío y de error, cliente generado y tokens del prototipo.

### 3.5 Pruebas
Unitarias del dominio con casos a mano y propiedades; API y repositorio contra la base real; RLS; unitarias del frontend; Playwright `trimestres.spec.ts` en Chromium, Firefox y WebKit a 390 y 1.440 px; mutaciones del dominio y de la interfaz.

## 4. Alcance excluido

- **Modelo 130** (SPEC-W-009) y la pestaña que lo enseña; la página solo deja el hueco (P-05).
- **Modelo 349**, **presentación o envío a la AEAT** (RES-04), **XLSX de los libros registro** (SPEC-W-019) y **recordatorios** de plazo (SPEC-W-014).
- **Compensación de cuotas de periodos anteriores**, **prorrata**, **regímenes especiales** (criterio de caja, recargo de equivalencia, REAGP), **adquisiciones intracomunitarias e inversión del sujeto pasivo en compras**, **importaciones** y el resultado final de la liquidación (casillas 64 a 71). El borrador lo dice en pantalla.
- **IGIC** (Canarias) y cualquier IVA que no sea el peninsular (P-04).
- **Congelar o guardar borradores** (D-09) y **cambiar facturas o gastos** desde esta pantalla: solo lee.
- La **pantalla del gestor** (SPEC-W-010) y las herramientas del chatbot (`borrador_trimestre`, SPEC-W-011): leerán la misma función de dominio.

## 5. Contrato de interfaces

### 5.1 Campos y reglas

**Periodo.** `year` (2000-9998) y `quarter` (1-4). Un trimestre que aún no ha empezado (según el reloj en Europe/Madrid) da `period_in_future`; el trimestre en curso se calcula con lo registrado hasta hoy. `period_start` y `period_end` (fechas ISO) y `deadline` (último día de presentación) salen del dominio.

**Estado del plazo** (`deadline_status`): `en_curso` (el trimestre no ha terminado), `plazo_abierto` (terminó y `today <= deadline`) y `plazo_cerrado` (`today > deadline`). El `deadline` es la **fecha del calendario**: la AEAT lo traslada al siguiente día hábil si cae en sábado, domingo o festivo y el dominio no lo calcula (el aviso de «lo que no incluye» lo dice).

**Clasificación de una factura** (de su `tax_treatment`, sin recalcular nada):

| `tax_treatment` | Va a |
|---|---|
| `national_vat`, `eu_consumer_vat`, `non_eu_consumer_vat` con tipo 4 / 10 / 21 | base y cuota de 01-03 / 04-06 / 07-09 |
| `eu_reverse_charge` | 59 (base) |
| `non_eu_not_subject` | 120 (base) |

**Casillas** (todas en céntimos enteros con signo): `01`, `03`, `04`, `06`, `07`, `09` por tipo; `27` = `03 + 06 + 09`; `28` y `29` de los gastos (D-04); `45` = `29`; `46` = `27 − 45`; `59` y `120`. Cada casilla lleva `code`, `label` (texto en español), `amount_cents`, `group` (`devengado`, `deducible`, `resultado`, `adicional`), `measure` (`base` o `vat`: qué importe de cada item suma en ella; `null` en las derivadas), `items` (vacío en las derivadas, que enlazan a sus `components`) y `components` (códigos). **Las trece casillas salen siempre**, también a cero; la interfaz oculta las nulas que no aplican.

**Item**: `kind` (`invoice` | `expense`), `id`, `label` (número de factura o proveedor del gasto), `date`, `base_cents`, `vat_cents`. Una rectificativa es un item más con importes negativos. El `label` de un gasto es el nombre del proveedor tal como lo registró la persona.

**Resultado**: `result_cents` (= casilla 46) y `result_kind` (`a_ingresar` | `a_compensar` | `a_cero` | `sin_actividad`): `a_cero` cuando hay documentos pero 27 = 45; `sin_actividad` solo si el trimestre no tiene ningún documento (los gastos anulados no cuentan como documento).

**Avisos fijos** (`notes`, textos del dominio, **siempre presentes**): borrador **orientativo** y sin presentar; lo que no incluye (§4); **«No incluye el IGIC ni las operaciones en Canarias, Ceuta y Melilla: si tu actividad o tus clientes están allí, consulta con un asesor.»** (P-04: la ficha del cliente solo guarda el país, así que el aviso no puede saber si aplica); y, solo si hay casilla 59, «también va en el modelo 349».

**Límite**: un trimestre con más de **5.000 documentos** da `quarter_too_large` (422) en vez de una respuesta que no cabría en 4,5 MB (ADR-0016).

### 5.2 Base de datos
Sin cambios (D-09). Las lecturas pasan por la sesión de la persona: RLS ya limita `invoices` y `expenses` a `owner_id = auth.uid()`; el gestor con vínculo lee por las políticas existentes (su pantalla es SPEC-W-010); el administrador no ve ninguna fila.

### 5.3 API HTTP

| Operación | Ruta | Respuesta |
|---|---|---|
| `get_modelo_303` | `GET /api/tax/303?year=&quarter=` | `200` con `Modelo303` (periodo, plazo y estado, casillas con items, resultado y avisos). `422` `invalid_period` / `period_in_future` / `unsupported_vat_rate` / `quarter_too_large`; `401`; `403` (no es `usuario`) |

`year` y `quarter` son **opcionales**: sin ellos se usan los de hoy en Europe/Madrid (cada uno por su cuenta). La ruta no los limita con `ge`/`le` para que un periodo que no existe dé el `invalid_period` propio y no un `validation_error` genérico; un valor que no sea entero sí es `validation_error`. El periodo se valida **antes** de leer la base. Los cuatro `422` llevan `application/problem+json` con `code` estable y un `detail` en español que no repite lo enviado ni datos de los documentos.

`Cache-Control: private, no-store`. Solo lee: no crea ni cambia nada (T8-07).

### 5.4 Backend
`cuadre/tax/modelo_303.py` (puro), `cuadre/tax/periods.py` (trimestres y plazos, puro) y `cuadre/tax/types_303.py` (tipos); **`cuadre/quarters/`** (paquete de lectura compartido con SPEC-W-009: `repository.py` desde el hito 2 y, en el hito 3, `service.py`, `models.py` —respuesta Pydantic— y `errors.py`; sin conexiones fuera de `cuadre.db`); `cuadre/api/routes_tax.py`. La lectura **no va en `cuadre.tax`** porque necesita el número de factura de `cuadre.invoicing` y `cuadre.tax` no depende de ese paquete (lo vigila `test_invoicing_boundary.py`). `cuadre.core.clock` aporta «hoy en Madrid».

### 5.5 Frontend
`lib/tax-api.ts` (lectura de servidor), `lib/tax.ts` (puro: formato de periodo, textos de estado y de resultado, enlaces de cada item), `app/(app)/trimestres/page.tsx`, `components/tax/*` (`quarter-picker`, `modelo-303`, `box-row`, `deadline-status` y `notes`: selector de año y de trimestre, hoja con las casillas por grupo, fila con desplegable de documentos, estado del plazo y avisos). El trimestre vive en la dirección: `?year=&quarter=`, los mismos nombres que la API. Todo son Server Components y HTML nativo (un `<form method="get">`, enlaces y `<details>`): ninguna línea de JavaScript de cliente. Ninguna cuenta ni regla fiscal en el navegador (D-08).

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T8-01 | **Sin `float`** en importes: céntimos enteros o `Decimal` con `ROUND_HALF_UP` (RES-02); un test lo vigila en código y migraciones |
| T8-02 | **El dominio es puro**: no lee la base ni el reloj; recibe los documentos y el «hoy» (RES-01) |
| T8-03 | **Sin red ni modelos de lenguaje**: nada se envía a la AEAT ni a otro servicio (RES-04); sin dependencias nuevas |
| T8-04 | **Cada casilla se explica** (NFR-08): la suma de sus `items` es igual a la casilla y las derivadas enumeran sus componentes; una prueba de propiedades lo cumple con documentos generados |
| T8-05 | **Solo `usuario`** lo lee por la API; el gestor, por RLS en su pantalla (SPEC-W-010); el administrador, nunca (D3) |
| T8-06 | **Sin datos personales en logs, trazas ni errores**: ni nombre de proveedor o cliente, ni NIF, ni concepto; los errores dicen qué campo falla |
| T8-07 | **Una lectura no escribe**: ninguna fila nueva ni cambiada, ni siquiera `activity_log` |
| T8-08 | **Cabe en una Vercel Function** (ADR-0016): sin trabajo posterior a la respuesta, respuesta < 4,5 MB (de ahí el límite de 5.000 documentos de §5.1), `test_vercel_compat` en verde |
| T8-09 | **Borrador orientativo**: la API y la pantalla lo dicen siempre, junto con el aviso de Canarias, Ceuta y Melilla; la pantalla no ofrece «presentar» ni «descargar para la AEAT» |
| T8-10 | **Interfaz** como T7-11: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, desplegables nativos, sin scroll horizontal a 390 y 1.440 px en los tres motores |
| T8-11 | **Datos sintéticos** (RES-07): los casos a mano y el seed no llevan datos reales; el seed añade facturas y gastos en los cuatro trimestres solo si hace falta para el E2E (y entonces se revisan las pruebas que cuentan filas) |
| T8-12 | **Las pruebas E2E no pueden borrar** facturas ni archivar gastos emitidos (T7-13): usan la cuenta nueva de cada worker y comparan contra el servidor, nunca contra números absolutos de otra prueba |

## 7. Criterios de aceptación (Given-When-Then)

**AC-01 · Factura nacional por tipo.** *Given* tres facturas nacionales del trimestre, una al 21 %, otra al 10 % y otra al 4 %; *When* se pide el 303; *Then* cada base y cuota aparece en las casillas 07/09, 04/06 y 01/03, y la 27 es la suma de las tres cuotas.

**AC-02 · UE y fuera de la UE.** *Given* una factura a una empresa de la UE (`eu_reverse_charge`) y otra a un cliente de fuera sin IVA (`non_eu_not_subject`); *Then* sus bases van a la 59 y a la 120 y **no** suman en la 27; con la 59 distinta de cero aparece «también va en el modelo 349».

**AC-03 · Particulares con IVA español.** *Given* facturas a un particular de la UE y a uno de fuera con IVA español; *Then* suman en la casilla de su tipo como las nacionales.

**AC-04 · Rectificativa.** *Given* una factura de 1.200,00 € de base emitida en el T1 y una rectificativa de −200,00 € emitida en el T2; *Then* el T1 cuenta 1.200,00 € y el T2 −200,00 € (con su IVA negativo), y la rectificativa figura como un item más.

**AC-05 · Gastos deducibles.** *Given* gastos con IVA deducible, uno con IVA no deducible y uno anulado; *Then* solo los deducibles y no anulados suman en la 28 (base) y la 29 (cuota) y la 45 es igual a la 29; los demás no aparecen.

**AC-06 · Líneas por tipo.** *Given* un gasto con dos líneas (21 % y 10 %) y otro con una línea al 0 %; *Then* las dos primeras suman en 28/29 por separado y la del 0 % no entra (P-02).

**AC-07 · Resultado.** *Given* 27 mayor que 45, menor, igual con documentos, y un trimestre sin documentos; *Then* el resultado es «a ingresar», «a compensar» (46 negativo), «a cero» y «sin actividad».

**AC-08 · Cada casilla se explica.** *Given* cualquier trimestre; *Then* la suma de los `items` de cada casilla con items es igual a su importe y las derivadas (27, 45, 46) enumeran sus componentes (NFR-08, 100 %).

**AC-09 · Fronteras de trimestre y de zona horaria.** *Given* facturas expedidas el 31/03 y el 01/04 (y el 31/12 y el 01/01); *Then* cada una cuenta en el trimestre de su fecha en Europe/Madrid.

**AC-10 · Plazo y estado.** *Given* el reloj en distintas fechas; *Then* el plazo es el 20 de abril, julio y octubre y el 30 de enero del año siguiente, y el estado es `en_curso`, `plazo_abierto` o `plazo_cerrado` según corresponda.

**AC-11 · Periodo inválido o futuro.** *Given* `quarter=5`, un año fuera de rango o un trimestre que no ha empezado; *Then* `422` con `invalid_period` o `period_in_future` y el texto en español.

**AC-12 · Tipo no soportado.** *Given* una factura con IVA y un tipo distinto de 4, 10 o 21, o una operación sin IVA (`eu_reverse_charge`, `non_eu_not_subject`) con tipo o cuota distintos de cero (dato corrupto); *Then* `422 unsupported_vat_rate`; la casilla no lo esconde.

**AC-13 · Redondeo al céntimo.** *Given* los **cinco trimestres simulados** del Anexo B.1 (cuotas con redondeo `ROUND_HALF_UP` por documento, resueltos a mano e independientes del código); *Then* todas las casillas coinciden **al céntimo** con el cálculo manual (NFR-03). Si llegan trimestres externos (DEP-01), se añaden aquí con la misma prueba.

**AC-14 · Aislamiento.** *Given* dos usuarios con documentos; *Then* cada uno solo ve los suyos; el gestor sin vínculo y el administrador no ven ninguno (`403` por la API, RLS por la base).

**AC-15 · Solo lectura y sin datos personales.** *Given* cualquier petición; *Then* no se escribe ninguna fila y ningún log, traza ni error contiene nombres, NIF o conceptos.

**AC-16 · Trimestre demasiado grande.** *Given* más de 5.000 documentos en un trimestre; *Then* `422 quarter_too_large`.

**AC-17 · Pantalla.** *Given* la persona con facturas y gastos; *When* abre «Trimestres» y elige un trimestre; *Then* ve las casillas agrupadas, el resultado con texto, el plazo y el estado, el aviso «orientativo», el detalle desplegable de cada casilla con enlaces a las facturas y a los gastos, y la dirección guarda el trimestre.

**AC-18 · Menú y pestaña del 130.** *Given* la sesión del autónomo; *Then* «Trimestres» está activo y lleva a `/trimestres`; la pestaña del 130 sale desactivada con su texto (P-05); el gestor y el administrador no la ven y `/trimestres` los lleva a `/403`.

**AC-19 · Sin datos y errores.** *Given* un trimestre sin facturas ni gastos; *Then* la pantalla dice «Sin actividad en este trimestre» y las casillas salen a cero; un fallo del servidor da un mensaje en español sin trazas.

**AC-20 · Adaptable y accesible.** *Given* 390 y 1.440 px en Chromium, Firefox y WebKit; *Then* no hay scroll horizontal, las casillas y los desplegables tienen etiqueta y se usan con el teclado, el estado se entiende sin color y la consola no registra errores.

**AC-21 · Avisos fijos.** *Given* cualquier trimestre, también uno sin actividad; *Then* la API devuelve en `notes` el aviso de **orientativo**, la lista de lo que no incluye y el aviso de **Canarias, Ceuta y Melilla**, y la pantalla los enseña; con la casilla 59 distinta de cero, además «también va en el modelo 349».

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-007 §8.1: pila de Supabase en marcha, puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 (o `E2E_AGENTS_PORT`) libres, sin red y con datos sintéticos.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                                  # migraciones + seed
pytest backend/tests/tax -k modelo_303 -q                              # AC-01 a AC-13 y AC-16 (dominio)
pytest backend/tests -m "not rls" -q                                   # incluye la API (AC-11, AC-12, AC-15, AC-16)
pytest backend/tests/rls -m rls -q                                     # AC-14
ruff check backend ; ruff format --check backend
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/trimestres.spec.ts   # AC-17 a AC-21 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/tax -k modelo_303` y `npm --prefix frontend exec -- playwright test e2e/trimestres.spec.ts`, además de las secuencias completas de SPEC-W-001, 002, 003, 005, 006 y 007.

### 8.3 Correspondencia criterio → prueba

| Criterio | Prueba |
|---|---|
| AC-01 a AC-03 | `backend/tests/tax/test_modelo_303.py` (clasificación por tratamiento y tipo) |
| AC-04, AC-05, AC-06 | `test_modelo_303.py` (rectificativas, gastos y líneas) |
| AC-07, AC-08 | `test_modelo_303.py` (resultado) y `test_modelo_303_properties.py` (propiedades de `items` con documentos generados) |
| AC-09, AC-10, AC-11 | `backend/tests/tax/test_modelo_303_periods.py` (el nombre lleva `modelo_303` para que el comando de la spec lo seleccione) y `test_modelo_303_api.py` |
| AC-12, AC-16 | `test_modelo_303.py` y `test_modelo_303_api.py` |
| AC-13 | `test_modelo_303_cases.py`: los cinco trimestres simulados a mano de esta spec (Anexo B.1) y, si llegan, los externos de DEP-01 |
| AC-14 | `backend/tests/rls/` (lecturas de `invoices` y `expenses` por rol) y `test_modelo_303_api.py` (403) |
| AC-15 | `test_modelo_303_api.py` (sin escrituras ni datos personales en logs) |
| AC-17 a AC-21 | `frontend/e2e/trimestres.spec.ts`, `roles.spec.ts`, `responsive.spec.ts` y las unitarias de `lib/tax.test.ts` (AC-21 también en `test_modelo_303_api.py`) |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005, 006 y 007 §8.2 siguen en verde. *(Local, verificado el 2026-11-11 —Anexo B.6—, con la batería completa en los tres motores; el CI lo confirma la persona.)*
- [x] Los **cinco trimestres simulados** del Anexo B.1 coinciden al céntimo (NFR-03, por decisión de la persona del 2026-11-11): en el dominio, desde la base de datos y por HTTP. La **validación externa de DEP-01** queda como mejora pendiente (Anexo B.6); si la persona la exige antes de cerrar, la spec no pasa de `en-revision`.
- [x] El 100 % de las casillas con documentos enumera sus items y su suma es la casilla (NFR-08): propiedad del dominio, pruebas de la API y E2E contra el servidor.
- [x] «Trimestres» está activo en el menú del autónomo y `/trimestres` hace todo lo de AC-17 a AC-21.
- [x] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0006, 0011, 0015 y 0016 enlazados.
- [x] Las preguntas P-01 a P-05 están resueltas (2026-11-11).
- [x] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

1. **Hito 0 · decisiones y cinco trimestres simulados**: se confirman D-01 a D-10 y se redactan en el Anexo B.1 **cinco trimestres resueltos a mano**, con las cuentas escritas paso a paso y sin ejecutar el código (solo nacional; UE y fuera de la UE con particulares; rectificativa que cruza trimestre; gastos de varios tipos con uno no deducible, uno anulado y una línea al 0 %; un trimestre «a compensar» y uno «sin actividad»), marcados «simulados, no externos».
   **Hecho el 2026-11-11** (cinco trimestres: T1 a T4 de 2025 y T1 de 2026, con empates de medio céntimo, los cuatro ámbitos, rectificativas que cruzan trimestre y cadenas, gastos de varios tipos y los resultados «a ingresar», «a compensar» y «sin actividad»; totales calculados a mano y contrastados al céntimo con un script independiente fuera del repositorio; D-01 a D-10 se confirman sin cambios; Anexo B.1).
2. **Hito 1 · dominio puro**: `periods.py` y `modelo_303.py` con sus tipos, pruebas de los casos a mano, propiedades de `items` y mutaciones.
   **Hecho el 2026-11-11** (`periods.py`, `types_303.py` y `modelo_303.py` puros; 113 pruebas nuevas, 3.768 sin RLS; los cinco trimestres simulados reproducidos al céntimo desde el bloque JSON de B.1; 75 mutaciones: 73 detectadas y 2 equivalentes por diseño; el resultado `a_cero` y el campo `measure` corrigieron §5.1 y D-06; Anexo B.2).
3. **Hito 2 · lectura de datos**: consultas de trimestre para facturas y gastos (SQL explícito) y, solo si hace falta, una migración con su matriz RLS y sus pruebas; prueba del límite de documentos.
   **Hecho el 2026-11-11** (paquete `cuadre.quarters` con `invoice_rows` y `expense_rows`, sin migración ni cambios de RLS; los cinco trimestres de B.1 sembrados con las funciones reales de la base y reproducidos al céntimo desde la base de datos hasta la casilla; 25 pruebas nuevas y 3.793 sin RLS; 23 mutaciones del repositorio: 22 detectadas y 1 equivalente; Anexo B.3).
4. **Hito 3 · API**: `get_modelo_303`, modelos, errores, OpenAPI y pruebas de la API (incluidas las de sin escrituras y sin datos personales).
   **Hecho el 2026-11-11** (`GET /api/tax/303` con `QuarterService`, modelos Pydantic y los cuatro errores 422; `openapi.json` y el cliente del frontend regenerados; los cinco trimestres de B.1 reproducidos al céntimo por HTTP; 35 pruebas nuevas y 3.828 sin RLS; 37 mutaciones de la capa de API: 36 detectadas y 1 equivalente; Anexo B.4).
5. **Hito 4 · frontend**: `gen:api`, `/trimestres`, el menú, `lib/tax.ts` con sus unitarias y la comprobación visual en tres motores.
   **Hecho el 2026-11-11** (la pantalla `/trimestres` con el selector de año y trimestre, la hoja del 303 por grupos, los documentos de cada casilla en desplegables y los avisos, sin JavaScript de cliente; «Trimestres» activo en el menú; 16 unitarias nuevas y 248 en total; 46 mutaciones de las piezas puras, todas detectadas; comprobación visual con la API y la base reales en Chromium, Firefox y WebKit a 390 y 1.440 px —48 comprobaciones por motor—; Anexo B.5).
6. **Hito 5 · E2E y cierre**: `trimestres.spec.ts`, ajustes de `roles.spec.ts` y `responsive.spec.ts`, mutaciones de la interfaz, Anexo B, `tasks.json` y, si llegan, los trimestres externos de DEP-01.
   **Hecho el 2026-11-11** (`trimestres.spec.ts` con 11 pruebas por proyecto, `helpers/tax.ts` y el fixture `tax`, ajustes de `roles.spec.ts` y `responsive.spec.ts`; 26 mutaciones de la interfaz, todas detectadas; batería completa por motor: Chromium 273, Firefox 265 y WebKit 265 correctas, con 6 omitidas en los dos últimos; ningún defecto de producto; Anexo B.6).

## Anexo B · Decisiones que esta spec deja a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-009 (130).** Reutiliza `cuadre.tax.periods` y la página `/trimestres` (la pestaña del 130 ya está prevista, P-05); las retenciones salen de `irpf_cents` de las mismas facturas (SPEC-W-007 B.0) y los ingresos y gastos del 130 se calculan con la misma clasificación de documentos.
- **SPEC-W-011 (MCP).** La herramienta `borrador_trimestre` llama a la **misma función de dominio**; no se reimplementa la regla.
- **SPEC-W-010 (gestor).** Lee el mismo borrador con las políticas de lectura que ya existen; hace falta su pantalla y el registro de cada lectura.
- **SPEC-W-019 (XLSX).** Los libros registro salen de los mismos documentos y del mismo trimestre.

### B.1 Hito 0 · cinco trimestres simulados, resueltos a mano · 2026-11-11

**Estado: «simulados, no externos».** Cada trimestre lleva la tabla de documentos, la cuenta de cada cuota (`base × tipo / 100`, con `ROUND_HALF_UP`: la mitad se aleja de cero) y las casillas con los documentos que las componen. Los totales se calcularon **a mano antes de ejecutar nada** y se contrastaron con un script desechable, **fuera del repositorio y sin importar `cuadre`**, con aritmética entera: **coinciden los cinco trimestres al céntimo** y la suma de los documentos de cada casilla es la casilla (NFR-08). Todos los importes están en **céntimos**; los gastos traen sus cuotas ya validadas (no se calculan).

**Límite de lo que demuestran.** Que el código reproduce un cálculo manual hecho con la misma interpretación de las reglas (D-02 a D-06). No demuestran que esa interpretación sea la de la AEAT: eso es lo que daría la validación externa de DEP-01 (equipo docente o gestoría), que sigue **pendiente** y que la persona decidió no esperar (2026-11-11).

**Convenciones de los casos.** Año 2025 y T1 de 2026 (todos pasados). Una rectificativa guarda la **diferencia** entre los valores tras la rectificación y los vigentes, con el tipo y el tratamiento de la original, y cuenta en el trimestre de **su** fecha de expedición (D-02). Un documento de gasto cuenta en la 28/29 con la suma de sus líneas con tipo > 0 (D-04). Los identificadores (`A1`, `R1`, `EB1`…) son de esta spec; las pruebas del hito 1 los reutilizan.

#### Q-A · T1 de 2025 · solo nacional, con empates de redondeo y la frontera del 31/03

| Id | Fecha | Documento | Tipo | Base | Cuota | Cuenta de la cuota |
|---|---|---|---|---|---|---|
| A1 | 2025-01-15 | factura nacional | 21 % | 250 | 53 | 250 × 21 % = 52,5 → 53 |
| A2 | 2025-02-03 | factura nacional | 21 % | 120000 | 25200 | 120000 × 21 % = 25200 |
| A3 | 2025-02-20 | factura nacional | 10 % | 105 | 11 | 105 × 10 % = 10,5 → 11 |
| A4 | 2025-03-10 | factura nacional | 10 % | 2345 | 235 | 2345 × 10 % = 234,5 → 235 |
| A5 | 2025-03-18 | factura nacional | 4 % | 1237 | 49 | 1237 × 4 % = 49,48 → 49 |
| A6 | 2025-03-31 | factura nacional | 4 % | 1238 | 50 | 1238 × 4 % = 49,52 → 50 |

| Casilla | Importe | Documentos |
|---|---|---|
| 01 Base al 4 % | 2475 | A5 (1237), A6 (1238) |
| 03 Cuota al 4 % | 99 | A5 (49), A6 (50) |
| 04 Base al 10 % | 2450 | A3 (105), A4 (2345) |
| 06 Cuota al 10 % | 246 | A3 (11), A4 (235) |
| 07 Base al 21 % | 120250 | A1 (250), A2 (120000) |
| 09 Cuota al 21 % | 25253 | A1 (53), A2 (25200) |
| 27 Total cuota devengada | 25598 | derivada: 03 + 06 + 09 |
| 28 Base deducible | 0 | — |
| 29 Cuota deducible | 0 | — |
| 45 Total a deducir | 0 | derivada: 29 |
| 46 Resultado (27 − 45) | 25598 | derivada: 27 − 45 |
| 59 Servicios a empresas de la UE | 0 | — |
| 120 No sujetas por localización | 0 | — |

**Resultado:** `a_ingresar` (255,98 €)

#### Q-B · T2 de 2025 · los cuatro ámbitos y gastos deducibles de varios tipos (empieza el 01/04)

| Id | Fecha | Documento | Tipo | Base | Cuota | Cuenta de la cuota |
|---|---|---|---|---|---|---|
| B1 | 2025-04-01 | factura nacional | 21 % | 80000 | 16800 | 80000 × 21 % = 16800 |
| B2 | 2025-04-22 | factura UE empresa (ISP) | sin IVA | 150000 | 0 | — |
| B3 | 2025-05-06 | factura fuera de la UE, no sujeta | sin IVA | 90000 | 0 | — |
| B4 | 2025-05-20 | factura particular UE con IVA | 21 % | 5050 | 1061 | 5050 × 21 % = 1060,5 → 1061 |
| B5 | 2025-06-10 | factura particular de fuera con IVA | 10 % | 3333 | 333 | 3333 × 10 % = 333,3 → 333 |
| B6 | 2025-06-30 | factura nacional | 21 % | 100000 | 21000 | 100000 × 21 % = 21000 |

| Id | Fecha | Gasto | Líneas (tipo: base / cuota) | Cuenta en 28 / 29 |
|---|---|---|---|---|
| EB1 | 2025-04-15 | deducible | 21 %: 40000 / 8400 | 40000 / 8400 |
| EB2 | 2025-05-12 | deducible | 21 %: 10000 / 2100; 10 %: 5000 / 500 | 15000 / 2600 |
| EB3 | 2025-06-20 | deducible | 4 %: 2500 / 100 | 2500 / 100 |

| Casilla | Importe | Documentos |
|---|---|---|
| 01 Base al 4 % | 0 | — |
| 03 Cuota al 4 % | 0 | — |
| 04 Base al 10 % | 3333 | B5 (3333) |
| 06 Cuota al 10 % | 333 | B5 (333) |
| 07 Base al 21 % | 185050 | B1 (80000), B4 (5050), B6 (100000) |
| 09 Cuota al 21 % | 38861 | B1 (16800), B4 (1061), B6 (21000) |
| 27 Total cuota devengada | 39194 | derivada: 03 + 06 + 09 |
| 28 Base deducible | 57500 | EB1 (40000), EB2 (15000), EB3 (2500) |
| 29 Cuota deducible | 11100 | EB1 (8400), EB2 (2600), EB3 (100) |
| 45 Total a deducir | 11100 | derivada: 29 |
| 46 Resultado (27 − 45) | 28094 | derivada: 27 − 45 |
| 59 Servicios a empresas de la UE | 150000 | B2 (150000) |
| 120 No sujetas por localización | 90000 | B3 (90000) |

**Resultado:** `a_ingresar` (280,94 €)

#### Q-C · T3 de 2025 · rectificativas que cruzan trimestre, cadenas de rectificativas y anulación completa

| Id | Fecha | Documento | Tipo | Base | Cuota | Cuenta de la cuota |
|---|---|---|---|---|---|---|
| C1 | 2025-07-08 | factura nacional | 21 % | 120000 | 25200 | 120000 × 21 % = 25200 |
| C2 | 2025-07-20 | factura nacional | 10 % | 2345 | 235 | 2345 × 10 % = 234,5 → 235 |
| C3 | 2025-07-25 | factura nacional | 10 % | 105 | 11 | 105 × 10 % = 10,5 → 11 |
| C4 | 2025-09-30 | factura nacional | 4 % | 50000 | 2000 | 50000 × 4 % = 2000 |
| R1 | 2025-07-15 | rectificativa de B1, base corregida 60000 | nacional 21 % | -20000 | -4200 | vigente 80000 / 16800; corregida 60000 × 21 % = 12600 → 12600; base 60000 − 80000 = -20000; cuota 12600 − 16800 = -4200 |
| R2 | 2025-08-02 | rectificativa de B2, base corregida 100000 | UE empresa (ISP) sin IVA | -50000 | 0 | vigente 150000 / 0; corregida 100000 × 0 % = 0 → 0; base 100000 − 150000 = -50000; cuota 0 − 0 = 0 |
| R3 | 2025-08-20 | rectificativa de C1, base corregida 0 | nacional 21 % | -120000 | -25200 | vigente 120000 / 25200; corregida 0 × 21 % = 0 → 0; base 0 − 120000 = -120000; cuota 0 − 25200 = -25200 |
| R5 | 2025-08-25 | rectificativa de C3, base corregida 53 | nacional 10 % | -52 | -6 | vigente 105 / 11; corregida 53 × 10 % = 5,3 → 5; base 53 − 105 = -52; cuota 5 − 11 = -6 |
| R4 | 2025-09-10 | rectificativa de C2, base corregida 1105 | nacional 10 % | -1240 | -124 | vigente 2345 / 235; corregida 1105 × 10 % = 110,5 → 111; base 1105 − 2345 = -1240; cuota 111 − 235 = -124 |
| R6 | 2025-09-25 | rectificativa de C3, base corregida 0 | nacional 10 % | -53 | -5 | vigente 53 / 5; corregida 0 × 10 % = 0 → 0; base 0 − 53 = -53; cuota 0 − 5 = -5 |

| Casilla | Importe | Documentos |
|---|---|---|
| 01 Base al 4 % | 50000 | C4 (50000) |
| 03 Cuota al 4 % | 2000 | C4 (2000) |
| 04 Base al 10 % | 1105 | C2 (2345), C3 (105), R5 (-52), R4 (-1240), R6 (-53) |
| 06 Cuota al 10 % | 111 | C2 (235), C3 (11), R5 (-6), R4 (-124), R6 (-5) |
| 07 Base al 21 % | -20000 | C1 (120000), R1 (-20000), R3 (-120000) |
| 09 Cuota al 21 % | -4200 | C1 (25200), R1 (-4200), R3 (-25200) |
| 27 Total cuota devengada | -2089 | derivada: 03 + 06 + 09 |
| 28 Base deducible | 0 | — |
| 29 Cuota deducible | 0 | — |
| 45 Total a deducir | 0 | derivada: 29 |
| 46 Resultado (27 − 45) | -2089 | derivada: 27 − 45 |
| 59 Servicios a empresas de la UE | -50000 | R2 (-50000) |
| 120 No sujetas por localización | 0 | — |

**Resultado:** `a_compensar` (−20,89 €)

#### Q-D · T4 de 2025 · gastos variados (dos líneas, no deducible, anulado, línea al 0 %, 31/12) y resultado «a compensar»

| Id | Fecha | Documento | Tipo | Base | Cuota | Cuenta de la cuota |
|---|---|---|---|---|---|---|
| D1 | 2025-10-05 | factura nacional | 21 % | 30000 | 6300 | 30000 × 21 % = 6300 |

| Id | Fecha | Gasto | Líneas (tipo: base / cuota) | Cuenta en 28 / 29 |
|---|---|---|---|---|
| ED1 | 2025-10-10 | deducible | 21 %: 200000 / 42000; 10 %: 50000 / 5000 | 250000 / 47000 |
| ED2 | 2025-11-04 | IVA no deducible | 21 %: 10000 / 2100 | no cuenta |
| ED3 | 2025-11-18 | anulado | 21 %: 7000 / 1470 | no cuenta |
| ED4 | 2025-12-02 | deducible | 0 %: 8000 / 0; 21 %: 1000 / 210 | 1000 / 210 (la línea al 0 % no entra) |
| ED5 | 2025-12-31 | manual sin IVA | base 5000, cuota 0 | no cuenta |
| ED6 | 2025-12-31 | deducible | 10 %: 2000 / 200 | 2000 / 200 |

| Casilla | Importe | Documentos |
|---|---|---|
| 01 Base al 4 % | 0 | — |
| 03 Cuota al 4 % | 0 | — |
| 04 Base al 10 % | 0 | — |
| 06 Cuota al 10 % | 0 | — |
| 07 Base al 21 % | 30000 | D1 (30000) |
| 09 Cuota al 21 % | 6300 | D1 (6300) |
| 27 Total cuota devengada | 6300 | derivada: 03 + 06 + 09 |
| 28 Base deducible | 253000 | ED1 (250000), ED4 (1000), ED6 (2000) |
| 29 Cuota deducible | 47410 | ED1 (47000), ED4 (210), ED6 (200) |
| 45 Total a deducir | 47410 | derivada: 29 |
| 46 Resultado (27 − 45) | -41110 | derivada: 27 − 45 |
| 59 Servicios a empresas de la UE | 0 | — |
| 120 No sujetas por localización | 0 | — |

**Resultado:** `a_compensar` (−411,10 €)

#### Q-E · T1 de 2026 · «sin actividad» entre dos documentos vecinos (31/12/2025 y 01/04/2026)

| Casilla | Importe | Documentos |
|---|---|---|
| 01 Base al 4 % | 0 | — |
| 03 Cuota al 4 % | 0 | — |
| 04 Base al 10 % | 0 | — |
| 06 Cuota al 10 % | 0 | — |
| 07 Base al 21 % | 0 | — |
| 09 Cuota al 21 % | 0 | — |
| 27 Total cuota devengada | 0 | derivada: 03 + 06 + 09 |
| 28 Base deducible | 0 | — |
| 29 Cuota deducible | 0 | — |
| 45 Total a deducir | 0 | derivada: 29 |
| 46 Resultado (27 − 45) | 0 | derivada: 27 − 45 |
| 59 Servicios a empresas de la UE | 0 | — |
| 120 No sujetas por localización | 0 | — |

**Resultado:** `sin_actividad`

**Lo que ejercita cada caso**

- **Q-A.** Empates de medio céntimo (A1 `52,5 → 53`, A3 `10,5 → 11`, A4 `234,5 → 235`) y redondeo por documento: la cuota del 10 % suma `246`, no `245` (que saldría de redondear una sola vez sobre la base total `2450`). A6 (31/03) cuenta en el T1; B1 (01/04) en el T2.
- **Q-B.** UE empresa → 59 y fuera de la UE sin IVA → 120 (no suman en la 27); el particular de la UE al 21 % (B4, empate `1060,5 → 1061`) y el de fuera al 10 % (B5, `333,3 → 333`) suman en su tipo; los tres gastos con cuota llenan 28/29 con todos los tipos; con la 59 distinta de cero el aviso del 349.
- **Q-C.** R1 y R2 rectifican documentos del T2 y **restan en el T3**; el T2 queda completo (Q-B no cambia). R3 anula C1 entera (base y cuota `−120000`/`−25200`, el 07 y el 09 quedan negativos). C2 y R4 dejan vigente `1105`/`111`; la cadena C3 → R5 → R6 deja a cero la base y la cuota (`105`/`11`, luego `−52`/`−6` y `−53`/`−5`: **no** `−5` y `−5`, que dejaría una cuota vigente de `1`). Resultado negativo solo por rectificativas.
- **Q-D.** Dos líneas con tipo en un mismo gasto (ED1), gasto con IVA no deducible (ED2), gasto anulado (ED3), línea al 0 % que no entra (ED4), gasto manual sin IVA (ED5) y un gasto del 31/12 (ED6) que cuenta en el T4. El resultado es negativo: «a compensar».
- **Q-E.** Entre el 31/12/2025 (T4, Q-D) y el 01/04/2026 (X1, factura al 21 % sobre `10000` con cuota `2100`, que cuenta en el T2 de 2026) el T1 de 2026 no tiene ningún documento: todas las casillas a cero y «sin actividad».

**Cómo las usan las pruebas del hito 1.** Se pasan **todos los documentos de los cinco casos juntos** (más `X1`) a la función y se pide cada trimestre por separado: así se ejercitan las fronteras (31/03, 01/04, 31/12) y que ningún documento se cuele en otro trimestre. El reloj de las pruebas está después de 2026-04-01 para que ningún trimestre sea futuro. Las rectificativas ya llevan la diferencia calculada (es lo que guarda la base de datos); su cálculo está en la columna «Cuenta de la cuota».

**Formato para las pruebas del hito 1** (los mismos datos, para no reescribirlos; `casillas` usa el número de casilla):

```json
{
 "nota": "simulados, no externos; importes en céntimos; las rectificativas llevan la diferencia (ya calculada) y la fecha de la rectificativa",
 "trimestres": [
  {
   "caso": "Q-A",
   "anio": 2025,
   "trimestre": 1,
   "documentos": [
    {
     "id": "A1",
     "tipo": "factura",
     "fecha": "2025-01-15",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": 250,
     "cuota": 53
    },
    {
     "id": "A2",
     "tipo": "factura",
     "fecha": "2025-02-03",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": 120000,
     "cuota": 25200
    },
    {
     "id": "A3",
     "tipo": "factura",
     "fecha": "2025-02-20",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": 105,
     "cuota": 11
    },
    {
     "id": "A4",
     "tipo": "factura",
     "fecha": "2025-03-10",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": 2345,
     "cuota": 235
    },
    {
     "id": "A5",
     "tipo": "factura",
     "fecha": "2025-03-18",
     "tratamiento": "national_vat",
     "iva": 4,
     "base": 1237,
     "cuota": 49
    },
    {
     "id": "A6",
     "tipo": "factura",
     "fecha": "2025-03-31",
     "tratamiento": "national_vat",
     "iva": 4,
     "base": 1238,
     "cuota": 50
    }
   ],
   "casillas": {
    "01": 2475,
    "03": 99,
    "04": 2450,
    "06": 246,
    "07": 120250,
    "09": 25253,
    "27": 25598,
    "28": 0,
    "29": 0,
    "45": 0,
    "46": 25598,
    "59": 0,
    "120": 0
   },
   "resultado": "a_ingresar"
  },
  {
   "caso": "Q-B",
   "anio": 2025,
   "trimestre": 2,
   "documentos": [
    {
     "id": "B1",
     "tipo": "factura",
     "fecha": "2025-04-01",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": 80000,
     "cuota": 16800
    },
    {
     "id": "B2",
     "tipo": "factura",
     "fecha": "2025-04-22",
     "tratamiento": "eu_reverse_charge",
     "iva": 0,
     "base": 150000,
     "cuota": 0
    },
    {
     "id": "B3",
     "tipo": "factura",
     "fecha": "2025-05-06",
     "tratamiento": "non_eu_not_subject",
     "iva": 0,
     "base": 90000,
     "cuota": 0
    },
    {
     "id": "B4",
     "tipo": "factura",
     "fecha": "2025-05-20",
     "tratamiento": "eu_consumer_vat",
     "iva": 21,
     "base": 5050,
     "cuota": 1061
    },
    {
     "id": "B5",
     "tipo": "factura",
     "fecha": "2025-06-10",
     "tratamiento": "non_eu_consumer_vat",
     "iva": 10,
     "base": 3333,
     "cuota": 333
    },
    {
     "id": "B6",
     "tipo": "factura",
     "fecha": "2025-06-30",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": 100000,
     "cuota": 21000
    },
    {
     "id": "EB1",
     "tipo": "gasto",
     "fecha": "2025-04-15",
     "iva_deducible": true,
     "anulado": false,
     "lineas": [
      {
       "iva": 21,
       "base": 40000,
       "cuota": 8400
      }
     ]
    },
    {
     "id": "EB2",
     "tipo": "gasto",
     "fecha": "2025-05-12",
     "iva_deducible": true,
     "anulado": false,
     "lineas": [
      {
       "iva": 21,
       "base": 10000,
       "cuota": 2100
      },
      {
       "iva": 10,
       "base": 5000,
       "cuota": 500
      }
     ]
    },
    {
     "id": "EB3",
     "tipo": "gasto",
     "fecha": "2025-06-20",
     "iva_deducible": true,
     "anulado": false,
     "lineas": [
      {
       "iva": 4,
       "base": 2500,
       "cuota": 100
      }
     ]
    }
   ],
   "casillas": {
    "01": 0,
    "03": 0,
    "04": 3333,
    "06": 333,
    "07": 185050,
    "09": 38861,
    "27": 39194,
    "28": 57500,
    "29": 11100,
    "45": 11100,
    "46": 28094,
    "59": 150000,
    "120": 90000
   },
   "resultado": "a_ingresar"
  },
  {
   "caso": "Q-C",
   "anio": 2025,
   "trimestre": 3,
   "documentos": [
    {
     "id": "C1",
     "tipo": "factura",
     "fecha": "2025-07-08",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": 120000,
     "cuota": 25200
    },
    {
     "id": "C2",
     "tipo": "factura",
     "fecha": "2025-07-20",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": 2345,
     "cuota": 235
    },
    {
     "id": "C3",
     "tipo": "factura",
     "fecha": "2025-07-25",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": 105,
     "cuota": 11
    },
    {
     "id": "C4",
     "tipo": "factura",
     "fecha": "2025-09-30",
     "tratamiento": "national_vat",
     "iva": 4,
     "base": 50000,
     "cuota": 2000
    },
    {
     "id": "R1",
     "tipo": "rectificativa",
     "fecha": "2025-07-15",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": -20000,
     "cuota": -4200
    },
    {
     "id": "R2",
     "tipo": "rectificativa",
     "fecha": "2025-08-02",
     "tratamiento": "eu_reverse_charge",
     "iva": 0,
     "base": -50000,
     "cuota": 0
    },
    {
     "id": "R3",
     "tipo": "rectificativa",
     "fecha": "2025-08-20",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": -120000,
     "cuota": -25200
    },
    {
     "id": "R5",
     "tipo": "rectificativa",
     "fecha": "2025-08-25",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": -52,
     "cuota": -6
    },
    {
     "id": "R4",
     "tipo": "rectificativa",
     "fecha": "2025-09-10",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": -1240,
     "cuota": -124
    },
    {
     "id": "R6",
     "tipo": "rectificativa",
     "fecha": "2025-09-25",
     "tratamiento": "national_vat",
     "iva": 10,
     "base": -53,
     "cuota": -5
    }
   ],
   "casillas": {
    "01": 50000,
    "03": 2000,
    "04": 1105,
    "06": 111,
    "07": -20000,
    "09": -4200,
    "27": -2089,
    "28": 0,
    "29": 0,
    "45": 0,
    "46": -2089,
    "59": -50000,
    "120": 0
   },
   "resultado": "a_compensar"
  },
  {
   "caso": "Q-D",
   "anio": 2025,
   "trimestre": 4,
   "documentos": [
    {
     "id": "D1",
     "tipo": "factura",
     "fecha": "2025-10-05",
     "tratamiento": "national_vat",
     "iva": 21,
     "base": 30000,
     "cuota": 6300
    },
    {
     "id": "ED1",
     "tipo": "gasto",
     "fecha": "2025-10-10",
     "iva_deducible": true,
     "anulado": false,
     "lineas": [
      {
       "iva": 21,
       "base": 200000,
       "cuota": 42000
      },
      {
       "iva": 10,
       "base": 50000,
       "cuota": 5000
      }
     ]
    },
    {
     "id": "ED2",
     "tipo": "gasto",
     "fecha": "2025-11-04",
     "iva_deducible": false,
     "anulado": false,
     "lineas": [
      {
       "iva": 21,
       "base": 10000,
       "cuota": 2100
      }
     ]
    },
    {
     "id": "ED3",
     "tipo": "gasto",
     "fecha": "2025-11-18",
     "iva_deducible": true,
     "anulado": true,
     "lineas": [
      {
       "iva": 21,
       "base": 7000,
       "cuota": 1470
      }
     ]
    },
    {
     "id": "ED4",
     "tipo": "gasto",
     "fecha": "2025-12-02",
     "iva_deducible": true,
     "anulado": false,
     "lineas": [
      {
       "iva": 0,
       "base": 8000,
       "cuota": 0
      },
      {
       "iva": 21,
       "base": 1000,
       "cuota": 210
      }
     ]
    },
    {
     "id": "ED5",
     "tipo": "gasto",
     "fecha": "2025-12-31",
     "iva_deducible": false,
     "anulado": false,
     "lineas": []
    },
    {
     "id": "ED6",
     "tipo": "gasto",
     "fecha": "2025-12-31",
     "iva_deducible": true,
     "anulado": false,
     "lineas": [
      {
       "iva": 10,
       "base": 2000,
       "cuota": 200
      }
     ]
    }
   ],
   "casillas": {
    "01": 0,
    "03": 0,
    "04": 0,
    "06": 0,
    "07": 30000,
    "09": 6300,
    "27": 6300,
    "28": 253000,
    "29": 47410,
    "45": 47410,
    "46": -41110,
    "59": 0,
    "120": 0
   },
   "resultado": "a_compensar"
  },
  {
   "caso": "Q-E",
   "anio": 2026,
   "trimestre": 1,
   "documentos": [],
   "casillas": {
    "01": 0,
    "03": 0,
    "04": 0,
    "06": 0,
    "07": 0,
    "09": 0,
    "27": 0,
    "28": 0,
    "29": 0,
    "45": 0,
    "46": 0,
    "59": 0,
    "120": 0
   },
   "resultado": "sin_actividad"
  }
 ],
 "fuera_de_los_cinco": [
  {
   "id": "X1",
   "tipo": "factura",
   "fecha": "2026-04-01",
   "tratamiento": "national_vat",
   "iva": 21,
   "base": 10000,
   "cuota": 2100
  }
 ]
}
```

### B.2 Hito 1 · dominio puro del modelo 303 · 2026-11-11

**Qué hay.** Tres módulos puros nuevos en `backend/src/cuadre/tax/` (declarados en `PURE_TAX` de `test_invoicing_boundary.py`, que vigila que no importen base de datos, red, FastAPI, Pydantic ni reloj): `periods.py`, `types_303.py` y `modelo_303.py`; constantes y textos en `limits.py`; todo exportado desde `cuadre.tax`. No hay base de datos, API ni pantalla todavía.

| Pieza | Contenido |
|---|---|
| `periods.py` | `quarter_of`, `quarter_bounds` (fin exclusivo), `filing_deadline`, `deadline_status`, `validate_period` y las excepciones `InvalidPeriod` (`invalid_period`) y `PeriodInFuture` (`period_in_future`). Recibe fechas, nunca lee un reloj |
| `types_303.py` | Dataclasses `frozen, slots`: entrada (`InvoiceRow`, `ExpenseRow`, `ExpenseLine`) y salida (`Item`, `Box`, `Modelo303`). Pydantic queda para los modelos de la API del hito 3 |
| `modelo_303.py` | `build_modelo_303(year, quarter, invoices, expenses, today)`; `UnsupportedVatRate` (`unsupported_vat_rate`) y `QuarterTooLarge` (`quarter_too_large`) |
| `limits.py` | `FILING_DEADLINES`, `QUARTER_MAX_DOCUMENTS = 5_000`, `PERIOD_MIN_YEAR/MAX_YEAR`, `VAT_TREATMENTS` y los cuatro textos de aviso |

**Decisiones tomadas al implementar** (completan o corrigen §5.1 y D-06, ya actualizadas):

| Tema | Decisión |
|---|---|
| **Resultado cero** | La spec solo preveía tres formas. Con documentos y 27 = 45 (o una factura anulada del todo en el mismo trimestre) el resultado es 0,00 € y **no** es «sin actividad»: se añade `a_cero`. `sin_actividad` queda para «ningún documento en el trimestre»; los gastos anulados no cuentan como documento, los no deducibles sí |
| **Plazo** | Es la fecha del calendario (20 de abril, julio y octubre; 30 de enero). No se traslada a día hábil: el aviso «lo que no incluye» lo dice |
| **Trece casillas siempre** | La función devuelve todas, también a cero; ocultar las nulas (01/03 y 04/06 sin operaciones) es cosa de la pantalla. Cada casilla lleva `measure` (`base` o `vat`) para que se pueda comprobar «la suma de los items es la casilla» sin conocer el mapa |
| **Sin redondeos** | El dominio solo suma céntimos enteros (D-05); no usa `Decimal` salvo para comparar tipos. Las cuotas de cada documento ya vienen redondeadas |
| **Filtro interno por trimestre** | Se le pueden pasar todos los documentos de la persona: filtra por fecha de expedición o de gasto. El repositorio del hito 2 igualmente acotará la consulta |
| **Datos incoherentes** | Una operación `eu_reverse_charge` o `non_eu_not_subject` con tipo o cuota distintos de cero falla con `UnsupportedVatRate` en vez de sumarse en silencio; un tratamiento desconocido es un `ValueError` (error de programación). Los mensajes no llevan ningún dato del documento |
| **Orden de los items** | Por fecha, etiqueta e id: determinista aunque cambie el orden de entrada |
| **Años** | 2000-9998 (el cuarto trimestre del 9998 acaba en el 9999, el último año de `date`). Un booleano no es un trimestre válido (`True` valdría 1); para el año ya lo rechaza el rango |
| **Tipos de línea de gasto** | En 28/29 cuenta toda línea con tipo > 0, sea cual sea (5 %, 7,5 %…), y no la de tipo 0 aunque trajera cuota (D-04, P-02) |

**Pruebas.** **113 nuevas** (`pytest backend/tests/tax -k modelo_303`) y **3.768 en total** sin RLS (3.655 + 113):

| Archivo | Cubre |
|---|---|
| `test_modelo_303_periods.py` (44) | AC-09, AC-10, AC-11: cada día del año en su trimestre, fronteras 31/03-01/04, 30/06-01/07, 30/09-01/10 y 31/12-01/01, plazos de los cuatro trimestres (el T4 en enero del año siguiente), estado del plazo en los días de borde, periodo inválido y futuro |
| `test_modelo_303.py` (47) | AC-01 a AC-08, AC-11, AC-12, AC-16, AC-21: clasificación por tratamiento y tipo, particulares, rectificativas con signo, gastos (deducible, no deducible, anulado, dos líneas, línea al 0 %), los cuatro resultados, fronteras, orden, determinismo, tipos y tratamientos que no existen, límite de 5.000, avisos |
| `test_modelo_303_cases.py` (16) | AC-13, AC-08: **lee el bloque JSON de B.1** de esta spec y reproduce los cinco trimestres simulados al céntimo (las 13 casillas, el resultado y los documentos de cada casilla), con todos los documentos juntos |
| `test_modelo_303_properties.py` (6) | NFR-08 con 300 conjuntos de documentos al azar y semilla fija: suma de items = casilla, derivadas, invariancia al orden, aditividad al partir los documentos, documentos de otros trimestres sin efecto |

**Mutaciones.** **75 mutaciones** de `periods.py`, `modelo_303.py` y `limits.py` con un ejecutor desechable fuera del repositorio: **73 detectadas y 2 equivalentes por diseño** (M22 y M24: cambiar el orden del par «casilla de base, casilla de cuota» de un tipo no cambia nada, porque cada factura se anota en las dos casillas y cada casilla suma su propio importe). La primera tanda destapó tres cosas: un `isinstance(year, bool)` **redundante** (el rango del año ya rechaza `True`; se quitó), y dos huecos de prueba reales (una línea al 0 % que trajera cuota, y dos documentos con la misma fecha y etiqueta, que ahora se ordenan por id). Lección del ejecutor: una mutación de igual longitud (`5_000` por `4_999`) puede reutilizar un `.pyc` viejo; el ejecutor borra `__pycache__` antes de cada mutante.

**Lo que no se ha comprobado:**
- **Contra la AEAT o una gestoría**: los cinco trimestres son simulados (B.1); solo prueban que el código reproduce ese cálculo manual con las mismas reglas.
- **Datos reales de la base**: los tipos de entrada son los que el hito 2 tiene que rellenar; aquí no hay ninguna lectura.
- **Rendimiento con 5.000 documentos**: se prueba el límite, no el tiempo.

**Para el hito 2** (lectura de datos):
- Rellenar `InvoiceRow` desde `public.invoices` (`id`, el número `{serie}-{NNN}` como `label`, `issue_date`, `tax_treatment`, `vat_rate`, `base_cents`, `vat_cents`; las rectificativas ya traen la diferencia con signo y el tipo de la original) y `ExpenseRow` desde `public.expenses` (`id`, `supplier_name` como `label`, `expense_date`, `deductible_vat`, `voided_at is not null` como `voided` y las líneas de `tax_breakdown`, cuyo `vat_rate` es un `str`: convertir a `Decimal`).
- Acotar la consulta al rango `[inicio, fin)` del trimestre (`quarter_bounds`) y, si hace falta, un índice; pasar el «hoy» de `today_in_madrid`.
- La fecha de un gasto de documento es la de la factura; la de uno manual, la que anotó la persona.

### B.3 Hito 2 · lectura de los documentos de un trimestre · 2026-11-11

**Qué hay.** El paquete `backend/src/cuadre/quarters/` con `repository.py`: `invoice_rows(conn, start, end)` y `expense_rows(conn, start, end)`, que devuelven las filas de entrada del dominio (`InvoiceRow`, `ExpenseRow`). Sin migración, sin cambios en `rls_matrix.yaml`, en `openapi.json` ni en el frontend.

| Tema | Decisión |
|---|---|
| **Dónde vive** | Un paquete aparte y no `cuadre.tax`: la etiqueta de una factura es su número (`display_number`, de `cuadre.invoicing`) y `cuadre.tax` no puede depender de `cuadre.invoicing`. `cuadre.quarters` depende de los dos y ninguno de ellos de él (lo vigila `test_invoicing_boundary.py`). Lo compartirá el 130 de SPEC-W-009 |
| **Rango, no trimestre** | Las funciones reciben `[start, end)`; quien llama pasa `quarter_bounds`. El 130 usará un rango desde enero sin tocar nada |
| **Quién lee** | Siempre `owner_id = (SELECT auth.uid())` además de la RLS, como el resto de lecturas: un gestor con vínculo activo **no** ve nada por esta vía (su pantalla es SPEC-W-010) |
| **Límite en SQL** | Cada consulta corta en `QUARTER_MAX_DOCUMENTS + 1` (5.001) filas: la memoria queda acotada y el dominio sigue decidiendo `QuarterTooLarge` con la suma de las dos listas |
| **Gastos anulados** | No se leen (`voided_at IS NULL`); `voided` llega siempre `False` |
| **Etiquetas** | Factura: `{serie}-{NNN}` (`2025-001`, `R-2025-001`); gasto: el nombre del proveedor tal como lo registró la persona |
| **Líneas de gasto** | `tax_breakdown` trae el tipo como **texto**; se lee con `parse_rate`. Un tipo ilegible es un dato corrupto: `UnsupportedVatRate` sin repetir lo que había. Un gasto manual llega con `lines == ()` y no deducible |
| **Orden de lectura** | `ORDER BY fecha, id`; dos documentos del mismo día salen en el orden de su `id` (aleatorio). El orden que ve la persona lo da el dominio (fecha, etiqueta, id), no la consulta |

**Pruebas.** **25 nuevas** (24 en `backend/tests/quarters/` y 1 de reglas) y **3.793 sin RLS** en total; las **1.561 de RLS** siguen igual. Las de `tests/quarters` usan la base real y no llevan el marcador `rls`:
- **De la base de datos a la casilla.** Los 33 documentos de B.1 (18 facturas, 6 rectificativas y 9 gastos) se siembran **una vez por módulo** con las funciones reales de la base (`app.issue_invoice`, `app.issue_rectifying_invoice`) y la inserción directa de gastos; se lee con el repositorio, se pasa a `build_modelo_303` y las 13 casillas, el resultado y los documentos de cada casilla de los cinco trimestres coinciden con B.1. **Además contrastan a B.1 con la base**: las diferencias y las cuotas de las seis rectificativas que calcula `cuadre.tax` dentro de la función son exactamente las calculadas a mano; no hizo falta corregir ninguna cifra de B.1.
- Fronteras de la consulta (inclusivo/exclusivo, rango vacío o invertido), etiquetas, gasto manual y anulados, aislamiento (otro autónomo, gestor con vínculo activo, segundo gestor y administrador no leen nada), dato corrupto, límites, solo lectura (recuento de `invoices`, `expenses` y `activity_log` antes y después) y un `EXPLAIN` con `enable_seqscan = off` que comprueba que las dos consultas pueden usar `invoices_owner_date` y `expenses_by_owner_date`.

**Mutaciones.** **23 mutaciones** del repositorio con un ejecutor desechable fuera del repositorio (borra `__pycache__` antes de cada una): **22 detectadas y 1 equivalente** (Q22: una línea de `tax_breakdown` que no sea un objeto; la tabla lo impide con un CHECK, así que no puede llegar). La primera tanda dejó viva Q04 (el último día del rango entraba en los gastos): ningún gasto de B.1 caía en el día del límite; se añadió la comprobación del 31/12 como final exclusivo.

**Lo que no se ha comprobado:**
- **Rendimiento con miles de filas**: se comprueba que los índices pueden usarse, no el tiempo con 5.000 documentos.
- **Concurrencia**: una lectura no toma cerrojos y se hace en una sola transacción; no se probó con emisiones simultáneas.
- **Una factura de otro año en la misma serie** o fechas fuera de orden: las fechas de B.1 respetan el orden de las series, que es lo que exige la base.

**Para el hito 3** (API):
- `service.py` abre `user_transaction` con el id de la persona, calcula `quarter_bounds`, lee con `invoice_rows` y `expense_rows` y llama a `build_modelo_303` con `today_in_madrid(clock)`.
- Traducir las excepciones del dominio: `InvalidPeriod` y `PeriodInFuture` (422 con su `code`), `QuarterTooLarge` (422) y `UnsupportedVatRate` (un dato corrupto: 422 con `unsupported_vat_rate`, sin datos del documento, y aviso en el registro con ids y sin importes).
- `models.py` (Pydantic): `Modelo303`, `Box` (con `measure`), `Item`, `deadline_status`, `result_kind` (con `a_cero`) y `notes`; `operation_id: get_modelo_303`, solo rol `usuario`, `Cache-Control: private, no-store`.
- Las dos consultas cortan a 5.001 por separado: una persona con 5.001 facturas y 0 gastos recibe `quarter_too_large` igualmente.

### B.4 Hito 3 · la API del borrador del 303 · 2026-11-11

**Qué hay.** `GET /api/tax/303?year=&quarter=` (`operation_id: get_modelo_303`, solo el rol `usuario`) en `backend/src/cuadre/api/routes_tax.py`, registrada en `main.py`. En `cuadre/quarters/`: `service.py` (`QuarterService`), `models.py` (`Modelo303`, `Box303` e `Item303` con `present`, que pasa el dominio a Pydantic) y `errors.py`. Regenerados, sin tocar a mano: `backend/openapi.json` y `frontend/src/api/schema.d.ts` (solo líneas añadidas). Ninguna pantalla usa aún el cliente.

| Tema | Decisión |
|---|---|
| **Periodo opcional** | Sin `year` o sin `quarter` se usa el de hoy en Europe/Madrid, cada uno por su cuenta (`year=2025` sin trimestre da el trimestre en el que estamos, del 2025). A las 23:30 UTC del 31 de marzo ya es 1 de abril |
| **Sin `ge`/`le` en la ruta** | `quarter=5` o un año fuera de 2000-9998 llegan al dominio y dan `invalid_period` (AC-11); un valor que no es entero (`abc`, `1.5`, vacío) es el `validation_error` de siempre |
| **Validar antes de leer** | `validate_period` va antes de abrir la transacción: un periodo inválido o futuro no toca la base (probado haciendo fallar `user_transaction`) |
| **Errores** | Los cuatro son 422 con `code` estable: `invalid_period`, `period_in_future`, `quarter_too_large` y `unsupported_vat_rate`. Ninguno repite lo enviado (el año, por ejemplo) ni datos de documentos |
| **Dato corrupto** | `unsupported_vat_rate` deja además un `WARNING` (`modelo_303_unsupported_vat_rate`) con el año y el trimestre y nada más: ni proveedor, ni importe, ni el texto del tipo |
| **Contrato** | `Cache-Control: private, no-store`; enumerados como `Literal` (`group`, `deadline_status`, `result_kind` con `a_cero`, `measure`); `id` de cada documento como UUID; fechas ISO |
| **Peor caso** | Un trimestre de 5.000 facturas (el máximo) mide **1,4 MB** de JSON, lejos de los 4,5 MB de una Vercel Function (T8-08); un test lo comprueba en memoria |

**Pruebas.** **35 nuevas** en `backend/tests/quarters/test_modelo_303_api.py` y **3.828 sin RLS** en total; las **1.561 de RLS** siguen igual. Con la aplicación real y la base real, sobre los cinco trimestres sembrados de B.1:
- Los cinco trimestres por HTTP: las 13 casillas, el resultado, los documentos de cada casilla (por id) y «suma de documentos = casilla» sobre el JSON (NFR-08).
- Forma de la respuesta y cabeceras, grupos y medidas de cada casilla, un gasto completo y un número de factura.
- Plazo y estado en los días de borde con relojes inyectados; periodo por defecto y cada parámetro por su cuenta.
- Periodo inválido (siete combinaciones, incluidas cifras enormes), valores que no son enteros, trimestre futuro, trimestre grande y tipo de IVA corrupto.
- Gestores (también con vínculo activo) y administrador → 403; sin sesión → 401; otro autónomo no ve nada.
- Una lectura no escribe (recuento de `invoices`, `expenses` y `activity_log`) y los registros no contienen ni un número de factura, ni un proveedor, ni un importe.
- Avisos (AC-21) y presencia de la operación en el contrato.

**Mutaciones.** **37 mutaciones** de `service.py`, `models.py`, `errors.py` y `routes_tax.py` con un ejecutor desechable fuera del repositorio: **36 detectadas y 1 equivalente** (S13: poner `str(exc)` en el aviso del registro; el mensaje de la excepción es un texto fijo sin datos). La primera tanda dejó vivas tres cosas de la forma de la respuesta que ninguna prueba miraba (los grupos de casilla, el tipo de documento y la fecha de cada item); ahora hay un caso que las fija.

**Lo que no se ha comprobado:**
- **Con el cliente generado desde una pantalla**: el hito 4 lo estrena; aquí solo se comprueba que `typecheck`, `lint` y las 232 unitarias siguen en verde con el esquema nuevo.
- **Carga y concurrencia**: ni muchas peticiones a la vez ni una base grande.
- **El reloj real**: todas las pruebas de la ruta fijan el reloj; el camino con `SystemClock` (el de producción) no se ejercita en ninguna.
- **Los cinco trimestres siguen siendo simulados, no externos.**

**Para el hito 4** (pantalla):
- `lib/tax-api.ts` (lectura de servidor con el JWT de la sesión, como `invoices-api.ts`); `/trimestres` con el selector de trimestre en la dirección (`?año=&trimestre=` o los nombres que se elijan), sin cálculos en el navegador.
- Mostrar solo las casillas con importe o con documentos en los grupos de 01-03 y 04-06 (las 13 vienen siempre); 27, 45 y 46 muestran sus componentes; `result_kind` con texto además de color (`a_ingresar`, `a_compensar`, `a_cero`, `sin_actividad`); el plazo y su estado; los cuatro avisos de `notes`.
- Enlaces: un `Item303` de tipo `invoice` lleva a `/facturas/{id}`; uno de tipo `expense`, a `/gastos` (no hay detalle de gasto por ruta).
- Errores 422: `period_in_future` (el selector no debería ofrecerlo), `quarter_too_large` y `unsupported_vat_rate` con su texto en español; 403 → `/403`.
- Activar «Trimestres» en el menú del autónomo (hoy `FUTURE("Trimestres")` en `roles.ts`) y dejar la pestaña del 130 desactivada con «Próximamente» (P-05).

### B.5 Hito 4 · la pantalla de trimestres · 2026-11-11

**Qué hay.** La pantalla `/trimestres` del autónomo, con el borrador del 303 que devuelve `GET /api/tax/303`. «Trimestres» pasa a ser un enlace del menú (`lib/roles.ts`: ruta del autónomo; el gestor y el administrador van a `/403`) y deja de anunciarse como futuro en la portada. Sin cambios de backend ni de base de datos.

| Pieza | Contenido |
|---|---|
| `lib/tax.ts` | Puro: `parseQuarterQuery`, `quarterOfDate`, `quarterEnabled`, `quarterTitle`, `quarterMonths`, `quarterHref`, `deadlineBanner`, `resultText`, `visibleBoxes`, `groupBoxes`, `itemSummary`, `itemHref`, `itemAmount` y `componentsText`. Solo orden y texto: ninguna cuenta fiscal |
| `lib/tax-api.ts` | Lectura de servidor con el JWT de la sesión: `ok`, o `problem` con el texto en español del 422 (trimestre futuro, demasiado grande, tipo ilegible); 401 y 403 redirigen y lo demás es «servicio no disponible». `lib/problems.ts` **no cambió**: ya enseña el `detail` de un 4xx corto |
| `components/tax/` | `quarter-picker`, `modelo-303` (la hoja del prototipo), `box-row`, `deadline-status` y `notes`. Todo Server Component y HTML nativo: **ninguna línea de JavaScript de cliente** |
| `app/(app)/trimestres/page.tsx` | `requireRole("usuario")`, el trimestre de la dirección y las cuatro piezas |

**Decisiones tomadas al implementar:**

| Tema | Decisión |
|---|---|
| **Dirección** | `?year=&quarter=`, los nombres de la API. Lo ausente o ilegible (`abc`, `0`, `5`, `1999`, `02025`, `+2025`…) vale el año y el trimestre de hoy en Madrid, cada uno por su cuenta: una dirección rara enseña el trimestre en curso, nunca una página de error. Un trimestre futuro sí se pasa y lo rechaza el servidor |
| **Selector** | Un `<form method="get">` con el año (y el trimestre en un campo oculto) y los cuatro trimestres como enlaces con `aria-current="page"`; los que aún no han empezado salen desactivados con su texto. Debajo, la pestaña del modelo: 303 activo y 130 desactivado |
| **Pestaña del 130** | «Próximamente», como el menú. P-05 proponía «Disponible con SPEC-W-009»: un identificador interno no le dice nada a quien usa la aplicación (corregido en P-05) |
| **Casillas visibles** | 01, 03, 04 y 06 solo si tienen documentos; el resto de la hoja sale siempre, aunque valga cero (como el prototipo). Se oculta por falta de documentos, no por valer cero: una casilla con documentos que suman cero sigue viéndose |
| **Documentos** | Cada casilla con documentos lleva un `<details>` nativo («Ver la factura», «Ver las 4 facturas», «Ver el gasto»…) con su número o proveedor, fecha e importe (la base o la cuota, según lo que suma la casilla). Una factura enlaza a `/facturas/{id}`; un gasto no tiene detalle por ruta y el desplegable acaba con un único «Ir a Gastos» |
| **Resultado** | Con palabras: «546,00 € a ingresar», «411,10 € a compensar en próximos trimestres» (sin signo, el texto ya lo dice), «0,00 €: nada que ingresar ni compensar» y «Sin actividad en este trimestre» |
| **Plazo** | Insignia con texto (el color solo refuerza) y la fecha larga que manda el servidor: «Trimestre en curso», «Plazo abierto», «Plazo cerrado» |
| **Error 422** | Un aviso con el texto de la API y un «Ir al trimestre actual»; no se tira la página |
| **Avisos** | Los de `notes`, siempre visibles debajo de la hoja (orientativo, lo que no incluye, Canarias/Ceuta/Melilla y, con la 59, el 349) |

**Pruebas.** **16 unitarias nuevas** (de 232 a **248**): `tax.test.ts` (dirección y sus rarezas, trimestres y días de borde, plazo, resultado, casillas visibles y agrupadas, resumen y enlaces de documentos, componentes de las derivadas) y los cambios de `roles.test.ts` (menú, `/trimestres` del autónomo y su límite de segmento). Backend sin cambios: **3.828 sin RLS** y 1.561 de RLS. `gen:api --check`, `lint`, `typecheck`, `build` y `check:bundle` en verde. **E2E existentes** de `roles.spec.ts` y `responsive.spec.ts` en Chromium a 390 y 1.440 px: **67 correctas** (hizo falta que `e2e/helpers/env.ts` contara «Trimestres» entre los enlaces de Alicia).

**Mutaciones.** **46 mutaciones** de `tax.ts` y `roles.ts` con un ejecutor desechable fuera del repositorio: **46 detectadas, ninguna equivalente**. La primera tanda dejó vivas tres cosas: dos huecos de prueba (un año de cinco cifras como `02025`, y el año por defecto, que ninguna prueba hacía depender de «hoy») y una **redundancia del código** (`count === 0` en `itemSummary`, que `kind === undefined` ya cubre; se quitó).

**Comprobación visual** con la API y la base reales, datos sintéticos y un guion desechable de Playwright en **Chromium, Firefox y WebKit**, a **390 y 1.440 px** (Alicia, con gastos deducibles sembrados para el T3 y el T4 de 2026): **48 comprobaciones por motor**, todas correctas. Menú y portada; selector (el actual, los futuros desactivados, el año conservando el trimestre); el 303 activo y el 130 «Próximamente»; casillas visibles (07, 09, 27, 28, 29, 45, 46, 59 y 120 en el T4); los cuatro avisos; los desplegables (cuatro facturas en la 07, un gasto con «Ir a Gastos» en la 28) y que se abren con el teclado; una factura lleva a su detalle; el T3 «a compensar» con plazo cerrado y sin aviso del 349; el T2 sin actividad; un trimestre futuro y una dirección ilegible; sin scroll horizontal, campos etiquetados y consola sin errores; y el gestor y el administrador a `/403`. Sin defectos de producto. Dos fallos del guion, no del producto: el selector tiene un formulario llamado «Año del trimestre» y un campo «Año» (hay que pedir la etiqueta exacta) y la pantalla usa renderizado parcial, de modo que el contenido llega por streaming y **hay que esperar a un elemento concreto antes de leer** (lo mismo valdrá para el E2E).

**Lo que no se ha comprobado:**
- **Los E2E propios** (`trimestres.spec.ts`) y las mutaciones de la interfaz entera: son del hito 5.
- **Firefox y WebKit con los E2E existentes**: solo Chromium (el equipo tenía unos 2,4 GB libres); los tres motores se vieron con el guion visual.
- **Muchos documentos**: los desplegables van cerrados, pero un trimestre con miles de documentos mete todas las filas en el HTML; no se midió.
- **Lectores de pantalla reales** (NVDA, VoiceOver): hay encabezados, etiquetas, `aria-current` y `aria-disabled`, pero no se probaron.
- **El enlace de un gasto**: lleva a la lista de Gastos, no a su ficha (no existe esa ruta).
- **Los cinco trimestres siguen siendo simulados, no externos.**

**Para el hito 5** (E2E y cierre):
- `trimestres.spec.ts` en tres motores y dos anchos con **esperas por un elemento concreto** (la página llega por streaming). Datos: las facturas por `InvoicesApi` (ya existe) y, para los gastos deducibles, el flujo real de Gastos con el servidor de agentes de E2E (como `gastos-registro.spec.ts`); las facturas y los gastos de una cuenta no se pueden borrar, así que se usa la cuenta nueva de cada worker y se localiza lo propio por su concepto o proveedor únicos.
- Ajustes de `responsive.spec.ts` (`/trimestres`) y `roles.spec.ts` (gestor y administrador a `/403` también en `/trimestres`).
- Mutaciones de los componentes de `components/tax/*` y de la página; verificación completa y el cierre (Anexo B.6, `tasks.json`, `en-revision`; `hecha` cuando se confirme el CI).

### B.6 Hito 5 · E2E y cierre · 2026-11-11

**Qué hay.** `e2e/trimestres.spec.ts` (11 pruebas por proyecto, seis proyectos), `e2e/helpers/tax.ts` (`TaxApi.modelo303(year?, quarter?)`: lee el borrador por la API con el token de GoTrue de la cuenta, como `InvoicesApi`; nunca la service key; ni el token ni la clave pública se escriben en ningún sitio) y el fixture `tax` en `helpers/fixtures.ts`. Ajustes de `roles.spec.ts` (el autónomo ve «Trimestres» activo; gestor y administrador no lo ven y `/trimestres` los lleva a `/403`) y de `responsive.spec.ts` (`/trimestres` como Alicia). Sin cambios de producto.

**Decisiones.**
- La cuenta de `usuario` del worker la comparten `factura.spec.ts` (emite facturas que no se pueden borrar, RES-03) y las pruebas de Gastos: **ninguna prueba espera cifras absolutas** del trimestre en curso. Cada una lee lo que dice el servidor (`tax.modelo303()`, el oráculo), comprueba que la pantalla enseña lo mismo y, cuando emite, que la **diferencia** es la esperada y que **sus documentos** salen en su casilla (localizados por número de factura).
- Las facturas que se emiten por la API llevan la fecha de hoy (la serie no admite fechas hacia atrás): caen en el trimestre en curso. El único gasto deducible que se puede registrar es el de ejemplo del servidor de agentes de E2E (`fixture:invoice_ok`, del 28/10/2026): cae en el T4 de 2026, así que esa prueba pide `?year=2026&quarter=4` y se **omite** si hoy es anterior al 1/10/2026.
- La página llega por streaming (renderizado parcial): toda lectura espera a un elemento concreto y los localizadores piden lo visible.

**Pruebas por proyecto:** la hoja (menú, selector, 303 activo y 130 «Próximamente», plazo con su fecha, avisos); lo que enseña la pantalla frente al servidor (cada casilla, sus documentos y el resultado); una factura de cada ámbito (07/09, 04/06, 59 y 120 con sus diferencias exactas, el enlace a cada factura y el aviso del 349); una rectificativa (−200,00 € y −42,00 €, con su número y su fecha); un gasto deducible y anulado (28 y 29, «Ir a Gastos»); un trimestre sin actividad; el selector (trimestre, año conservando el trimestre, recarga); un trimestre futuro y direcciones raras; interfaz (sin scroll horizontal, etiquetas, teclado, foco y consola); sin red; y cada persona, lo suyo.

**Hallazgos.** **Ningún defecto de producto.** Cuatro fallos del guion, no de la pantalla: (1) el nombre accesible de un enlace de trimestre es «T4 , octubre a diciembre» (el texto solo para lectores de pantalla se maqueta como bloque y Chromium añade un espacio); las pruebas piden `^T4\b`. (2) El formulario del año manda `quarter` (campo oculto) antes que `year`: la dirección es `?quarter=1&year=2025`; el orden no importa y la prueba lo lee con `searchParams`. (3) WebKit no recorre los enlaces con Tab por defecto, como Safari: allí solo se exige llegar al desplegable, y en todos los motores se comprueba que un trimestre se activa con foco y Enter. (4) Mi comprobación del foco de «Ver» se hacía después de pulsar Tab.

**Resultados** (con `--workers=1`, un motor por invocación, tras `supabase db reset`):

| Qué | Resultado |
|---|---|
| `trimestres.spec.ts` por motor | 25 correctas en Chromium, Firefox y WebKit (la de interfaz de WebKit, tras el ajuste 3) |
| Batería completa, Chromium (390 y 1.440 px) | **273 correctas** |
| Batería completa, Firefox | **265 correctas**, 6 omitidas |
| Batería completa, WebKit | **265 correctas**, 6 omitidas |
| Backend sin RLS | 3.828 correctas |
| RLS (con la base recién reiniciada) | 1.561 correctas |
| `ruff`, `export_openapi --check`, `gen:api --check`, `lint`, `typecheck`, `build` y `check:bundle` | código 0 |
| Pruebas unitarias del frontend | 248 correctas |

La batería completa incluye W-001, 002, 003, 005, 006, 007 y 008. Las omitidas son pruebas que no corren fuera de Chromium. **Dos intentos de la batería se cortaron por memoria** (el sistema paró la cadena: la primera vez, el servidor web de Playwright murió con el código `3221225794` antes de ejecutar ninguna prueba; la segunda, ya con Chromium y Firefox terminados, el trabajador de WebKit murió con el mismo código a media tanda y arrastró al resto con fallos de tiempo y de trabajador caído); ninguno de los dos se cuenta. Chromium y Firefox son de la segunda tanda, que los completó; WebKit se repitió **solo**, con el equipo recién despejado (más de 3 GB libres), y terminó limpio.

**Mutaciones de la interfaz.** **26 mutaciones** de `quarter-picker`, `deadline-status`, `box-row`, `modelo-303`, `notes` y la página, con un ejecutor desechable fuera del repositorio (`next build` y `trimestres.spec.ts` en Chromium a 390 y 1.440 px por mutante, restauración por huella, tandas de 6): **26 detectadas, ninguna equivalente**. La primera tanda dejó vivas dos cosas que ninguna prueba miraba, y se cubrieron: la frase del plazo con su fecha larga y la fecha de cada documento. No se mutó `requireRole` de la página: el proxy y la API rechazan antes al gestor y al administrador, así que un E2E no puede distinguirlo (defensa en profundidad).

**Lo que no se ha comprobado:**
- **El CI de GitHub**: la verificación es local; la spec queda en `en-revision` hasta que la persona lo confirme.
- **Validación externa (DEP-01)**: los cinco trimestres de B.1 son **simulados, no externos**; solo prueban que el código reproduce un cálculo manual con las mismas reglas (D-02 a D-06). Sigue siendo una mejora pendiente.
- **Los seis proyectos en paralelo**: se ejecutó con un worker y un motor por vez, no con la configuración del CI.
- **El reloj real del servidor** (`SystemClock`): las pruebas de la ruta fijan el reloj; el E2E usa el de verdad solo de forma indirecta.
- **Lectores de pantalla reales** y **trimestres con miles de documentos**.
- **Un trimestre «a compensar» en el E2E**: la cuenta del worker acumula facturas y no se puede garantizar; lo cubren las pruebas del dominio, de la API y la comprobación visual del hito 4.

**Estado de la spec.** Todos los hitos hechos y la verificación local en verde: `en-revision`. Pasará a `hecha` cuando la persona confirme el CI (como W-005, W-006 y W-007) y deje escrito si da por buena la validación simulada o exige la externa de DEP-01.
