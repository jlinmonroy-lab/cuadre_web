---
tipo: spec
id: SPEC-W-007
titulo: Emisión de facturas: inmutables, numeración, mención legal, PDF, QR simulado y rectificativas
estado: en-progreso
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
| D-05 | **Condiciones fiscales por ámbito** (`invoice_terms`, §5.1.2), calculadas **solo en código puro** y guardadas en la factura como **tratamiento fiscal** (`tax_treatment`: `national_vat`, `eu_reverse_charge`, `eu_consumer_vat`, `non_eu_consumer_vat`, `non_eu_not_subject`), para que SPEC-W-008 lea las casillas 59 y 120 y el 349 sin recalcular. **Un particular de fuera de la UE lleva IVA español** (art. 69.Uno.2.º de la Ley del IVA; **P-05, decidida el 2026-11-10**), no «sin IVA» como decía el prototipo (B.1-B) | Calcular el tratamiento al declarar: dos reglas para lo mismo, y el cambio de ficha del cliente movería facturas ya emitidas |
| D-06 | **Importes**: céntimos enteros con signo en la base y la API (`*_cents`), `Decimal` con `ROUND_HALF_UP` en el cálculo, una sola divisa (EUR). IVA a elegir entre 21, 10 y 4 % solo cuando hay IVA; la **retención** (15 o 7 %) la pone el perfil, solo a una **empresa nacional**, y se calcula sobre la base. Si el perfil no tiene retención elegida y hace falta, **no se emite** (`irpf_rate_missing`; pregunta abierta P-01) | Retención a 0 si falta: una factura sin retención que debía llevarla es un error silencioso |
| D-07 | **La emisión es una función** `app.issue_invoice` (`SECURITY DEFINER`, `search_path = ''`, rol `usuario`, cerrojo por serie): valida, asigna el número, congela las copias y escribe la factura en una sola transacción. Un **trigger** impide `UPDATE` y `DELETE` en `invoices` salvo la columna `paid_at`; el `TRUNCATE` también se impide | Escribir desde la API con `INSERT` directo: sin cerrojo ni garantía de que no se edite |
| D-08 | **Numeración correlativa por serie**, sin huecos: la serie es la que se elija (por defecto la predeterminada) y el número, el `next_number` de esa serie; el formato es `{serie}-{NNN}` (mínimo tres dígitos). La **fecha de expedición** no puede ser futura (día de Madrid) ni anterior a la de la última factura de **esa serie** | Serie deducida del año de la fecha (prototipo): no cabe una serie propia ni emitir en enero una factura del año anterior |
| D-09 | **La factura congela una copia** del emisor (nombre, NIF, domicilio fiscal e IBAN del perfil), del cliente (nombre, tipo, país, ámbito, NIF y domicilio) y de las condiciones aplicadas. Editar el perfil o el cliente después **no cambia** facturas ya emitidas (D-08 de SPEC-W-006) | Leer del perfil y del cliente al mostrar: una factura «viva» deja de ser un documento |
| D-10 | **El PDF se produce justo después de emitir, en la misma petición**: la factura se confirma primero (número e inmutabilidad no esperan a Storage), después se dibuja y se sube (sin conexión de base retenida durante la subida) y se registra su huella con `app.attach_invoice_pdf` (una sola vez, en la tabla `invoice_files`, no en `invoices`). Si algo falla, la factura queda **emitida sin PDF** (`pdf_status: "pending"`) y `POST /api/invoices/{id}/pdf` lo genera de forma **idempotente**. El PDF es **reproducible dentro de un mismo entorno** (sin hora actual ni identificador aleatorio; idéntico entre Windows y Linux con la misma zlib: B.1-A) y la **ruta lleva el prefijo de la huella** (`{owner_id}/{invoice_id}-{sha256[:16]}.pdf`): subir lo mismo otra vez da un 409 de Storage que se toma por **éxito idempotente** tras comprobar la huella (B.1-C) | Generarlo dentro de la transacción de emisión: retiene la conexión mientras se espera a Storage (ADR-0016) |
| D-11 | **QR de VeriFactu simulado**: el QR codifica un texto **no resoluble** con los cuatro datos del de VeriFactu (NIF del emisor, serie y número, fecha de expedición e importe total) y con **los formatos del QR real de la AEAT** (fecha `DD-MM-AAAA`, importe con punto decimal y signo en una rectificativa): `CUADRE-VERIFACTU-SIMULADO\|{NIF}\|{serie}-{NNN}\|{DD-MM-AAAA}\|{importe}`. Mide **35 mm** (la AEAT pide de 30 a 40), nivel de corrección **M**, va **arriba y centrado** en la primera página, y el PDF lo rotula **«QR VeriFactu simulado, no remitido a la AEAT»**. No apunta a la URL real de validación (RES-04) y **no usa la frase «VERI*FACTU»**, que solo corresponde a un sistema verificable (B.1-B) | QR con la URL real de la AEAT: al escanearlo diría «factura no encontrada» y parecería un fallo del documento |
| D-12 | **Rectificativas** (§5.1.5): en una **serie propia** (`invoice_series.kind = 'rectifying'`, código `R-{año}`, creada como la del año; el art. 6.1.a prevé series separadas); llevan la referencia a la original, un **motivo obligatorio** (decisión de esta spec, no del Reglamento) y el importe de la rectificación **con signo** (art. 15.4 y 15.5 del Reglamento: «una nueva factura» con los datos de la rectificada y el importe «con independencia de su signo»; el Reglamento no nombra «sustitución» ni «diferencias»); heredan la copia del cliente y las condiciones de la original; una original puede tener varias; **no se rectifica una rectificativa**; la suma de bases no baja de cero. «Rectificada» se **deduce** de que exista una rectificativa: la original no se toca | Una factura nueva que sustituye a la anterior: el total no cambia el libro y dos documentos dicen lo mismo |
| D-13 | **Cobro**: `paid_at` es lo único modificable de una factura emitida; se marca (ahora) y se puede desmarcar. Las rectificativas **no se cobran** (`invoice_not_payable`) | Importe cobrado parcial y fecha elegida: no hay conexión bancaria en la v1 (PRD, Won't) |
| D-14 | **La vista previa la calcula el servidor** (`preview_invoice`, una lectura que no escribe): la interfaz **no calcula impuestos**; enseña lo que devuelve la API, con la misma función que la emisión | Calcular en el navegador: dos implementaciones de una regla fiscal |
| D-15 | **Lecturas.** `list_invoices` por año (el actual por defecto), más reciente primero; `get_clients_billing` da «Facturado en {año}» de `/clientes` **sin tocar el contrato de clientes**. El gestor con vínculo activo lee por RLS (su pantalla es SPEC-W-010); el administrador, nada (D3) | Añadir el total facturado a `Client`: cambia el contrato de SPEC-W-006 |
| D-16 | **Registro de actividad**: emitir, rectificar y cambiar el cobro escriben `activity_log` **en la misma transacción** (`invoice.issued`, `invoice.rectified`, `invoice.payment_changed`), con solo ids, la serie, el número y el tratamiento fiscal: **nunca** nombres, NIF, domicilios, IBAN ni conceptos | Sin registro: la gestora no vería cuándo se emitió ni se corrigió nada (SPEC-W-010) |

*Visto bueno del 2026-11-10: la persona pidió el plan del hito 0 tras decidir **D-01 a D-04** y **P-01** (se bloquea y se enlaza al perfil), sin cambios a D-05 a D-16; se tratan como aprobadas y la spec pasa a `en-progreso`. El spike del hito 0 midió el PDF y el QR, leyó la normativa, probó Storage con el JWT, el DDL con sus carreras y el seed, y corrigió D-05, D-10, D-11, D-12, T7-09, T7-10, §5.1.2, §5.1.5, §5.1.6, §5.2, §5.3, §5.4, AC-03, AC-16 y AC-17; la persona decidió además **P-05** (Anexo B.1).*

**Preguntas abiertas** (**P-01, P-03 y P-05 quedaron resueltas en el hito 0**; P-02 y P-04 siguen abiertas y se anotan en el Anexo B):

| ID | Pregunta | Propuesta por defecto |
|---|---|---|
| P-01 | ¿Cómo se expresa una actividad **sin retención** (el perfil solo ofrece 15 %, 7 % o «sin elegir»)? | **Decidida el 2026-11-10:** se bloquea con `irpf_rate_missing` y enlace al perfil; no cambia SPEC-W-005 |
| P-02 | **Canarias, Ceuta y Melilla** (heredada de SPEC-W-006 D-11): `ES` es nacional con IVA | Se queda como nacional; se documenta y se resuelve en SPEC-W-008 |
| P-03 | Texto exacto de la **mención legal** de la inversión del sujeto pasivo y del artículo 69, y contenido y tamaño del **QR** de VeriFactu | **Cerrada en el hito 0 (B.1-B):** «inversión del sujeto pasivo» es literal del art. 6.1.m del Reglamento; la del art. 69 es práctica habitual (no hay texto impuesto); QR de 35 mm, nivel M y formatos de la AEAT |
| P-04 | **Fecha de la operación** distinta de la de expedición | Fuera de la v1: se asume la misma fecha |
| P-05 | Un **particular de fuera de la UE**: ¿sin IVA con el art. 69 (prototipo) o IVA español? (art. 69.Uno.2.º y Dos de la Ley del IVA) | **Decidida el 2026-11-10:** IVA español sin retención (`non_eu_consumer_vat`); la excepción de las letras a) a l) del 69.Dos no se modela (B.1-B) |

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
- Tipos `invoice_kind`, `invoice_tax_treatment`; columna `kind` en `invoice_series` (migración nueva: las aplicadas no se tocan); tablas `invoices` e `invoice_files` con RLS activada y forzada; trigger de inmutabilidad; funciones `app.issue_invoice`, `app.issue_rectifying_invoice`, `app.set_invoice_paid`, `app.attach_invoice_pdf` y `app.ensure_rectifying_series`; bucket privado `invoices` y sus políticas; entradas en `backend/tests/rls/rls_matrix.yaml`; seed con facturas sintéticas de los cinco tratamientos.

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
| Presentación ante la AEAT, VeriFactu certificado, registros de facturación remitidos y factura electrónica B2B (RES-04; el RD 238/2026 la hará obligatoria entre empresarios cuando se dicte su orden ministerial: B.1-B) | Fuera de la v1 (PRD, R-06) |
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
| Fuera de la UE, **empresa** | `non_eu_not_subject` | Sin IVA | Ninguna | «Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA).» |
| Fuera de la UE, **particular** | `non_eu_consumer_vat` | 21 % por defecto (21, 10 o 4): IVA español | Ninguna | — |

La retención se calcula sobre la **base**, no sobre el IVA. Un cliente nacional empresa con el perfil **sin retención elegida** da `irpf_rate_missing` (D-06, P-01). `ES` es siempre nacional (P-02). Los **particulares** de la UE y de fuera de la UE llevan IVA español (art. 69.Uno.2.º de la Ley del IVA; P-05): no se modela la excepción de las letras a) a l) del 69.Dos ni el umbral de ventanilla única de la UE (B.1-B). «Inversión del sujeto pasivo.» es literal del art. 6.1.m del Reglamento de facturación; la del artículo 69 es práctica habitual y no un texto impuesto; la empresa de la UE lleva su NIF-IVA en la factura (art. 6.1.d: el destinatario es el sujeto pasivo).

#### 5.1.3 Importes

`vat_cents = round(base_cents × vat_rate / 100)` y `irpf_cents = round(base_cents × irpf_rate / 100)`, en `Decimal` con `ROUND_HALF_UP`; `total_cents = base_cents + vat_cents − irpf_cents`. Con importes negativos (rectificativas) se redondea el **valor absoluto** y se aplica el signo, de modo que el redondeo es **simétrico** (−333 × 21 % = −70, no −69).

Ejemplos (fijan las pruebas de tabla):

| Caso | Base | IVA | Retención | Total |
|---|---|---|---|---|
| Nacional empresa, 21 % y retención del 15 % | 120.000 | 25.200 | 18.000 | 127.200 |
| UE empresa, inversión del sujeto pasivo (US-006) | 150.000 | 0 | 0 | 150.000 |
| UE particular, 21 % | 100.000 | 21.000 | 0 | 121.000 |
| Fuera de la UE, empresa | 50.000 | 0 | 0 | 50.000 |
| Fuera de la UE, particular, 21 % | 100.000 | 21.000 | 0 | 121.000 |
| Redondeo hacia arriba en el medio céntimo (base 1.050 al 10 %) | 1.050 | 105 | 0 | 1.155 |
| Rectificativa de −333 al 21 % | −333 | −70 | 0 | −403 |

#### 5.1.4 Número, serie y fechas

El número visible es `{serie}-{NNN}`, con el número a **tres dígitos como mínimo** (`2026-001`; a partir del 1000, `2026-1000`). El número es el `next_number` de la serie en el momento de emitir, que avanza en la misma transacción; **no hay huecos** (si la emisión falla, no se consume) y **no se repite** (cerrojo por serie). La serie del año la crea `app.ensure_year_series` si no existe (D-07 de SPEC-W-005); una serie archivada no se ofrece.

#### 5.1.5 Rectificativas (D-12)

Entrada: la factura original (`rectifies`), el **motivo** (2 a 300 caracteres, sin saltos de línea), la **base corregida** (`corrected_base_cents`, de 0 a la base vigente) o la anulación completa (base corregida 0) y la fecha de expedición.

El Reglamento no nombra «por sustitución» ni «por diferencias» (art. 15.4 y 15.5; B.1-B): esta spec expresa **el importe de la rectificación con signo**, con la referencia a la original y un motivo (decisión de la spec, no del Reglamento). El plazo de **cuatro años desde el devengo** (art. 15.3) **no se comprueba**.

- La **base de la rectificativa** es `corrected_base_cents − base vigente`, donde la base vigente es la de la original más las diferencias de sus rectificativas anteriores; el IVA y la retención se calculan **con los tipos y el tratamiento de la original** y con el redondeo simétrico de 5.1.3.
- Va en la **serie rectificativa** del año (`R-{año}`, `kind = 'rectifying'`), con su propia numeración correlativa y las reglas de fecha de 5.1.4 aplicadas a **esa** serie; la fecha tampoco puede ser anterior a la de la original.
- Lleva la copia del cliente y de las condiciones de la original; el emisor, el actual (D-09 se aplica a cada factura al emitirse).
- `rectification_exceeds` (409) si la base corregida es mayor que la vigente (una rectificativa no sube la factura: eso es una factura nueva) o negativa; no se puede rectificar una rectificativa (`invoice_not_rectifiable`); una rectificativa **no se cobra** (D-13).
- Ejemplo: original de base 120.000 al 21 % con retención del 15 % (total 127.200), corregida a 100.000 → base −20.000, IVA −4.200, retención −3.000, **total −21.200**; anulación completa → base −120.000, IVA −25.200, retención −18.000 (se devuelve), **total −127.200**.

#### 5.1.6 PDF y QR (D-03, D-10, D-11)

El PDF lleva: número y serie, **fecha de expedición**, el **emisor** (nombre, NIF, domicilio y el logo del perfil, que **solo se dibuja si mide 4 Mpx o menos**, medido con `Image.open().size` sin decodificarlo: B.1-A), el **cliente** (nombre, NIF o NIF-IVA y domicilio), el concepto, la base, el IVA con su tipo (o «Sin IVA»), la retención con su tipo, el **total**, la **mención legal** del tratamiento, el IBAN para el pago si el perfil lo tiene, y el **QR simulado** con su leyenda. La rectificativa lleva además «Factura rectificativa de la {número} de {fecha}», el motivo y los importes con signo. Sin hora actual ni identificadores aleatorios (`Canvas(invariant=1)`). **QR** (D-11, B.1-B): **arriba y centrado**, de **35 mm** y nivel **M**, con el texto `CUADRE-VERIFACTU-SIMULADO|{NIF}|{serie}-{NNN}|{DD-MM-AAAA}|{importe}` (fecha y importe en los formatos del QR real de la AEAT, con signo en una rectificativa) y debajo la leyenda «QR VeriFactu simulado, no remitido a la AEAT».

### 5.2 Base de datos

Migraciones nuevas (`YYYYMMDDHHMMSS_descripcion.sql`, sin destructivas; las ya aplicadas no se tocan). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`. El DDL es **la propuesta** que el spike del hito 0 comprueba en seco.

```
TYPE invoice_kind          AS ENUM ('standard', 'rectifying')
TYPE invoice_tax_treatment AS ENUM ('national_vat', 'eu_reverse_charge', 'eu_consumer_vat', 'non_eu_consumer_vat', 'non_eu_not_subject')
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
  CHECK ((kind = 'rectifying') = (rectifies_id IS NOT NULL))               -- invoices_rectification_ref
  CHECK ((kind = 'rectifying') = (rectification_reason IS NOT NULL))       -- invoices_rectification_reason (B.1-D: el CHECK único admitía dos combinaciones inválidas)
  CHECK (kind = 'rectifying' OR base_cents > 0)   -- la ordinaria siempre positiva; la rectificativa puede ser negativa
  CHECK (kind = 'standard' OR paid_at IS NULL)
INDEX invoices_owner_date ON invoices (owner_id, issue_date DESC, id)
INDEX invoices_rectifies ON invoices (rectifies_id) WHERE rectifies_id IS NOT NULL

invoice_files
  invoice_id  uuid PK REFERENCES invoices(id) ON DELETE RESTRICT
  storage_path text NOT NULL, sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'), size_bytes integer NOT NULL
  created_at timestamptz NOT NULL DEFAULT now()
```

Las restricciones llevan nombre propio (`invoices_total_matches`, `invoices_rectification_ref`, `invoices_rectification_reason`, `invoices_base_positive`, `invoices_rectifying_not_paid`, `invoices_owner_series_number_key`…) para que la API las traduzca por nombre; el CHECK único de la rectificativa de la primera versión de esta spec **se partió en dos** porque admitía una ordinaria con referencia pero sin motivo y al revés (B.1-D). **Trigger `invoices_immutable`** (`BEFORE UPDATE OR DELETE`, más `BEFORE TRUNCATE`): rechaza con `invoice_immutable` (P0001) todo `DELETE`, todo `TRUNCATE` y todo `UPDATE` en el que la fila, **sin `paid_at`**, cambie (`(to_jsonb(new) - 'paid_at') IS DISTINCT FROM (to_jsonb(old) - 'paid_at')`: no hay una lista de columnas que mantener); `invoice_files` es de solo inserción (sin `UPDATE`, `DELETE` ni `TRUNCATE`). **Límite**: el dueño de la base puede hacer `DISABLE TRIGGER`; la inmutabilidad lo es frente a la aplicación y a los roles de la API, no frente a quien administra la base. `app.set_invoice_paid` es la única que escribe `paid_at`.

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

**Cerrojos (obligatorios; B.1-D).** `app.issue_invoice` y `app.issue_rectifying_invoice` toman `SELECT … FOR UPDATE` de la **fila de la serie** (o `pg_advisory_xact_lock`: dan lo mismo) y comprueban la fecha **dentro** del cerrojo; `app.issue_rectifying_invoice` bloquea además la **fila de la original** (`FOR UPDATE`) antes de calcular la base vigente. Medido: sin cerrojo, 20 hilos × 5 emiten 18 de 100 (el resto cae en el `UNIQUE` con un error sin código útil) y cinco anulaciones simultáneas de una misma factura admiten 2 (se devuelve dos veces); con cerrojo, 100 de 100 sin huecos ni repetidos y exactamente una anulación.

**Cambios en SPEC-W-005 (B.1-D).** La migración que añade `kind` a `invoice_series` (por defecto `'standard'`) cambia: `private.series_lock_own` filtra `kind = 'standard'` (una serie rectificativa no se edita, no es predeterminada ni se archiva); `list_invoice_series` filtra `kind = 'standard'` (no sale en Perfil); `app.create_invoice_series` y `app.update_invoice_series` **reservan** los códigos `^R-\d{4}$` para las rectificativas (`series_code_reserved`); y `app.ensure_rectifying_series(p_year)` crea `R-{año}` sin ser predeterminada. El trigger `invoice_series_guard` **deja avanzar** `next_number` (lo que hace la emisión) y rechaza bajarlo.

**Storage.** Bucket privado `invoices` (solo `application/pdf`, hasta 1 MiB: un PDF típico mide de 8 a 18 KB), ruta `{owner_id}/{invoice_id}-{sha256[:16]}.pdf` (el prefijo de la huella hace **idempotente** la subida: el mismo contenido da siempre la misma ruta y un 409 de Storage significa «ya está»). Políticas como las de `logos` (funciones `private.invoice_file_*` que **nunca** lanzan errores; B.1-C lo midió): **insertar**, solo un `usuario` en su carpeta y con nombre de la forma exacta (la política se evalúa **al subir**); **leer**, el dueño o un gestor con vínculo activo (un vínculo revocado, otro usuario y el administrador reciben 404); **sin** `UPDATE` ni `DELETE` (reemplazar o borrar da 403: nadie puede sustituir un PDF subido). Que la persona pueda subir su propio archivo a una ruta de su carpeta no compromete la factura: la fila de `invoice_files` guarda la huella y la descarga la comprueba (D-03).

**Matriz de RLS.** `invoices` e `invoice_files`: `kind: financial`, `owner_column: owner_id` (en `invoice_files`, a través de la factura), privilegios `SELECT`, con `seed` y sondas de escritura.

**Seed (sintético).** Facturas de Alicia de los **cinco tratamientos** y una rectificativa, emitidas **por las propias funciones** desde `seed.sql` con `set_config('request.jwt.claims', …)` (B.1-E), con fechas **anteriores o iguales a hoy** y crecientes dentro de la serie. Para cubrirlos, el seed gana **dos clientes de Alicia** (un particular de la UE y uno de fuera de la UE, con domicilio) y se actualizan `test_clients_seed` y la matriz. Las facturas sembradas quedan con `pdf_status: "pending"` (el seed no dibuja PDF): se generan con «Generar PDF». Nombres y NIF inventados con dígitos de control válidos (RES-07).

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
InvoiceInput { client_id, series_id: uuid|null, issue_date: "AAAA-MM-DD", concept, base_cents: integer (estricto: `true`, `"120"` y `120.0` dan `validation_error`; el dominio comprueba de 1 a 9.999.999.999), vat_rate: "21.00"|"10.00"|"4.00"|null }
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
- **Modelos.** La **entrada es suelta** (`client_id`, `series_id`, `issue_date`, `concept` y `vat_rate` como `str` con `max_length`, `extra="forbid"`): una fecha `2026-02-30` o un cliente `no-uuid` llegan al dominio y salen en `invalid_invoice` con **todos los errores a la vez**. **`base_cents` va con `StrictInt | None`**: un `int` normal acepta `true`, `"120"`, `120.0` y `1e3` sin avisar (B.1-F). `paid` con `StrictBool`; la salida lleva uniones de literales. Importes siempre `int` de céntimos y tipos como cadenas `"21.00"`; **ningún `float`** (RES-02: un test lo vigila en código y migraciones).
- **PDF y QR** (B.1-A). `reportlab` 5.1.0 (BSD) con `Pillow` 13.0.0 y `charset-normalizer` 3.5.2: es la única que cubre `€`, `ñ` y acentos con las fuentes base y trae un QR decodificable (no `fpdf2`, que exige empaquetar una TTF y es LGPL, ni `segno`). `Pillow` es una rueda **con extensión nativa** (`manylinux` para Vercel; sin binarios del sistema). `Canvas(invariant=1)` y metadatos fijos: mismos bytes en Windows y Linux con la misma zlib. El logo se mide con `Image.open().size` y solo se dibuja si tiene 4 Mpx o menos (un PNG de 269 KiB y 88 Mpx cuesta 872 MiB y 2 s). `pypdf` 7.0.0 solo como dependencia de pruebas (extracción de texto).
- **Storage.** `StorageGateway` gana la **subida de bytes** (`POST /object/{bucket}/{ruta}` con el JWT de la persona) y la **descarga entera**. Storage responde HTTP 400 con el estado real en el cuerpo (409 «Duplicate», 403, 413, 415, 404); el 409 de una ruta con prefijo de huella es un éxito idempotente (B.1-C).
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
| T7-09 | **Dependencias nuevas mínimas** (B.1-A): `reportlab` 5.1.0, `Pillow` 13.0.0 y `charset-normalizer` 3.5.2 (y `pypdf` 7.0.0 solo en pruebas), fijadas por versión; sin binarios del sistema (`Pillow` es una rueda con extensión nativa); ninguna llama a la red |
| T7-10 | **El PDF es reproducible dentro de un mismo entorno** (mismos datos, mismos bytes; B.1-A lo midió idéntico entre Windows y Linux con la misma zlib) y su huella SHA-256 guardada **manda**: se comprueba en cada descarga |
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
  Given un particular de la UE, un particular español, un particular de fuera de la UE y una empresa de fuera de la UE
  When se emite una factura a cada uno
  Then el particular de la UE (eu_consumer_vat), el español (national_vat) y el de fuera de la UE (non_eu_consumer_vat) llevan IVA español sin retención
    And la de la empresa de fuera de la UE va sin IVA con el artículo 69 de la Ley del IVA (non_eu_not_subject)

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
  Then el PDF existe en el bucket invoices (ruta con el prefijo de su huella), lleva número, fecha, emisor, cliente, concepto, importes, mención legal y el QR simulado con su leyenda, y su SHA-256 coincide con el guardado
    And el PDF de los mismos datos, generado dos veces, es idéntico
    And si el archivo se altera, la descarga da 409 «invoice_pdf_corrupt»
    And si la generación falló al emitir, la factura queda con pdf_status «pending» y POST /pdf la completa sin duplicarla, también si el objeto ya estaba subido (el 409 de Storage no es un error)
    And un logo de más de 4 Mpx o ilegible no se dibuja y la factura sale sin él

AC-17  QR simulado (RES-04)
  Given cualquier factura
  When se mira su QR y su PDF
  Then el QR lleva el texto simulado de §5.1.6 (fecha DD-MM-AAAA e importe con punto decimal), mide 35 mm, va arriba y centrado y es de nivel M
    And la leyenda dice «QR VeriFactu simulado, no remitido a la AEAT», no aparece la frase «VERI*FACTU» y ninguna petición sale de la aplicación

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
- [ ] El seed lleva facturas sintéticas de los cinco tratamientos y una rectificativa, y las pruebas que dependían del menú se han revisado.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0011, 0015 y 0016 enlazados.
- [ ] Las preguntas abiertas P-02 y P-04 siguen anotadas en el Anexo B (P-01, P-03 y P-05 se resolvieron en el hito 0).
- [ ] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike**: con valores **sintéticos**, (a) qué librería de **PDF** y de **QR** (Python puro, fuentes con `ñ` y `€`) caben en una función de Vercel por tamaño, tiempo y reproducibilidad de los bytes; (b) la norma del **QR de VeriFactu** y el contenido mínimo de la **factura completa** (RD 1619/2012) y el texto de las **menciones** (P-03), con fuentes oficiales; (c) la **subida con el JWT** al bucket `invoices` y las políticas que no lancen errores; (d) el DDL de §5.2 en seco, con la **carrera de numeración** con y sin cerrojo, el trigger de inmutabilidad y `TRUNCATE`; (e) cómo **sembrar** facturas sin saltarse el trigger; (f) P-01 y P-02 con la persona. Resultado al Anexo B.
   **Hecho el 2026-11-10** (seis guiones desechables fuera del repositorio; resultado en el Anexo B.1: `reportlab` + `Pillow` y no `fpdf2`, reproducibilidad entre Windows y Linux, guarda de dimensiones del logo, normativa del Reglamento de facturación, del QR y de la Ley del IVA, Storage con el JWT, DDL con sus carreras y cerrojos, cambios en las series de SPEC-W-005, seed por las funciones y forma de la API; corrigió D-05, D-10, D-11, D-12, T7-09, T7-10, §5.1.2, §5.1.5, §5.1.6, §5.2, §5.3, §5.4, AC-03, AC-16 y AC-17, y cerró P-01, P-03 y P-05).
1. **Dominio puro**: `cuadre.tax` y `cuadre.invoicing` (condiciones, importes, número, validación, rectificativas, contenido del QR) con tablas de pruebas y mutaciones; `test_invoicing_boundary.py`.
2. **Base de datos**: migraciones (tipos, `kind` de serie, `invoices`, `invoice_files`, trigger, funciones, bucket y políticas), matriz de RLS y seed; pruebas de RLS, de trigger y de concurrencia; mutaciones.
3. **API**: emitir, previsualizar, listar, leer, cobrar, rectificar y `get_clients_billing`; `openapi.json` y `schema.d.ts` regenerados; mutaciones.
4. **PDF, QR y almacenamiento**: generación determinista, subida, huella, descarga con comprobación y reintento; pruebas de contenido y de alteración.
5. **Frontend**: `/facturas`, `/facturas/[id]`, menú, columna «Facturado en {año}» y condiciones en `/clientes`; unitarias; comprobación visual en los tres motores.
6. **E2E y cierre**: `factura.spec.ts` en tres motores y dos anchos, ajustes de `roles.spec.ts`, `responsive.spec.ts` y `env.ts`, mutaciones de la interfaz, Anexo B, `tasks.json`.

## Anexo B · Decisiones que esta spec dejó a la implementación

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-008 (303).** Lee `tax_treatment`, `base_cents`, `vat_cents` e `irpf_cents` de cada factura (con signo: las rectificativas restan en el periodo de **su** fecha de expedición), sin recalcular nada: `eu_reverse_charge` → casilla 59 y modelo 349; `non_eu_not_subject` → casilla 120; `national_vat`, `eu_consumer_vat` y `non_eu_consumer_vat` → IVA devengado por tipo. La retención y el 130 salen de `irpf_cents`.
- **SPEC-W-010 (gestor).** Las políticas de lectura de `invoices`, `invoice_files` y del bucket ya existen; faltan la pantalla y el registro de cada lectura.
- **SPEC-W-011 (MCP).** `buscar_facturas`, `resumen_mes`, `resumen_anio` y `gastos_por_categoria` leen estas tablas con el token acotado; el ámbito se mapea con `cuadre.clients.scope` (no se duplica).
- **SPEC-W-012 (cierre mensual) y SPEC-W-013 (reporte).** Cuentan las facturas por fecha de expedición, con las rectificativas restando; el cobro (`paid_at`) alimenta «pendiente de cobro».
- **SPEC-W-017 (CONF-004).** Las facturas no cascadean con la cuenta (`ON DELETE RESTRICT`): la conservación fiscal frente al borrado RGPD se resuelve ahí.

### B.1 Spike · hito 0 · 2026-11-10

Entorno: Windows 11, Python 3.12.10 (y 3.12.16 en el contenedor Linux), PostgreSQL 17.11 del Supabase local, `storage-api` v1.88.0, GoTrue v2.197.0, FastAPI 0.162.0, Pydantic 2.14.2, `openapi-typescript` (el del repositorio), Docker 29.6.2 y, solo para el spike, un `venv` **fuera del repositorio** con `reportlab` 5.1.0, `fpdf2` 2.9.0, `segno` 1.6.6, `qrcode` 8.2, `pypdf` 7.0.0, `zxing-cpp` 3.1.1, `Pillow` 13.0.0 y `psutil`. Seis guiones desechables fuera del repositorio (A a F). **No se ha tocado el proyecto**: la huella del esquema (`da121f8d…`) y el `pip freeze` (`120a09f4…`) son idénticos antes y después, no queda ningún bucket, esquema, política ni vínculo de prueba, y `activity_log` no tiene entradas nuevas.

**A · PDF y QR**

| Pregunta | Resultado |
|---|---|
| ¿Qué pesan y qué exigen los candidatos? | `reportlab` 4,65 MB (BSD; requiere `Pillow` y `charset-normalizer`), `fpdf2` 1,49 MB (**LGPL-3.0**; requiere `Pillow` y `fonttools`, de 12 MB), `segno` 0,39 MB (BSD), `qrcode` 0,23 MB. **Los dos de PDF exigen Pillow** (14,2 MB, MIT-CMU, con **extensiones nativas**: 8 archivos `.pyd`/`.so`), así que «Python puro» de T7-09 era falso: hacen falta **ruedas** (existen `manylinux` para Linux). Fuera de Pillow no hay binarios del sistema. Solo `Pillow` y `zxing-cpp` traen código nativo |
| Tiempo de importación (mediana de 3, Windows) | `reportlab.pdfgen.canvas` 141 ms (213 ms con su QR), `fpdf` 509 ms, `segno` 95 ms, `Pillow` 41 ms, `pypdf` 217 ms |
| ¿`€`, `ñ` y acentos con las fuentes base? | **`reportlab` sí** (Helvetica con WinAnsi: no hace falta incrustar una TTF). **`fpdf2` no**: sus fuentes base son latin-1 y falla con `FPDFUnicodeEncodingException` en el primer `€`; necesitaría una TTF empaquetada |
| Factura A4 con logo, concepto largo y QR | `reportlab`: **8.259 bytes** con logo PNG, **12.549** con JPEG y **18.425** con WebP (la rectificativa, 8.387, 12.678 y 18.554); **32 a 36 ms en caliente** y de 31 a 260 ms en frío (la primera llamada de un proceso: 260 ms en Windows y 170 ms en Linux). Pillow lee los tres formatos |
| QR | `reportlab.graphics.barcode.qr.QrCodeWidget` (sin `segno`): nivel M, **37×37 módulos (versión 5)** para 63 caracteres y también para 71 y 120; **zxing-cpp lo decodifica** y el texto coincide. `segno` y `qrcode` no hacen falta |
| ¿Mismos bytes siempre? | Con `Canvas(invariant=1)` (fecha de creación fija `D:20000101000000`): **15 repeticiones idénticas** en cada una de las seis combinaciones, **tres procesos distintos con el mismo SHA-256** (`41fb642d…`) y **Windows frente al contenedor `python:3.12-slim` con la misma versión de `reportlab`, `Pillow` y zlib (1.3.1): idénticos** en la ordinaria (`41fb642d…`) y en la rectificativa (`e385f522…`). Con otra versión de zlib no se ha probado |
| ¿Cómo se prueba el contenido? | `pypdf` (solo de pruebas) extrae todo el texto (737 y 845 caracteres): número, fecha de expedición, `Muñoz`, `Diseño`, `1.200,00 €`, `Inversión del sujeto pasivo`, `art. 69`, IBAN, leyenda del QR y, en la rectificativa, la referencia y el motivo; el título y el creador salen en los metadatos. El QR se comprueba regenerando su matriz de módulos con `reportlab`, sin decodificador |
| Un logo de ≤ 1 MiB (límite de SPEC-W-005) con dimensiones enormes | **Es un riesgo real**: un PNG de **269 KiB y 88 Mpx** tarda **1,9 s y llega a 872 MiB de memoria** en dibujarse (16 Mpx: 0,3 s y 180 MiB; 64 Mpx: 1,3 s y 639 MiB; 1 Mpx: 23 ms y 37 MiB). `Image.open(...).size` cuesta **0,2 ms y no decodifica** los píxeles; el límite de Pillow (89.478.485 px) no protege (avisa por encima, no impide 88 Mpx). W-005 solo comprobó el tipo y el tamaño del archivo, no las dimensiones |

**B · Normativa** (fuentes oficiales, consultadas el 2026-11-10 por lectores de páginas: lo literal va entre comillas; el resto es lectura y se marca)

| Pregunta | Resultado |
|---|---|
| Contenido de la factura completa (RD 1619/2012, art. 6.1; [BOE-A-2012-14696](https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696), «Última actualización publicada el 31/03/2026») | Literal: «Toda factura y sus copias contendrán los datos o requisitos que se citan a continuación». a) número y, en su caso, serie: «La numeración de las facturas dentro de cada serie será correlativa»; b) fecha de expedición; c) nombre y apellidos o razón social del emisor **y del destinatario**; d) **NIF del emisor**; el del destinatario, **solo** en entregas intracomunitarias exentas, en operaciones cuyo destinatario es el sujeto pasivo y en operaciones en territorio español con un obligado allí establecido; e) **domicilio del emisor y del destinatario**; f) descripción de las operaciones, precio unitario sin IVA y descuentos; g) tipo o tipos impositivos; h) cuota «consignada por separado»; i) fecha de las operaciones si es distinta de la de expedición; j) operaciones exentas; m) «inversión del sujeto pasivo»; apartado 5 (RD 1007/2023): el QR y la frase de VERI*FACTU. **No hay letra propia para operaciones no sujetas.** Confirma D-04 (domicilio) y la serie correlativa; **la mención de la inversión del sujeto pasivo es literal; la del artículo 69 es práctica habitual, no un texto impuesto** |
| Rectificativas (art. 15) | Literal: se expide factura rectificativa cuando no se cumplen los requisitos de los arts. 6 o 7, cuando las cuotas «se hubiesen determinado incorrectamente» o se dan las circunstancias del art. 80 de la Ley del IVA; «La rectificación se realizará mediante la emisión de una nueva factura» con «los datos identificativos de la factura rectificada» (15.4); los datos de las letras f), g) y h) «expresarán la rectificación efectuada» y pueden consignarse «con independencia de su signo» el importe de la rectificación, o los valores tras la rectificación y además el importe de la rectificación (15.5); plazo de **cuatro años** desde el devengo (15.3). **El texto no nombra «sustitución» ni «diferencias» ni exige expresamente una causa**: nuestro modelo (importe de la rectificación con signo, referencia a la original y motivo) cumple 15.4 y 15.5; el motivo es una decisión de la spec. Las series rectificativas son de las series separadas que prevé el art. 6.1.a |
| Factura electrónica obligatoria (RD 238/2026, de 25 de marzo; BOE núm. 79, de 31/03/2026, en vigor el 20/04/2026) | **No estaba en el PRD ni en la spec.** Impone la factura electrónica entre empresarios y profesionales en operaciones **con destinatario que tenga sede, establecimiento o domicilio en España** (art. 8 bis del RD 1619/2012), no a facturas simplificadas ni, según el preámbulo, a consumidores finales. Su aplicación efectiva «queda diferida» a una orden ministerial de desarrollo (12 meses para quien facture más de 8 M€ y 24 meses para el resto, incluidas las personas físicas) que **no consta** en lo leído. Es la parte «B2B» de lo que PRD y charter dejan **fuera de la v1**: se anota como riesgo (R-06) y como exclusión, no se implementa |
| QR de VERI*FACTU (Orden HAC/1177/2024 y páginas de la AEAT) | Contenido: URL del servicio de cotejo con `nif`, `numserie`, `fecha` (`DD-MM-AAAA`) e `importe` (con punto decimal): `https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?…` (VERI*FACTU) y `…/ValidarQRNoVerifactu?…` (no verificable). Tamaño **entre 30×30 y 40×40 mm** (FAQ de la AEAT), nivel de corrección **M** y norma **ISO/IEC 18004** (según la orden, por resumen del buscador: no leído literal), **el primer QR de la factura, arriba y preferiblemente centrado** (FAQ). El QR es obligatorio en las facturas de **cualquier** sistema informático de facturación; la frase «VERI*FACTU» o «Factura verificable en la sede electrónica de la AEAT» solo en los verificables. **Nada dice cómo se representa una rectificativa o un importe negativo.** El PDF técnico del QR solo se pudo leer en parte |
| Localización de los servicios (Ley 37/1992, art. 69; [BOE-A-1992-28740](https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740), «Última actualización, publicada el 07/10/2026») | Uno.1.º: servicios a «un empresario o profesional que actúe como tal y radique en el citado territorio» se localizan en España; Uno.2.º: a quien **no** es empresario o profesional, si el prestador está establecido en España; **Dos**: excepción para destinatarios que **no son empresarios y están establecidos fuera de la Comunidad**, solo para la lista de las letras a) a l) (cesiones de derechos de propiedad intelectual o industrial, publicidad, asesoramiento, ingeniería y «gabinete de estudios», tratamiento de datos, traducción, seguros, cesión de personal…); **«diseño» no aparece literalmente**. Consecuencia: **un cliente de fuera de la UE que es empresa no soporta IVA español; uno que es particular sí, salvo que el servicio esté en esa lista** (lectura mía; el art. 84.Uno.2.º, sujeto pasivo, no se leyó entero) |
| Tipos del IVA | 21 %, 10 % y 4 % vigentes en 2026 ([tipos de la AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/calculo-iva-repercutido-clientes/tipos-impositivos-iva.html), por resumen del buscador; los arts. 90 y 91 no se pudieron leer enteros). El RDL 29/2026 (efectos desde el 1 de diciembre de 2026) cambia tipos de vivienda, no de servicios profesionales |

**C · Storage con el JWT de la persona** (bucket de prueba `spike_w007_invoices`, 1 MiB y solo `application/pdf`; políticas con funciones que nunca lanzan errores, como `logos`; Storage devuelve HTTP 400 con el estado real en `statusCode`)

| Pregunta | Resultado |
|---|---|
| Subida **desde el servidor** (`POST /object/{bucket}/{ruta}` con el JWT y el cuerpo en bruto) | **200** (163 ms la primera, **19 ms** de mediana después). La política de INSERT se evalúa **al subir** |
| Segunda subida a la misma ruta | **409 `Duplicate`**. Con `x-upsert: true`, `PUT` o `DELETE` del dueño: **403** (no hay política de `UPDATE` ni de `DELETE`); el objeto sigue igual. **Nadie puede sustituir ni borrar un PDF** ya subido |
| Descarga entera con el JWT | Dueño **200** (13 ms, 8.259 bytes, **huella idéntica**, `application/pdf`); gestora con vínculo **activo** 200 e igual huella; vínculo **revocado**, otro usuario, gestor sin vínculo y administrador: **404** |
| Quién puede subir | Alicia a la carpeta de Beto, la gestora y el administrador a la suya y los nombres raros (`not-a-uuid/…`, `factura.pdf`, `.png`, subcarpeta, uuid en mayúsculas): **403**. Leer `not-a-uuid/x.pdf`: **404** (la política no lanza error) |
| Límites | 1 MiB exacto: 200; +1 byte: **413**; `text/plain`: **415** `invalid_mime_type`; `application/pdf; charset=binary`: 200; **un texto subido como `application/pdf` entra** (no mira el contenido). Un PDF típico mide 8 a 18 KB: el límite de 1 MiB sobra |
| Reintento tras un huérfano | Subir otra vez da **409**; `object/info` (tamaño 8.259) y la descarga (huella igual) **reconocen el objeto existente**; `Range: bytes=0-4` devuelve 206 y `%PDF-`. Como el PDF es reproducible, **generar de nuevo y subir da 409 y la huella coincide**: el reintento es idempotente |
| Limpieza | `DELETE` de objetos por SQL **no se permite** (`storage.protect_delete`): se vacía y borra el bucket por la API de Storage (con la clave de servicio **local**, solo para esto y fuera del repositorio) |

**D · Base de datos** (esquema desechable `spike_w007` en PostgreSQL 17, 100.290 filas para los planes)

| Pregunta | Resultado |
|---|---|
| ¿Compila el DDL de §5.2? | Sí, con las restricciones con nombre. **El CHECK `(kind = 'rectifying') = (rectifies_id IS NOT NULL AND rectification_reason IS NOT NULL)` deja pasar dos combinaciones inválidas**: una ordinaria con referencia pero sin motivo, y una con motivo pero sin referencia. Se parte en **dos**: `invoices_rectification_ref` y `invoices_rectification_reason`, que rechazan las dos. El resto: base 0 o negativa en una ordinaria, total que no cuadra, número 0 o 1.000.000, rectificativa sin motivo, rectificativa cobrada y número repetido (`invoices_owner_series_number_key`) se rechazan por nombre; una rectificativa negativa y la base máxima (9.999.999.999 con IVA y retención) se admiten |
| `ON DELETE RESTRICT` | Borrar un perfil o una serie con facturas: **rechazado** (`…_owner_id_fkey`) |
| Trigger de inmutabilidad | Con `(to_jsonb(new) - 'paid_at') IS DISTINCT FROM (to_jsonb(old) - 'paid_at')` (no hay que mantener una lista de columnas): `UPDATE` de `paid_at` (marcar y desmarcar) **sí**; de `concept`, `base_cents`, `client_id`, `issue_date`, `number`, `legal_note` y `owner_id`, **no** (`invoice_immutable`); `DELETE` y `TRUNCATE`, **no**; también para `service_role`. Un `UPDATE` sin cambios reales pasa. `invoice_files` de solo inserción (`UPDATE`, `DELETE` y un segundo `INSERT` rechazados). **Límite**: `postgres` (no es superusuario) puede hacer `DISABLE TRIGGER`: la inmutabilidad es frente a la aplicación y a los roles de la API, **no frente al dueño de la base** |
| Numeración **sin cerrojo** | 5 hilos a la vez: **1 de 5** emitidas, 4 errores `23505`; 20 hilos × 5: **18 de 100** y 82 errores. El `UNIQUE (owner, serie, número)` impide los duplicados, pero **no es un cerrojo** y el error no tiene código útil |
| Numeración **con cerrojo** (`FOR UPDATE` de la fila de la serie, o `pg_advisory_xact_lock`) | 5 hilos: **5 de 5**; 20 hilos × 5: **100 de 100**, sin repetidos ni huecos y sin errores, en 249 ms; las dos formas dan lo mismo. Un fallo a mitad de la emisión **no consume** el número (el siguiente es el 2); la comprobación «fecha no anterior a la última de la serie» dentro del cerrojo rechaza `invoice_date_out_of_order` |
| Rectificaciones a la vez sobre la misma original | Cinco anulaciones completas simultáneas: **sin cerrojo** se admiten **2** y la base vigente final es **−100.000** (se devuelve dos veces); **con `FOR UPDATE` de la original**, **1 admitida y 4 `rectification_exceeds`**, base vigente 0 |
| Planes (100.290 filas, 2.000 por persona) | Lista del año con `(owner_id, issue_date DESC, id)`: **0,20 ms**, `Index Scan` + ordenación incremental; «Facturado en el año»: **0,32 ms** con el mismo índice; un segundo índice `(owner, cliente, fecha) INCLUDE (base)` **no se usa ni hace falta** |
| RLS (políticas de dueño y de gestor) | Alicia 2.005 filas, Beto 236, **Gina con vínculo activo con Alicia 2.005**, administrador **0**; un `INSERT` directo del dueño: `permission denied` (solo `SELECT` concedido) |
| `private.log_activity('data', …, 'invoice.issued', …)` | Escribe la fila con el metadato `{series_code, number, tax_treatment}` (deshecho: `activity_log` es de solo inserción) |

**Qué hay que tocar de SPEC-W-005 al añadir `kind` a `invoice_series`** (revisado en `20261107200100` y `20261107200200` y en `profile/repository.py`): la columna `kind invoice_kind NOT NULL DEFAULT 'standard'` no rompe nada existente. (1) `private.series_lock_own` (la usan `update`, `set_default` y `archive`) filtra `kind = 'standard'`, así que una serie rectificativa es «no encontrada» para esas operaciones (no se edita, no es predeterminada, no se archiva); la emisión usa un cerrojo propio sin filtro. (2) `list_invoice_series` filtra `kind = 'standard'` (la serie `R-` no aparece en Perfil ni se puede elegir). (3) `app.ensure_year_series` no cambia (la predeterminada solo se mira entre ordinarias porque la rectificativa nunca lo es). (4) **El código `R-{año}` comparte el espacio de nombres `(owner, code)` de las ordinarias**: si la persona crea antes una ordinaria llamada `R-2026`, la rectificativa no se podría crear; `app.create_invoice_series` y `app.update_invoice_series` **reservan** los códigos que cumplen `^R-\d{4}$`. (5) El trigger `invoice_series_guard` **deja avanzar `next_number`** y rechaza bajarlo (`series_number_regression`) y cambiar código o número inicial de una serie en uso (`series_in_use`): `app.issue_invoice` puede hacer su `UPDATE` sin tocar el trigger.

**E · Seed** (transacciones deshechas)

| Pregunta | Resultado |
|---|---|
| ¿Puede `seed.sql` emitir por las funciones? | **Sí**: `seed.sql` corre como `postgres` (no superusuario); con `set_config('request.jwt.claims', '{"sub": "<uuid>", "role": "authenticated"}', true)` en la transacción, `auth.uid()` es Alicia, `private.app_role()` es `usuario`, `private.today_madrid()` es el día real y `app.ensure_year_series()` devuelve su serie. Con las claims de la gestora la misma función da `42501` |
| Reloj | `private.today_madrid()` es el día real: las fechas de las facturas del seed han de ser **anteriores o iguales a hoy** (y crecientes dentro de la serie), no fijas en el futuro |
| Datos del seed | Alicia: perfil completo con retención **7 %**, IBAN y domicilio, y tres clientes **con domicilio** (nacional, UE empresa y México empresa). **No hay particulares** de la UE ni de fuera de la UE en la cuenta de Alicia: para cubrir todos los tratamientos el seed gana dos clientes (un particular de la UE y uno de fuera de la UE) y `test_clients_seed` se actualiza |
| Efecto lateral | Cada factura escribe `activity_log` (de solo inserción): es lo esperado en el seed |
| PDF del seed | El seed **no puede dibujar PDF** (no hay Python en SQL): las facturas sembradas quedan con `pdf_status: "pending"` y se generan al pulsar «Generar PDF» (`POST /api/invoices/{id}/pdf`), que es además la prueba del camino de reintento |

**F · Forma de la API** (modelos de Pydantic en seco y generador)

| Pregunta | Resultado |
|---|---|
| `base_cents` como `int` normal | **Acepta `true` (como 1), `"120"`, `120.0` y `1e3`** sin avisar; rechaza `120.5` con un error de Pydantic. **`StrictInt` rechaza todos** (`int_type`, 422 `validation_error`). La interfaz solo envía enteros (`parseAmount` los convierte), así que es un error de forma y no de la persona: `StrictInt \| None` y el dominio comprueba el rango (1 a 9.999.999.999) |
| Resto de la entrada | `client_id`, `series_id`, `issue_date` y `concept` van como `str \| None` con `max_length` y `extra="forbid"`: una fecha `2026-02-30` y un cliente `no-uuid` **llegan al dominio** y salen en `invalid_invoice` con todos los errores a la vez; un campo de más (`scope`) da `extra_forbidden` y `vat_rate` numérico (`21`) da `string_type`; `"21.00"` pasa |
| Cliente TypeScript | `InvoiceOut` sale con las uniones de literales (`kind`, `tax_treatment`, `pdf_status`), `base_cents: number`, `paid_at: string \| null` y el cliente anidado; la entrada, `base_cents?: number \| null` |
| Respuesta PDF | Con `response_class=Response` y `responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}}`, el generador da `content: { "application/pdf": string }`; el Route Handler de Next la pedirá con `openapi-fetch` (`parseAs: "arrayBuffer"`, no probado aquí) |
| Importes en la interfaz | `lib/money.ts` (`parseAmount`) ya lee `1.234,50`, `1234,5`, `1234.50` y `12 €`, y **rechaza `1.200` sin coma por ambiguo**: la ayuda del campo dice «por ejemplo 1.200,00» |

**Lo que no se ha comprobado:**
- **El calendario de VERI*FACTU para autónomos y el aplazamiento** que cita el PRD (DEP-07): ni las páginas de la AEAT ni lo leído del BOE los confirman.
- **El PDF técnico del QR entero** (nivel M e ISO/IEC 18004 salen del resumen de la orden): la spec usa lo medido (nivel M, 35 mm), que cumple lo citado.
- **Cuándo se aplicará la factura electrónica B2B**: depende de una orden ministerial que no consta.
- **El PDF byte a byte con otra versión de zlib** (por ejemplo, la de la función de Vercel): idéntico entre Windows y Linux con la misma, sin garantía más allá. Por eso la **huella guardada manda** y la reproducibilidad solo se exige dentro de un mismo entorno.
- **Las ruedas de `Pillow` y `reportlab` en Vercel**: existen para `manylinux`, pero no se ha desplegado (ADR-0016: «decidido, aún sin desplegar»); tampoco el peso real de la función.
- **El art. 84.Uno.2.º** (sujeto pasivo en servicios de empresarios de otro Estado miembro) y el umbral de ventanilla única (OSS) de las ventas a particulares de la UE: no se modelan.
- **Storage en producción**: las políticas y los códigos se midieron en el local (`storage-api` v1.88.0).
- **Veinte hilos son pocos** para decir nada de la carga real; sí demuestran que sin cerrojo hay pérdidas y con él no.
- **El texto de la mención del artículo 69**: es práctica habitual, no un texto impuesto; la inversión del sujeto pasivo sí es literal del Reglamento.

**Consecuencias para los hitos siguientes** (ya reflejadas en §1, §5 y los criterios):
- **Hito 1.** Cinco tratamientos fiscales (`national_vat`, `eu_reverse_charge`, `eu_consumer_vat`, `non_eu_consumer_vat`, `non_eu_not_subject`); el particular de fuera de la UE lleva IVA español (**P-05, decidida**) y no se modela la excepción del 69.Dos; textos de las menciones; contenido del QR con `DD-MM-AAAA` e importe con punto; tablas de importes con el redondeo simétrico; `pypdf` solo como dependencia de pruebas.
- **Hito 2.** Migraciones con los dos CHECK de la rectificativa, el trigger genérico de inmutabilidad y los de `invoice_files`; el cerrojo `FOR UPDATE` de la serie (y de la original al rectificar) **obligatorio**; `kind` en `invoice_series` con los cambios de W-005 de arriba y los códigos `R-AAAA` reservados; bucket `invoices` con `application/pdf` y 1 MiB; seed con dos clientes más y facturas emitidas por las funciones, con fechas ≤ hoy; `test_clients_seed` actualizado.
- **Hito 3.** `base_cents: StrictInt \| None`; entrada suelta en lo demás; `StorageGateway` gana la subida de bytes y la descarga entera con el JWT (hoy solo firma y mira); la API traduce el 409 de Storage como «ya existe» y el 400 con el estado real en el cuerpo.
- **Hito 4.** `reportlab` 5.1.0, `Pillow` 13.0.0 y `charset-normalizer` 3.5.2 (no `fpdf2` ni `segno`), `Canvas(invariant=1)`, fuentes base; **el logo solo se dibuja si mide ≤ 4 Mpx** (se lee con `Image.open().size`); ruta `{owner_id}/{invoice_id}-{sha256[:16]}.pdf` (el 409 es éxito idempotente tras comprobar la huella); QR de 35 mm, nivel M, arriba y centrado; leyenda «QR VeriFactu simulado, no remitido a la AEAT»; `POST /pdf` como reintento y «Generar PDF» para el seed.
- **Hito 5.** La pantalla ofrece «Generar PDF» cuando `pdf_status` es `pending`; los selectores y la lista usan los nombres de país del servidor (lección de SPEC-W-006).
- **Hito 6.** `factura.spec.ts` no puede borrar facturas: cuentas nuevas por worker.
