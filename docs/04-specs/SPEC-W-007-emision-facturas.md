---
tipo: spec
id: SPEC-W-007
titulo: Emisión de facturas: inmutables, numeración, mención legal, PDF, QR simulado y rectificativas
estado: hecha
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

`vat_cents = round(base_cents × vat_rate / 100)` y `irpf_cents = round(base_cents × irpf_rate / 100)`, en `Decimal` con `ROUND_HALF_UP` (el de `cuadre.validators.vat.percentage_of`); `total_cents = base_cents + vat_cents − irpf_cents`. Una rectificativa **no** calcula un porcentaje de un importe negativo (desvía céntimos en cadenas de rectificaciones: B.2): sus cuotas son las de la base corregida menos las vigentes (§5.1.5).

Ejemplos (fijan las pruebas de tabla):

| Caso | Base | IVA | Retención | Total |
|---|---|---|---|---|
| Nacional empresa, 21 % y retención del 15 % | 120.000 | 25.200 | 18.000 | 127.200 |
| UE empresa, inversión del sujeto pasivo (US-006) | 150.000 | 0 | 0 | 150.000 |
| UE particular, 21 % | 100.000 | 21.000 | 0 | 121.000 |
| Fuera de la UE, empresa | 50.000 | 0 | 0 | 50.000 |
| Fuera de la UE, particular, 21 % | 100.000 | 21.000 | 0 | 121.000 |
| Redondeo hacia arriba en el medio céntimo (base 1.050 al 10 %) | 1.050 | 105 | 0 | 1.155 |
| Anulación de 105 al 10 % en dos pasos, −52 y −53 (suma de las dos rectificativas) | −105 | −11 | 0 | −116 |

#### 5.1.4 Número, serie y fechas

El número visible es `{serie}-{NNN}`, con el número a **tres dígitos como mínimo** (`2026-001`; a partir del 1000, `2026-1000`). El número es el `next_number` de la serie en el momento de emitir, que avanza en la misma transacción; **no hay huecos** (si la emisión falla, no se consume) y **no se repite** (cerrojo por serie). La serie del año la crea `app.ensure_year_series` si no existe (D-07 de SPEC-W-005); una serie archivada no se ofrece.

#### 5.1.5 Rectificativas (D-12)

Entrada: la factura original (`rectifies`), el **motivo** (2 a 300 caracteres, sin saltos de línea), la **base corregida** (`corrected_base_cents`, de 0 a la base vigente) o la anulación completa (base corregida 0) y la fecha de expedición.

El Reglamento no nombra «por sustitución» ni «por diferencias» (art. 15.4 y 15.5; B.1-B): esta spec expresa **el importe de la rectificación con signo**, con la referencia a la original y un motivo (decisión de la spec, no del Reglamento). El plazo de **cuatro años desde el devengo** (art. 15.3) **no se comprueba**.

- La **base de la rectificativa** es `corrected_base_cents − base vigente`, donde la base vigente es la de la original más las diferencias de sus rectificativas anteriores. El IVA y la retención son **los de la base corregida, con los tipos y el tratamiento de la original, menos los vigentes** (art. 15.5, «los valores tras la rectificación»), nunca un porcentaje del importe negativo: así la factura corregida cuadra al céntimo con cualquier cadena de rectificaciones (B.2).
- Va en la **serie rectificativa** del año (`R-{año}`, `kind = 'rectifying'`), con su propia numeración correlativa y las reglas de fecha de 5.1.4 aplicadas a **esa** serie; la fecha tampoco puede ser anterior a la de la original.
- Lleva la copia del cliente y de las condiciones de la original; el emisor, el actual (D-09 se aplica a cada factura al emitirse).
- `rectification_exceeds` (409) si la base corregida es mayor que la vigente (una rectificativa no sube la factura: eso es una factura nueva) o negativa; no se puede rectificar una rectificativa (`invoice_not_rectifiable`); una rectificativa **no se cobra** (D-13).
- Ejemplo: original de base 120.000 al 21 % con retención del 15 % (total 127.200), corregida a 100.000 → base −20.000, IVA −4.200, retención −3.000, **total −21.200**; anulación completa → base −120.000, IVA −25.200, retención −18.000 (se devuelve), **total −127.200**.

#### 5.1.6 PDF y QR (D-03, D-10, D-11)

El PDF lleva: número y serie, **fecha de expedición**, el **emisor** (nombre, NIF, domicilio y el logo del perfil, que **solo se dibuja si mide 4 Mpx o menos**, medido con `Image.open().size` sin decodificarlo: B.1-A), el **cliente** (nombre, NIF o NIF-IVA y domicilio), el concepto, la base, el IVA con su tipo (o «Sin IVA»), la retención con su tipo, el **total**, la **mención legal** del tratamiento, el IBAN para el pago si el perfil lo tiene, y el **QR simulado** con su leyenda. La rectificativa lleva además «Factura rectificativa de la {número} de {fecha}», el motivo y los importes con signo. Sin hora actual ni identificadores aleatorios (`Canvas(invariant=1)`). **QR** (D-11, B.1-B): **arriba y centrado**, de **35 mm** y nivel **M**, con el texto `CUADRE-VERIFACTU-SIMULADO|{NIF}|{serie}-{NNN}|{DD-MM-AAAA}|{importe}` (fecha y importe en los formatos del QR real de la AEAT, con signo en una rectificativa) y debajo la leyenda «QR VeriFactu simulado, no remitido a la AEAT». Los 35 mm incluyen la zona de silencio; la retención solo se escribe si su tipo no es 0 y «Sin IVA» sustituye a la línea del IVA cuando su tipo es 0. Helvetica no tiene todas las letras: `reportlab` **no falla**, dibuja un cuadrado negro, así que el texto pasa por `pdf_text` (lo que cabe en WinAnsi tal cual, el resto sin signo y lo que no cabe, `?`: B.5).

### 5.2 Base de datos

Migraciones nuevas (`YYYYMMDDHHMMSS_descripcion.sql`, sin destructivas; las ya aplicadas no se tocan). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`. El DDL es **la propuesta** que el spike del hito 0 comprueba en seco.

```
TYPE invoice_kind          AS ENUM ('standard', 'rectifying')
TYPE invoice_tax_treatment AS ENUM ('national_vat', 'eu_reverse_charge', 'eu_consumer_vat', 'non_eu_consumer_vat', 'non_eu_not_subject')
ALTER TABLE invoice_series ADD COLUMN kind invoice_kind NOT NULL DEFAULT 'standard'
  CHECK ((kind = 'rectifying') = (code ~ '^R-[0-9]{4}$'))      -- invoice_series_kind_matches_code (B.3)
  CHECK (kind = 'standard' OR NOT is_default)                  -- invoice_series_rectifying_not_default
  UNIQUE (id, owner_id, kind)                                  -- para la clave foránea de las facturas; ALTER TABLE clients ADD UNIQUE (id, owner_id)

invoices
  id                uuid PK DEFAULT gen_random_uuid()
  owner_id          uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT       -- no cascadea (CONF-004, RES-03)
  series_id         uuid NOT NULL                                                   -- FK (series_id, owner_id, kind) → invoice_series, ON DELETE RESTRICT (B.3)
  series_code       text NOT NULL                                                   -- copia: el código de una serie usada no cambia, pero la factura no depende de ello
  number            integer NOT NULL CHECK (number BETWEEN 1 AND 999999)
  kind              invoice_kind NOT NULL
  issue_date        date NOT NULL
  client_id         uuid NOT NULL                                                   -- FK (client_id, owner_id) → clients, ON DELETE RESTRICT (B.3)
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
  rectifies_id      uuid                                                            -- FK (rectifies_id, owner_id) → invoices (id, owner_id), ON DELETE RESTRICT (B.3)
  rectification_reason text CHECK (char_length(rectification_reason) BETWEEN 2 AND 300)
  paid_at           timestamptz                                                      -- lo ÚNICO modificable
  created_at        timestamptz NOT NULL DEFAULT now()
  UNIQUE (owner_id, series_id, number), UNIQUE (id, owner_id)
  CHECK (total_cents = base_cents + vat_cents - irpf_cents)
  CHECK (base_cents BETWEEN -9999999999 AND 9999999999), CHECK (issue_date >= '2000-01-01'), CHECK (vat_rate IN (0, 4, 10, 21)), CHECK (irpf_rate IN (0, 7, 15))   -- B.3
  CHECK (kind = 'standard' OR base_cents < 0)                       -- invoices_rectifying_base_negative (B.3)
  CHECK ((kind = 'standard' AND vat_cents >= 0 AND irpf_cents >= 0) OR (kind = 'rectifying' AND vat_cents <= 0 AND irpf_cents <= 0))   -- invoices_amounts_sign (B.3)
  CHECK ((kind = 'rectifying') = (rectifies_id IS NOT NULL))               -- invoices_rectification_ref
  CHECK ((kind = 'rectifying') = (rectification_reason IS NOT NULL))       -- invoices_rectification_reason (B.1-D: el CHECK único admitía dos combinaciones inválidas)
  CHECK (kind = 'rectifying' OR base_cents > 0)   -- la ordinaria siempre positiva; la rectificativa puede ser negativa
  CHECK (kind = 'standard' OR paid_at IS NULL)
INDEX invoices_owner_date ON invoices (owner_id, issue_date DESC, id)
INDEX invoices_rectifies ON invoices (rectifies_id) WHERE rectifies_id IS NOT NULL

invoice_files
  invoice_id  uuid PK
  owner_id    uuid NOT NULL                                  -- el de la factura; FK (invoice_id, owner_id) → invoices (id, owner_id) ON DELETE RESTRICT (B.3: la política y la matriz son de una columna)
  storage_path text NOT NULL, sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'), size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 1048576)
  created_at timestamptz NOT NULL DEFAULT now()
  CHECK (storage_path = owner_id || '/' || invoice_id || '-' || substr(sha256, 1, 16) || '.pdf')   -- invoice_files_path_matches
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
| `app.issue_invoice(p_client_id, p_series_id, p_issue_date, p_concept, p_base_cents, p_terms jsonb)` (el tipo de IVA va dentro de `p_terms`, que lleva las siete condiciones: B.3) | Comprueba el perfil, el cliente (activo, con domicilio), la serie (activa, ordinaria) y las fechas; copia emisor y cliente; escribe las condiciones que le pasa la API ya calculadas (la base **repite** las comprobaciones baratas y la identidad aritmética `total = base + IVA − retención`, no la regla fiscal: D-10 de SPEC-W-006 aplica igual); asigna `next_number` y lo avanza; escribe `activity_log`. Devuelve el id |
| `app.issue_rectifying_invoice(p_original_id, p_reason, p_corrected_base_cents, p_issue_date, p_terms jsonb)` | Lo anterior para la serie rectificativa del año (`app.ensure_rectifying_series`), con las reglas de 5.1.5 (`rectification_exceeds`, `invoice_not_rectifiable`, fecha). `p_terms` lleva solo `vat_cents`, `irpf_cents` y `total_cents`; **la base y lo vigente los calcula la base de datos bajo el cerrojo** y el resto se hereda de la original (B.3) |
| `app.set_invoice_paid(p_id, p_paid)` | Marca o desmarca `paid_at` de una factura ordinaria (`invoice_not_payable` si es rectificativa) y lo registra |
| `app.attach_invoice_pdf(p_invoice_id, p_path, p_sha256, p_size)` | Inserta **una sola vez** la fila de `invoice_files` de una factura propia (`invoice_pdf_exists` si ya hay) |
| `app.ensure_rectifying_series(p_year)` | Crea `R-{año}` si no existe, idempotente, como `app.ensure_year_series` |

Los errores `P0001` son `invoice_not_found`, `client_not_found`, `client_not_billable`, `series_not_found`, `profile_incomplete`, `irpf_rate_missing`, `invoice_date_out_of_order`, `invalid_invoice` (campo en el `DETAIL`), `rectification_exceeds`, `invoice_not_rectifiable`, `invoice_not_payable`, `invoice_immutable`, `invoice_pdf_exists` y `series_exhausted` (la serie llegó al 999.999); las de series añaden `series_code_reserved` (B.3).

**Cerrojos (obligatorios; B.1-D).** `app.issue_invoice` y `app.issue_rectifying_invoice` toman `SELECT … FOR UPDATE` de la **fila de la serie** (o `pg_advisory_xact_lock`: dan lo mismo) y comprueban la fecha **dentro** del cerrojo; `app.issue_rectifying_invoice` bloquea además la **fila de la original** (`FOR UPDATE`) antes de calcular la base vigente. Se ponen **las dos capas**, siempre en el mismo orden (persona → serie → cliente con `FOR SHARE` → original), para no abrir interbloqueos (B.3). Medido: sin cerrojo, 20 hilos × 5 emiten 18 de 100 (el resto cae en el `UNIQUE` con un error sin código útil) y cinco anulaciones simultáneas de una misma factura admiten 2 (se devuelve dos veces); con cerrojo, 100 de 100 sin huecos ni repetidos y exactamente una anulación.

**Cambios en SPEC-W-005 (B.1-D).** La migración que añade `kind` a `invoice_series` (por defecto `'standard'`) cambia: `private.series_lock_own` filtra `kind = 'standard'` (una serie rectificativa no se edita, no es predeterminada ni se archiva); `list_invoice_series` filtra `kind = 'standard'` (no sale en Perfil); `app.create_invoice_series` y `app.update_invoice_series` **reservan** los códigos `^R-\d{4}$` para las rectificativas (`series_code_reserved`); y `app.ensure_rectifying_series(p_year)` crea `R-{año}` sin ser predeterminada. El trigger `invoice_series_guard` **deja avanzar** `next_number` (lo que hace la emisión) y rechaza bajarlo.

**Storage.** Bucket privado `invoices` (solo `application/pdf`, hasta 1 MiB: un PDF típico mide de 8 a 18 KB), ruta `{owner_id}/{invoice_id}-{sha256[:16]}.pdf` (el prefijo de la huella hace **idempotente** la subida: el mismo contenido da siempre la misma ruta y un 409 de Storage significa «ya está»). Políticas como las de `logos` (funciones `private.invoice_file_*` que **nunca** lanzan errores; B.1-C lo midió): **insertar**, solo un `usuario` en su carpeta y con nombre de la forma exacta (la política se evalúa **al subir**); **leer**, el dueño o un gestor con vínculo activo (un vínculo revocado, otro usuario y el administrador reciben 404); **sin** `UPDATE` ni `DELETE` (reemplazar o borrar da 403: nadie puede sustituir un PDF subido). Que la persona pueda subir su propio archivo a una ruta de su carpeta no compromete la factura: la fila de `invoice_files` guarda la huella y la descarga la comprueba (D-03).

**Matriz de RLS.** `invoices` e `invoice_files`: `kind: financial`, `owner_column: owner_id` (`invoice_files` lleva su propio `owner_id`, B.3), privilegios `SELECT`, con `seed` y sondas de escritura.

**Seed (sintético).** Facturas de Alicia de los **cinco tratamientos** y una rectificativa, emitidas **por las propias funciones** desde `seed.sql` con `set_config('request.jwt.claims', …)` (B.1-E), con fechas **anteriores o iguales a hoy** y crecientes dentro de la serie. Para cubrirlos, el seed gana **dos clientes de Alicia** (un particular de la UE y uno de fuera de la UE, con domicilio) y se actualizan `test_clients_seed` y la matriz. Las facturas sembradas quedan con `pdf_status: "pending"` (el seed no dibuja PDF): se generan con «Generar PDF». Nombres y NIF inventados con dígitos de control válidos (RES-07).

### 5.3 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador); errores en `application/problem+json`.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `preview_invoice` | `POST /api/invoices/preview` | `InvoiceInput`. **200** `InvoicePreview` (condiciones, importes y mención, **sin número**); **no escribe**; mismos 422 que emitir |
| `issue_invoice` | `POST /api/invoices` | `InvoiceInput`. Valida, emite y genera el PDF; **201** `Invoice`; **422** `invalid_invoice`, `profile_incomplete` o `irpf_rate_missing`; **409** `client_not_billable` o `invoice_date_out_of_order` |
| `issue_rectifying_invoice` | `POST /api/invoices/{invoice_id}/rectifications` | `RectificationInput`. **201** `Invoice`; **404**; **409** `rectification_exceeds`, `invoice_not_rectifiable` o `invoice_date_out_of_order`; **422** |
| `list_invoices` | `GET /api/invoices` | Query `year` (de 2000 a 9998; por defecto el actual), `scope` y `paid` (filtros; `paid` solo mira las ordinarias: una rectificativa no se cobra). **200** `[Invoice]`, la más reciente primero |
| `get_invoice` | `GET /api/invoices/{invoice_id}` | **200** `Invoice` (con `pdf_status`, `rectified_by` y la base vigente); **404** `invoice_not_found` |
| `get_invoice_pdf` | `GET /api/invoices/{invoice_id}/pdf` | **200** `application/pdf` con la huella comprobada (`attachment`, `Cache-Control: private, no-store`); **404**; **409** `invoice_pdf_pending` o `invoice_pdf_corrupt`; **503** `storage_unavailable` |
| `create_invoice_pdf` | `POST /api/invoices/{invoice_id}/pdf` | Genera el PDF de una factura emitida **sin** él, de forma idempotente. **200** `Invoice`; **404** |
| `set_invoice_payment` | `PUT /api/invoices/{invoice_id}/payment` | `{ "paid": bool }`. **200** `Invoice`; **404**; **409** `invoice_not_payable` |
| `get_clients_billing` | `GET /api/clients/billing` | Query `year`. **200** `[{ client_id, billed_cents }]` (suma de bases, con signo) |

```
InvoiceInput { client_id, series_id: uuid|null, issue_date: "AAAA-MM-DD", concept, base_cents: integer (estricto: `true`, `"120"` y `120.0` dan `validation_error`; el dominio comprueba de 1 a 9.999.999.999), vat_rate: "21.00"|"10.00"|"4.00"|null }
RectificationInput { reason, corrected_base_cents: integer, issue_date }
InvoicePreview { scope, kind, tax_treatment, base_cents, vat_rate, vat_cents, irpf_rate, irpf_cents, total_cents, legal_note: string|null, vat_editable: bool }
Invoice { id, series_code, number, display_number, kind: "standard"|"rectifying", issue_date,
          issuer: { name, tax_id, address, iban: string|null },   # copia congelada del emisor, la misma que dibuja el PDF (B.6)
          client: { id, name, kind, country, scope, tax_id, address },
          concept, tax_treatment, base_cents, vat_rate, vat_cents, irpf_rate, irpf_cents, total_cents, legal_note,
          rectifies: { id, display_number, issue_date }|null, rectification_reason, rectified_by: [display_number], standing: { base_cents, vat_cents, irpf_cents }|null,   # lo vigente de una ordinaria; null en una rectificativa (B.4)
          paid_at: datetime|null, pdf_status: "ready"|"pending", created_at }
```

**Códigos de error nuevos** (`code`, HTTP): `invalid_invoice` 422 (con `fields: [ { field, message } ]`, **todos** los que fallan) · `profile_incomplete` 422 (con `missing`) · `irpf_rate_missing` 422 · `client_not_billable` 409 (con `field`) · `invoice_date_out_of_order` 409 · `rectification_exceeds` 409 · `invoice_not_rectifiable` 409 · `invoice_not_payable` 409 · `invoice_changed` 409 (otra rectificativa cambió lo vigente mientras se rectificaba; B.4) · `series_exhausted` 409 · `invoice_pdf_pending` 409 · `invoice_pdf_corrupt` 409 · `invoice_not_found` 404 (también si es de otra persona) · `forbidden` 403. Los errores de forma del cuerpo son el `validation_error` 422 de siempre. Los textos van en español y no repiten el valor escrito.

### 5.4 Backend

- **Paquetes.** `cuadre.tax` (puro: `invoice_terms`, importes y redondeo) y `cuadre.invoicing` (puros: `limits`, `types`, `numbering`, `rules`, `rectification`, `qr`; con base de datos y Storage, a partir del hito 3: `service`, `repository`, `models`, `errors`, `pdf`, `storage`) y `api/routes_invoices.py`. Los módulos puros **no importan base de datos, red, FastAPI, `float` ni reloj**; lo vigila `backend/tests/rules/test_invoicing_boundary.py`, como `test_clients_boundary.py`, y un test de **paridad** compara las constantes de `limits` con los CHECK.
- **Flujo de `issue_invoice`.** (1) Leer perfil, cliente y serie y **calcular** las condiciones con `cuadre.tax`; (2) transacción corta: `app.issue_invoice` con las condiciones ya calculadas → leer la fila → confirmar; (3) **fuera** de la transacción, dibujar el PDF y el QR, subirlo con el JWT de la persona, comprobar y registrar la huella con `app.attach_invoice_pdf`; (4) responder. Nunca una conexión retenida mientras se espera a Storage (D-10, ADR-0016).
- **Modelos.** La **entrada es suelta** (`client_id`, `series_id`, `issue_date`, `concept` y `vat_rate` como `str` con `max_length`, `extra="forbid"`): una fecha `2026-02-30` o un cliente `no-uuid` llegan al dominio y salen en `invalid_invoice` con **todos los errores a la vez**. **`base_cents` va con `StrictInt | None`**: un `int` normal acepta `true`, `"120"`, `120.0` y `1e3` sin avisar (B.1-F). `paid` con `StrictBool`; la salida lleva uniones de literales. Importes siempre `int` de céntimos y tipos como cadenas `"21.00"`; **ningún `float`** (RES-02: un test lo vigila en código y migraciones).
- **PDF y QR** (B.1-A). `reportlab` 5.1.0 (BSD) con `Pillow` 13.0.0 y `charset-normalizer` 3.5.2: es la única que cubre `€`, `ñ` y acentos con las fuentes base y trae un QR decodificable (no `fpdf2`, que exige empaquetar una TTF y es LGPL, ni `segno`). `Pillow` es una rueda **con extensión nativa** (`manylinux` para Vercel; sin binarios del sistema). `Canvas(invariant=1)` y metadatos fijos: mismos bytes en Windows y Linux con la misma zlib. El logo se mide con `Image.open().size` y solo se dibuja si tiene 4 Mpx o menos (un PNG de 269 KiB y 88 Mpx cuesta 872 MiB y 2 s). `pypdf` 7.0.0 solo como dependencia de pruebas (extracción de texto).
- **Storage.** `HttpStorage` gana la **subida de bytes** (`upload`: `POST /object/{bucket}/{ruta}` con el JWT de la persona, sin `x-upsert`) y la **descarga entera con tope** (`download`: nunca más de `max_bytes + 1`). La facturación los usa por los protocolos `PdfStorage` y `LogoReader` (`invoicing/storage.py`), sin tocar `StorageGateway` ni los dobles de documentos y perfil (B.5). Storage responde HTTP 400 con el estado real en el cuerpo (409 «Duplicate», 403, 413, 415, 404); el 409 de una ruta con prefijo de huella es un éxito idempotente (B.1-C).
- **Registro.** Ni el nombre, ni el NIF, ni el IBAN, ni el domicilio, ni el concepto de una factura se escriben en ningún registro: `request_id`, `user_id`, ruta, código y duración.

### 5.5 Frontend

| Ruta | Quién | Contenido |
|---|---|---|
| `/facturas` | `usuario` | Cabecera con «Nueva factura». Lista del año (selector de año): tarjetas hasta 1.279 px y tabla desde 1.280 px (Número, Fecha, Cliente, Base, IVA, Retención, Total, Cobro, Ámbito); el ámbito es **texto con insignia** como en `/clientes`; las rectificativas se distinguen por texto («Rectificativa»). Filtros de ámbito y cobro. Formulario «Nueva factura» (desplegable) con Cliente (solo activos), Serie, Fecha de expedición, Concepto, Base imponible (€) y Tipo de IVA; una **vista previa servida por la API** (`preview_invoice`) enseña ámbito, base, IVA, retención, total y mención **antes** de emitir, y el selector de IVA solo aparece si hay IVA. Perfil incompleto: se enumera por nombre lo que falta con enlace a `/perfil`. Cliente sin domicilio: enlace a editarlo |
| `/facturas/[id]` | `usuario` | Detalle del documento (emisor, cliente, concepto, importes, mención, rectificativas que la corrigen), **descarga del PDF**, «Marcar como cobrada» / «Marcar como pendiente» y «Emitir rectificativa» (motivo, base corregida o anular, fecha). Aviso «Emitida y bloqueada. Para corregirla, emite una rectificativa.» |
| `/clientes` | `usuario` | Columna «Facturado en {año}» (de `get_clients_billing`, con signo) y, en cada cliente, el texto de condiciones de la factura (lo que `preview_invoice` devuelve para una base de ejemplo, una petición por cliente activo con domicilio), sin lógica fiscal en el navegador |

Emitir, rectificar, cobrar y generar el PDF son **Server Actions** (`useActionState`, errores junto a cada campo con `aria-describedby`, resumen que recibe el foco, como `client-form`); emitir y rectificar **redirigen** al detalle (`?emitida=1`). La **vista previa en directo** es un Route Handler (`POST /facturas/vista-previa`), no una acción: Next despacha las acciones de una en una y aquí solo vale la última petición (B.6). El importe se escribe en euros (`1.200,00`) y la Server Action lo pasa a céntimos con `lib/money.ts`. La interfaz **muestra** lo que dice el servidor y no calcula impuestos. Los nombres de país salen **del servidor** (lección de SPEC-W-006: cada motor nombra distinto algunos códigos). «Facturas» pasa de `FUTURE` a enlace en `navFor('usuario')` y a `SECTIONS.usuario`; gestor y administrador no lo ven y `/facturas` para ellos lleva a `/403`. Hay que actualizar `lib/roles.test.ts` y `PEOPLE.alicia.nav` / `enabledNav` en `e2e/helpers/env.ts`. La **descarga** del PDF es un Route Handler del servidor (la web nunca ve la URL de Storage ni el JWT de la persona).

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
    And una original de base 105 al 10 % anulada en dos pasos (−52 y −53) queda con base, IVA y retención vigentes en 0, al céntimo
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

- [x] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003, 005 y 006 §8.2 siguen en verde. *(Local, verificado el 2026-11-11 —Anexo B.7—; CI de GitHub confirmado en verde por la persona el mismo día.)*
- [x] `pytest backend/tests/rls -m rls` incluye `invoices`, `invoice_files`, sus funciones y el bucket `invoices`.
- [x] «Facturas» está activo en el menú del autónomo y `/facturas` hace todo lo de AC-21; `/clientes` enseña «Facturado en {año}».
- [x] El seed lleva facturas sintéticas de los cinco tratamientos y una rectificativa, y las pruebas que dependían del menú se han revisado.
- [x] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0011, 0015 y 0016 enlazados.
- [x] Las preguntas abiertas P-02 y P-04 siguen anotadas en el Anexo B (P-01, P-03 y P-05 se resolvieron en el hito 0).
- [x] Sin secretos, NIF, IBAN reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike**: con valores **sintéticos**, (a) qué librería de **PDF** y de **QR** (Python puro, fuentes con `ñ` y `€`) caben en una función de Vercel por tamaño, tiempo y reproducibilidad de los bytes; (b) la norma del **QR de VeriFactu** y el contenido mínimo de la **factura completa** (RD 1619/2012) y el texto de las **menciones** (P-03), con fuentes oficiales; (c) la **subida con el JWT** al bucket `invoices` y las políticas que no lancen errores; (d) el DDL de §5.2 en seco, con la **carrera de numeración** con y sin cerrojo, el trigger de inmutabilidad y `TRUNCATE`; (e) cómo **sembrar** facturas sin saltarse el trigger; (f) P-01 y P-02 con la persona. Resultado al Anexo B.
   **Hecho el 2026-11-10** (seis guiones desechables fuera del repositorio; resultado en el Anexo B.1: `reportlab` + `Pillow` y no `fpdf2`, reproducibilidad entre Windows y Linux, guarda de dimensiones del logo, normativa del Reglamento de facturación, del QR y de la Ley del IVA, Storage con el JWT, DDL con sus carreras y cerrojos, cambios en las series de SPEC-W-005, seed por las funciones y forma de la API; corrigió D-05, D-10, D-11, D-12, T7-09, T7-10, §5.1.2, §5.1.5, §5.1.6, §5.2, §5.3, §5.4, AC-03, AC-16 y AC-17, y cerró P-01, P-03 y P-05).
1. **Dominio puro**: `cuadre.tax` y `cuadre.invoicing` (condiciones, importes, número, validación, rectificativas, contenido del QR) con tablas de pruebas y mutaciones; `test_invoicing_boundary.py`.
   **Hecho el 2026-11-10** (`cuadre.tax` y `cuadre.invoicing`, 15 módulos puros; 412 pruebas y 84 mutaciones —83 detectadas y 1 equivalente—; la rectificativa por diferencia de valores y la guarda del QR corrigieron §5.1.3, §5.1.5, AC-14 y B.1-A; Anexo B.2).
2. **Base de datos**: migraciones (tipos, `kind` de serie, `invoices`, `invoice_files`, trigger, funciones, bucket y políticas), matriz de RLS y seed; pruebas de RLS, de trigger y de concurrencia; mutaciones.
   **Hecho el 2026-11-10** (cuatro migraciones, seed y matriz; 466 pruebas de RLS nuevas y 244 mutaciones SQL —237 detectadas y 7 equivalentes por diseño—; `migration up` y `db reset` dan la misma huella; las claves foráneas compuestas, el orden de los cerrojos, la base de datos que recalcula lo vigente de una rectificativa y `invoice_files.owner_id` corrigieron §5.2; Anexo B.3).
3. **API**: emitir, previsualizar, listar, leer, cobrar, rectificar y `get_clients_billing`; `openapi.json` y `schema.d.ts` regenerados; mutaciones.
   **Hecho el 2026-11-10** (siete rutas: las dos del PDF pasan al hito 4; 199 pruebas nuevas y 79 mutaciones —71 detectadas y 8 equivalentes por diseño—; la rectificativa relee una vez si otra se coló y, si no, `invoice_changed`; `Invoice.standing`, el filtro `paid` solo de ordinarias y el perfil que rechaza `R-AAAA` corrigieron §5.3; Anexo B.4).
4. **PDF, QR y almacenamiento**: generación determinista, subida, huella, descarga con comprobación y reintento; pruebas de contenido y de alteración.
   **Hecho el 2026-11-10** (las dos rutas del PDF, el paso 3 de emitir y de rectificar, `HttpStorage.upload` y `download`, el dibujo con `reportlab` y `Pillow`, el QR simulado y el logo con su guarda; 180 pruebas nuevas, 11 de ellas contra el Storage real, y 89 mutaciones —86 detectadas y 3 equivalentes por diseño—; el QR de cada PDF se decodificó a mano con `zxing-cpp`; las letras que Helvetica no tiene, `application/pdf` en OpenAPI y que `create_invoice_pdf` sí falla corrigieron §5.1.6, §5.3 y §5.4; Anexo B.5).
5. **Frontend**: `/facturas`, `/facturas/[id]`, menú, columna «Facturado en {año}» y condiciones en `/clientes`; unitarias; comprobación visual en los tres motores.
   **Hecho el 2026-11-10** (las dos pantallas, dos Route Handlers —vista previa en directo y descarga del PDF— y cuatro Server Actions; `Invoice.issuer` como copia congelada del emisor; 26 unitarias nuevas y 39 mutaciones de las piezas puras, todas detectadas; comprobación visual con la API y el Storage reales en Chromium, Firefox y WebKit a 390 y 1.440 px, y 91 E2E existentes en Chromium; la columna nueva de `/clientes` obligó a rebalancear su tabla; Anexo B.6).
6. **E2E y cierre**: `factura.spec.ts` en tres motores y dos anchos, ajustes de `roles.spec.ts`, `responsive.spec.ts` y `env.ts`, mutaciones de la interfaz, Anexo B, `tasks.json`.
   **Hecho el 2026-11-11** (`factura.spec.ts` con 20 pruebas, el fixture `biller` y `InvoicesApi`; ajustes de `roles.spec.ts` y `responsive.spec.ts`; 22 mutaciones de la interfaz, todas detectadas; batería completa por motor en Chromium, Firefox y WebKit; la vista previa dejó de contestar 4xx a los avisos normales; Anexo B.7).

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
| QR | `reportlab.graphics.barcode.qr.QrCodeWidget` (sin `segno`): nivel M, **37×37 módulos (versión 5)** para 63 y 71 caracteres (el de 120 era solo letras mayúsculas y números: con `|` el QR va en modo de bytes y la versión 5 admite 84, B.2); **zxing-cpp lo decodifica** y el texto coincide. `segno` y `qrcode` no hacen falta |
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

### B.2 Hito 1 · dominio puro de facturación · 2026-11-10

**Qué hay.** Dos paquetes de Python puro (821 líneas en 15 módulos), sin base de datos, red, FastAPI, Pydantic, `stdnum`, `float` ni reloj; la fecha de hoy es un argumento:

| Paquete | Módulos |
|---|---|
| `backend/src/cuadre/tax/` | `limits` (tipos 21, 10 y 4; por defecto 21; las dos menciones; los cinco tratamientos), `types` (`TaxTreatment`, `InvoiceTerms`, `Amounts`, `Standing`), `invoice_terms` (la tabla de §5.1.2), `amounts` (`compute_amounts` y `rectification_amounts`) |
| `backend/src/cuadre/invoicing/` | `limits`, `types` (los `Raw*`, `ClientCopy`, `SeriesInfo`, `OriginalInvoice`, `InvoiceValues`, `RectificationValues`, `Problem` y los resultados), `rules` (`validate_invoice`, `validate_rectification`, `parse_uuid`), `numbering` (número visible, serie `R-AAAA` y orden de fechas), `rectification` (`standing_of`), `qr` (contenido del QR simulado), `storage_path` (ruta del PDF), `logo` (guarda de dimensiones) y `texts` (fechas en español y la referencia de la rectificativa) |

**Decisiones tomadas al implementar** (completan §5.1):

| Tema | Decisión |
|---|---|
| **Corrección a §5.1.3 y §5.1.5** | **Una rectificativa no calcula un porcentaje de un importe negativo**: eso desvía céntimos en cadenas de rectificaciones. Base 105 al 10 % lleva 11 de IVA; anulada en dos pasos de −52 y −53, el porcentaje del negativo da −5 y −5 y deja **una cuota vigente de 1 con base 0**. Como permite el art. 15.5 («los valores tras la rectificación»), sus cuotas son **las de la base corregida (con los tipos de la original) menos las vigentes**, siempre sobre una base ≥ 0. Los números de AC-14 no cambian y el redondeo simétrico de §5.1.3 deja de hacer falta; el ejemplo «−333 al 21 %» se sustituye por la anulación de 105 en dos pasos. Una **prueba de propiedad** (miles de cadenas aleatorias, con la validación entera) comprueba que la cuota y la retención vigentes finales son las de `percentage_of(base final)` |
| Qué resuelve la API | El dominio recibe **ya resueltos** el cliente (`ClientCopy`, `None` si no existe o es ajeno), la serie (`SeriesInfo` con la fecha de su última factura), la retención del perfil, la original, las rectificaciones que ya tiene y `today`. El ámbito y la retención del perfil entran como datos; el dominio no lee nada |
| Resultado | **O** los valores, **O** todos los errores de campo, **O** un problema único (nunca dos). Los campos van en el orden de la pantalla: `client_id`, `series_id`, `issue_date`, `concept`, `base_cents`, `vat_rate` (y en la rectificativa `reason`, `corrected_base_cents`, `issue_date`). Sin errores de campo, el problema sale en este orden: cliente archivado, cliente sin domicilio, retención sin elegir (422), fecha anterior a la última de la serie (409); en la rectificativa, **primero** que la original no sea una rectificativa, y después que no suba el importe y las dos fechas (la de la original y la de la serie) |
| Tipos de IVA | `21`, `21.0` y `21.00` son el mismo tipo (`parse_rate`); un número JSON, `True` o `"21 %"` no lo son; vacío es el del tratamiento. A un cliente sin IVA no se le envía ninguno (`vat_not_applicable`), pero un tipo que no es 21, 10 o 4 se dice igual para todos |
| Fechas | `AAAA-MM-DD` con un prefiltro **ASCII** antes de `date` (con `\d` entrarían los dígitos de ancho completo), o un `date`; un `datetime` no vale; **antes del 2000-01-01 no se admite** (`cuadre.validators.limits.EARLIEST_DATE`, la de los gastos: no estaba en la spec) |
| Base | `bool`, cadenas, decimales y flotantes **no** son una base (`True` es un `int` en Python); de 1 a 9.999.999.999 céntimos. La API la declarará `StrictInt` (B.1-F) |
| Rectificativa | Base corregida **igual** a la vigente es un error de campo («no hay nada que rectificar»; también cuando ya está en 0); **mayor** es el problema `rectification_exceeds` (409); negativa o no entera, error de campo. La serie de una rectificativa que no sea la rectificativa del año o esté archivada es un `ValueError` (la elige la API, no la persona) |
| QR | `CUADRE-VERIFACTU-SIMULADO\|{NIF}\|{serie}-{NNN}\|{DD-MM-AAAA}\|{importe}`; el importe sale de céntimos enteros (`1272.00`, `-212.00`), sin `float`; un campo vacío o con `\|` es un `ValueError`. Con NIF español (9), serie de 8 y 6 dígitos, el peor caso mide 76 caracteres |
| **Corrección a B.1-A** | El QR de 120 caracteres que midió el spike era solo mayúsculas y números (modo alfanumérico). Con `\|` el texto va en **modo de bytes** y la versión 5 de nivel M admite **84**: el peor caso real (76) cabe, y una prueba lo fija |
| Series | `rectifying_series_code(año)` da `R-AAAA` y `is_reserved_series_code` reconoce `^R-[0-9]{4}$` (ASCII): lo usará el hito 2 para reservar esos códigos en las series ordinarias |
| PDF y logo | `invoice_pdf_path(owner, invoice, sha256)` construye `{owner}/{invoice}-{sha256[:16]}.pdf` (minúsculas estrictas) y `pdf_path_owner` devuelve la carpeta o `None` sin lanzar nunca; `logo_fits` acepta hasta **4 Mpx exactos** y rechaza dimensiones que no son enteros positivos |

**Pruebas.** **412 nuevas**: `tests/tax/` 56, `tests/invoicing/` 346 y `tests/rules/test_invoicing_boundary.py` 10. Suite sin RLS **3.276** (antes 2.864); RLS 1.095 sin cambios; `ruff` y `pip freeze` sin cambios (no hay dependencias nuevas). Lo que fijan: la tabla de condiciones de §5.1.2 en sus seis cruces y las dos menciones exactas; los importes de §5.1.3 con 21/10/4/0, retención 15/7, el medio céntimo hacia arriba, la base máxima y la identidad `total = base + IVA − retención` con 5.000 casos aleatorios contra un oráculo de enteros; cada campo y cada mensaje de §5.1.1 (los textos de la spec se comparan con `MESSAGES`), **todos los errores a la vez y su orden**, fechas con formatos raros y de ancho completo, `base_cents` con `True`, `"120"`, `120.0`, 0, −1 y el máximo ±1, controles y saltos en concepto y motivo, **el orden de los problemas**; los ejemplos de AC-14 y la anulación en dos pasos; los límites de AC-15; el relleno del número (`2026-001`, `2026-1000`, `2026-999999`); el QR, la ruta del PDF, el logo y los 12 meses; y la guarda estructural (cada módulo declarado como puro, sin base de datos, red, FastAPI, Pydantic, `stdnum` ni reloj, `cuadre.tax` sin depender de `cuadre.invoicing`, y de `cuadre.validators` solo el IVA y la fecha mínima).

**Mutaciones.** **84** con un ejecutor desechable fuera del repositorio (restaura por hash): cada tratamiento y su tabla (retención, IVA elegible, mención, el particular de fuera de la UE como el prototipo), el tipo por defecto y la lista de tipos, el redondeo (truncar en vez de medio hacia arriba, en IVA y retención), el signo del total, el cálculo por porcentaje del negativo frente a la diferencia de valores, las cotas de base, concepto, motivo y número (±1), el relleno del número, `<` frente a `<=` en cada fecha, el prefiltro de fechas Unicode, `bool` como base, el tipo de IVA a un cliente sin IVA, las series (rectificativa o archivada), el cliente archivado o sin domicilio, la retención ausente, las rectificativas (no rectificar una rectificativa, la base vigente sin cada suma, `>` frente a `>=`, la igualdad, la negativa, las dos fechas, los tipos intercambiados, la mención no heredada), el QR (signo, orden de la fecha, céntimos, separador), la ruta del PDF (prefijo, mayúsculas, dueño), los textos y la guarda (un import de red, un reloj, un módulo sin declarar y un `float`). **83 detectadas y 1 equivalente por construcción**: **M58** (`>` en lugar de `>=` en el exceso): la igualdad ya la corta `_corrected` como error de campo antes de llegar, así que `>=` y `>` dan lo mismo. Ninguna superviviente real; un patrón de mi ejecutor no casó por el formateo de `ruff` y se corrigió.

**Lo que no se ha comprobado:**
- **Los campos reales de `ClientCopy` y `SeriesInfo`**: salen de la base en el hito 3 (`last_issue_date` es la fecha máxima de la serie, y debe leerse **dentro del cerrojo**, B.1-D).
- **La retención del perfil** como `Decimal`: `irpf_rate` se guarda como `numeric(5,2)`; el hito 3 lo convierte sin pasar por `float`.
- **Los textos de los mensajes en la interfaz**: se pintan en el hito 5.
- **Territorios especiales** (P-02) y la excepción del art. 69.Dos (P-05): no se modelan.

**Para el hito 2** (base de datos):
- **Paridad de constantes** (`test_limits_parity.py`): concepto y motivo de 2 a 300; número de 1 a 999.999; `RECTIFYING_CODE`; `PDF_PATH` y `PDF_HASH_PREFIX` frente a la política del bucket; los cinco valores de `TREATMENTS` frente al enum; `SERIES_KINDS` frente a `invoice_kind`; la base de 1 a 9.999.999.999 (en la ordinaria, `base_cents > 0`).
- **Reservar** los códigos `^R-\d{4}$` en `app.create_invoice_series` y `app.update_invoice_series` (`series_code_reserved`) con `is_reserved_series_code` como referencia.
- Las funciones `app.*` **repiten lo barato** y la identidad `total = base + IVA − retención`, no la regla fiscal; reciben las condiciones ya calculadas por `cuadre.tax`.
- **Cerrojos** de la serie (`FOR UPDATE`) y de la original (B.1-D), con la fecha comprobada dentro.
- El seed emite por las funciones con `set_config` de las claims, con fechas ≤ hoy, y gana dos clientes de Alicia (un particular de la UE y uno de fuera de la UE).

### B.3 Hito 2 · base de datos de las facturas · 2026-11-10

**Qué hay.** Cuatro migraciones nuevas (887 líneas de SQL; no se tocó ninguna aplicada), el seed y la matriz de RLS. No hay Python de producción nuevo: `openapi.json` y `schema.d.ts` no cambian.

| Migración | Contenido |
|---|---|
| `20261110100000_invoice_kinds_and_series_kind` | Tipos `invoice_kind` e `invoice_tax_treatment`; `invoice_series.kind` con sus dos CHECK; sustituye `invoice_series_guard` (`kind` no cambia nunca), `series_lock_own` (solo ordinarias), `create_invoice_series` y `update_invoice_series` (reservan `R-AAAA`); nuevas `series_lock_for_issue` y `app.ensure_rectifying_series` |
| `20261110100100_invoices` | `invoices` e `invoice_files` con 28 restricciones (sin contar las claves primarias), todas con nombre, y claves compuestas, RLS activada y forzada, dos políticas de lectura por tabla, el trigger de inmutabilidad (más `TRUNCATE`) y el de solo inserción |
| `20261110100200_invoices_functions` | Cinco ayudantes privados y las cuatro funciones de emisión, rectificación, cobro y PDF |
| `20261110100300_invoices_bucket` | Bucket privado `invoices` (PDF, 1 MiB), funciones `invoice_file_*` que no lanzan y las políticas de insertar y leer |

**Decisiones tomadas al implementar** (corrigen o completan §5.2, ya actualizada):

| Tema | Decisión |
|---|---|
| `invoice_files.owner_id` | La tabla lleva su propio `owner_id` y una clave compuesta `(invoice_id, owner_id) → invoices`: la matriz de RLS exige una columna de dueño y así la política es de una sola columna, sin `exists`. La spec decía «a través de la factura» |
| Claves foráneas compuestas | `invoices` apunta a `(series_id, owner_id, kind)`, `(client_id, owner_id)` y `(rectifies_id, owner_id)`: una factura no puede colgar de la serie o del cliente de otra persona, una rectificativa no cabe en una serie ordinaria ni al revés. Obliga a `UNIQUE (id, owner_id)` en `clients` y `invoices` y `UNIQUE (id, owner_id, kind)` en `invoice_series` |
| Firma de las funciones | `app.issue_invoice(p_client_id, p_series_id, p_issue_date, p_concept, p_base_cents, p_terms)`: el tipo de IVA va **dentro** de `p_terms` (las siete condiciones, con los tipos como números JSON). `app.issue_rectifying_invoice` recibe en `p_terms` **solo** `vat_cents`, `irpf_cents` y `total_cents`; el tratamiento, los tipos, la mención, el cliente y el concepto se heredan de la original |
| La base **recalcula lo vigente** | Bajo el cerrojo, la rectificativa suma la base, el IVA y la retención de la original y de sus rectificativas, calcula `base = corregida − vigente` y exige: que la corregida no suba (`rectification_exceeds`) ni iguale lo vigente, que el IVA y la retención no sumen ni dejen lo vigente por debajo de cero, que una anulación completa lo devuelva todo y la identidad del total. **No recalcula ningún porcentaje**: esa regla sigue siendo de `cuadre.tax`. Así nadie devuelve dos veces una factura aunque llame a la función a mano |
| Coherencia de las condiciones | La base conoce la tabla de §5.1.2 en una sola función (`invoice_expected_treatment`) y comprueba que el tratamiento es el del cliente, que sin IVA no hay tipo ni cuota, que los tipos son 4, 10 o 21, que la retención es la del perfil (y cero para quien no la lleva), la identidad `total = base + IVA − retención` y que la mención aparece exactamente en los dos tratamientos sin IVA |
| Orden de las comprobaciones | Emitir: rol → serie → cliente (no existe, archivado, sin domicilio) → perfil → campos (fecha no futura, concepto, base, condiciones) → retención sin elegir → fecha anterior a la última de la serie → serie agotada → coherencia. Rectificar: rol → fecha → serie del año → original (no existe, ya es rectificativa) → perfil → motivo, base corregida y condiciones → nada que rectificar → la base sube → fechas (la de la original, la de la serie) → serie agotada → coherencia |
| Cerrojos | Dos capas, siempre en el mismo orden (persona → serie → cliente con `FOR SHARE` → original): `series_enter()` (cerrojo asesor por persona, el de SPEC-W-005) y `FOR UPDATE` de la fila de la serie y de la original. El cliente se bloquea con `FOR SHARE`: no se edita ni se archiva entre la comprobación y la copia |
| Errores nuevos | `series_exhausted` (la serie llegó al 999.999), `series_code_reserved` (una serie ordinaria no usa `R-AAAA`); `profile_incomplete` lleva en el `DETAIL` los campos que faltan separados por comas e `invoice_date_out_of_order` la fecha de la última factura en ISO |
| CHECK de más | Respecto a §5.2: `invoices_issue_date_min` (la mínima del dominio), `invoices_base_range` (±9.999.999.999), `invoices_rectifying_base_negative` (la rectificativa siempre resta), `invoices_amounts_sign` (el IVA y la retención no cambian de signo), `invoices_vat_rate_values` e `invoices_irpf_rate_values`, las longitudes de la copia del emisor y de la mención, e `invoice_files_path_matches` (la ruta se deduce de la fila) |
| Series | `invoice_series_kind_matches_code` (`R-AAAA` es rectificativa y solo ella) e `invoice_series_rectifying_not_default`; `ensure_rectifying_series` admite los años 2000 a 9999 |
| `TRUNCATE` | PostgreSQL ya se niega a vaciar `invoices` sin `cascade` mientras `invoice_files` la referencie (`FeatureNotSupported`); con `cascade`, impiden el vaciado los triggers de las dos tablas, y el de `invoices` se prueba por sí solo desactivando el otro |
| Seed | Alicia gana dos particulares (UE y fuera de la UE) y seis facturas emitidas por las propias funciones con sus claims: una de cada tratamiento, la primera cobrada y una rectificativa. Las fechas son **relativas a hoy** (de −30 a −5 días): una factura no puede ser futura. `invoices` e `invoice_files` entran en la matriz con su `seed` y sus sondas |

**Pruebas.** **466 nuevas de RLS** (de 1.095 a 1.561; las 3.276 sin RLS no cambian): 28 de la matriz (dos tablas por cinco estados del vínculo y los roles) y nueve archivos nuevos con 438.

| Archivo | Pruebas | Qué fija |
|---|---|---|
| `test_invoices.py` | 93 | Nadie escribe (cinco personas por siete sentencias), RLS forzada y solo `SELECT`, dos políticas de lectura y ninguna del administrador, cada CHECK **por nombre y en su frontera**, la clave única, las claves compuestas, `RESTRICT` frente a cuenta, serie, cliente y original, el trigger columna a columna (31 columnas: una nueva obliga a decidir), `paid_at`, `DELETE`, `TRUNCATE`, `service_role`, `invoice_files` de solo inserción |
| `test_invoices_issue.py` | 104 | Cada tratamiento con sus importes y su mención, números 1-2-3, serie con otro inicio, las copias congeladas, el registro de actividad sin datos personales, roles, ajenos, cliente archivado o sin domicilio, perfil incompleto, cada campo con su `DETAIL` y el orden, las condiciones incoherentes, fechas (hoy, futura, mañana en Madrid con dos husos horarios, 2000-01-01), serie agotada y que **un fallo dentro del INSERT no consume el número** |
| `test_invoices_rectify.py` | 52 | Rectificativa simple, anulación completa, cadena a cero, el caso de 105 al 10 % en dos pasos, herencia de cliente, tratamiento, tipos y mención, emisor actual, serie `R-AAAA` creada una vez y por año de la fecha, fechas, cada campo, cuotas que devuelven de más, orden |
| `test_invoices_pay_and_pdf.py` | 53 | Cobrar (fecha conservada, solo se registra el cambio real), el PDF una sola vez con ruta y huella coherentes, `R-AAAA` reservado al crear y al renombrar, serie rectificativa invisible para las funciones ordinarias |
| `test_invoices_concurrency.py` | 21 | **20 hilos × 5 emisiones = 100 de 100 sin huecos ni repetidos**, dos personas a la vez, cinco anulaciones completas = exactamente una, fecha y número dentro del cerrojo, archivar o editar al cliente espera a la emisión, permisos de las funciones |
| `test_invoices_limits_parity.py` | 34 | Concepto, motivo, base, número, tipos de IVA y de retención, fecha mínima, enums, `R-AAAA`, ruta y huella del PDF, y tamaño del bucket, contra las constantes de `cuadre.invoicing`, `cuadre.tax` y `cuadre.profile` |
| `test_invoices_storage.py` | 43 | Las políticas del bucket por SQL: subir, leer (cinco estados del vínculo), nombres raros sin error, sin `UPDATE` ni `DELETE` |
| `test_invoices_storage_live.py` | 25 | Lo mismo contra la API real de Storage con tokens de GoTrue: firmar, 413, 415, 409 al repetir, 403 al reemplazar o borrar, lecturas firmadas y su caducidad |
| `test_invoices_seed.py` | 13 | Las facturas sembradas coinciden con lo que calcula `cuadre.tax`, el contador de cada serie, el registro de actividad y los particulares |

Ajustes: `test_clients_seed.py` (Alicia con cinco clientes) y `test_profile_seed.py` (su serie va por el 6).

**Mutaciones.** **244 mutaciones SQL** con un ejecutor desechable fuera del repositorio (rompe un objeto con `create or replace`, ejecuta primero los tests de su área y, si sobrevive, toda la batería; restaura y compara la huella del esquema —no cambió ni una vez—): cada cerrojo, cada comprobación de `issue_invoice` y de `issue_rectifying_invoice` y su orden, `<` frente a `<=` en las fechas, el huso horario del reloj, la base vigente sin cada suma, `corregida >` y `>=`, cada condición del IVA y de la retención devueltos, el total, las copias, la ruta del PDF, el registro de actividad, el trigger (cada columna que se permitiría cambiar), cada privilegio, política, RLS y CHECK, cada clave foránea, el bucket (público, 2 MiB, imágenes, políticas de más) y la regla `R-AAAA`. **237 detectadas y 7 equivalentes por diseño**:

| Mutante | Por qué es equivalente |
|---|---|
| L01, L06, L08, L09: quitar `FOR UPDATE` de la serie, de la original, de la factura al cobrar o al registrar el PDF | Capas de defensa redundantes con el cerrojo asesor por persona, que serializa todo lo que emite, rectifica, cobra o registra. Quitar **a la vez** el asesor y la fila (L03, L04) sí se detecta; quitar solo el asesor (L02) lo detecta el test de series de SPEC-W-005 (altas con predeterminada a la vez), no los de facturas |
| N05: quitar la comprobación de serie agotada de `invoice_insert` | `issue_invoice` e `issue_rectifying_invoice` la repiten antes; quitar las tres a la vez (N06) sí se detecta |
| N14: el último día de la serie sin filtrar por dueño | `series_id` ya identifica a la persona |
| R17: `>=` en lugar de `>` en «la base sube» | La igualdad se corta antes como «nada que rectificar» (el mismo caso que M58 en B.2) |

Los **seis huecos reales** que encontraron las mutaciones y cerraron pruebas: el 2000-01-01 por la función, el reloj de Madrid frente a `current_date` (se prueba con Kiritimati y Pago Pago: una de las dos está en otro día a cualquier hora), una mención de 301 caracteres donde la mención es obligatoria, renombrar a un código que solo se parece a `R-AAAA`, el trigger de `TRUNCATE` de `invoices` por sí solo y la huella del PDF en mayúsculas en la política del bucket.

**Verificación.** `migration up` sobre el esquema anterior y `db reset` dan la **misma huella** del esquema (funciones, políticas, restricciones, triggers, índices, privilegios, RLS, enums, columnas y buckets). Ruff limpio; `pip freeze` sin cambios; `openapi.json` y `schema.d.ts` al día.

**Lo que no se ha comprobado:**
- **Los textos y códigos HTTP** de los errores de la base: salen de la API en el hito 3.
- **`cuadre.profile` y el listado de series** siguen sin conocer `R-AAAA`: `normalize_series_code` acepta `R-2026` como código válido (la base responde `series_code_reserved`) y `list_invoice_series` mostraría la serie rectificativa en Perfil. Es del hito 3.
- **Subir un PDF de verdad** (bytes generados por el hito 4): aquí solo se prueban las políticas con un PDF mínimo.
- **El dueño de la base** puede hacer `DISABLE TRIGGER`; la inmutabilidad lo es frente a la aplicación y a los roles de la API (B.1-D).
- **Rendimiento con muchos miles de facturas**: el índice del listado existe, no se ha medido.
- **Los trabajos** (`cuadre_jobs`) no tienen privilegios sobre las dos tablas; los pedirá quien los necesite (SPEC-W-012).

**Para el hito 3** (API):
- Llamar a `app.ensure_year_series` antes de emitir si no hay serie y mapear los códigos: `invoice_not_found` y `client_not_found` a 404/422, `client_not_billable` (`archived` o `address` en el `DETAIL`), `profile_incomplete` (los campos faltantes en el `DETAIL`, separados por comas), `irpf_rate_missing`, `invoice_date_out_of_order` (la fecha en el `DETAIL`), `rectification_exceeds`, `invoice_not_rectifiable`, `invoice_not_payable`, `invoice_pdf_exists`, `series_exhausted` y `series_code_reserved`; `invalid_invoice` lleva el campo en el `DETAIL` (`issue_date`, `concept`, `base_cents`, `terms`, `tax_treatment`, `vat_rate`, `irpf_rate`, `vat_cents`, `irpf_cents`, `total_cents`, `legal_note`, `reason`, `corrected_base_cents`, `paid`, `sha256`, `size_bytes`, `storage_path`).
- `p_terms` va como `Jsonb` con **enteros** JSON para los tipos (`21`) y los importes, y `legal_note` como cadena o `null`; `p_base_cents` y `p_corrected_base_cents` como `bigint`. En una rectificativa, `p_terms` lleva solo los tres importes de `rectification_amounts`, calculados desde `standing_of` **leído después de bloquear**; si otra rectificativa llega entre medias, la base responde `invalid_invoice` o `rectification_exceeds` y la API vuelve a leer y devuelve 409.
- Filtrar `kind = 'standard'` en `list_invoice_series` y hacer que `normalize_series_code` rechace `^R-[0-9]{4}$` (o traducir `series_code_reserved`).
- Un `StorageGateway` que suba **bytes** al bucket `invoices` con el JWT de la persona, sin `UPDATE` ni `DELETE`: un 409 de Storage significa «ya está» (ruta con la huella).

### B.4 Hito 3 · API de las facturas · 2026-11-10

**Qué hay.** Siete de las nueve rutas de §5.3 (`get_invoice_pdf` y `create_invoice_pdf` son del hito 4, con el dibujo, la subida y la huella del PDF) y cuatro módulos impuros nuevos de `cuadre.invoicing` (917 líneas con las rutas); `backend/openapi.json` y `frontend/src/api/schema.d.ts` regenerados (no se editan a mano).

| Pieza | Contenido |
|---|---|
| `api/routes_invoices.py` | `preview_invoice`, `issue_invoice`, `issue_rectifying_invoice`, `list_invoices`, `get_invoice`, `set_invoice_payment` y `get_clients_billing`. Solo `usuario`; sin `PUT` ni `DELETE` de facturas |
| `invoicing/models.py` | Entrada suelta (`str` con `max_length`, `extra="forbid"`, `StrictInt` en `base_cents` y `corrected_base_cents`, `StrictBool` en `paid`) y salida con uniones de literales: `Invoice`, `InvoicePreview`, `ClientBilling` |
| `invoicing/service.py` | `InvoiceService`: emitir, vista previa, rectificar (con un reintento), cobrar, listar, leer y facturado. Valida con el dominio **antes** de llamar a la base |
| `invoicing/repository.py` | SQL explícito; `translate_db_error` de cada código de §5.2 y `is_stale_rectification` |
| `invoicing/errors.py` | `invalid_invoice` (con `fields`), `profile_incomplete` (con `missing`), `invoice_not_found`, `invoice_not_payable`, `invoice_changed`, `series_exhausted` y los problemas del dominio |
| Dominio y perfil | `issue_year` en `cuadre.invoicing.rules`; en `cuadre.profile`: `R-AAAA` reservado con mensaje propio, `list_series` y `get_series` sin las rectificativas y `series_code_reserved` traducido |

**Decisiones tomadas al implementar** (completan o corrigen §5.3, ya actualizada):

| Tema | Decisión |
|---|---|
| Orden al emitir | Una sola transacción: perfil (`profile_incomplete` **antes** de mirar el cuerpo) → `ensure_year_series` → cliente, serie y retención → `validate_invoice` → `app.issue_invoice` → releer la fila. Un fallo deshace también la serie del año |
| La vista previa no escribe | Es el mismo camino sin `ensure_year_series` ni la función de la base: no avanza el contador, no crea la serie del año, no deja rastro en `activity_log` y no necesita un número libre |
| Serie | Vacía (o ausente) es la predeterminada; un texto que no es un uuid no es «vacío» sino una serie que no existe; archivada o rectificativa, un error de campo `series_id` |
| Rectificar y la carrera | La API lee la original, las rectificativas previas y la última fecha de la serie `R-AAAA` **antes** de bloquear (el rol de la API no puede hacer `FOR UPDATE` sobre `invoices`). Si otra rectificativa llegó entre medias, la base lo rechaza (`rectification_exceeds` o `invalid_invoice` en `corrected_base_cents`, `vat_cents`, `irpf_cents` o `total_cents`) y la API **relee una vez**; si vuelve a pasar, `invoice_changed` (409, código nuevo). Una lectura vieja que la relectura desmiente sale como el error normal (`rectification_exceeds`) |
| La serie rectificativa | La del **año de la fecha** (`issue_year`); si la fecha no se entiende, la del año de hoy, solo para validar (el error de la fecha sale igualmente). Se crea en la misma transacción |
| `Invoice.standing` | Campo nuevo: lo vigente (`base_cents`, `vat_cents`, `irpf_cents`) de una ordinaria y `null` en una rectificativa. §5.3 decía que `get_invoice` devuelve la base vigente pero `Invoice` no tenía dónde; el formulario de rectificar la necesita |
| Filtro `paid` | Solo mira ordinarias: una rectificativa no se cobra, así que ni es «cobrada» ni está «pendiente de cobro» |
| Facturado | `GET /api/clients/billing?year=` suma `base_cents` con signo por cliente en el año de **expedición** (las rectificativas restan en su fecha), con los archivados incluidos. La ruta se registra **antes** de `/api/clients/{client_id}`: `routes_invoices` va antes que `routes_clients` en `main.py` y un test lo fija |
| Años | `year` de 2000 a 9998 (2000 es la fecha mínima del dominio; 9999 no tiene «1 de enero siguiente»); por defecto el año de hoy en Madrid |
| Perfil (deuda de B.3) | `R-AAAA` se rechaza al crear y al renombrar una serie con «Los códigos con la forma R-2026 están reservados para las rectificativas» (422 de campo `code`); Perfil no enseña la serie rectificativa. El patrón se repite en `profile/limits.py` (este paquete no importa `cuadre.invoicing`) y una prueba lo compara |
| `operation_id` | `preview` entra en la lista de verbos de `test_operation_ids.py` porque §5.3 fija `preview_invoice` |

**Pruebas.** **199 nuevas** (sin RLS: de 3.276 a **3.475**; las 1.561 de RLS no cambian), contra la app real con la base real y el reloj real (la base comprueba «no futura» con el suyo, así que las fechas son fijas y pasadas o relativas a hoy):

| Archivo | Pruebas | Qué fija |
|---|---|---|
| `test_invoices_api.py` | 52 | Los seis tratamientos con importes y mención, forma de `Invoice`, números 1-2-3, serie elegida o predeterminada, copias congeladas, la serie del año creada al emitir, **todos los errores a la vez** y que nada se emite, `StrictInt`, perfil incompleto antes del cuerpo, retención sin elegir solo para la empresa nacional, cliente archivado o sin domicilio, fecha fuera de orden, serie agotada, leer y cobrar |
| `test_preview.py` | 14 | Importes y mención de cada ámbito, es lo que luego se guarda, **no escribe** (contadores, series y registro intactos), mismos errores que emitir |
| `test_rectifications_api.py` | 25 | Simple, anulación, cadena a cero, 105 al 10 % en dos pasos, serie `R-AAAA` por año, errores y su orden, y **la carrera**: relectura con éxito, relectura que desmiente y `invoice_changed` |
| `test_listing.py` / `test_billing.py` | 13 / 12 | Orden, año por defecto y fronteras del 31/12 y el 1/1, filtros, signo, archivados, que una lectura no escribe ni descobra |
| `test_roles.py` | 34 | Gestor y administrador 403 en las siete rutas, 401 sin sesión, gestor con vínculo activo también 403, cuenta suspendida, ajenas = inexistentes, sin `PUT`/`DELETE` |
| `test_error_mapping.py` | 15 | Cada código de la base con errores REALES de PostgreSQL, y lo que no es nuestro no se traduce |
| `test_no_sensitive_logs.py` | 1 | Ni concepto, motivo, cliente, domicilio, NIF ni IBAN en los registros, en los errores ni en `activity_log` a lo largo de todo el flujo |
| `test_concurrency.py` | 3 | 20 emisiones simultáneas por HTTP = números 1…20; cinco anulaciones = exactamente una; rectificaciones parciales simultáneas sin devolver de más |
| Dominio y perfil | 30 | `issue_year`; `R-AAAA` reservado y su patrón igual al de `cuadre.invoicing`; el listado sin rectificativas; la traducción de `series_code_reserved` |

**Mutaciones.** **79 mutaciones** de `service`, `repository`, `errors`, `models`, las rutas, `main.py`, el dominio y el perfil, con un ejecutor desechable fuera del repositorio (restaura por hash; ninguna dejó huella). **71 detectadas y 8 equivalentes por diseño**, todas razonadas:

| Mutante | Por qué es equivalente |
|---|---|
| S26: rectificar sin mirar la completitud del perfil | La base repite la comprobación (`profile_incomplete`) y la API traduce el mismo problema |
| S29: el tratamiento de la original fijo en la API | Solo viaja a la base el importe; el tratamiento, los tipos y la mención los hereda la función de la original |
| R13: traducir cualquier estado SQL | Un error que no es `P0001` nunca lleva como mensaje uno de nuestros códigos |
| R21: aceptar tipos fraccionarios | El dominio solo produce 21, 10, 4 y los 7 y 15 del perfil |
| R22, R23: la serie predeterminada archivada o rectificativa | Dos CHECK de la tabla lo impiden (`invoice_series_default_not_archived`, `invoice_series_rectifying_not_default`) |
| R24: el último día de la serie sin filtrar por dueño | `series_id` ya identifica a la persona |
| P05: `get_series` del perfil sin el filtro de tipo | Las funciones de la base no encuentran una rectificativa (`series_lock_own`), así que la ruta ya da 404 |

Los **tres huecos reales** que encontraron y cerraron pruebas: el orden de fechas se comprueba en la serie rectificativa del año de la fecha (S24), una lectura de una factura cobrada no la descobra (S31) y la base que rechaza un código reservado se traduce a 422 de campo (P04); y el filtro de años de lo facturado ganó su frontera del 1 de enero (R06).

**Verificación a mano** con la API real y un token de GoTrue de Alicia: vista previa, emitir (`2026-006`), rectificar (`R-2026-002`), cobrar, listar (8), facturado y un 422 de campo; Perfil solo enseña la serie `2026`. Después se paró el servidor (puerto 8000 libre), se reinició la base y se comprobó todo: ruff, `openapi.json` y `schema.d.ts` al día, `typecheck`, `lint` y 206 unitarias del frontend.

**Lo que no se ha comprobado:**
- **El PDF** (`pdf_status` vale `pending` salvo que exista fila en `invoice_files`) y sus dos rutas: hito 4.
- **El rendimiento del listado** con miles de facturas (el índice `invoices_owner_date` existe, no se ha medido).
- **La pantalla** y los textos tal como se ven: hito 5.
- **Dos rectificativas a la vez desde procesos distintos de la API** (varias instancias): la prueba usa hilos de un solo proceso contra la misma base; el cerrojo es de la base, así que no cambia, pero no se ha medido con varios procesos.

**Para el hito 4** (PDF, QR y almacenamiento):
- Añadir al final de `issue_invoice` el paso 3 de §5.4: **fuera** de la transacción, dibujar el PDF, subirlo con el JWT de la persona (`StorageGateway` gana la subida de bytes y la descarga entera; un 409 de Storage con la huella en la ruta es éxito) y `app.attach_invoice_pdf`; si falla, la factura sigue emitida con `pdf_status: pending` y `create_invoice_pdf` la completa de forma idempotente.
- Las dos rutas pendientes (`get_invoice_pdf`, `create_invoice_pdf`) y los códigos `invoice_pdf_pending`, `invoice_pdf_corrupt` e `invoice_pdf_exists`.
- La copia del emisor para el PDF sale de la fila de la factura (`issuer_*`), no del perfil; el logo, del perfil actual.

### B.5 Hito 4 · PDF, QR y almacenamiento · 2026-11-10

**Qué hay.** Las dos rutas del PDF (`get_invoice_pdf` y `create_invoice_pdf`, con lo que las rutas de §5.3 quedan **nueve**), el paso 3 de §5.4 al final de emitir y de rectificar, el dibujo del PDF con su QR, la subida y la descarga de bytes en `HttpStorage` y el logo con su guarda. Cuatro dependencias nuevas, las únicas que cambian `pip freeze`: `reportlab` 5.1.0, `Pillow` 13.0.0 y `charset-normalizer` 3.5.2 en producción y `pypdf` 7.0.0 solo en pruebas.

| Pieza | Contenido |
|---|---|
| `invoicing/pdf.py` (234 líneas) | `render_invoice_pdf(factura, logo) -> bytes`, `qr_widget` y `logo_image`. Sin base de datos ni red; es el único módulo que importa `reportlab` y `Pillow` |
| `invoicing/storage.py` | Los protocolos `PdfStorage` y `LogoReader`, el bucket `invoices` (1 MiB, `application/pdf`) y `invoice_storage()` sobre `HttpStorage` con la regla de ruta de `PDF_PATH` |
| `documents/storage.py` | `HttpStorage.upload` (200 «creado», **409 «ya estaba»**, 403 denegado, 413, 415 y el resto «no disponible») y `HttpStorage.download` (con tope de `max_bytes + 1`), con el cuerpo binario en `_call` |
| `invoicing/texts.py` | `format_euros` (`1.200,00 €`), `format_percent`, `format_iban` y `pdf_text` (el texto que Helvetica sí dibuja) |
| `invoicing/service.py` | `_store_pdf` (leer → dibujar → huella → subir → registrar), `_with_pdf` (emitir y rectificar), `create_pdf` y `get_pdf` |

**Decisiones tomadas al implementar** (completan o corrigen §5.1.6, §5.3 y §5.4, ya actualizadas):

| Tema | Decisión |
|---|---|
| **Letras que Helvetica no tiene** (hueco del spike) | `reportlab` **no falla**: dibuja un **cuadrado negro** (se midió con `ł`, `ş`, cirílico, chino y emoji). `pdf_text` deja pasar lo que cabe en cp1252 (`ñ`, `€`, `Š`, `Ž`…), baja el resto a su letra sin signo (`ł` → `l`, `ş` → `s`) y escribe `?` para lo que aun así no cabe; quita también los controles. Sin fuente empaquetada (T7-09) |
| Orden del paso 3 | La transacción de la factura **se cierra**; después, cada paso con su transacción corta: leer la fila y el logo, dibujar, `sha256`, ruta `{owner}/{factura}-{sha[:16]}.pdf`, subir, comprobar si ya estaba, `app.attach_invoice_pdf`. Nunca una conexión retenida esperando a Storage (ADR-0016) |
| Emitir no depende del PDF | Un fallo (reportlab, Storage, la base) se registra **solo con el tipo de la excepción** y la factura se devuelve emitida con `pdf_status: "pending"`. **`create_invoice_pdf` es lo contrario**: aquí la persona lo pidió y un fallo es un error (503 `storage_unavailable`) |
| «Ya estaba» se verifica | Un 409 de Storage no basta: se **descarga y se compara la huella**. Si el objeto de esa ruta es otro (alguien subió otra cosa a esa ruta, que es suya), `invoice_pdf_corrupt` 409 y no se registra nada |
| Registro del PDF | `invoice_pdf_exists` (otra petición lo registró antes) es **éxito**: cinco `POST /pdf` a la vez dejan una fila y cinco 200 |
| Descarga | Sin fila: 409 `invoice_pdf_pending`. Con fila: se descarga con el JWT y se comparan **tamaño y SHA-256**; distinto o ausente: 409 `invoice_pdf_corrupt`; Storage caído: 503. Cabeceras `application/pdf`, `attachment; filename="2026-001.pdf"` (el número, ASCII) y `Cache-Control: private, no-store` |
| El PDF sale de la fila | Emisor y cliente son las **copias congeladas** (D-09), no el perfil de ahora: un `POST /pdf` posterior dice lo de entonces. El **logo** sí es el del perfil actual (no se copia) |
| Contenido | QR **arriba, centrado, 35 mm (zona de silencio incluida) y nivel M**; la retención solo se escribe si el tipo no es 0 y se ve con el signo contrario (resta); «Sin IVA» cuando el tipo es 0; la mención en negrita; el IBAN en grupos de cuatro; metadatos fijos (título = número, creador `cuadre-web`), sin datos personales; pie «Documento generado con cuadre-web. Proyecto de demostración: no se remite a la AEAT.» |
| Sin `float` | `test_no_float.py` es estricto (ni literales con decimales ni anotaciones): la geometría del dibujo va en **enteros** (milímetros y puntos; el gris, en por ciento) y las anotaciones usan `SupportsFloat`. No se hizo una excepción a la guarda |
| OpenAPI | `application/pdf` es la **única** respuesta no JSON y solo en `get_invoice_pdf`; `test_vercel_compat.py` lo fija y comprueba que ninguna ruta recibe un archivo. ADR-0016 (punto 5) habla de subidas y archivos grandes: el PDF pesa de 5 a 18 KB y el bucket lo limita a 1 MiB, muy por debajo de los 4,5 MB; no se edita el ADR |

**Pruebas.** **180 nuevas sin RLS** (de 3.475 a **3.655**; las 1.561 de RLS no cambian):

| Archivo | Pruebas | Qué fija |
|---|---|---|
| `test_pdf.py` | 28 | Cada dato del PDF extraído con `pypdf` (número, fecha, emisor, cliente, concepto, importes en es-ES, tipos, «Sin IVA», cada mención, IBAN o su ausencia, referencia y motivo con importes con signo), la leyenda del QR y **ni «VERI\*FACTU» ni una URL**, metadatos y fecha de creación fijos, **mismos datos = mismos bytes** y datos distintos = otros bytes, letras que Helvetica no tiene, la factura más larga posible en **una página** y bajo 1 MiB |
| `test_pdf_texts.py` | 46 | `format_euros` (de 0,05 € a 99.999.999,99 € y negativos), `format_percent`, `format_iban` y `pdf_text` |
| `test_qr_drawing.py` | 11 | Nivel M, 35 mm, arriba y centrado (se espía `renderPDF.draw`), texto exacto, matriz de módulos (versión 5, 37 × 37) que cambia con el texto, y que lo codificado sale **de la fila** (NIF del emisor, número, fecha y total con signo) |
| `test_logo.py` | 16 | PNG, JPEG y WebP se dibujan; GIF, BMP y TIFF no; el límite de 4 Mpx exactos; las dimensiones se leen **sin decodificar un píxel** (se prohíbe `Image.load`); un logo enorme, ilegible o truncado = factura sin logo y sin error |
| `test_pdf_api.py` | 27 | Emitir deja `ready` con la ruta y la huella coherentes, todas las llamadas a Storage con el JWT de la persona, un Storage caído no tumba la factura, un registro que falla deja el objeto reutilizable, `POST /pdf` idempotente y concurrente, objeto ajeno en la ruta = `invoice_pdf_corrupt`, la descarga devuelve exactamente los bytes con sus cabeceras, **un archivo alterado, ausente o con otro contenido de igual tamaño** = 409, sin PDF = 409, Storage caído al descargar = 503, el logo del perfil, y que el PDF lleva las copias de la fila |
| `test_pdf_storage_client.py` | 24 | `upload` y `download` contra un servidor local guionado: el cuerpo en bruto, solo el JWT en la cabecera, 409, 403, 413, 415, el tope de lectura, rutas rechazadas antes de salir y registros sin JWT, ruta ni contenido |
| `test_storage_live.py` | 11 | Lo mismo contra el **Storage real** con tokens de GoTrue: subir y descargar byte a byte, 409 que no reemplaza, gestor con vínculo activo lee y el resto no, 403 al subir quien no es `usuario` o a la carpeta de otro, nadie reemplaza ni borra, 1 MiB exacto y 413/415 |
| `test_pdf_dependencies.py` | 9 | Versiones exactas fijadas y las instaladas son esas, `pypdf` solo de pruebas, solo `pdf.py` importa las librerías de dibujo y sin red ni base de datos en él |
| Ampliados | — | `test_roles.py` (las dos rutas nuevas), `test_no_sensitive_logs.py` (ni datos, ni bytes, ni rutas con huella, ni el texto de una excepción que trae datos), `test_vercel_compat.py` y `test_invoicing_boundary.py` |

**Mutaciones.** **89 mutaciones** de `pdf.py`, `texts.py`, `documents/storage.py`, `storage.py`, `service.py`, las rutas, los errores y el repositorio, con un ejecutor desechable fuera del repositorio (restaura por hash; ninguna dejó huella). **86 detectadas y 3 equivalentes por diseño**:

| Mutante | Por qué es equivalente |
|---|---|
| P34: dibujar el texto alineado a la derecha sin pasar por `pdf_text` | Solo se alinea a la derecha la fecha y los importes, que son ASCII y `€` (cabe en WinAnsi) |
| V09: descargar sin comparar el tamaño | La huella SHA-256 ya cubre cualquier cambio de longitud |
| V19: no comprobar que el PDF cabe en 1 MiB | Si no cupiera, Storage lo rechazaría con 413 y el resultado sería el mismo (factura `pending`) |

Los **ocho huecos reales** que encontraron y cerraron pruebas: el QR del PDF codificaba otro NIF o la base y ningún test miraba lo dibujado (P05 y P06), el emisor y el nombre del PDF sacados de otra columna (V20 y B03), la fecha de creación fija (P09), el byte de más de la descarga (D06), el cuerpo binario que sale por el cable (D09) y el objeto ya subido que no se verificaba (V04). Dos mutaciones más (los saltos de línea del concepto y la medición del logo sin decodificar) estaban detectadas por pruebas que se **afinaron** para que fallaran por la razón correcta.

**Verificación a mano** con la API real, Storage real y un token de GoTrue de Alicia: emitir cuatro facturas de ámbitos distintos y rectificar una (las cinco con `pdf_status: ready`), descargar los cinco PDF y comprobar que su SHA-256 y su tamaño coinciden con lo guardado en `invoice_files`, **decodificar el QR de cada uno con `zxing-cpp`** (en un entorno desechable: da exactamente `CUADRE-VERIFACTU-SIMULADO|12345678Z|2026-006|10-11-2026|1407.40` y los demás, y `-267.40` en la rectificativa), **mirar** el PDF renderizado (QR arriba y centrado, logo a la izquierda, importes, referencia y motivo), completar con `POST /pdf` una factura sembrada sin PDF (dos veces: una fila), y alterar un objeto en Storage para ver el 409. Después: servidor parado (puerto 8000 libre), objetos de prueba retirados de Storage local y `db reset`. Ruff, `openapi.json` y `schema.d.ts` al día, `typecheck`, `lint` y 206 unitarias del frontend.

**Lo que no se ha comprobado:**
- **Reproducibilidad entre entornos**: solo se midió idéntica entre Windows y Linux con la misma `zlib` 1.3.1 (B.1-A). No se fija un hash de oro en el repositorio; un PDF guardado manda por su huella, no por regenerarlo.
- **Un decodificador de QR en el CI**: `zxing-cpp` trae código nativo y no es una dependencia; el QR se comprueba por construcción en las pruebas y por decodificación a mano.
- **Huérfanos**: un PDF subido cuyo registro falla queda en Storage hasta que el reintento lo reconoce (con los mismos datos, la misma ruta); si el logo cambió entre medias la huella es otra y el primero queda huérfano (ya excluido en §4).
- **El logo de la factura rectificativa** es el del perfil de ahora, no el de la original (solo el emisor y el cliente son copias).
- **Varios procesos de la API a la vez** sobre una misma factura: el cerrojo y el registro único son de la base y la prueba concurrente usa hilos de un proceso.
- **La pantalla**: la descarga desde el navegador, y que el nombre y las cabeceras se vean como se espera, son del hito 5.

**Para el hito 5** (frontend):
- `/facturas/[id]`: descarga con un **Route Handler** del servidor que pida `GET /api/invoices/{id}/pdf` con el JWT de la sesión (`openapi-fetch` con `parseAs: "arrayBuffer"`, sin probar) y reenvíe el cuerpo y las cabeceras `Content-Type`, `Content-Disposition` y `Cache-Control`; la web nunca ve la URL de Storage ni el JWT en el navegador.
- Estados del PDF: `pdf_status: "pending"` enseña «Generar PDF» (`POST /pdf`, que es idempotente y puede tardar: indicador y anuncio en `aria-live`); `ready` enseña «Descargar PDF»; errores `invoice_pdf_pending`, `invoice_pdf_corrupt` (409) y `storage_unavailable` (503, con `Retry-After`) con su texto en español.
- Las facturas sembradas de Alicia salen con PDF pendiente: es lo que la pantalla y el E2E del hito 6 usarán para probar «Generar PDF».

### B.6 Hito 5 · frontend de las facturas · 2026-11-10

**Qué hay.** Las pantallas `/facturas` y `/facturas/[id]`, dos Route Handlers del servidor (la vista previa en directo y la descarga del PDF), cuatro Server Actions (emitir, rectificar, cobrar y generar el PDF), la columna «Facturado en {año}» y las condiciones de facturación de cada cliente en `/clientes`, y «Facturas» como enlace del menú del autónomo. Una corrección de backend, aditiva: `Invoice.issuer`.

| Pieza | Contenido |
|---|---|
| `lib/invoices.ts` | Puro: fechas (`dd/mm/aaaa` y larga, sin pasar por `Date`), «hoy» de Madrid, tipos con coma, IVA («Sin IVA» si el tipo es 0), retención con signo (`−` resta, `+` si una rectificativa la devuelve), cobro con texto, filtros de la dirección, años ofrecidos y `conditionsText` (la frase de condiciones, redactada con los campos que devuelve el servidor) |
| `lib/invoices-form.ts` | Puro: formulario ↔ cuerpo de la API (vacío = `null`, importe en euros → céntimos enteros con `parseAmount`, ilegible o ambiguo → `null`), cuerpo de la vista previa con valores neutros, errores del servidor → campo de la pantalla (`base_cents` → «Base imponible») y `invoiceFailure` |
| `lib/invoice-handlers.ts` | Puro: errores de la vista previa (solo los de cliente, serie, importe e IVA) y cabeceras de la descarga (tipo fijo, adjunto con nombre sencillo, `private, no-store`) y texto de cada fallo del PDF |
| `lib/invoice-routes.ts` | `handlePreview` (comprueba el origen, lee el JWT de la sesión, pide `preview_invoice`) y `handleInvoicePdf` (`get_invoice_pdf` con `parseAs: "arrayBuffer"`); `app/(app)/facturas/vista-previa/route.ts` y `app/(app)/facturas/[id]/pdf/route.ts` son una línea cada uno |
| `lib/invoices-api.ts`, `invoices-actions.ts` | Lecturas de servidor (`list_invoices`, `get_invoice`, `get_clients_billing` y una `preview_invoice` por cliente activo) y las acciones; ninguna regla fiscal |
| `components/invoices/*` | Lista (tarjetas / tabla), insignias, filtros (un `<form method="get">`), «Nueva factura» con vista previa en directo, detalle como documento, cobro, PDF y rectificar |
| `lib/problems.ts` | `invoiceFields` (`invalid_invoice`, lista cerrada de ocho campos) y `missing` (`profile_incomplete`, solo campos del perfil); `client_id`, `address`, `series_id` e `issue_date` pasan a la lista de `field` |

**Decisiones tomadas al implementar** (completan o corrigen §5.3 y §5.5, ya actualizadas):

| Tema | Decisión |
|---|---|
| **Condiciones en `/clientes`** (decidido por la persona) | La página pide `preview_invoice` con una base de ejemplo para cada cliente **activo con domicilio**, en paralelo, y pinta la frase con lo que devuelve la API. Sin domicilio: «Añade el domicilio para poder facturarle.»; `irpf_rate_missing` y `profile_incomplete`, una frase con enlace a `/perfil`; archivado o fallo: nada. Una petición por cliente es aceptable con decenas; si crecieran, se cachearía por ámbito, tipo y retención |
| **Vista previa por Route Handler** | Next despacha las Server Actions de una en una por cliente: aquí cada cambio espera 300 ms, cancela la petición anterior y solo vale la última. El concepto no la recalcula. Mientras falta el importe (o no se entiende) se envía una base neutra y la pantalla **no enseña importes**, solo ámbito, condiciones y mención; la fecha y el concepto que faltan van con valores neutros y sus errores se avisan al emitir |
| **Selector de IVA** | Solo existe si `vat_editable`; al cambiar de cliente se olvida el tipo elegido (el nuevo puede no admitirlo y, si lo admite, empieza en el 21 %) |
| **Tras emitir o rectificar** | La Server Action **redirige** al detalle (`?emitida=1`: «Factura 2026-007 emitida.», y si el PDF quedó `pending`, un aviso). Las acciones nunca devuelven `sent` al formulario |
| **Perfil incompleto** | En vez del formulario se enseña `CompleteProfileNotice` (lo que falta, por nombre, con enlace a `/perfil`); si el perfil no se puede leer, no se bloquea y decide la API. Un `profile_incomplete` que llegue al emitir enseña el mismo aviso |
| **`Invoice.issuer`** (cambio de backend) | §5.5 pide emisor en el detalle y `Invoice` no lo llevaba: se añade `issuer { name, tax_id, address, iban }`, la **copia congelada** (la misma que dibuja el PDF), no el perfil de ahora. La prueba de forma cambia el perfil después de emitir y comprueba que el detalle no cambia |
| **Rectificativas** | `rectified_by` solo trae números, no ids: «Rectificada por: R-2026-001, R-2026-002» va como texto, sin enlaces (la rectificativa sí enlaza a su original). El formulario solo aparece en una ordinaria con base vigente > 0; «Anular por completo» fija la base corregida en 0 y la casilla es **sin controlar** (con `key`) para que un error no la desmarque |
| **Descarga del PDF** | Route Handler: la API contesta con `parseAs: "arrayBuffer"` y se reenvía con `Content-Type: application/pdf`, `attachment` con un nombre `[A-Za-z0-9._-]` (si no, `factura.pdf`), `Cache-Control: private, no-store` y `nosniff`; **nada más** de lo que diga la API. Si no es un PDF o falla, texto plano en español con el estado de la API (409 con su texto, 503 con `Retry-After`; un 5xx nunca enseña su cuerpo) |
| **Sin JavaScript** | Lista, filtros y tabla son Server Components y un `<form method="get">`: los importes y las fechas salen formateados en el servidor, nada que hidratar (lección de W-006) |
| **Tabla de `/clientes`** | La columna nueva dejó al nombre en ~100 px a 1.440; se rebalancean los anchos (NIF `w-32`, País `w-28`, Ámbito `w-52`, Facturado `w-28`, Acciones `w-44`): el nombre mide 216 px a 1.280 y 376 a 1.440 |
| **Lint de React 19** | `set-state-in-effect` y `immutability` obligaron a lanzar la vista previa desde el evento (`onChange`) y desde la propia acción, no desde un efecto; ningún `window.location` (una sesión caducada se dice en la vista previa y la redirección la hace la acción al emitir) |

**Pruebas.** **26 unitarias nuevas** (de 206 a **232**): `invoices.test.ts` 9, `invoices-form.test.ts` 8, `invoice-handlers.test.ts` 6 y 3 en `problems.test.ts`; `roles.test.ts` y `e2e/helpers/env.ts` ajustados (`Facturas` activa y `/facturas` es del autónomo, con su límite de segmento). Backend sin cambios de cifra: 3.655 sin RLS (la prueba de forma ahora incluye `issuer` y su copia congelada) y 1.561 de RLS.

**Mutaciones.** **39 mutaciones** de las piezas puras (`invoices`, `invoices-form`, `invoice-handlers`, `problems` y `roles`) con un ejecutor desechable fuera del repositorio: **39 detectadas, ninguna equivalente**. Dos huecos del propio ejecutor, no del código: un mutante parcial de `UUID` (solo la primera cifra aceptaba mayúsculas) y una cadena con la `−` mal escrita, ambos corregidos. Las mutaciones de la interfaz entera son del hito 6.

**Comprobación visual** con la API real y Storage real, datos sintéticos y un guion desechable de Playwright en **Chromium, Firefox y WebKit**, a **390 y 1.440 px**: 44 comprobaciones de lectura por motor (lista, filtros por la dirección, errores de campo a la vez, vista previa de cada uno de los cinco clientes —nacional con retención, UE empresa con «Inversión del sujeto pasivo», particular de la UE con IVA, particular de fuera con IVA español, empresa de fuera sin IVA con su mención—, base ambigua sin importes inventados, `/clientes`, sin scroll horizontal, campos etiquetados, consola sin errores) y **80 con escritura** (emitir, detalle, **descargar el PDF** —`%PDF-` y `2026-008.pdf`—, cobrar y volver a pendiente, rectificar con errores y con éxito, la original «Rectificada por», anular, no poder rectificar más, lista final, factura inexistente) más gestor y administrador a `/403` también con el PDF (403). **Generar PDF** sobre una factura sembrada en los tres motores. `/clientes` a 1.280 y 1.440 px sin scroll horizontal. E2E existentes `roles`, `clientes` y `responsive` en Chromium a 390 y 1.440 px: **91 correctas**.

**Lo que no se ha comprobado:**
- **Firefox y WebKit con los E2E existentes**: solo Chromium (el equipo tenía ~2,2 GB libres); los tres motores se vieron con el guion visual.
- **`storage_unavailable` y `invoice_pdf_corrupt` en pantalla**: están cubiertos como texto en las unitarias, pero no se provocaron con la web delante.
- **La descarga con el menú del navegador** (guardar como, visor integrado de iOS): se comprobó el archivo y su nombre, no cada visor.
- **Lectores de pantalla reales**: `aria-live`, `aria-describedby` y el foco del resumen están, pero no se probaron con NVDA o VoiceOver.
- **Muchos clientes**: una `preview_invoice` por cliente activo en cada carga de `/clientes`.
- **La vista previa con red lenta**: solo vale la última petición y se cancela la anterior; no se midió con latencia alta.
- **Una factura emitida desde dos pestañas a la vez**: el número lo asigna la base y el cerrojo es suyo.

**Para el hito 6** (E2E y cierre):
- `factura.spec.ts` en tres motores y dos anchos: lista sembrada, filtros, errores de campo, vista previa por ámbito y selector de IVA, base ambigua, perfil incompleto y cliente sin domicilio (hace falta un fixture que cambie y restaure el perfil y el cliente, como `profile`), emitir, detalle, PDF (`pending` → «Generar PDF» → descarga), cobro, rectificar y anular, 403 y 404.
- Ajustes de `responsive.spec.ts` (`/facturas` y `/facturas/[id]`) y de `roles.spec.ts` (Facturas activa para el autónomo y `/facturas` → `/403` para gestor y administrador).
- Mutaciones de la interfaz entera (los componentes de `components/invoices/*`), que este hito no cubre.
- Las facturas sembradas de Alicia siguen sin PDF; las que emiten las pruebas, no: usar las sembradas para «Generar PDF».
- Cuidado con el orden: las pruebas que emiten dejan facturas y sus números no se reutilizan (`db reset` entre baterías).

### B.7 Hito 6 · E2E y cierre · 2026-11-11

**Qué hay.** `e2e/factura.spec.ts` (20 pruebas por proyecto, seis proyectos), el fixture `biller` en `e2e/helpers/fixtures.ts` (completa el perfil de la cuenta del worker, con retención del 15 %, y siembra por la API seis clientes: empresa española, empresa alemana, particular alemán, particular de EE. UU., empresa mexicana y uno sin domicilio; al terminar restaura el perfil y archiva los clientes), el ayudante `e2e/helpers/invoices.ts` (`InvoicesApi`: emitir, rectificar y listar por la API con el token de GoTrue de la cuenta, nunca la service key), y ajustes de `roles.spec.ts` (Facturas activa para el autónomo; gestor y administrador a `/403` y la descarga de un PDF ajeno, 403) y de `responsive.spec.ts` (`/facturas`).

**Decisiones.**
- Las facturas no se pueden borrar ni archivar (RES-03): las pruebas que emiten usan la cuenta del worker y localizan lo suyo por un concepto único; ninguna cuenta filas ni números absolutos.
- «Generar PDF» se prueba con las facturas sembradas de Alicia, una distinta por proyecto (`chromium-390` → `2026-001`, … `webkit-1440` → `R-2026-001`); si ya tienen PDF (segunda vuelta sin `db reset`), la prueba lo anota y comprueba solo la descarga. No se añadió ningún gancho de prueba al producto.

**Hallazgos del E2E.**
1. **Producto, corregido.** La vista previa (`POST /facturas/vista-previa`) contestaba con el estado 4xx de la API (422, 409) ante los avisos normales —perfil incompleto, importe que falta, retención sin elegir—, y el navegador registraba cada uno como error de consola, que el fixture trata como fallo. Ahora `handlePreview` contesta 200 con el problema en el cuerpo y deja el estado real solo para 5xx y 403 (`lib/invoice-routes.ts`). Lo cubre la mutación F21.
2. **Guion, no producto.** Pulsar la tarjeta de una factura con `click()` caía en el `sr-only` de 1 px del enlace; se pulsa con una posición dentro de la tarjeta. También se afinaron un selector (`shown(...).first()` en «Facturado en {año}») y la prueba de la vista previa (cambio nacional → particular de la UE → empresa de la UE, y `aria-live="polite"`).

**Resultados.**

| Qué | Resultado |
|---|---|
| Batería completa, Chromium (390 y 1.440 px) | 243 correctas |
| Batería completa, Firefox | 235 correctas, 6 omitidas |
| Batería completa, WebKit | 234 correctas, 6 omitidas, 1 fallo intermitente (abajo) |
| Backend sin RLS | 3.655 correctas |
| RLS | 1.561 correctas con la base recién reiniciada |
| `ruff check` y `ruff format --check`, `export_openapi --check`, `gen:api`, lint, typecheck, build y `check:bundle` | código 0 |
| Pruebas unitarias del frontend | 232 correctas |

Las baterías se lanzaron una por motor, con `--workers=1`, tras `supabase db reset`. Las omitidas son pruebas que no corren fuera de Chromium (entre ellas las dos del límite de ancho de la tabla de facturas); no se desglosaron las de otras specs.

**Fallo intermitente.** En WebKit a 390 px falló una vez `auth.spec.ts:60` (SPEC-W-001, «recuperación · restablecer la contraseña con el enlace»): el formulario se envió con los campos vacíos («Escribe una contraseña. Las contraseñas no coinciden.»). Repetida tres veces, pasó las tres. No se ha cambiado esa prueba ni el producto de W-001; queda anotado como probable carrera de hidratación en WebKit.

**Mutaciones de la interfaz.** **22 mutaciones** (F01–F22: selector de IVA siempre visible, importes con base ilegible, insignias de ámbito y de cobro sin texto, «Descargar PDF» con otra ruta, descarga sin cabeceras, detalle sin «Emisora», rectificar sin base vigente, casilla de anular sin `key`, resumen de errores sin foco, aviso «emitida» oculto, cobro invertido, «Generar PDF» inerte, tabla desde 1.200 px, filtro de cobro con otro nombre, «Facturado» de otro año, condiciones sin pintar, IVA arrastrado al cambiar de cliente, rectificativa sin ir a ella, factura ajena sin 404, vista previa con 4xx y sin `aria-live`) con un ejecutor desechable fuera del repositorio, en Chromium a 390 y 1.440 px: **22 detectadas, ninguna equivalente ni inválida**. Se ejecutaron en cuatro tandas porque el sistema había cortado antes la ejecución completa por memoria; tras cada tanda el árbol quedó sin restos.

**Orden de las baterías.** Las pruebas E2E dejan datos: «Generar PDF» da PDF a las facturas sembradas de Alicia, y `backend/tests/rls/test_invoices_seed.py::test_nobody_else_has_any_invoice_or_pdf` exige que no lo tengan. Tras una batería E2E hace falta `supabase db reset` antes de la suite RLS (así ocurrió aquí: falló una vez con la base usada y pasó con la base reiniciada).

**Lo que no se ha comprobado:**
- **El CI de GitHub**: la verificación es local; la spec queda en `en-revision` hasta que se confirme.
- **Los seis proyectos en paralelo**: las baterías fueron con un solo worker y un motor por vez, no con la configuración del CI.
- **`storage_unavailable` y `invoice_pdf_corrupt` con la web delante**: solo como texto en las unitarias.
- **Lectores de pantalla reales** (NVDA, VoiceOver) y visores de PDF de cada navegador.
- **Muchos clientes** (una `preview_invoice` por cliente activo en cada carga de `/clientes`) y **red lenta** en la vista previa.
- **Una factura emitida desde dos pestañas a la vez**: el cerrojo es de la base de datos.
- **La causa del fallo intermitente de WebKit** en `auth.spec.ts`.

**Estado de la spec.** Todos los hitos hechos, la verificación local en verde y el CI de GitHub confirmado en verde por la persona tras el push de `bbed2a8` (2026-11-11): `hecha`.
