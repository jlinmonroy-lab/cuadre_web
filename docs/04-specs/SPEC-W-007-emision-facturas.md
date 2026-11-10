---
tipo: spec
id: SPEC-W-007
titulo: Emisión de facturas: inmutables, numeración, mención legal, PDF, QR simulado y rectificativas
estado: propuesta
prioridad: must
riesgo: medio
historias: [US-006, US-007]
requisitos: [RF-006, RF-007]
nfr: [NFR-06, NFR-10, NFR-11]
restricciones: [RES-02, RES-03, RES-04, RES-07]
adr: [0003, 0004, 0006, 0011, 0015, 0016]
depende_de: [SPEC-W-005, SPEC-W-006]
bloquea: [SPEC-W-008, SPEC-W-011, SPEC-W-012]
fecha: 2026-11-10
---

# SPEC-W-007 · Emisión de facturas: inmutables, numeración, mención legal, PDF, QR simulado y rectificativas

> Tercer paso de la cadena **perfil → clientes → facturas**. La persona elige un cliente, escribe el concepto y la base, y la aplicación aplica **sola** el IVA, la retención de IRPF y la mención legal que corresponden al ámbito del cliente, numera la factura de forma correlativa dentro de su serie, la **congela** (una factura emitida no se edita ni se borra: RES-03), genera su **PDF** con un **QR de VeriFactu simulado** (RES-04) y lo guarda con su huella. Un error se corrige con una **factura rectificativa** en serie propia.
> Lo que **no** hace es declarar: las casillas del 303 y el modelo 349 (SPEC-W-008), la presentación ante la AEAT y la factura electrónica B2B quedan fuera. Esta spec deja guardado, factura a factura, el dato que esas declaraciones necesitan (el **tratamiento fiscal**) para que no haya que recalcular nada.

## 1. Contexto

**Situación de partida.** No hay tabla, ruta ni pantalla de facturas: en el menú del autónomo «Facturas» sale desactivado («Próximamente»). Las dos specs previas dejaron casi todo lo que hace falta: SPEC-W-005 dejó las **series** (`invoice_series`, con `next_number`, el cerrojo asesor `private.series_enter` y `app.ensure_year_series`) y la regla de **qué falta para poder emitir** (`GET /api/profile` → `missing_for_invoicing`, `can_issue`); SPEC-W-006 dejó la **ficha de cliente** (`scope`, `kind`, `tax_id`, `address`, archivada o activa) y anotó (B.0) que la factura debe congelar una copia del cliente, que decide si exige el domicilio y que las condiciones por ámbito (`invoice_terms`) son de esta spec. El prototipo (`docs/cuadre-interfaz.html`) trae la pantalla (`renderFacturas`, `buildInvoice`, `invoiceTerms`, `openInvoice`) y los `operation_id` `issue_invoice` y `set_invoice_payment`. **No existen** el paquete de dominio fiscal (`cuadre.tax`, `cuadre.invoicing`) ni una librería de PDF o de QR instalada (ni `reportlab`, `fpdf2`, `segno` ni `qrcode`): el spike del hito 0 elige y fija versiones (T7-09).

**Por qué es de riesgo medio.** Es la primera spec que **calcula impuestos y que no se puede deshacer**: (1) una factura emitida con el IVA o la mención equivocados es un documento legal equivocado, y su corrección es otra factura, no un `UPDATE`; (2) la **numeración correlativa sin huecos** exige que asignar el número y escribir la factura sean una sola transacción con cerrojo (si falla, el número no se consume), y que dos emisiones a la vez no repitan ni se salten ninguno; (3) la **inmutabilidad** tiene que estar en la base (trigger), no solo en la API (CLAUDE.md, «reglas críticas en triggers o funciones»); (4) el **PDF** es el documento que se entrega: debe salir igual siempre y su alteración debe poder detectarse; (5) el nombre, el NIF, el domicilio y el IBAN de la persona y de sus clientes son datos personales (NFR-11) y no pueden salir en registros ni en errores. Por eso todo cálculo vive en código puro con tablas de pruebas, y la interfaz **no calcula impuestos**: pide una vista previa al servidor.

**Decisiones vigentes** (no se reabren aquí): ADR-0003 y ADR-0015 (SQL explícito, reglas críticas en la base); ADR-0004 (Supabase UE, Storage privado); ADR-0006 (importes en céntimos); ADR-0011 (cliente generado y `operation_id`); ADR-0016 (backend en Vercel: sin trabajo posterior a la respuesta, sin proceso persistente, 4,5 MB por petición); CONF-001 (a) y D3 (el gestor solo lee, el administrador no ve datos financieros); RES-02 (nunca `float`), RES-03 (una factura emitida no se edita ni se borra), RES-04 (nada se presenta ante la AEAT; el QR se marca como simulado); de SPEC-W-005, el rol único `usuario`, las series y la regla `missing_for_invoicing`; de SPEC-W-006, el ámbito (`scope`) y el tipo (`kind`) del cliente y que archivar no borra.

**Decisiones que propone esta spec.** **D-01 a D-04 las decidió la persona el 2026-11-10**; el resto queda a su visto bueno.

| ID | Decisión | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Decidida.** Las **rectificativas entran en esta spec** (RF-007): serie propia, **por diferencias**, con motivo y referencia a la original (§5.1.5) | Spec posterior: acota esta, pero la inmutabilidad queda sin su salida legal y el seguimiento de errores se aplaza |
| D-02 | **Decidida.** **Una línea** por factura: un concepto, una base y un tipo de IVA (como el prototipo). Dos tipos de IVA son dos facturas | Varias líneas con desglose de IVA por tipo: más modelo, formulario y pruebas; añadirlas luego es una tabla `invoice_lines` y migrar el total |
| D-03 | **Decidida.** El PDF **se genera al emitir y se guarda** en el bucket privado `invoices` (`{owner_id}/{invoice_id}.pdf`) con su **huella SHA-256** en la base; se descarga con la huella comprobada | Regenerarlo en cada descarga: nada que guardar, pero una plantilla nueva cambiaría el aspecto de facturas antiguas y no habría nada con que comparar |
| D-04 | **Decidida.** El **domicilio del cliente es obligatorio para emitir** (el RD 1619/2012 lo pide en la factura completa); en la ficha sigue siendo opcional. Falta → `client_not_billable` con el campo `address` y enlace a editar el cliente | Opcional al emitir: más cómodo, pero la factura puede incumplir el contenido mínimo |
| D-05 | **Condiciones fiscales por ámbito** (`invoice_terms`, §5.1.2), calculadas **solo en código puro** y guardadas en la factura como **tratamiento fiscal** (`tax_treatment`: `national_vat`, `eu_reverse_charge`, `eu_consumer_vat`, `non_eu_not_subject`), para que SPEC-W-008 lea las casillas 59 y 120 y el 349 sin recalcular | Calcular el tratamiento al declarar: dos reglas para lo mismo, y el cambio de ficha del cliente movería facturas ya emitidas |
| D-06 | **Importes**: céntimos enteros con signo en la base y la API (`*_cents`), `Decimal` con `ROUND_HALF_UP` en el cálculo, una sola divisa (EUR). IVA a elegir entre 21, 10 y 4 % solo cuando hay IVA; la **retención** (15 o 7 %) la pone el perfil, solo a una **empresa nacional**, y se calcula sobre la base. Si el perfil no tiene retención elegida y hace falta, **no se emite** (`irpf_rate_missing`; pregunta abierta P-01) | Retención a 0 si falta: una factura sin retención que debía llevarla es un error silencioso |
| D-07 | **La emisión es una función** `app.issue_invoice` (`SECURITY DEFINER`, `search_path = ''`, rol `usuario`, cerrojo por serie): valida, asigna el número, congela las copias y escribe la factura en una sola transacción. Un **trigger** impide `UPDATE` y `DELETE` en `invoices` salvo la columna `paid_at`; el `TRUNCATE` también se impide | Escribir desde la API con `INSERT` directo: sin cerrojo ni garantía de que no se edite |
| D-08 | **Numeración correlativa por serie**, sin huecos: la serie es la que se elija (por defecto la predeterminada) y el número, el `next_number` de esa serie; el formato es `{serie}-{NNN}` (mínimo tres dígitos). La **fecha de expedición** no puede ser futura (día de Madrid) ni anterior a la de la última factura de **esa serie** | Serie deducida del año de la fecha (prototipo): no cabe una serie propia ni emitir en enero una factura del año anterior |
| D-09 | **La factura congela una copia** del emisor (nombre, NIF, domicilio fiscal e IBAN del perfil), del cliente (nombre, tipo, país, ámbito, NIF y domicilio) y de las condiciones aplicadas. Editar el perfil o el cliente después **no cambia** facturas ya emitidas (D-08 de SPEC-W-006) | Leer del perfil y del cliente al mostrar: una factura «viva» deja de ser un documento |
| D-10 | **El PDF se produce justo después de emitir, en la misma petición**: la factura se confirma primero (número y inmutabilidad no esperan a Storage), después se dibuja y se sube (sin conexión de base retenida durante la subida) y se registra su huella con `app.attach_invoice_pdf` (una sola vez, en la tabla `invoice_files`, no en `invoices`). Si algo falla, la factura queda **emitida sin PDF** (`pdf_status: "pending"`) y `POST /api/invoices/{id}/pdf` lo genera de forma **idempotente**. El PDF es **reproducible**: no lleva la hora actual ni un identificador aleatorio (su fecha es la de expedición), así que el mismo dato da los mismos bytes | Generarlo dentro de la transacción de emisión: retiene la conexión mientras se espera a Storage (ADR-0016) |
| D-11 | **QR de VeriFactu simulado**: el QR codifica un texto **no resoluble** con los cuatro datos que lleva el de VeriFactu (NIF del emisor, serie y número, fecha de expedición e importe total) y el PDF lo rotula **«QR VeriFactu simulado, no remitido a la AEAT»**. No apunta a la URL real de validación de la AEAT (RES-04). La norma exacta del QR y el texto se fijan en el spike | QR con la URL real de la AEAT: al escanearlo diría «factura no encontrada» y parecería un fallo del documento |
| D-12 | **Rectificativas** (§5.1.5): por **diferencias**, en una **serie propia** (`invoice_series.kind = 'rectifying'`, código `R-{año}`, creada como la del año); llevan la referencia a la original, un **motivo obligatorio** y el importe corregido (o la anulación completa); heredan la copia del cliente y las condiciones de la original; los importes llevan **signo**; una original puede tener varias; **no se rectifica una rectificativa**; la suma de bases no baja de cero. «Rectificada» se **deduce** de que exista una rectificativa: la original no se toca | Por sustitución (una factura nueva que anula la anterior): el total no cambia el libro y dos documentos dicen lo mismo |
| D-13 | **Cobro**: `paid_at` es lo único modificable de una factura emitida; se marca (ahora) y se puede desmarcar. Las rectificativas **no se cobran** (`invoice_not_payable`) | Importe cobrado parcial y fecha elegida: no hay conexión bancaria en la v1 (PRD, Won't) |
| D-14 | **La vista previa la calcula el servidor** (`preview_invoice`, una lectura que no escribe): la interfaz **no calcula impuestos**; enseña lo que devuelve la API, con la misma función que la emisión | Calcular en el navegador: dos implementaciones de una regla fiscal |
| D-15 | **Lecturas.** `list_invoices` por año (el actual por defecto), más reciente primero; `get_clients_billing` da «Facturado en {año}» de `/clientes` **sin tocar el contrato de clientes**. El gestor con vínculo activo lee por RLS (su pantalla es SPEC-W-010); el administrador, nada (D3) | Añadir el total facturado a `Client`: cambia el contrato de SPEC-W-006 |
| D-16 | **Registro de actividad**: emitir, rectificar y cambiar el cobro escriben `activity_log` **en la misma transacción** (`invoice.issued`, `invoice.rectified`, `invoice.payment_changed`), con solo ids, la serie, el número y el tratamiento fiscal: **nunca** nombres, NIF, domicilios, IBAN ni conceptos | Sin registro: la gestora no vería cuándo se emitió ni se corrigió nada (SPEC-W-010) |

**Preguntas abiertas** (no bloquean el hito 0; se cierran en el spike o con la persona):

| ID | Pregunta | Propuesta por defecto |
|---|---|---|
| P-01 | ¿Cómo se expresa una actividad **sin retención** (el perfil solo ofrece 15 %, 7 % o «sin elegir»)? | Bloquear con `irpf_rate_missing` y enlace al perfil; decidir con la persona si el perfil gana la opción «sin retención» (cambio de SPEC-W-005) |
| P-02 | **Canarias, Ceuta y Melilla** (heredada de SPEC-W-006 D-11): `ES` es nacional con IVA | Se queda como nacional; se documenta y se resuelve en SPEC-W-008 |
| P-03 | Texto exacto de la **mención legal** de la inversión del sujeto pasivo y del artículo 69, y contenido y tamaño del **QR** de VeriFactu | Los del prototipo; el spike los contrasta con fuentes oficiales (BOE, AEAT) |
| P-04 | **Fecha de la operación** distinta de la de expedición | Fuera de la v1: se asume la misma fecha |

## 2. Objetivo

Al terminar esta spec:

1. La persona tiene una pantalla **Facturas** (`/facturas`, activa en el menú) donde emite, consulta, descarga y cobra sus facturas, y emite **rectificativas** (RF-006, RF-007).
2. El **IVA, la retención y la mención legal** se aplican **solos** según el ámbito y el tipo del cliente (US-006), y la vista previa los enseña antes de emitir.
3. Cada factura recibe el **siguiente número de su serie**, sin huecos ni repeticiones, también con emisiones simultáneas.
4. Una factura emitida **no se edita ni se borra**, ni siquiera desde la base (trigger); solo cambia su cobro (RES-03).
5. Emitir con el **perfil incompleto** (US-007), con un cliente **sin domicilio** o **archivado** se impide diciendo por nombre qué falta.
6. Cada factura tiene su **PDF**, con el QR de VeriFactu **simulado**, guardado con su huella y descargable (RES-04).
7. Un error se corrige con una **rectificativa por diferencias**, en serie propia y con motivo; la original no se toca.
8. Todo está **aislado por RLS** (NFR-06) y ni los datos de la persona ni los de sus clientes salen en registros, trazas o errores (NFR-11).
9. Cada factura lleva el **tratamiento fiscal** que SPEC-W-008 lee para el 303 y el 349.
10. `/clientes` enseña por fin la columna **«Facturado en {año}»**.

## 3. Alcance explícito

### 3.1 Dominio puro (`cuadre.tax`, `cuadre.invoicing`)
- Funciones sin base de datos, sin red, sin reloj propio y sin `float`: condiciones por ámbito (`invoice_terms`), cálculo de importes (`Decimal`, `ROUND_HALF_UP`, redondeo simétrico para importes negativos), validación de los campos, formato del número, reglas de la rectificativa (diferencias, límites, motivo) y el contenido del QR simulado. `limits` en un solo sitio.

### 3.2 Base de datos (migraciones nuevas)
- Tipos `invoice_kind`, `invoice_tax_treatment`; columna `kind` en `invoice_series` (migración nueva: las aplicadas no se tocan); tablas `invoices` e `invoice_files` con RLS activada y forzada; trigger de inmutabilidad; funciones `app.issue_invoice`, `app.issue_rectifying_invoice`, `app.set_invoice_paid`, `app.attach_invoice_pdf` y `app.ensure_rectifying_series`; bucket privado `invoices` y sus políticas; entradas en `backend/tests/rls/rls_matrix.yaml`; seed con facturas sintéticas de los cuatro tratamientos.

### 3.3 Backend (FastAPI)
- Rutas `preview_invoice`, `issue_invoice`, `issue_rectifying_invoice`, `list_invoices`, `get_invoice`, `get_invoice_pdf`, `create_invoice_pdf`, `set_invoice_payment` y `get_clients_billing` (§5.3), solo para el rol `usuario`. Paquetes `cuadre.tax` y `cuadre.invoicing` (puros) y, con base de datos, servicio, repositorio, modelos y errores de facturas.

### 3.4 PDF, QR y almacenamiento
- Generación determinista del PDF y del QR en Python puro, subida al bucket con el JWT de la persona (sin service key), huella SHA-256 y comprobación al descargar.

### 3.5 Frontend (Next.js)
- `/facturas` (lista con filtros y «Nueva factura» con vista previa del servidor), `/facturas/[id]` (detalle, descarga del PDF, cobro y «Emitir rectificativa»), «Facturas» activo en el menú, la columna «Facturado en {año}» y el texto de condiciones en `/clientes`.

### 3.6 Pruebas
- `backend/tests/invoicing/` y `backend/tests/tax/`, ampliación de `backend/tests/rls/` (tablas, trigger, funciones y bucket), `backend/tests/rules/test_invoicing_boundary.py`, unitarias del frontend, `frontend/e2e/factura.spec.ts` en los tres motores y los dos anchos, y los ajustes de `roles.spec.ts`, `responsive.spec.ts` y `e2e/helpers/env.ts`.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Casillas del 303 por tratamiento (59, 120…), modelo 349 y el 130 | SPEC-W-008 y SPEC-W-009 |
| Presentación ante la AEAT, VeriFactu certificado, registros de facturación remitidos y factura electrónica B2B (RES-04) | Fuera de la v1 |
| Varias líneas, varios tipos de IVA por factura, descuentos y suplidos (D-02) | Futura |
| Otras divisas (solo EUR) | Futura |
| Factura simplificada y facturas de venta a particulares sin NIF | Futura |
| Rectificativa por sustitución y rectificación de una rectificativa (D-12) | Futura |
| Fecha de operación distinta de la de expedición (P-04), vencimiento y condiciones de pago más allá del IBAN | Futura |
| Cobro parcial, conciliación bancaria y fecha de cobro elegida (D-13) | Futura (PRD: sin conexión bancaria) |
| Envío de la factura por correo | SPEC-W-014 o futura |
| Plantillas o personalización del PDF más allá del logo del perfil | Futura |
| Pantalla del gestor para ver las facturas de sus autónomos (aquí solo la política de lectura) | SPEC-W-010 |
| Borrado de la cuenta y exportación de las facturas (CONF-004: conservación fiscal frente a RGPD) | SPEC-W-017 |
| Territorios especiales de España (P-02) | SPEC-W-008 |

## 5. Contrato de interfaces

### 5.1 Campos y reglas

Los textos de error van en español, **no repiten el valor escrito** y salen del servidor. `POST /api/invoices` y `POST /api/invoices/rectifications` validan **todos** los campos a la vez y, si alguno falla, **no guardan nada** y devuelven todos los errores.

#### 5.1.1 Campos de la factura

| Campo | Regla | Mensaje |
|---|---|---|
| `client_id` | UUID de un cliente **activo** de la persona, con **domicilio** | «Elige un cliente.» · `client_not_billable`: «Ese cliente está archivado: reactívalo para facturarle.» · «Falta el domicilio del cliente: añádelo para emitir la factura.» |
| `series_id` | UUID de una serie **activa** de la persona y de tipo ordinario (`kind = 'standard'`); vacío = la predeterminada | «Elige una serie activa.» |
| `issue_date` | Fecha real `AAAA-MM-DD`; **no futura** (día de Madrid) y **no anterior a la de la última factura de la serie** | «La fecha no puede ser futura.» · «La fecha no puede ser anterior a la de la última factura de la serie ({fecha}).» |
| `concept` | Texto de 2 a 300 caracteres, sin saltos de línea ni controles | «Describe el servicio facturado.» · «El concepto admite entre 2 y 300 caracteres, sin saltos de línea.» |
| `base_cents` | Entero de 1 a 9.999.999.999 (99.999.999,99 €) | «Escribe un importe mayor que cero, por ejemplo 1.200,00.» |
| `vat_rate` | `"21.00"`, `"10.00"` o `"4.00"` solo si el tratamiento lleva IVA; vacío = 21 %; en los demás tratamientos **se rechaza** (la interfaz no lo envía) | «El tipo de IVA no es válido: elige 21, 10 o 4 %.» · «Este cliente no lleva IVA: no envíes tipo de IVA.» |

Con el **perfil incompleto** (`missing_for_invoicing` de SPEC-W-005) emitir da `profile_incomplete` (422) con el miembro extra `missing: [ { field, label } ]` (US-007).

#### 5.1.2 Condiciones fiscales (`invoice_terms`)

Dependen del ámbito (`scope`) y del tipo (`kind`) de la **copia del cliente** y de la retención del perfil. Es la regla del prototipo y de B.0 de SPEC-W-006.

| Cliente | `tax_treatment` | IVA | Retención de IRPF | Mención legal |
|---|---|---|---|---|
| Nacional, **empresa** | `national_vat` | 21 % por defecto (21, 10 o 4) | La del perfil (15 o 7 %), sobre la base | — |
| Nacional, **particular** | `national_vat` | 21 % por defecto (21, 10 o 4) | Ninguna | — |
| UE, **empresa** (NIF-IVA válido) | `eu_reverse_charge` | Sin IVA | Ninguna | «Inversión del sujeto pasivo.» |
| UE, **particular** | `eu_consumer_vat` | 21 % por defecto (IVA español) | Ninguna | — |
| Fuera de la UE | `non_eu_not_subject` | Sin IVA | Ninguna | «Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA).» |

La retención se calcula sobre la **base**, no sobre el IVA. Un cliente nacional empresa con el perfil **sin retención elegida** da `irpf_rate_missing` (D-06, P-01). `ES` es siempre nacional (P-02). El texto exacto de las menciones se confirma en el spike (P-03).

#### 5.1.3 Importes

`vat_cents = round(base_cents × vat_rate / 100)` y `irpf_cents = round(base_cents × irpf_rate / 100)`, en `Decimal` con `ROUND_HALF_UP`; `total_cents = base_cents + vat_cents − irpf_cents`. Con importes negativos (rectificativas) se redondea el **valor absoluto** y se aplica el signo, de modo que el redondeo es **simétrico** (−333 × 21 % = −70, no −69).

Ejemplos (fijan las pruebas de tabla):

| Caso | Base | IVA | Retención | Total |
|---|---|---|---|---|
| Nacional empresa, 21 % y retención del 15 % | 120.000 | 25.200 | 18.000 | 127.200 |
| UE empresa, inversión del sujeto pasivo (US-006) | 150.000 | 0 | 0 | 150.000 |
| UE particular, 21 % | 100.000 | 21.000 | 0 | 121.000 |
| Fuera de la UE | 50.000 | 0 | 0 | 50.000 |
| Redondeo hacia arriba en el medio céntimo (base 1.050 al 10 %) | 1.050 | 105 | 0 | 1.155 |
| Rectificativa de −333 al 21 % | −333 | −70 | 0 | −403 |

#### 5.1.4 Número, serie y fechas

El número visible es `{serie}-{NNN}`, con el número a **tres dígitos como mínimo** (`2026-001`; a partir del 1000, `2026-1000`). El número es el `next_number` de la serie en el momento de emitir, que avanza en la misma transacción; **no hay huecos** (si la emisión falla, no se consume) y **no se repite** (cerrojo por serie). La serie del año la crea `app.ensure_year_series` si no existe (D-07 de SPEC-W-005); una serie archivada no se ofrece.

#### 5.1.5 Rectificativas (D-12)

Entrada: la factura original (`rectifies`), el **motivo** (2 a 300 caracteres, sin saltos de línea), la **base corregida** (`corrected_base_cents`, de 0 a la base vigente) o la anulación completa (base corregida 0) y la fecha de expedición.

- La **base de la rectificativa** es `corrected_base_cents − base vigente`, donde la base vigente es la de la original más las diferencias de sus rectificativas anteriores; el IVA y la retención se calculan **con los tipos y el tratamiento de la original** y con el redondeo simétrico de 5.1.3.
- Va en la **serie rectificativa** del año (`R-{año}`, `kind = 'rectifying'`), con su propia numeración correlativa y las reglas de fecha de 5.1.4 aplicadas a **esa** serie; la fecha tampoco puede ser anterior a la de la original.
- Lleva la copia del cliente y de las condiciones de la original; el emisor, el actual (D-09 se aplica a cada factura al emitirse).
- `rectification_exceeds` (409) si la base corregida es mayor que la vigente (una rectificativa no sube la factura: eso es una factura nueva) o negativa; no se puede rectificar una rectificativa (`invoice_not_rectifiable`); una rectificativa **no se cobra** (D-13).
- Ejemplo: original de base 120.000 al 21 % con retención del 15 % (total 127.200), corregida a 100.000 → base −20.000, IVA −4.200, retención −3.000, **total −21.200**; anulación completa → base −120.000, IVA −25.200, retención −18.000 (se devuelve), **total −127.200**.

#### 5.1.6 PDF y QR (D-03, D-10, D-11)

El PDF lleva: número y serie, **fecha de expedición**, el **emisor** (nombre, NIF, domicilio y logo del perfil), el **cliente** (nombre, NIF o NIF-IVA y domicilio), el concepto, la base, el IVA con su tipo (o «Sin IVA»), la retención con su tipo, el **total**, la **mención legal** del tratamiento, el IBAN para el pago si el perfil lo tiene, y el **QR simulado** con su leyenda. La rectificativa lleva además «Factura rectificativa de la {número} de {fecha}», el motivo y los importes con signo. Sin hora actual ni identificadores aleatorios (reproducible). Contenido del QR propuesto (se fija en el spike): `CUADRE-VERIFACTU-SIMULADO|{NIF}|{serie}-{NNN}|{AAAA-MM-DD}|{total con dos decimales}`.

### 5.2 Base de datos

Migraciones nuevas (`YYYYMMDDHHMMSS_descripcion.sql`, sin destructivas; las ya aplicadas no se tocan). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`. El DDL es **la propuesta** que el spike del hito 0 comprueba en seco.

```
TYPE invoice_kind          AS ENUM ('standard', 'rectifying')
TYPE invoice_tax_treatment AS ENUM ('national_vat', 'eu_reverse_charge', 'eu_consumer_vat', 'non_eu_not_subject')
ALTER TABLE invoice_series ADD COLUMN kind invoice_kind NOT NULL DEFAULT 'standard'

invoices
  id                uuid PK DEFAULT gen_random_uuid()
  owner_id          uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT       -- no cascadea (CONF-004, RES-03)
  series_id         uuid NOT NULL REFERENCES invoice_series(id) ON DELETE RESTRICT
  series_code       text NOT NULL                                                   -- copia: el código de una serie usada no cambia, pero la factura no depende de ello
  number            integer NOT NULL CHECK (number BETWEEN 1 AND 999999)
  kind              invoice_kind NOT NULL
  issue_date        date NOT NULL
  client_id         uuid NOT NULL REFERENCES clients(id) ON DELETE RESTRICT
  client_name       text NOT NULL, client_kind client_kind NOT NULL, client_country text NOT NULL,
  client_scope      client_scope NOT NULL, client_tax_id text, client_address text NOT NULL   -- copia congelada (D-09)
  issuer_name       text NOT NULL, issuer_tax_id text NOT NULL, issuer_address text NOT NULL, issuer_iban text   -- copia del perfil
  concept           text NOT NULL CHECK (char_length(concept) BETWEEN 2 AND 300)
  tax_treatment     invoice_tax_treatment NOT NULL
  base_cents        bigint NOT NULL
  vat_rate          numeric(5,2) NOT NULL DEFAULT 0, vat_cents bigint NOT NULL DEFAULT 0
  irpf_rate         numeric(5,2) NOT NULL DEFAULT 0, irpf_cents bigint NOT NULL DEFAULT 0
  total_cents       bigint NOT NULL
  legal_note        text
  rectifies_id      uuid REFERENCES invoices(id) ON DELETE RESTRICT
  rectification_reason text CHECK (char_length(rectification_reason) BETWEEN 2 AND 300)
  paid_at           timestamptz                                                      -- lo ÚNICO modificable
  created_at        timestamptz NOT NULL DEFAULT now()
  UNIQUE (owner_id, series_id, number)
  CHECK (total_cents = base_cents + vat_cents - irpf_cents)
  CHECK ((kind = 'rectifying') = (rectifies_id IS NOT NULL AND rectification_reason IS NOT NULL))
  CHECK (kind = 'rectifying' OR base_cents > 0)   -- la ordinaria siempre positiva; la rectificativa puede ser negativa
  CHECK (kind = 'standard' OR paid_at IS NULL)
INDEX invoices_owner_date ON invoices (owner_id, issue_date DESC, id)
INDEX invoices_rectifies ON invoices (rectifies_id) WHERE rectifies_id IS NOT NULL

invoice_files
  invoice_id  uuid PK REFERENCES invoices(id) ON DELETE RESTRICT
  storage_path text NOT NULL, sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'), size_bytes integer NOT NULL
  created_at timestamptz NOT NULL DEFAULT now()
```

Las restricciones llevan nombre propio (`invoices_total_matches`, `invoices_kind_matches_rectification`, `invoices_base_positive`…) para que la API las traduzca por nombre. **Trigger `invoices_immutable`** (`BEFORE UPDATE OR DELETE`, más `BEFORE TRUNCATE`): rechaza con `invoice_immutable` (P0001) cualquier `UPDATE` que cambie una columna distinta de `paid_at` y todo `DELETE`; `invoice_files` es de solo inserción (sin `UPDATE`, `DELETE` ni `TRUNCATE`). `app.set_invoice_paid` es la única que escribe `paid_at`.

**Privilegios.** `authenticated`: `SELECT` en `invoices` e `invoice_files` y nada más; toda escritura por funciones.

| Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|
| SELECT | las suyas | las de usuarios con vínculo activo (`private.gestor_has_access(owner_id)`) | **ninguna** |
| INSERT / UPDATE / DELETE | denegado (solo `app.*`) | denegado | denegado |

**Funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`; verifican `auth.uid()` y `private.app_role() = 'usuario'`; `P0001` con código estable, `42501` si el rol no basta). Todas toman el cerrojo asesor por persona y, las que numeran, el de la **serie** (`private.series_lock_own`):

| Función | Efecto |
|---|---|
| `app.issue_invoice(p_client_id, p_series_id, p_issue_date, p_concept, p_base_cents, p_vat_rate, p_terms jsonb)` | Comprueba el perfil, el cliente (activo, con domicilio), la serie (activa, ordinaria) y las fechas; copia emisor y cliente; escribe las condiciones que le pasa la API ya calculadas (la base **repite** las comprobaciones baratas y la identidad aritmética `total = base + IVA − retención`, no la regla fiscal: D-10 de SPEC-W-006 aplica igual); asigna `next_number` y lo avanza; escribe `activity_log`. Devuelve el id |
| `app.issue_rectifying_invoice(p_original_id, p_reason, p_corrected_base_cents, p_issue_date, p_terms jsonb)` | Lo anterior para la serie rectificativa del año (`app.ensure_rectifying_series`), con las reglas de 5.1.5 (`rectification_exceeds`, `invoice_not_rectifiable`, fecha) |
| `app.set_invoice_paid(p_id, p_paid)` | Marca o desmarca `paid_at` de una factura ordinaria (`invoice_not_payable` si es rectificativa) y lo registra |
| `app.attach_invoice_pdf(p_invoice_id, p_path, p_sha256, p_size)` | Inserta **una sola vez** la fila de `invoice_files` de una factura propia (`invoice_pdf_exists` si ya hay) |
| `app.ensure_rectifying_series(p_year)` | Crea `R-{año}` si no existe, idempotente, como `app.ensure_year_series` |

Los errores `P0001` son `invoice_not_found`, `client_not_found`, `client_not_billable`, `series_not_found`, `profile_incomplete`, `irpf_rate_missing`, `invoice_date_out_of_order`, `invalid_invoice` (campo en el `DETAIL`), `rectification_exceeds`, `invoice_not_rectifiable`, `invoice_not_payable`, `invoice_immutable` e `invoice_pdf_exists`.

**Storage.** Bucket privado `invoices` (solo PDF, hasta 1 MiB), ruta `{owner_id}/{invoice_id}.pdf`. Políticas como las de `logos` (funciones `private.invoice_file_*` que **nunca** lanzan errores): **insertar**, solo un `usuario` en su carpeta y con nombre de la forma exacta; **leer**, el dueño o un gestor con vínculo activo; el administrador, nada; **sin** `UPDATE` ni `DELETE`. Que la persona pueda subir su propio archivo a esa ruta no compromete la factura: la fila de `invoice_files` guarda la huella, y la descarga la comprueba (D-03).

**Matriz de RLS.** `invoices` e `invoice_files`: `kind: financial`, `owner_column: owner_id` (en `invoice_files`, a través de la factura), privilegios `SELECT`, con `seed` y sondas de escritura.

**Seed (sintético).** Facturas de Alicia de los **cuatro tratamientos** y una rectificativa, emitidas **por las propias funciones** con un reloj fijo (cómo se siembra sin saltarse el trigger lo fija el hito 0); nombres y NIF inventados con dígitos de control válidos. Ningún dato real (RES-07).

### 5.3 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador); errores en `application/problem+json`.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `preview_invoice` | `POST /api/invoices/preview` | `InvoiceInput`. **200** `InvoicePreview` (condiciones, importes y mención, **sin número**); **no escribe**; mismos 422 que emitir |
| `issue_invoice` | `POST /api/invoices` | `InvoiceInput`. Valida, emite y genera el PDF; **201** `Invoice`; **422** `invalid_invoice`, `profile_incomplete` o `irpf_rate_missing`; **409** `client_not_billable` o `invoice_date_out_of_order` |
| `issue_rectifying_invoice` | `POST /api/invoices/{invoice_id}/rectifications` | `RectificationInput`. **201** `Invoice`; **404**; **409** `rectification_exceeds`, `invoice_not_rectifiable` o `invoice_date_out_of_order`; **422** |
| `list_invoices` | `GET /api/invoices` | Query `year` (por defecto el actual), `scope` y `paid` (filtros). **200** `[Invoice]`, la más reciente primero |
| `get_invoice` | `GET /api/invoices/{invoice_id}` | **200** `Invoice` (con `pdf_status`, `rectified_by` y la base vigente); **404** `invoice_not_found` |
| `get_invoice_pdf` | `GET /api/invoices/{invoice_id}/pdf` | **200** `application/pdf` con la huella comprobada; **404**; **409** `invoice_pdf_pending` o `invoice_pdf_corrupt` |
| `create_invoice_pdf` | `POST /api/invoices/{invoice_id}/pdf` | Genera el PDF de una factura emitida **sin** él, de forma idempotente. **200** `Invoice`; **404** |
| `set_invoice_payment` | `PUT /api/invoices/{invoice_id}/payment` | `{ "paid": bool }`. **200** `Invoice`; **404**; **409** `invoice_not_payable` |
| `get_clients_billing` | `GET /api/clients/billing` | Query `year`. **200** `[{ client_id, billed_cents }]` (suma de bases, con signo) |

```
InvoiceInput { client_id, series_id: uuid|null, issue_date: "AAAA-MM-DD", concept, base_cents: integer, vat_rate: "21.00"|"10.00"|"4.00"|null }
RectificationInput { reason, corrected_base_cents: integer, issue_date }
InvoicePreview { scope, kind, tax_treatment, base_cents, vat_rate, vat_cents, irpf_rate, irpf_cents, total_cents, legal_note: string|null, vat_editable: bool }
Invoice { id, series_code, number, display_number, kind: "standard"|"rectifying", issue_date, client: { id, name, kind, country, scope, tax_id, address },
          concept, tax_treatment, base_cents, vat_rate, vat_cents, irpf_rate, irpf_cents, total_cents, legal_note,
          rectifies: { id, display_number, issue_date }|null, rectification_reason, rectified_by: [display_number],
          paid_at: datetime|null, pdf_status: "ready"|"pending", created_at }
```

**Códigos de error nuevos** (`code`, HTTP): `invalid_invoice` 422 (con `fields: [ { field, message } ]`, **todos** los que fallan) · `profile_incomplete` 422 (con `missing`) · `irpf_rate_missing` 422 · `client_not_billable` 409 (con `field`) · `invoice_date_out_of_order` 409 · `rectification_exceeds` 409 · `invoice_not_rectifiable` 409 · `invoice_not_payable` 409 · `invoice_pdf_pending` 409 · `invoice_pdf_corrupt` 409 · `invoice_not_found` 404 (también si es de otra persona) · `forbidden` 403. Los errores de forma del cuerpo son el `validation_error` 422 de siempre. Los textos van en español y no repiten el valor escrito.

### 5.4 Backend

- **Paquetes.** `cuadre.tax` (puro: `invoice_terms`, importes y redondeo) y `cuadre.invoicing` (puros: `limits`, `types`, `numbering`, `rules`, `rectification`, `qr`; con base de datos y Storage, a partir del hito 3: `service`, `repository`, `models`, `errors`, `pdf`, `storage`) y `api/routes_invoices.py`. Los módulos puros **no importan base de datos, red, FastAPI, `float` ni reloj**; lo vigila `backend/tests/rules/test_invoicing_boundary.py`, como `test_clients_boundary.py`, y un test de **paridad** compara las constantes de `limits` con los CHECK.
- **Flujo de `issue_invoice`.** (1) Leer perfil, cliente y serie y **calcular** las condiciones con `cuadre.tax`; (2) transacción corta: `app.issue_invoice` con las condiciones ya calculadas → leer la fila → confirmar; (3) **fuera** de la transacción, dibujar el PDF y el QR, subirlo con el JWT de la persona, comprobar y registrar la huella con `app.attach_invoice_pdf`; (4) responder. Nunca una conexión retenida mientras se espera a Storage (D-10, ADR-0016).
- **Modelos.** La **entrada es suelta** (`str` con `max_length`, `extra="forbid"`, sin `Literal` para lo que valida el dominio) para devolver **todos los errores a la vez** como `invalid_invoice`; `paid` con `StrictBool`; la salida lleva uniones de literales. Importes siempre `int` de céntimos y tipos como cadenas `"21.00"`; **ningún `float`** (RES-02: un test lo vigila en código y migraciones).
- **PDF y QR.** Librerías de Python puro, fijadas y compatibles con una función de Vercel (sin binarios del sistema, T7-09); fuentes con `ñ`, `€` y acentos; metadatos y orden de objetos deterministas (D-10). Se elige en el spike.
- **Registro.** Ni el nombre, ni el NIF, ni el IBAN, ni el domicilio, ni el concepto de una factura se escriben en ningún registro: `request_id`, `user_id`, ruta, código y duración.

### 5.5 Frontend

| Ruta | Quién | Contenido |
|---|---|---|
| `/facturas` | `usuario` | Cabecera con «Nueva factura». Lista del año (selector de año): tarjetas hasta 1.279 px y tabla desde 1.280 px (Número, Fecha, Cliente, Base, IVA, Retención, Total, Cobro, Ámbito); el ámbito es **texto con insignia** como en `/clientes`; las rectificativas se distinguen por texto («Rectificativa»). Filtros de ámbito y cobro. Formulario «Nueva factura» (desplegable) con Cliente (solo activos), Serie, Fecha de expedición, Concepto, Base imponible (€) y Tipo de IVA; una **vista previa servida por la API** (`preview_invoice`) enseña ámbito, base, IVA, retención, total y mención **antes** de emitir, y el selector de IVA solo aparece si hay IVA. Perfil incompleto: se enumera por nombre lo que falta con enlace a `/perfil`. Cliente sin domicilio: enlace a editarlo |
| `/facturas/[id]` | `usuario` | Detalle del documento (emisor, cliente, concepto, importes, mención, rectificativas que la corrigen), **descarga del PDF**, «Marcar como cobrada» / «Marcar como pendiente» y «Emitir rectificativa» (motivo, base corregida o anular, fecha). Aviso «Emitida y bloqueada. Para corregirla, emite una rectificativa.» |
| `/clientes` | `usuario` | Columna «Facturado en {año}» (de `get_clients_billing`) y, en el formulario, el texto de condiciones de la factura del cliente (lo que `preview_invoice` devuelve), sin lógica fiscal en el navegador |

Emitir, rectificar y cobrar son **Server Actions** (`useActionState`, errores junto a cada campo con `aria-describedby`, resumen que recibe el foco, como `client-form`). El importe se escribe en euros (`1.200,00`) y la Server Action lo pasa a céntimos con `lib/money.ts`. La interfaz **muestra** lo que dice el servidor y no calcula impuestos. Los nombres de país salen **del servidor** (lección de SPEC-W-006: cada motor nombra distinto algunos códigos). «Facturas» pasa de `FUTURE` a enlace en `navFor('usuario')` y a `SECTIONS.usuario`; gestor y administrador no lo ven y `/facturas` para ellos lleva a `/403`. Hay que actualizar `lib/roles.test.ts` y `PEOPLE.alicia.nav` / `enabledNav` en `e2e/helpers/env.ts`. La **descarga** del PDF es un Route Handler del servidor (la web nunca ve la URL de Storage ni el JWT de la persona).

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T7-01 | **Sin `float`** en importes: céntimos enteros o `Decimal` con `ROUND_HALF_UP` (RES-02); un test lo vigila en código y migraciones |
| T7-02 | **Una factura emitida no se edita ni se borra** (RES-03): trigger en la base, solo `paid_at`; la API no ofrece `PUT` ni `DELETE` de facturas |
| T7-03 | **Numeración correlativa sin huecos ni repeticiones**, con cerrojo por serie y en la misma transacción que la factura; también con emisiones simultáneas |
| T7-04 | **Sin red ni modelos de lenguaje** (RES-04): nada se envía a la AEAT ni a VIES; el QR no apunta a ninguna URL oficial y se rotula como simulado |
| T7-05 | **Solo `usuario`** emite y lee sus facturas por la API; el gestor con vínculo activo lee por RLS (revocar corta el acceso en la petición siguiente) y el administrador no ve ninguna (D3, NFR-06). La service key no interviene en ninguna ruta |
| T7-06 | **Sin datos personales en logs, trazas, errores ni `activity_log`**: ni nombre, ni NIF, ni domicilio, ni IBAN, ni concepto. Los `422` dicen qué campo falla, no qué se escribió. Un test captura los registros de todo el flujo |
| T7-07 | **Una lectura no escribe**: `preview_invoice`, `list_invoices`, `get_invoice`, `get_invoice_pdf` y `get_clients_billing` no crean ni cambian nada |
| T7-08 | **Sin trabajo posterior a la respuesta** (ADR-0016) y **sin conexión retenida** mientras se espera a Storage; `test_vercel_compat` sigue verde; cada petición cabe en 4,5 MB |
| T7-09 | **Dependencias nuevas mínimas**: solo las de PDF y QR que el spike elija, de Python puro, fijadas por versión y sin binarios del sistema; ninguna llama a la red |
| T7-10 | **El PDF es reproducible** (mismos datos, mismos bytes) y su huella SHA-256 se comprueba en cada descarga |
| T7-11 | **Interfaz** como T6-08: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, anuncios con `aria-live`, sin scroll horizontal a 390 y 1.440 px en los tres motores |
| T7-12 | **Migraciones sin datos reales y sin destructivas**; no se editan las aplicadas (la columna `kind` de las series va en una migración nueva); el seed es sintético (RES-07) |
| T7-13 | Una prueba E2E que emita facturas **no puede borrarlas ni archivarlas**: usa la cuenta nueva de cada worker, en la que la numeración correlativa es un efecto esperado; ninguna depende de lo que dejó otra |

## 7. Criterios de aceptación (Given-When-Then)

```gherkin
AC-01  Factura nacional a una empresa (RF-006)
  Given una persona con perfil completo y retención del 15 % y un cliente empresa en España
  When emite una factura de 1.200,00 € con IVA del 21 %
  Then la factura es la siguiente de su serie y lleva base 120.000, IVA 25.200, retención 18.000 y total 127.200 (en céntimos)
    And su tratamiento fiscal es national_vat y no lleva mención legal

AC-02  Factura a una empresa de la UE (US-006)
  Given un cliente empresa de Alemania con NIF-IVA válido
  When la persona emite una factura de 1.500,00 € a ese cliente
  Then no lleva IVA ni retención e incluye «Inversión del sujeto pasivo.»
    And recibe el siguiente número de su serie, el tratamiento es eu_reverse_charge y ya no se puede editar

AC-03  Otros ámbitos
  Given un particular de la UE, un particular español y una empresa de fuera de la UE
  When se emite una factura a cada uno
  Then el particular de la UE lleva IVA español sin retención (eu_consumer_vat), el español lleva IVA sin retención (national_vat)
    And la de fuera de la UE va sin IVA con el artículo 69 de la Ley del IVA (non_eu_not_subject)

AC-04  Tipos de IVA y redondeo
  Given un cliente nacional
  When se emite con IVA del 21, 10 y 4 %, y con una base de 10,50 € al 10 %
  Then cada cuota es la de la tabla de §5.1.3, redondeada medio céntimo hacia arriba
    And un tipo que no sea 21, 10 o 4, o un IVA enviado a un cliente sin IVA, no se admite

AC-05  Perfil incompleto (US-007)
  Given una persona sin NIF ni domicilio fiscal en su perfil
  When intenta emitir su primera factura
  Then la respuesta es 422 «profile_incomplete» con missing que enumera por nombre los campos que faltan, y no se crea nada
    And con el perfil sin retención elegida y un cliente empresa nacional, la respuesta es 422 «irpf_rate_missing»

AC-06  Cliente sin domicilio o archivado
  Given un cliente sin domicilio y otro archivado
  When la persona intenta facturarlos
  Then ambos dan 409 «client_not_billable», el primero con field «address», y no se consume ningún número

AC-07  Numeración correlativa y sin huecos
  Given una serie sin facturas emitidas
  When se emiten tres facturas y una cuarta falla por un dato inválido
  Then los números son 1, 2 y 3 con el formato «2026-001», y el siguiente emitido es el 4 (la que falló no consumió ninguno)
    And a partir del 1000 el número se escribe sin relleno («2026-1000»)

AC-08  Concurrencia
  Given una serie sin facturas
  When cinco peticiones emiten a la vez
  Then salen cinco facturas con los números 1 a 5, sin repetidos ni huecos, y ninguna da un 500

AC-09  Fechas
  Given una serie cuya última factura es del 10 de marzo
  When se emite con fecha 9 de marzo, con una fecha futura o con una fecha que no existe
  Then la primera da 409 «invoice_date_out_of_order», y las otras dos 422 «invalid_invoice»
    And con la fecha del 10 de marzo o posterior se emite

AC-10  Todos los errores a la vez
  Given una persona con sesión
  When envía sin cliente, sin concepto, con base 0 y sin fecha
  Then la respuesta es 422 «invalid_invoice» con fields que enumera los cuatro en el orden de la pantalla, y no se crea nada

AC-11  Inmutabilidad (RES-03)
  Given una factura emitida
  When se intenta un UPDATE de cualquier columna salvo paid_at, un DELETE o un TRUNCATE, por la API o directamente en la base
  Then todos se rechazan (invoice_immutable) y la fila sigue igual
    And la API no ofrece ninguna ruta para editar ni borrar facturas

AC-12  Copia congelada
  Given una factura emitida a un cliente y con un perfil
  When la persona cambia después el nombre, el país o el domicilio del cliente y los datos del perfil
  Then la factura sigue mostrando los datos de cuando se emitió, con el mismo ámbito y las mismas condiciones

AC-13  Cobro
  Given una factura emitida
  When la persona la marca como cobrada y después como pendiente
  Then paid_at se rellena y se vacía, el resto de la factura no cambia y cada cambio queda en el registro de actividad
    And una rectificativa no se puede cobrar (409 «invoice_not_payable»)

AC-14  Rectificativa por diferencias (RF-007)
  Given una factura de base 120.000 al 21 % con retención del 15 %
  When la persona emite una rectificativa con base corregida 100.000, y otra anulando el resto
  Then la primera lleva base −20.000, IVA −4.200, retención −3.000 y total −21.200 en la serie R-{año}, con su propio número, el motivo y la referencia a la original
    And la segunda lleva base −100.000 y las dos juntas dejan la base vigente en 0
    And la original no cambia y aparece como rectificada

AC-15  Límites de las rectificativas
  Given una factura original y una rectificativa suya
  When se intenta rectificar la rectificativa, subir la base por encima de la vigente o dejarla negativa
  Then cada intento da 409 («invoice_not_rectifiable» o «rectification_exceeds») y no se crea nada
    And sin motivo da 422 «invalid_invoice» con field «reason»

AC-16  PDF con huella (D-03, D-10)
  Given una factura recién emitida
  When la persona descarga su PDF
  Then el PDF existe en el bucket invoices, lleva número, fecha, emisor, cliente, concepto, importes, mención legal y el QR simulado con su leyenda, y su SHA-256 coincide con el guardado
    And el PDF de los mismos datos, generado dos veces, es idéntico
    And si el archivo se altera, la descarga da 409 «invoice_pdf_corrupt»
    And si la generación falló al emitir, la factura queda con pdf_status «pending» y POST /pdf la completa sin duplicarla

AC-17  QR simulado (RES-04)
  Given cualquier factura
  When se mira su QR y su PDF
  Then el QR lleva el texto simulado de §5.1.6, la leyenda dice «QR VeriFactu simulado, no remitido a la AEAT» y ninguna petición sale de la aplicación

AC-18  Vista previa
  Given una persona con sesión
  When pide la vista previa de una factura
  Then recibe las mismas condiciones, importes y mención que tendrá al emitirla, sin número, y no se escribe nada
    And lo emitido coincide con la vista previa de los mismos datos

AC-19  Aislamiento (NFR-06)
  Given Alicia y Beto (usuarios), Gina (gestora con vínculo activo con Alicia) y Adán (administrador)
  When cada uno intenta leer o escribir las facturas y los PDF de otro
  Then Beto no ve nada de Alicia y no puede escribirlo; Gina lee las de Alicia y no escribe nada; tras revocar, no ve nada
    And Adán no ve ninguna factura de nadie (D3)
    And Gina y Adán reciben 403 «forbidden» en las rutas de facturas
    And un INSERT, UPDATE o DELETE directo sobre invoices o invoice_files, y subir, sobrescribir o borrar en el bucket por otra vía, se rechazan

AC-20  Sin datos personales en los registros (NFR-11)
  Given el flujo completo (vista previa, emisión, errores, rectificativa, cobro, descarga, 403 y 404)
  When se capturan todos los registros
  Then ni el nombre, ni el NIF, ni el domicilio, ni el IBAN, ni el concepto aparecen en ellos ni en el cuerpo de ningún error, y activity_log solo lleva ids, serie, número y tratamiento

AC-21  Interfaz de Facturas (NFR-10)
  Given la persona en /facturas con la sesión de un usuario
  When emite una factura de cada tratamiento, la descarga, la cobra y la rectifica, a 390 y a 1.440 px
  Then no hay scroll horizontal, todo campo tiene su etiqueta, cada error sale junto a su campo y en un resumen que recibe el foco
    And la vista previa cambia con el cliente y el tipo de IVA, y la mención legal se ve antes de emitir
    And se puede hacer todo con el teclado, el foco siempre se ve y no hay errores de consola en Chromium, Firefox ni WebKit

AC-22  Menú, portadas y roles
  Given un usuario, una gestora y un administrador con sesión
  When ven su menú y entran en /facturas
  Then el usuario ve «Facturas» activo; la gestora y el administrador no lo ven y /facturas los lleva a /403
    And las portadas, /perfil y /clientes siguen mostrando lo de SPEC-W-001, 005 y 006

AC-23  Facturado en el año
  Given una persona con facturas y una rectificativa de un cliente en el año
  When abre /clientes
  Then cada cliente enseña la suma de las bases de sus facturas del año (las rectificativas restan) y los demás, cero

AC-24  Guardas (T7-01, T7-04, T7-08)
  Given el repositorio entero
  When corren las guardas
  Then cuadre.tax y los módulos puros de cuadre.invoicing no importan base de datos, httpx, FastAPI ni usan float ni el reloj del sistema
    And las constantes de limits y los CHECK de la base coinciden
    And test_rls_guard exige invoices e invoice_files en la matriz y test_vercel_compat, test_no_float y test_operation_ids siguen verdes
```

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-005 §8.1, con la pila de Supabase en marcha y los puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 (o `E2E_AGENTS_PORT`) libres. Sin red: los NIF, NIF-IVA e IBAN de las pruebas son inventados con dígitos de control válidos y nada sale a Internet. Los E2E de facturas usan la cuenta nueva del worker; **no se pueden borrar ni archivar facturas** (T7-13), así que ninguna prueba depende de la numeración que dejó otra: cada una lee su número de la respuesta.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                                  # migraciones + seed
pytest backend/tests/tax backend/tests/invoicing -q                    # AC-01 a AC-18, AC-20 y AC-24 (lado API)
pytest backend/tests/rls -m rls -q                                     # AC-11 y AC-19 (tablas, trigger, funciones y bucket)
pytest backend/tests -m "not rls" -q
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/factura.spec.ts      # AC-21 a AC-23 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/invoicing` y `npm --prefix frontend exec -- playwright test e2e/factura.spec.ts`, además de las secuencias completas de SPEC-W-001, 002, 003, 005 y 006 §8.2, que deben seguir en verde (la batería de E2E se ejecuta con `--workers=1`).

### 8.3 Correspondencia criterio → prueba

| AC | Prueba |
|---|---|
| AC-01 a AC-04 | `backend/tests/tax/` (tablas de condiciones, importes y redondeo, sin red), `backend/tests/invoicing/test_invoices_api.py`; `frontend/e2e/factura.spec.ts` · «una factura de cada tratamiento» |
| AC-05, AC-06, AC-10 | `backend/tests/invoicing/test_invoices_api.py`; `factura.spec.ts` · «perfil incompleto», «cliente sin domicilio» y «todos los errores a la vez» |
| AC-07, AC-08, AC-09 | `backend/tests/invoicing/test_numbering.py`, `test_concurrency.py`; `backend/tests/rls/test_invoices.py` (cerrojo con dos transacciones) |
| AC-11, AC-12, AC-13 | `backend/tests/rls/test_invoices.py` (trigger, `TRUNCATE`, funciones), `backend/tests/invoicing/test_invoices_api.py`; `factura.spec.ts` · «cobrar» |
| AC-14, AC-15 | `backend/tests/tax/test_rectification.py`, `backend/tests/invoicing/test_rectifications_api.py`; `factura.spec.ts` · «rectificar» |
| AC-16, AC-17 | `backend/tests/invoicing/test_pdf.py` (contenido, reproducibilidad, huella, alteración, reintento), `test_qr.py`; `factura.spec.ts` · «descargar el PDF» |
| AC-18 | `backend/tests/invoicing/test_preview.py`; `factura.spec.ts` · «vista previa» |
| AC-19 | `backend/tests/rls/test_invoices.py`, `test_invoices_storage.py` y `rls_matrix.yaml`; `backend/tests/invoicing/test_roles.py` |
| AC-20 | `backend/tests/invoicing/test_no_sensitive_logs.py` |
| AC-21, AC-22 | `frontend/e2e/factura.spec.ts` (seis proyectos), `responsive.spec.ts` (`/facturas`), `roles.spec.ts`; `frontend/src/lib/roles.test.ts` |
| AC-23 | `backend/tests/invoicing/test_billing.py`; `factura.spec.ts` · «facturado en el año» |
| AC-24 | `backend/tests/rules/test_invoicing_boundary.py`, `backend/tests/invoicing/test_limits_parity.py`, `backend/tests/rls/test_rls_guard.py` y las guardas de `backend/tests/rules/` |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005 y 006 §8.2 siguen en verde.
- [ ] `pytest backend/tests/rls -m rls` incluye `invoices`, `invoice_files`, sus funciones y el bucket `invoices`.
- [ ] «Facturas» está activo en el menú del autónomo y `/facturas` hace todo lo de AC-21; `/clientes` enseña «Facturado en {año}».
- [ ] El seed lleva facturas sintéticas de los cuatro tratamientos y una rectificativa, y las pruebas que dependían del menú se han revisado.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0011, 0015 y 0016 enlazados.
- [ ] Las preguntas abiertas P-01 a P-04 están resueltas o anotadas en el Anexo B.
- [ ] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike**: con valores **sintéticos**, (a) qué librería de **PDF** y de **QR** (Python puro, fuentes con `ñ` y `€`) caben en una función de Vercel por tamaño, tiempo y reproducibilidad de los bytes; (b) la norma del **QR de VeriFactu** y el contenido mínimo de la **factura completa** (RD 1619/2012) y el texto de las **menciones** (P-03), con fuentes oficiales; (c) la **subida con el JWT** al bucket `invoices` y las políticas que no lancen errores; (d) el DDL de §5.2 en seco, con la **carrera de numeración** con y sin cerrojo, el trigger de inmutabilidad y `TRUNCATE`; (e) cómo **sembrar** facturas sin saltarse el trigger; (f) P-01 y P-02 con la persona. Resultado al Anexo B.
1. **Dominio puro**: `cuadre.tax` y `cuadre.invoicing` (condiciones, importes, número, validación, rectificativas, contenido del QR) con tablas de pruebas y mutaciones; `test_invoicing_boundary.py`.
2. **Base de datos**: migraciones (tipos, `kind` de serie, `invoices`, `invoice_files`, trigger, funciones, bucket y políticas), matriz de RLS y seed; pruebas de RLS, de trigger y de concurrencia; mutaciones.
3. **API**: emitir, previsualizar, listar, leer, cobrar, rectificar y `get_clients_billing`; `openapi.json` y `schema.d.ts` regenerados; mutaciones.
4. **PDF, QR y almacenamiento**: generación determinista, subida, huella, descarga con comprobación y reintento; pruebas de contenido y de alteración.
5. **Frontend**: `/facturas`, `/facturas/[id]`, menú, columna «Facturado en {año}» y condiciones en `/clientes`; unitarias; comprobación visual en los tres motores.
6. **E2E y cierre**: `factura.spec.ts` en tres motores y dos anchos, ajustes de `roles.spec.ts`, `responsive.spec.ts` y `env.ts`, mutaciones de la interfaz, Anexo B, `tasks.json`.

## Anexo B · Decisiones que esta spec dejó a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-008 (303).** Lee `tax_treatment`, `base_cents`, `vat_cents` e `irpf_cents` de cada factura (con signo: las rectificativas restan en el periodo de **su** fecha de expedición), sin recalcular nada: `eu_reverse_charge` → casilla 59 y modelo 349; `non_eu_not_subject` → casilla 120; `national_vat` y `eu_consumer_vat` → IVA devengado por tipo. La retención y el 130 salen de `irpf_cents`.
- **SPEC-W-010 (gestor).** Las políticas de lectura de `invoices`, `invoice_files` y del bucket ya existen; faltan la pantalla y el registro de cada lectura.
- **SPEC-W-011 (MCP).** `buscar_facturas`, `resumen_mes`, `resumen_anio` y `gastos_por_categoria` leen estas tablas con el token acotado; el ámbito se mapea con `cuadre.clients.scope` (no se duplica).
- **SPEC-W-012 (cierre mensual) y SPEC-W-013 (reporte).** Cuentan las facturas por fecha de expedición, con las rectificativas restando; el cobro (`paid_at`) alimenta «pendiente de cobro».
- **SPEC-W-017 (CONF-004).** Las facturas no cascadean con la cuenta (`ON DELETE RESTRICT`): la conservación fiscal frente al borrado RGPD se resuelve ahí.
