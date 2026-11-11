---
tipo: spec
id: SPEC-W-008
titulo: Modelo 303 casilla a casilla: borrador orientativo del IVA trimestral con cada casilla enlazada a sus facturas y gastos
estado: propuesta
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
| D-06 | **Resultado 46 = 27 − 45** en céntimos con signo: positivo = «a ingresar»; negativo = «a compensar» en próximos trimestres (sin compensar nada, D-01); cero con todas las casillas a cero = «sin actividad» | Calcular el resultado final con compensaciones: fuera de alcance |
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
| P-05 | ¿«Trimestres» muestra desde ya la pestaña del 130 desactivada («Próximamente»)? | **Sí**, desactivada y con el texto «Disponible con SPEC-W-009» |

## 2. Objetivo

Que la persona abra **«Trimestres»**, elija un trimestre y vea su **borrador del modelo 303** con las casillas del régimen general, el resultado («a ingresar», «a compensar» o «sin actividad»), el plazo de presentación y, **bajo cada casilla, las facturas y los gastos que la componen**, todo calculado por el servidor con reglas deterministas, en céntimos exactos, marcado como **orientativo** y sin enviar nada a la AEAT.

## 3. Alcance explícito

### 3.1 Dominio puro (`cuadre.tax.modelo_303`)
Función pura `build_modelo_303(year, quarter, invoices, expenses, today)` que recibe documentos ya leídos (tipos inmutables, sin base de datos ni reloj), clasifica cada factura por `tax_treatment` y tipo y cada gasto por línea con cuota, suma en céntimos enteros y devuelve las casillas con sus `items`, el resultado, el plazo y el estado. Errores explícitos (`unsupported_vat_rate`, `invalid_period`, `period_in_future`). Funciones de periodo: inicio y fin de cada trimestre natural, trimestre de una fecha y plazo de presentación (1-20 de abril, julio y octubre; 1-30 de enero).

### 3.2 Base de datos
Sin migraciones previstas (D-09). Una consulta por tabla con el rango `[inicio, fin)` del trimestre y `voided_at is null` en gastos. Si el hito 2 añade una función SQL o un índice, va en su propia migración, entra en `rls_matrix.yaml` y tiene sus pruebas de RLS.

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

**Estado del plazo** (`deadline_status`): `en_curso` (el trimestre no ha terminado), `plazo_abierto` (terminó y `today <= deadline`) y `plazo_cerrado` (`today > deadline`).

**Clasificación de una factura** (de su `tax_treatment`, sin recalcular nada):

| `tax_treatment` | Va a |
|---|---|
| `national_vat`, `eu_consumer_vat`, `non_eu_consumer_vat` con tipo 4 / 10 / 21 | base y cuota de 01-03 / 04-06 / 07-09 |
| `eu_reverse_charge` | 59 (base) |
| `non_eu_not_subject` | 120 (base) |

**Casillas** (todas en céntimos enteros con signo): `01`, `03`, `04`, `06`, `07`, `09` por tipo; `27` = `03 + 06 + 09`; `28` y `29` de los gastos (D-04); `45` = `29`; `46` = `27 − 45`; `59` y `120`. Cada casilla lleva `code`, `label` (texto en español), `amount_cents`, `group` (`devengado`, `deducible`, `resultado`, `adicional`), `items` (vacío en las derivadas, que enlazan a sus `components`) y `components` (códigos).

**Item**: `kind` (`invoice` | `expense`), `id`, `label` (número de factura o proveedor del gasto), `date`, `base_cents`, `vat_cents`. Una rectificativa es un item más con importes negativos. El `label` de un gasto es el nombre del proveedor tal como lo registró la persona.

**Resultado**: `result_cents` (= casilla 46) y `result_kind` (`a_ingresar` | `a_compensar` | `sin_actividad`).

**Avisos fijos** (`notes`, textos del dominio, **siempre presentes**): borrador **orientativo** y sin presentar; lo que no incluye (§4); **«No incluye el IGIC ni las operaciones en Canarias, Ceuta y Melilla: si tu actividad o tus clientes están allí, consulta con un asesor.»** (P-04: la ficha del cliente solo guarda el país, así que el aviso no puede saber si aplica); y, solo si hay casilla 59, «también va en el modelo 349».

**Límite**: un trimestre con más de **5.000 documentos** da `quarter_too_large` (422) en vez de una respuesta que no cabría en 4,5 MB (ADR-0016).

### 5.2 Base de datos
Sin cambios (D-09). Las lecturas pasan por la sesión de la persona: RLS ya limita `invoices` y `expenses` a `owner_id = auth.uid()`; el gestor con vínculo lee por las políticas existentes (su pantalla es SPEC-W-010); el administrador no ve ninguna fila.

### 5.3 API HTTP

| Operación | Ruta | Respuesta |
|---|---|---|
| `get_modelo_303` | `GET /api/tax/303?year=&quarter=` | `200` con `Modelo303` (periodo, plazo y estado, casillas con items, resultado y avisos). `422` `invalid_period` / `period_in_future` / `unsupported_vat_rate` / `quarter_too_large`; `401`; `403` (no es `usuario`) |

`Cache-Control: private, no-store`. Solo lee: no crea ni cambia nada (T8-07).

### 5.4 Backend
`cuadre/tax/modelo_303.py` (puro) y `cuadre/tax/periods.py` (trimestres y plazos, puro); `cuadre/tax/models_303.py` (modelos de respuesta); `cuadre/api/routes_tax.py`; servicio y repositorio de lectura en el mismo paquete que los demás (`cuadre.db`, sin conexiones fuera). `cuadre.core.clock` aporta «hoy en Madrid».

### 5.5 Frontend
`lib/tax-api.ts` (lectura de servidor), `lib/tax.ts` (puro: formato de periodo, textos de estado y de resultado, enlaces de cada item), `app/(app)/trimestres/page.tsx`, `components/tax/*` (selector de trimestre, grupo de casillas, fila con detalle desplegable y badge de estado). Ninguna cuenta ni regla fiscal en el navegador (D-08).

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

**AC-07 · Resultado.** *Given* 27 mayor que 45, menor y todo a cero; *Then* el resultado es «a ingresar», «a compensar» (46 negativo) y «sin actividad».

**AC-08 · Cada casilla se explica.** *Given* cualquier trimestre; *Then* la suma de los `items` de cada casilla con items es igual a su importe y las derivadas (27, 45, 46) enumeran sus componentes (NFR-08, 100 %).

**AC-09 · Fronteras de trimestre y de zona horaria.** *Given* facturas expedidas el 31/03 y el 01/04 (y el 31/12 y el 01/01); *Then* cada una cuenta en el trimestre de su fecha en Europe/Madrid.

**AC-10 · Plazo y estado.** *Given* el reloj en distintas fechas; *Then* el plazo es el 20 de abril, julio y octubre y el 30 de enero del año siguiente, y el estado es `en_curso`, `plazo_abierto` o `plazo_cerrado` según corresponda.

**AC-11 · Periodo inválido o futuro.** *Given* `quarter=5`, un año fuera de rango o un trimestre que no ha empezado; *Then* `422` con `invalid_period` o `period_in_future` y el texto en español.

**AC-12 · Tipo no soportado.** *Given* una factura con un tipo de IVA distinto de 4, 10 o 21 (dato corrupto); *Then* `422 unsupported_vat_rate`; la casilla no lo esconde.

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
| AC-07, AC-08 | `test_modelo_303.py` (resultado) y propiedades de `items` (documentos generados) |
| AC-09, AC-10, AC-11 | `backend/tests/tax/test_periods.py` y `test_modelo_303_api.py` |
| AC-12, AC-16 | `test_modelo_303.py` y `test_modelo_303_api.py` |
| AC-13 | `test_modelo_303_cases.py`: los cinco trimestres simulados a mano de esta spec (Anexo B.1) y, si llegan, los externos de DEP-01 |
| AC-14 | `backend/tests/rls/` (lecturas de `invoices` y `expenses` por rol) y `test_modelo_303_api.py` (403) |
| AC-15 | `test_modelo_303_api.py` (sin escrituras ni datos personales en logs) |
| AC-17 a AC-21 | `frontend/e2e/trimestres.spec.ts`, `roles.spec.ts`, `responsive.spec.ts` y las unitarias de `lib/tax.test.ts` (AC-21 también en `test_modelo_303_api.py`) |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005, 006 y 007 §8.2 siguen en verde.
- [ ] Los **cinco trimestres simulados** del Anexo B.1 coinciden al céntimo (NFR-03, por decisión de la persona del 2026-11-11). La **validación externa de DEP-01** queda como mejora pendiente y se anota en el Anexo B al cerrar; si la persona la exige antes de cerrar, la spec no pasa de `en-revision`.
- [ ] El 100 % de las casillas con documentos enumera sus items y su suma es la casilla (NFR-08).
- [ ] «Trimestres» está activo en el menú del autónomo y `/trimestres` hace todo lo de AC-17 a AC-21.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0006, 0011, 0015 y 0016 enlazados.
- [x] Las preguntas P-01 a P-05 están resueltas (2026-11-11).
- [ ] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

1. **Hito 0 · decisiones y cinco trimestres simulados**: se confirman D-01 a D-10 y se redactan en el Anexo B.1 **cinco trimestres resueltos a mano**, con las cuentas escritas paso a paso y sin ejecutar el código (solo nacional; UE y fuera de la UE con particulares; rectificativa que cruza trimestre; gastos de varios tipos con uno no deducible, uno anulado y una línea al 0 %; un trimestre «a compensar» y uno «sin actividad»), marcados «simulados, no externos».
2. **Hito 1 · dominio puro**: `periods.py` y `modelo_303.py` con sus tipos, pruebas de los casos a mano, propiedades de `items` y mutaciones.
3. **Hito 2 · lectura de datos**: consultas de trimestre para facturas y gastos (SQL explícito) y, solo si hace falta, una migración con su matriz RLS y sus pruebas; prueba del límite de documentos.
4. **Hito 3 · API**: `get_modelo_303`, modelos, errores, OpenAPI y pruebas de la API (incluidas las de sin escrituras y sin datos personales).
5. **Hito 4 · frontend**: `gen:api`, `/trimestres`, el menú, `lib/tax.ts` con sus unitarias y la comprobación visual en tres motores.
6. **Hito 5 · E2E y cierre**: `trimestres.spec.ts`, ajustes de `roles.spec.ts` y `responsive.spec.ts`, mutaciones de la interfaz, Anexo B, `tasks.json` y, si llegan, los trimestres externos de DEP-01.

## Anexo B · Decisiones que esta spec deja a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-009 (130).** Reutiliza `cuadre.tax.periods` y la página `/trimestres` (la pestaña del 130 ya está prevista, P-05); las retenciones salen de `irpf_cents` de las mismas facturas (SPEC-W-007 B.0) y los ingresos y gastos del 130 se calculan con la misma clasificación de documentos.
- **SPEC-W-011 (MCP).** La herramienta `borrador_trimestre` llama a la **misma función de dominio**; no se reimplementa la regla.
- **SPEC-W-010 (gestor).** Lee el mismo borrador con las políticas de lectura que ya existen; hace falta su pantalla y el registro de cada lectura.
- **SPEC-W-019 (XLSX).** Los libros registro salen de los mismos documentos y del mismo trimestre.

### B.1 Hito 0 · cinco trimestres simulados, resueltos a mano · pendiente

**Estado: «simulados, no externos».** Se redactan en el hito 0 con una tabla por trimestre (documento → base → tipo → cuota redondeada `ROUND_HALF_UP` → casilla) y las sumas escritas paso a paso. Los cálculos son **manuales e independientes del código**: no se obtienen ejecutando `build_modelo_303`. Cubren, entre los cinco: solo nacional (4, 10 y 21 %); UE empresa y fuera de la UE sin IVA y particulares con IVA español; una rectificativa que cruza trimestre; gastos con varias líneas, uno con IVA no deducible, uno anulado y una línea al 0 %; un trimestre «a compensar» y uno «sin actividad».

**Límite de lo que demuestran.** Que el código reproduce un cálculo manual hecho con la misma interpretación de las reglas (D-02 a D-06). No demuestran que esa interpretación sea la de la AEAT: eso es lo que daría la validación externa de DEP-01 (equipo docente o gestoría), que sigue **pendiente** y que la persona decidió no esperar (2026-11-11).
