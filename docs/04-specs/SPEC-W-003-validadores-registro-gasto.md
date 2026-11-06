---
tipo: spec
id: SPEC-W-003
titulo: Validadores deterministas y registro del gasto
estado: en-progreso
prioridad: must
riesgo: alto
historias: [US-005]
requisitos: [RF-010, RF-011]
nfr: [NFR-06, NFR-07, NFR-10, NFR-11]
restricciones: [RES-01, RES-02]
adr: [0003, 0004, 0006, 0012, 0015, 0016]
depende_de: [SPEC-W-002]
bloquea: [SPEC-W-008, SPEC-W-010, SPEC-W-012, SPEC-W-016, SPEC-W-019]
fecha: 2026-11-06
---

# SPEC-W-003 · Validadores deterministas y registro del gasto

> Cierra el camino que abrió SPEC-W-002: lo que el agente leyó **se comprueba con código** (RES-01) y, solo si todo pasa y la persona lo confirma, se **registra como gasto**.
> Añade los gastos sin factura y las categorías. Lo que **no** hace es calcular impuestos: el 303 y el 130 son SPEC-W-008 y W-009, y consumen lo que esta spec deja registrado.

## 1. Contexto

**Situación de partida.** SPEC-W-002 (en revisión) entrega subida, lectura y revisión: un documento llega a `review`, la persona corrige y guarda (`documents.review`) y el botón «Registrar gasto» está desactivado con «Próximamente».
El estado `registered` existe en el enum y **ninguna ruta lleva a él**; no hay tabla de gastos. `python-stdnum` no está en el backend (el prototipo trae una rutina propia de NIF «hasta que llegue la librería»). El contrato C1 declara que el servicio de agentes
**no** valida NIF, sumas, tipos de IVA ni duplicados. El prototipo (`docs/cuadre-interfaz.html`) fija las cinco comprobaciones, las ocho categorías, el registro y el gasto sin factura; sus comentarios `operation_id` son `validate_extraction`, `confirm_document` y `create_expense`.

**Por qué es de riesgo alto.** (1) Lo registrado alimenta el 303 y el 130 (R-03): un error aquí se arrastra a una declaración. (2) La entrada es un dato no confiable (NFR-07): un documento puede traer instrucciones ocultas o cifras inventadas, y la regla es que **0 facturas
con instrucciones ocultas se registran sin revisión**. (3) Hay una carrera real: dos pestañas confirmando la misma factura a la vez. (4) Es la segunda tabla financiera nueva y debe pasar la matriz de RLS (NFR-06).

**Decisiones vigentes** (no se reabren aquí): ADR-0006 (céntimos enteros en base y API, `Decimal` con `ROUND_HALF_UP` en el cálculo); ADR-0012 (todo lo que necesite IA pasa por `AgentsClient`; este repositorio no llama a ningún modelo); ADR-0015 (`psycopg` síncrono con SQL explícito);
ADR-0016 (backend en Vercel: sin trabajo posterior a la respuesta); ADR-0003 y ADR-0004; CONF-001 (a) y D3 (el gestor solo lee, el administrador no ve datos financieros); y de SPEC-W-002, D-07 (se guarda la lectura normalizada y las correcciones aparte en `review`).

**Decisiones de diseño que esta spec propone** (cada una con su alternativa y lo que cuesta cambiarla). **D-10 y la parte de D-05 sobre el NIF-IVA de la UE las decidió la persona el 2026-11-06**; el resto, incluida la moneda y los terceros países de D-05, queda a su visto bueno:

| ID | Decisión propuesta | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Los validadores son Python puro** (`cuadre.validators`: sin base de datos, sin red, sin reloj propio, `Decimal` con `ROUND_HALF_UP`) y se ejecutan en la API. La base defiende solo lo barato y lo que protege la contabilidad: importes enteros, total coherente con las líneas, índice anti-duplicados, estado, dueño y reconocimiento de la sospecha. `CLAUDE.md` pide dominio puro con tests | Hacerlo en SQL: una sola capa, pero sin `python-stdnum`, con reglas fiscales difíciles de leer y de probar. Lo que cuesta lo elegido: si algo se saltara la API, la base no sabría comprobar un NIF. Se acepta porque la única vía de escritura es la API (los usuarios no tienen escritura directa) |
| D-02 | **Se valida lo guardado, en el servidor**: `Document.validation` se calcula al leer el documento y «Registrar gasto» exige el formulario guardado | Validar en vivo mientras se teclea (como el prototipo): mejor sensación, pero obliga a duplicar la regla en TypeScript o a añadir una ruta que valide un cuerpo sin guardar. Si se rechaza, se añade la ruta `validate_extraction` con cuerpo opcional sin tocar el resto |
| D-03 | **Tolerancias y tipos**: la cuota puede diferir ±1 céntimo del tipo (por línea) y el total ±1 céntimo de la suma; tipos de IVA nacionales 0, 4, 10 y 21; para proveedores de la UE, de 0 a 30. Son **decisiones de trabajo**, como el redondeo de ADR-0006, hasta validarlas con DEP-01 | ±0 rechaza facturas correctas con redondeos del proveedor; ±2 o más deja pasar un dígito mal leído en los céntimos. Cambiarlas es una constante (`cuadre.validators.limits`) y su tabla de pruebas |
| D-04 | **Duplicado duro** = mismo NIF del proveedor y mismo número de factura, normalizados, entre los gastos no anulados: lo hace cumplir un índice único parcial en la base (la normalización del número es una columna generada, replicada y probada en Python). **Duplicado blando** (mismo día, total y NIF con otro número o sin número) = solo un aviso | Solo avisar: deja pasar duplicados. Duro por fecha + total: falsos positivos (dos cafés iguales el mismo día) |
| D-05 | **Proveedores de la UE** *(decidido por la persona)*: se acepta su NIF-IVA, validado sin red (formato y dígitos de control del país con `python-stdnum`; nunca VIES en tiempo real), y se registran **sin IVA deducible**. **La moneda sigue siendo solo euro y los proveedores de fuera de la UE no se reconocen** *(propuesta de esta spec, a tu visto bueno)* | La alternativa recomendada para la persona era solo España. **Lo que cuesta lo elegido:** el 303 de la v1 no declara las adquisiciones intracomunitarias, así que estos gastos cuentan en el 130 pero **ninguna casilla del 303 los recoge** (aviso en pantalla y nota para SPEC-W-008, §4 y B.0). Aceptar otras monedas o terceros países exige conversión de moneda y las casillas de importaciones: otra spec |
| D-06 | **Deducibilidad del IVA, orientativa**: factura completa de proveedor español con IVA, sí; simplificada o ticket, solo si el NIF del destinatario es el del perfil; recibo, otros y proveedor de la UE, no. No decide gastos de deducción limitada (vehículo, vivienda afecta, atenciones) | Marcar todo deducible: infla el 303. Pedírselo a la persona en cada gasto: fricción y errores. Depende, en parte, de SPEC-W-005 (sin NIF en el perfil ninguna simplificada es deducible) |
| D-07 | **`injection_suspected` obliga a reconocerlo para registrar** (`acknowledge_suspicion`), exigido en la API **y en la función SQL**; nunca valida ni exime de ninguna comprobación (NFR-07) | Bloquear siempre: impediría registrar facturas legítimas que contienen una frase rara. No hacer nada: incumple NFR-07 |
| D-08 | **Categorías: lista cerrada de ocho** (enum de base, identificadores en inglés y las etiquetas del prototipo), con una **sugerencia por palabras clave en el código**, siempre editable. Sin modelo (RES-01; C1 no trae categoría) | Categorías propias de cada persona: otra tabla y otra pantalla. Sugerencia por modelo: exige subir el contrato C1 y trabajo en cuadre-agents |
| D-09 | **El gasto sin factura es puntual y sin IVA** (concepto, categoría, importe, fecha). La cuota de autónomos mensual automática queda fuera | Generador recurrente: toca el cierre mensual (SPEC-W-012) y el perfil (SPEC-W-005) |
| D-10 | **Decidida.** **Corregir gastos:** la categoría se puede cambiar; **anular** un gasto lo saca de las cuentas, deja rastro y **devuelve su documento a revisión** (a `review`, o a `extraction_failed` si nunca hubo lectura) para corregirlo y registrarlo de nuevo. Un gasto sin factura anulado no vuelve. No se edita ni se borra nada más | Solo cambiar categoría: más simple, pero un error al teclear un gasto sin factura no tendría remedio. Editar y borrar libremente: cambia cifras ya contabilizadas, también de meses cerrados, sin rastro |
| D-11 | **Un documento en `extraction_failed` rellenado a mano también se puede registrar** (el trigger de SPEC-W-002 solo permitía llegar a `registered` desde `review`, y ahí no había nada que registrar). Se valida y se registra igual que los demás | Obligar a reintentar la lectura: deja fuera a quien no consigue que se lea y rompe «rellena los datos a mano» de SPEC-W-002 |

*Visto bueno del 2026-11-06: la persona pidió el plan del hito 0 sin cambios a D-01 a D-11 (D-05 y D-10 ya estaban decididas); se tratan como aprobadas y la spec pasa a `en-progreso`. El spike del hito 0 comprobó la librería y corrigió el tratamiento del NIF (§3.1, §5.1, §5.4, T3-03, AC-03 y AC-04 y Anexo B.1).*

## 2. Objetivo

Al terminar esta spec:

1. Cada documento en `review` (o en `extraction_failed` rellenado a mano) muestra una **lista cerrada de comprobaciones deterministas** con su resultado y su motivo: tipo de documento, datos obligatorios, NIF, fecha, moneda, tipos de IVA, cuota, total, retención y duplicado (RF-010, US-005).
2. «**Registrar gasto**» está activo solo cuando **todas** pasan y el formulario está guardado, y crea un gasto; una factura cuya suma no cuadra no se puede registrar ni saltándose la interfaz (AC-01).
3. Una sospecha de instrucciones ocultas **obliga a reconocerla** para registrar, y eso lo exige también la base de datos (NFR-07).
4. Se pueden **anotar gastos sin factura** y clasificar todos por **categoría**, con una sugerencia que la persona puede cambiar (RF-011).
5. Un gasto registrado se puede **cambiar de categoría** o **anular** (con su documento de vuelta en revisión); nunca se edita ni se borra en silencio, y todo deja rastro sin datos sensibles.
6. Lo registrado queda **aislado por RLS**: el dueño lo ve, el gestor con vínculo activo lo lee, el administrador no (NFR-06).

## 3. Alcance explícito

### 3.1 Validadores (`cuadre.validators`)
- Funciones puras de comprobación (§5.1) y su orquestación `validate(data, context) → Validation`; normalización del NIF y del número de factura; deducibilidad del IVA; sugerencia de categoría.
- NIF español (NIF, NIE, CIF y los especiales K, L y M) y NIF-IVA de los 26 países de la UE con `python-stdnum` (dependencia nueva, versión fijada; ver §5.4), siempre tras un prefiltro ASCII (Anexo B.1). Fecha con **reloj inyectado** (`today`), tipos y cuotas con `Decimal`.
- Constantes en un solo sitio (`limits`): tolerancias, tipos permitidos, máximos.

### 3.2 Base de datos (migraciones nuevas)
- Enums `expense_category`, `expense_origin` y `supplier_scope`; tabla `expenses` con RLS activada y forzada, índices únicos y CHECK de importes; funciones `app.*` para registrar, anotar, recategorizar y anular; trigger de `expenses`; **`documents_guard` ampliado** con las nuevas transiciones; eventos en `activity_log`.
- `expenses` registrada en `backend/tests/rls/rls_matrix.yaml`.

### 3.3 Backend (FastAPI)
- Rutas `confirm_document`, `create_expense`, `list_expenses`, `get_expense`, `set_expense_category` y `void_expense` (§5.3), solo para el rol `usuario`.
- `Document` gana `validation` y `expense_id`; `list_documents` deja de listar los `registered`. Validar y registrar ocurren **en una sola transacción con la fila de `documents` bloqueada**.
- Paquete `cuadre.expenses` (servicio, repositorio, modelos, categorías), `Clock` mínimo inyectable y errores `problem+json` nuevos.

### 3.4 Frontend (Next.js)
- En `/gastos/[id]`: lista de comprobaciones (icono y texto), selector de categoría con la sugerida, casilla de reconocimiento si hay sospecha y «Registrar gasto» activo.
- En `/gastos`: sección «Gastos registrados» y acceso a «Gasto sin factura» (`/gastos/nuevo`); detalle de solo lectura con cambio de categoría y anulación en `/gastos/registrados/[id]`; un documento ya registrado redirige a su gasto.

### 3.5 Pruebas
- `backend/tests/validators/`, `backend/tests/expenses/`, ampliación de `backend/tests/rls/` (tabla, funciones, trigger de `expenses` y `documents_guard`), `backend/tests/rules/test_validators_boundary.py`, unitarias del frontend y `frontend/e2e/gastos-registro.spec.ts` en los tres motores y los dos anchos.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Editar importes, fecha, NIF o número de un gasto registrado (se anula y se vuelve a registrar) | Decisión D-10 |
| Facturas con importes negativos (abonos, rectificativas recibidas) | SPEC-W-018 (Should) |
| Compras a la UE y a terceros países con inversión del sujeto pasivo, casillas de adquisiciones del 303 y consulta de VIES en tiempo real | SPEC-W-008 decide las casillas; VIES simulado, SPEC-W-006. **Limitación conocida de D-05: estos gastos no figuran en el 303 de la v1** |
| Proveedores de fuera de la UE y facturas en otra moneda (se anotan a mano como gasto sin factura, con el importe en euros) | Una spec futura de moneda extranjera |
| Calcular el 303 y el 130; deducción limitada (vehículo, vivienda afecta `home_pct`, atenciones) | SPEC-W-008 y W-009 |
| Gastos recurrentes (cuota de autónomos mensual automática) | Futura (cierre mensual, SPEC-W-012, y perfil, SPEC-W-005) |
| Categorías propias y clasificación por modelo | Contrato C1 v1.1 y cuadre-agents |
| Pantalla del gestor para ver gastos (aquí solo la política de lectura) | SPEC-W-010 |
| Cierre mensual y reapertura de un mes cerrado | SPEC-W-012 |
| Pantalla del perfil (necesaria para que exista el NIF propio) | SPEC-W-005 |
| Exportación, borrado y retención de gastos | SPEC-W-017 (CONF-004) |
| Validación mientras se teclea | Decisión D-02 |

## 5. Contrato de interfaces

### 5.1 Comprobaciones, avisos y reglas

Todas se calculan sobre **lo que se registraría**: `review` si existe y `extraction` si no (la misma regla que la pantalla de revisión; `review` sustituye entera a la lectura). Son una **lista cerrada y ordenada**; las que no aplican no aparecen. Cada una devuelve `status` (`ok` o `failed`) y, si falla, un `detail` en español con el motivo concreto.
Si le faltan datos, la comprobación **falla** con «No se puede comprobar: faltan datos» y los datos que faltan los detalla `required_data`.

| `code` | Etiqueta | Regla |
|---|---|---|
| `doc_type` | Tipo de documento válido | `full_invoice`, `simplified_invoice`, `ticket` o `receipt`. `other`, `not_an_invoice` o vacío fallan: «Elige el tipo de documento» |
| `required_data` | Datos obligatorios completos | Nombre del proveedor; número de factura (solo en `full_invoice`); al menos una línea de IVA con tipo, base y cuota; total presente y mayor que cero; ningún importe negativo (los abonos no se registran todavía) |
| `doubts_reviewed` | Datos dudosos revisados | Solo si la lectura marcó dudosos: falla mientras no exista `review` (haber guardado el formulario es confirmarlos; US-001: «el gasto no se registra hasta que el usuario confirma el dato») |
| `supplier_tax_id` | NIF del proveedor válido | Obligatorio. **Antes de llamar a la librería**: prefiltro ASCII (`[0-9A-Za-z .-]{1,32}` con `fullmatch`), se quitan espacios, puntos y guiones y se pasa a mayúsculas. Si empieza por dos letras: `ES` → NIF español; `EL` o `GR` → Grecia; otro prefijo de la **lista cerrada de 26 países** (AT, BE, BG, CY, CZ, DE, DK, EE, FI, FR, HR, HU, IE, IT, LT, LU, LV, MT, NL, PL, PT, RO, SE, SI y SK, más Grecia) → NIF-IVA de ese país (formato y control, sin red); cualquier otro prefijo (`XI`, `EU`, `IM`, `GB`, `CH`…) → «no se reconoce». Sin prefijo → NIF español: NIF, NIE, CIF y los especiales K, L y M, con su dígito o letra de control (`python-stdnum`). **Cualquier excepción de la librería es «no válido»** y lo que devuelve debe ser solo `A-Z` y `0-9` (Anexo B.1: la librería valida entradas con un salto de línea dentro y lanza `ValueError`). Cualquier otra cosa: «no se reconoce como NIF español ni NIF-IVA de la UE» |
| `issue_date` | Fecha correcta y no futura | Fecha real, no anterior al 1 de enero de 2000 y **no posterior a hoy en Europe/Madrid** (con `today` inyectado: a las 23:30 UTC de un 31 de diciembre ya es 1 de enero en Madrid) |
| `currency` | Importe en euros | Vacía o `EUR`. Otra moneda falla: «La factura no está en euros: anótala como gasto sin factura con el importe que te cargaron en euros» |
| `vat_rates` | Tipos de IVA permitidos | Proveedor español: cada tipo es 0, 4, 10 o 21 (se compara el número: `21.00` es 21). Proveedor de la UE: de 0 a 30, porque cada país tiene los suyos |
| `vat_amounts` | Cuota acorde al tipo de IVA | Por línea: `redondeo_medio_arriba(base × tipo / 100)` difiere de la cuota como mucho 1 céntimo (D-03) |
| `withholding` | Retención acorde a su porcentaje | Solo si hay retención: `redondeo_medio_arriba(suma de bases × porcentaje / 100)` difiere del importe retenido como mucho 1 céntimo, y el importe está presente |
| `total` | Base más IVA igual al total *(«Base más IVA menos retención igual al total» si hay retención)* | `Σ(base + cuota) − retención` difiere del total como mucho 1 céntimo. Es el escenario de US-005: 120,00 + 25,20 frente a 147,00 falla |
| `not_duplicate` | No está registrada ya | No existe un gasto **no anulado** de la persona con el mismo NIF y el mismo número de factura normalizados. Sin número (tickets), no hay duplicado duro |

**Avisos** (nunca bloquean): `possible_duplicate` (mismo día, total y NIF con otro número o sin número), `recipient_mismatch` (la factura trae un NIF de destinatario distinto del del perfil; solo si ambos existen) y `eu_supplier` («El IVA de un proveedor de la UE no se deduce en el 303 de Cuadre; el gasto cuenta en el 130», D-05).

**Normalización.** `supplier_tax_id`: forma compacta de `python-stdnum` tras el prefiltro; un NIF español se guarda **sin** el prefijo `ES`, uno de la UE **con** su prefijo y Grecia siempre como `EL` (la librería conserva `GR` si se escribe así), de modo que `ES B12345678` y `B12345678`, o `GR…` y `EL…`, se reconocen como el mismo proveedor. `invoice_number_key` = el número sin ningún carácter que no sea
`[0-9A-Za-z]`, en mayúsculas (vacío es nulo): `A-311`, `a 311` y `A311` son el mismo número. Esa normalización **vive en la base** (columna generada) y la réplica en Python se prueba contra ella con un corpus (T3-04).

**Deducibilidad** (`deductible_vat`, orientativa, D-06): falso si el proveedor es de la UE o si la cuota total es 0. Verdadero para `full_invoice`. Para `simplified_invoice` y `ticket`, solo si el NIF del destinatario, normalizado, es el de `business_profiles.tax_id` y no está vacío. Falso para `receipt`. Se muestra siempre **con su motivo** («Factura simplificada: el IVA solo se deduce si lleva tu NIF»).

**Categorías** (D-08). Identificador en base → etiqueta: `software` → Software · `workspace` → Coworking y oficina · `supplies` → Material · `utilities` → Suministros y teléfono · `advisory` → Asesoría · `self_employed_fee` → Cuota de autónomos · `training` → Formación · `other` → Otros.
La sugerencia mira el nombre del proveedor (minúsculas, sin tildes, **inicio de palabra**) y parte de la tabla del prototipo: `soft`, `nube`, `cloud`, `app` → `software`; `papeler`, `imprenta`, `material` → `supplies`; `cowork`, `espacio`, `oficina` → `workspace`; `telef`, `fibra`, `luz`, `energ` → `utilities`; `gestor`, `asesor` → `advisory`; si nada coincide, `other`.
Solo puede devolver uno de los ocho: el texto del proveedor no se interpreta.

**Constantes** (`cuadre.validators.limits`): `TOLERANCE_CENTS = 1`, `VAT_RATES_ES = {0, 4, 10, 21}`, `VAT_RATE_MAX_EU = 30`, `MAX_TAX_LINES = 10` (el de SPEC-W-002), `EARLIEST_DATE = 2000-01-01`.

### 5.2 Base de datos

Migraciones nuevas (`YYYYMMDDHHMMSS_descripcion.sql`, sin destructivas; **las ya aplicadas no se tocan**: `documents_guard` se sustituye con `CREATE OR REPLACE` en una migración nueva). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`.

```
CREATE TYPE expense_category AS ENUM ('software','workspace','supplies','utilities','advisory','self_employed_fee','training','other');
CREATE TYPE expense_origin   AS ENUM ('document','manual');
CREATE TYPE supplier_scope   AS ENUM ('national','eu');

expenses                                                    -- tabla financiera
  id                  uuid PK DEFAULT gen_random_uuid()
  owner_id            uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE
  origin              expense_origin NOT NULL
  document_id         uuid REFERENCES documents(id)          -- NULL si es manual
  expense_date        date NOT NULL                          -- la fecha de la factura, o la que se anota
  supplier_name       text NOT NULL CHECK (char_length(supplier_name) BETWEEN 1 AND 200)    -- el concepto, en los manuales
  supplier_tax_id     text CHECK (supplier_tax_id ~ '^[A-Z0-9]{5,20}$')                     -- normalizado; NULL en los manuales
  invoice_number      text CHECK (char_length(invoice_number) BETWEEN 1 AND 64)
  invoice_number_key  text GENERATED ALWAYS AS (nullif(upper(regexp_replace(invoice_number, '[^0-9A-Za-z]', '', 'g')), '')) STORED
  doc_type            text CHECK (doc_type IN ('full_invoice','simplified_invoice','ticket','receipt'))   -- NULL en los manuales
  supplier_scope      supplier_scope                          -- NULL en los manuales
  category            expense_category NOT NULL
  base_cents          bigint NOT NULL CHECK (base_cents >= 0)
  vat_cents           bigint NOT NULL CHECK (vat_cents >= 0)
  withholding_cents   bigint NOT NULL DEFAULT 0 CHECK (withholding_cents >= 0)
  total_cents         bigint NOT NULL CHECK (total_cents > 0)   -- y como máximo 15 cifras, como en documents
  tax_breakdown       jsonb NOT NULL DEFAULT '[]'              -- líneas validadas: solo céntimos enteros
  deductible_vat      boolean NOT NULL
  suspicion_acknowledged boolean NOT NULL DEFAULT false
  created_at, updated_at  timestamptz NOT NULL DEFAULT now()
  voided_at           timestamptz                              -- NULL = cuenta; no NULL = anulado
  CHECK ((origin = 'document') = (document_id IS NOT NULL))
  CHECK (origin = 'document' OR (supplier_tax_id IS NULL AND invoice_number IS NULL AND supplier_scope IS NULL AND doc_type IS NULL
         AND vat_cents = 0 AND withholding_cents = 0 AND base_cents = total_cents AND NOT deductible_vat AND tax_breakdown = '[]'))
  CHECK (abs(total_cents - (base_cents + vat_cents - withholding_cents)) <= 1)
  CHECK (NOT deductible_vat OR (supplier_scope = 'national' AND vat_cents > 0))
  -- en los de documento, base_cents y vat_cents son exactamente la suma de las líneas de tax_breakdown
UNIQUE INDEX expenses_one_active_per_document  ON expenses (document_id) WHERE voided_at IS NULL AND document_id IS NOT NULL
UNIQUE INDEX expenses_duplicate_invoice        ON expenses (owner_id, supplier_tax_id, invoice_number_key)
                                                  WHERE voided_at IS NULL AND supplier_tax_id IS NOT NULL AND invoice_number_key IS NOT NULL
INDEX        expenses_by_owner_date            ON expenses (owner_id, expense_date DESC, created_at DESC, id DESC)
```

**Privilegios.** `authenticated`: `SELECT` y nada más; ninguna escritura directa, todo por funciones (como `documents`).

| Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|
| SELECT | los suyos, anulados incluidos | los de usuarios con vínculo activo (`private.gestor_has_access(owner_id)`) | **ninguna** |
| INSERT / UPDATE / DELETE | denegado (solo `app.*`) | denegado | denegado |

**Funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`, verifican `auth.uid()` y `private.app_role() = 'usuario'`, escriben `activity_log` en la misma transacción; `P0001` con código estable, `42501` si el rol no basta):

| Función | Efecto |
|---|---|
| `app.lock_document(p_id)` | Devuelve la fila de `documents` de quien llama **bloqueada** (`FOR UPDATE`). `document_not_found` si no existe, es ajena o está `discarded`. Es lo que permite validar y registrar sin que nadie cambie el documento entre medias |
| `app.register_expense_from_document(p_document_id, p_category, p_values jsonb, p_acknowledged boolean)` | El documento debe estar en `review` o `extraction_failed` (`document_wrong_state`). Si `injection_suspected` y no `p_acknowledged`: `suspicion_not_acknowledged`. Comprueba **lo barato**: la fecha está entre 2000-01-01 y hoy en Europe/Madrid (`invalid_expense`) y las CHECK de la tabla (importes enteros, total coherente, deducibilidad). Inserta el gasto, pasa el documento a `registered` y registra `expense.registered`. Devuelve el id. Un duplicado vivo lo rechaza el índice (`23505`) |
| `app.create_manual_expense(p_date, p_concept, p_category, p_amount_cents)` | Importe > 0, concepto de 1 a 200 caracteres, fecha entre 2000-01-01 y hoy. Inserta un gasto `manual` (sin IVA, no deducible) y registra `expense.registered` |
| `app.set_expense_category(p_id, p_category)` | Solo en un gasto no anulado (`expense_wrong_state`). Si la categoría es la misma, no hace nada ni registra. Registra `expense.category_changed` |
| `app.void_expense(p_id)` | Pone `voided_at = now()` (`expense_wrong_state` si ya estaba anulado). Si es de documento, lo devuelve a `review` si tiene lectura y a `extraction_failed` si no; su `review` se conserva. Registra `expense.voided`. Devuelve el estado del documento, o nulo |

**Lo que la función no puede garantizar:** que el NIF sea válido, que la cuota cuadre con el tipo o que no sea un duplicado salvo el exacto; eso es de `cuadre.validators` (D-01). Recomprueba lo que se puede sin duplicar las reglas fiscales.

**Trigger de `expenses`** (`expenses_guard`, `BEFORE UPDATE`): solo cambian `category`, `voided_at` y `updated_at`; cualquier otra columna da `expense_immutable_column`. `voided_at` solo pasa de nulo a no nulo (`expense_already_voided`) y una vez anulado, la categoría tampoco cambia.

**`documents_guard` ampliado** (sustituye al de SPEC-W-002): `discarded` sigue siendo terminal; `registered` deja de serlo. Transiciones nuevas: `review → registered` y `extraction_failed → registered`, **solo si existe un gasto no anulado de ese documento**; `registered → review` y `registered → extraction_failed`, **solo si el gasto de ese documento se ha anulado en esta misma transacción**
(`voided_at = now()`, que en PostgreSQL es la hora de la transacción). Cualquier otra actualización de un `registered` sigue dando `document_invalid_transition`. `discard_document` y `save_document_review` siguen respondiendo `document_wrong_state` sobre un `registered`. La lectura original sigue congelada.

**`activity_log`** (categoría `data`, `owner_id` = la persona): `expense.registered` `{expense_id, document_id, origin, category, acknowledged_suspicion}`, `expense.category_changed` `{expense_id, from_category, to_category}` y `expense.voided` `{expense_id, origin}`. **Nunca** nombres, NIF, números de factura ni importes.

**Matriz de RLS.** `expenses`: `kind: financial`, `owner_column: owner_id`, privilegios `SELECT`, y un `seed` que inserta un gasto manual por persona (sin él, «nadie ve nada» sería una afirmación vacía). Dueño ve el suyo; el gestor, el de quien le dio acceso activo; el administrador, ninguno.

### 5.3 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador); errores en `application/problem+json` como en SPEC-W-001. Los errores de forma del cuerpo son el `validation_error` 422 de siempre.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `confirm_document` | `POST /api/documents/{id}/confirm` | Cuerpo `{ "category": ExpenseCategory, "acknowledge_suspicion": bool }` (`false` por defecto). En **una transacción**: bloquea el documento (`app.lock_document`), recalcula la validación sobre lo guardado y, si todo pasa, llama a `app.register_expense_from_document`. **201** `Expense`. Estados `review` y `extraction_failed` |
| `create_expense` | `POST /api/expenses` | Cuerpo `{ "expense_date": date, "concept": string, "category": ExpenseCategory, "amount_cents": int }`. **201** `Expense`. Gasto sin factura |
| `list_expenses` | `GET /api/expenses` | Parámetros opcionales `limit` (50 por defecto, máximo 100), `cursor`, `year`, `month` (exige `year`) y `category`. **200** `{ "items": [ExpenseSummary], "next_cursor": string \| null }`, sin anulados, de la fecha más reciente a la más antigua (`expense_date`, `created_at`, `id`). `cursor` es opaco; uno manipulado da `invalid_cursor` |
| `get_expense` | `GET /api/expenses/{id}` | **200** `Expense`, también un anulado (con `voided_at`) |
| `set_expense_category` | `PUT /api/expenses/{id}/category` | Cuerpo `{ "category": ExpenseCategory }`. **200** `Expense` |
| `void_expense` | `POST /api/expenses/{id}/void` | Sin cuerpo. **200** `{ "id", "document_id": uuid \| null, "document_status": DocumentStatus \| null }` |

`ExpenseSummary` = `{ id, origin, expense_date, supplier_name, category, total_cents, vat_cents, deductible_vat, supplier_scope, document_id }`.
`Expense` = `ExpenseSummary` + `{ doc_type, supplier_tax_id, invoice_number, base_cents, withholding_cents, tax_breakdown, suspicion_acknowledged, created_at, voided_at }`. **Todos los importes son `*_cents` enteros** (ADR-0006).

**`Validation`** (en `Document.validation`; nulo si no hay `review` ni `extraction` que comprobar, y en cualquier estado que no sea `review` o `extraction_failed`):

```
Validation {
  can_register: bool                  # todas las comprobaciones en ok
  requires_acknowledgement: bool      # injection_suspected
  checks:   [ { code: CheckCode, label: string, status: "ok"|"failed", detail: string|null } ]    # orden y lista de §5.1
  warnings: [ { code: WarningCode, message: string } ]
  preview:  { supplier_scope: "national"|"eu"|null, deductible_vat: bool, deductible_note: string|null, suggested_category: ExpenseCategory }
}
```

`Document` gana `validation` y `expense_id` (el gasto no anulado del documento, o nulo). **Cambios en lo ya hecho:** `list_documents` deja de listar los `registered` (pasan a la lista de gastos); `get_document` y `get_document_preview` ya funcionan sobre un `registered`, y esta spec lo fija con una prueba.
`validate_extraction`, que SPEC-W-002 §5.1 reservaba, **no es una ruta**: la validación viaja en el documento para no tener dos fuentes de la misma regla (D-02).

**Códigos de error nuevos** (`code`, HTTP): `validation_failed` 422 (con el miembro extra `failed_checks: [code]`; no se registra nada) · `suspicion_not_acknowledged` 422 · `duplicate_expense` 409 (lo detecta el índice único, también si dos confirmaciones llegan a la vez) · `invalid_expense` 422 (un gasto sin factura con fecha futura o fuera de rango; con `field`) ·
`expense_not_found` 404 (también si es de otra persona: no se distingue) · `expense_wrong_state` 409 (ya anulado) · `invalid_cursor` 422. Los de documentos de SPEC-W-002 siguen igual (`document_wrong_state` 409 si ya está registrado o no está en un estado registrable). Los textos van en español y no repiten datos del documento.

### 5.4 Backend

- **Paquetes.** `cuadre.validators` (puro: `tax_id`, `dates`, `vat`, `duplicates`, `deductibility`, `categories`, `checks`, `limits`) y `cuadre.expenses` (`service`, `repository`, `models`, `presentation`, `errors`). `api/routes_expenses.py`; las rutas de `confirm_document` van con las de documentos.
- **Flujo de `confirm_document`.** Una transacción corta (sin esperas externas): `app.lock_document` → leer el perfil (NIF propio) y los gastos del mismo proveedor (por RLS, como la persona) → `validate(...)` → si falla, `validation_failed` → `register_expense_from_document` con los valores ya normalizados → confirmar. El error `23505` del índice se traduce a `duplicate_expense` según el nombre del índice.
- **Reloj.** `cuadre.core.clock.Clock` (un `Protocol` con `now()`) y `SystemClock`; `today` se calcula en `Europe/Madrid` y se pasa a los validadores. Los tests inyectan uno fijo (SPEC-W-012 lo reutilizará). Se declara `tzdata` como dependencia del backend (en Windows `zoneinfo` lo necesita; hoy está instalado, pero no declarado).
- **Dependencias nuevas:** `python-stdnum==2.2` (la última publicada el 2026-11-06; licencia LGPL-2.1+, se usa solo como biblioteca, sin copiar código) y `tzdata`. Se instala **sin extras** (`zeep`, que usa la consulta a VIES, no entra). Un test comprueba que el pin está en `backend/pyproject.toml` y que `cuadre.validators` no usa `check_vies*` ni `get_soap_client` (nada sale a la red, T3-03; el spike midió 0 intentos de red, Anexo B.1).
- **`test_operation_ids`** añade el verbo `void`; `confirm`, `create`, `list`, `get` y `set` ya existen.

### 5.5 Frontend

| Ruta | Quién | Contenido |
|---|---|---|
| `/gastos/[id]` | `usuario` | Lo de SPEC-W-002 más: lista de comprobaciones (icono y texto, no solo color) con su motivo, avisos, «Se deducirá el IVA: sí/no» con su razón, selector de categoría con la **sugerida** marcada, casilla «He comparado los datos con el original» si hay sospecha y «**Registrar gasto**» (activo solo con todo en verde, el formulario guardado y la casilla marcada si hace falta). Un documento `registered` redirige a su gasto |
| `/gastos` | `usuario` | Lo de SPEC-W-002 más: «Gastos registrados» (tarjetas en 390 px y tabla en 1.440 px, sin scroll horizontal; fecha, proveedor o concepto, categoría, total, y las marcas «Sin factura», «IVA no deducible» y «UE»), enlace «Ver más antiguos» (parámetro `cursor`) y «Añadir gasto sin factura» |
| `/gastos/nuevo` | `usuario` | Formulario «Gasto sin factura»: concepto, categoría (por defecto «Cuota de autónomos» como el prototipo), importe (con `parseAmount`, que rechaza lo ambiguo) y fecha |
| `/gastos/registrados/[id]` | `usuario` | Detalle de solo lectura (datos, líneas de IVA, original), cambio de categoría y «Anular gasto» en dos pasos (sin `confirm()`); un anulado se ve marcado y sin acciones |

Registrar, anotar, recategorizar y anular son **Server Actions** (son cortas: a diferencia de la lectura, no hay nada que esperar al agente). Tras registrar, `/gastos` con el aviso «Gasto registrado»; tras anular un gasto de documento, `/gastos/{document_id}` con «Gasto anulado: el documento vuelve a «Para revisar»». Las etiquetas de categoría viven en un `Record<ExpenseCategory, string>` tipado contra el enum del cliente generado: añadir una categoría sin etiqueta no compila.
La interfaz no valida nada fiscal: **muestra** el resultado del servidor. Si hay cambios sin guardar, avisa «Guarda los cambios para volver a comprobar» y el botón queda desactivado (D-02). La casilla de reconocimiento y cada comprobación llevan etiqueta y se anuncian con `aria-live`.

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T3-01 | **Sin modelos de lenguaje** (RES-01, ADR-0012): ni para el NIF, ni para la categoría, ni para la deducibilidad. Se mantienen `test_no_llm_sdk` y las guardas de W-001 y W-002 |
| T3-02 | **Sin `float`** en código, migraciones ni jsonb: céntimos enteros y `Decimal` solo en el cálculo de cuota y retención. `test_no_float` sigue verde |
| T3-03 | **Validadores puros**: `cuadre.validators` no importa base de datos, `httpx`, FastAPI ni usa `datetime.now()` / `time` (el reloj entra como parámetro) y **no sale a la red** (ni VIES). Toda llamada a `python-stdnum` va **después** del prefiltro ASCII y dentro de un `try` que convierte cualquier excepción en «no válido» (Anexo B.1). Lo vigila `backend/tests/rules/test_validators_boundary.py`, como `test_agents_boundary` |
| T3-04 | **Una fuente por regla.** Los dígitos de control los pone solo `python-stdnum`; la normalización del número de factura vive en la base (columna generada) y su réplica en Python se prueba contra ella con un corpus; las constantes (tolerancia, tipos permitidos, tope de líneas…) no se repiten, y si se repiten, un test las compara |
| T3-05 | **Validar y registrar, atómico**: en una sola transacción con el documento bloqueado. Dos confirmaciones del mismo documento: una gana y la otra recibe `document_wrong_state`; dos documentos con la misma factura: uno se registra y el otro `duplicate_expense` |
| T3-06 | **La lectura sigue siendo un dato no confiable** (T2-05): `injection_suspected` exige reconocimiento y **nunca valida ni exime** de ninguna comprobación; la sugerencia de categoría solo puede devolver uno de los ocho valores |
| T3-07 | **Solo `usuario` escribe**; el gestor lee con vínculo activo (revocar corta el acceso en la petición siguiente) y el administrador no ve nada. La service key no interviene (T2-03) |
| T3-08 | **Sin datos sensibles** en logs, trazas ni `activity_log`: ni NIF, ni nombres, ni números de factura, ni importes (NFR-11). Un test captura los registros de todo el flujo |
| T3-09 | **Sin trabajo posterior a la respuesta** (ADR-0016): todo ocurre dentro de la petición. `test_vercel_compat` sigue verde |
| T3-10 | **Lo registrado no se edita ni se borra**: solo cambia la categoría y solo se anula (con rastro). `expenses` no tiene escritura directa ni `DELETE` |
| T3-11 | **Interfaz** como T2-11: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, anuncios con `aria-live`, sin scroll horizontal a 390 y 1.440 px en los tres navegadores |
| T3-12 | **Migraciones sin datos reales y sin destructivas**; no se editan las aplicadas (`documents_guard` se sustituye con una migración nueva). Los archivos de prueba son sintéticos (RES-07) y los NIF de los tests son de ejemplo |

## 7. Criterios de aceptación (Given-When-Then)

```gherkin
AC-01  Suma que no cuadra (US-005, fixture invoice_sum_mismatch)
  Given una factura leída con base 120,00 €, cuota 25,20 € y total 147,00 €
  When la app valida la lectura
  Then la comprobación "Base más IVA igual al total" aparece como fallida con su motivo
    And "Registrar gasto" está desactivado
    And POST /confirm responde 422 "validation_failed" con failed_checks = ["total"] y no se crea ningún gasto

AC-02  Registro de una factura correcta
  Given una factura de un proveedor español (fixture invoice_ok) con todas las comprobaciones en verde
  When la persona elige categoría y confirma
  Then se crea un gasto con importes en céntimos, deducible, con su NIF y su número normalizados
    And el documento pasa a "registered", deja la lista de documentos y aparece en "Gastos registrados"
    And se registra "expense.registered" sin nombre, NIF, número ni importes

AC-03  NIF español
  Given NIF de persona, NIE, CIF y K, L y M válidos (con y sin prefijo "ES", en minúsculas, con espacios, puntos o guiones), y otros con la letra o el dígito de control equivocado o vacíos
    And entradas hostiles: un salto de línea o un carácter de control en medio con la letra de control que corresponde a los dígitos, espacios de no separación, cifras de ancho completo y ligaduras
  Then los válidos pasan y se guardan sin "ES" y compactos, y los demás fallan con su motivo ("revisa el dígito o la letra de control", "falta el NIF")
    And las hostiles se rechazan sin excepción ni error 500 y nunca llegan a la clave de duplicados

AC-04  NIF-IVA de la UE y no reconocidos (D-05)
  Given un NIF-IVA válido de Alemania, uno de Grecia con prefijo "EL" y el mismo con "GR", uno de la UE con el dígito mal, y números con prefijo "XI", "EU" y "GB" y un identificador de fuera de la UE
  Then los de Alemania y Grecia pasan con supplier_scope = "eu", deductible_vat = false y el aviso "eu_supplier"
    And "GR…" y "EL…" dan la misma clave, "EL…"
    And el del dígito mal falla por su control y los de "XI", "EU", "GB" y fuera de la UE como "no reconocido"
    And la validación no hace ninguna llamada de red

AC-05  Fecha
  Given un reloj fijo y fechas de mañana, de hoy, de ayer, imposible (30 de febrero) y anterior a 2000
  Then fallan la de mañana, la imposible y la anterior a 2000; pasan la de hoy y la de ayer
    And con el reloj a las 23:30 UTC del 31 de diciembre (en Madrid ya es 1 de enero), una fecha del 1 de enero pasa y una del 2 de enero falla

AC-06  Tipos de IVA, cuota y total en la frontera (D-03)
  Given tipos 21, 21.00, 19 y 7 con proveedor español, y el 23 con proveedor de la UE
  And cuotas a 1 y a 2 céntimos de la esperada, y totales a 1 y a 2 céntimos de la suma
  Then 21 y 21.00 pasan, 19 y 7 fallan en España y 23 pasa en la UE
    And la cuota y el total a 1 céntimo pasan y a 2 fallan, con una tabla de importes con "trampas" de coma flotante (0,29, 1,15, 4,35)

AC-07  Retención
  Given una factura con retención del 15 % de 1.000,00 €, con el importe correcto, con otro y sin importe
  Then solo el correcto pasa, y el total se comprueba como base + IVA − retención

AC-08  Duplicados (D-04)
  Given un gasto registrado con un NIF español válido (sintético) y el número "A-311"
  When llega otra factura con el mismo NIF escrito en minúsculas y con espacios, o con "ES" delante, y el número "a311"
  Then "No está registrada ya" falla; tras anular el primero, pasa
  And dos confirmaciones simultáneas de la misma factura en dos documentos distintos dejan exactamente un gasto y devuelven 409 "duplicate_expense" a la otra
  And un ticket sin número con el mismo día, total y NIF muestra el aviso "possible_duplicate" y sí se puede registrar

AC-09  Sospecha de instrucciones ocultas (NFR-07, fixture invoice_injection)
  Given un documento con injection_suspected = true y todas las comprobaciones en verde
  When se confirma sin acknowledge_suspicion
  Then responde 422 "suspicion_not_acknowledged" y no se registra nada
    And con acknowledge_suspicion = true se registra, con suspicion_acknowledged = true en el gasto
    And llamar a app.register_expense_from_document sin reconocerlo falla también en la base
    And la sospecha no cambia el resultado de ninguna comprobación

AC-10  Moneda, tipo de documento, importes y dudosos
  Given una factura en USD, un documento "not_an_invoice", un total negativo o cero, y un documento con dudosos que la persona no ha guardado nunca
  Then fallan "Importe en euros" (con la sugerencia de anotarlo a mano), "Tipo de documento válido", "Datos obligatorios completos" y "Datos dudosos revisados"
    And al guardar el formulario sin cambios, "Datos dudosos revisados" pasa

AC-11  Gasto sin factura (RF-011)
  Given concepto "Cuota de autónomos", categoría, importe 294,00 € y una fecha pasada
  When se crea
  Then se registra un gasto "manual" sin IVA, no deducible, con base = total
    And un concepto vacío, un importe 0 o negativo, una fecha futura o una categoría fuera de la lista se rechazan sin crear nada, con el mensaje junto a su campo

AC-12  Categorías (D-08)
  Given proveedores "Nubesoft S.L.", "Imprenta Sol", "Espacio Común", "Papelería Arce", "Gestoría Puerta" y uno cualquiera
  Then la sugerida es software, supplies, workspace, supplies, advisory y other, y la persona puede elegir otra
    And cambiar la categoría de un gasto registrado la actualiza y registra "expense.category_changed" una sola vez (cambiar a la misma no registra nada)
    And las ocho etiquetas existen en español y no hay categorías sin etiqueta

AC-13  Anular y volver a registrar (D-10)
  Given un gasto registrado a partir de un documento con lectura
  When la persona lo anula
  Then el gasto deja de contar y de salir en la lista, se registra "expense.voided", y el documento vuelve a "review" con su "review" intacta
    And se puede corregir y registrar de nuevo, y ese segundo gasto es un gasto nuevo
    And anular otra vez devuelve 409 "expense_wrong_state"
    And un gasto sin factura anulado no vuelve y un documento que nunca tuvo lectura vuelve a "extraction_failed"
    And un documento "registered" no se puede descartar ni guardar (409 "document_wrong_state") mientras su gasto cuente

AC-14  Lista y detalle
  Given 120 gastos de varios meses y categorías, y uno anulado
  Then list_expenses devuelve páginas de 50 de la fecha más reciente a la más antigua, sin el anulado, sin repetir ni saltarse ninguno al seguir next_cursor
    And los filtros de año, mes y categoría funcionan y un cursor manipulado da 422 "invalid_cursor"
    And get_expense devuelve el gasto (también el anulado, marcado) y su documento original se puede abrir

AC-15  Aislamiento (NFR-06)
  Given Alicia con gastos, Beto, Gina (gestor) y Adán (admin)
  Then Beto no ve ni toca los gastos de Alicia (404 "expense_not_found")
    And Gina los lee solo con vínculo activo (con pendiente, revocado o rechazado, no) y no puede registrar, anotar, recategorizar ni anular (403 en la API y sin política de escritura en la base)
    And Adán no ve ninguno, y la matriz de RLS lo prueba

AC-16  Invariantes de la base
  Given acceso directo a la base como cada rol
  Then no hay forma de insertar, actualizar ni borrar un gasto sin pasar por app.*
    And un gasto con importes no enteros, negativos, un total que difiere más de 1 céntimo, deducible de un proveedor de la UE o con líneas que no suman la base se rechaza
    And solo cambian la categoría y voided_at, y voided_at no vuelve a nulo
    And documents_guard solo permite los nuevos cambios de estado con su gasto (registrar con uno vivo, volver con uno anulado en la misma transacción)

AC-17  Sin datos sensibles en los registros (NFR-11)
  Given el flujo completo: registrar, anotar un gasto sin factura, recategorizar, anular y los fallos de validación
  Then ningún registro ni activity_log contiene NIF, nombres, números de factura, importes ni la URL firmada del original

AC-18  Interfaz (NFR-10)
  Given viewports de 390 y 1.440 px en Chromium, Firefox y WebKit
  Then la lista de comprobaciones muestra icono y texto, "Registrar gasto" cambia de estado como dice §5.5, la casilla de reconocimiento aparece solo con sospecha, el formulario "Gasto sin factura" y los gastos registrados caben sin scroll horizontal, y todo campo tiene etiqueta

AC-19  Guardas del proyecto
  Then expenses figura en rls_matrix.yaml con RLS forzada; test_rls_guard, test_no_float, test_no_llm_sdk, test_service_key_scope, test_operation_ids (con "void"), test_openapi_drift, test_vercel_compat, test_validators_boundary y gen:api --check siguen en verde
```

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-002 §8.1, con la pila de Supabase en marcha y los puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 libres. Sin red: los NIF de las pruebas son de ejemplo y nada consulta VIES.
Los ejemplos de `contracts/examples/extract/` sirven tal cual para el E2E (comprobado al especificar con el algoritmo del NIF y del CIF): sus NIF de proveedor son CIF válidos y sus cifras cuadran, salvo `invoice_sum_mismatch` (la suma, a propósito) e `invoice_doubtful_nif` (NIF vacío, a propósito). `ticket_simplified` no lleva NIF de destinatario, así que no es deducible.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"      # entra python-stdnum 2.2 (y tzdata)
npx supabase db reset                                                 # migraciones + seed
pytest backend/tests/validators backend/tests/expenses -q            # AC-01 a AC-15 (lado API) y AC-17
pytest backend/tests/rls -m rls -q                                    # AC-15, AC-16 (expenses y documents_guard)
pytest backend/tests -m "not rls" -q
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/gastos-registro.spec.ts      # AC-18 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/validators backend/tests/expenses` y `npm --prefix frontend exec -- playwright test e2e/gastos-registro.spec.ts`, además de las secuencias completas de SPEC-W-001 §8.2 y SPEC-W-002 §8.2, que deben seguir en verde (incluida la batería de E2E: se ejecuta con `--workers=1` y un motor por invocación si hay poca memoria libre).

### 8.3 Correspondencia criterio → prueba

| AC | Prueba |
|---|---|
| AC-01 | `backend/tests/validators/test_checks.py` (el escenario de US-005 de punta a punta); `backend/tests/expenses/test_confirm.py` (422 y nada registrado); `frontend/e2e/gastos-registro.spec.ts` · «suma que no cuadra» |
| AC-02 | `backend/tests/expenses/test_confirm.py`, `test_no_sensitive_logs.py`; `frontend/e2e/gastos-registro.spec.ts` · «registrar una factura» |
| AC-03, AC-04 | `backend/tests/validators/test_tax_id.py` (tablas de valores sintéticos; sin red, comprobado con un guard de sockets) |
| AC-05 | `backend/tests/validators/test_dates.py` (reloj fijo, frontera de Madrid) |
| AC-06, AC-07 | `backend/tests/validators/test_vat.py` (fronteras de ±1 y ±2 céntimos, importes con trampas de coma flotante) |
| AC-08 | `backend/tests/validators/test_duplicates.py` (normalización y **paridad con la columna generada**); `backend/tests/expenses/test_concurrency.py` (dos confirmaciones a la vez); `frontend/e2e/gastos-registro.spec.ts` · «la misma factura dos veces» |
| AC-09 | `backend/tests/expenses/test_confirm.py`; `backend/tests/rls/test_expenses_states.py` (la función SQL sin reconocimiento); `frontend/e2e/gastos-registro.spec.ts` · «instrucciones ocultas» |
| AC-10 | `backend/tests/validators/test_checks.py`, `test_deductibility.py`; `frontend/e2e/gastos-registro.spec.ts` · «dato dudoso» (reinterpreta el AC-02 de SPEC-W-002: el botón está desactivado mientras haya comprobaciones fallidas, ya no «hasta SPEC-W-003») |
| AC-11 | `backend/tests/expenses/test_manual_expense.py`; `frontend/src/lib/expenses.test.ts`; `frontend/e2e/gastos-registro.spec.ts` · «gasto sin factura» |
| AC-12 | `backend/tests/validators/test_categories.py`; `backend/tests/expenses/test_categories_api.py`; `frontend/src/lib/expenses.test.ts` (etiquetas completas) |
| AC-13 | `backend/tests/expenses/test_void.py`; `backend/tests/rls/test_expenses_states.py`; `frontend/e2e/gastos-registro.spec.ts` · «anular y volver a registrar» |
| AC-14 | `backend/tests/expenses/test_list_expenses.py` (paginación, filtros, cursor); `frontend/e2e/gastos-registro.spec.ts` |
| AC-15 | `backend/tests/rls/test_expenses.py` y `rls_matrix.yaml`; lado API: `backend/tests/expenses/test_roles.py` |
| AC-16 | `backend/tests/rls/test_expenses_states.py` (CHECK, índices, trigger, `documents_guard`) |
| AC-17 | `backend/tests/expenses/test_no_sensitive_logs.py` |
| AC-18 | `frontend/e2e/gastos-registro.spec.ts` (seis proyectos) y `frontend/src/lib/expenses.test.ts` |
| AC-19 | `backend/tests/rls/test_rls_guard.py` y las guardas de `backend/tests/rules/` (incluida `test_validators_boundary.py`) |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001 y SPEC-W-002 §8.2 siguen en verde.
- [ ] `pytest backend/tests/rls -m rls` incluye `expenses` y el `documents_guard` ampliado.
- [ ] `python-stdnum` y `tzdata` están fijados en `backend/pyproject.toml` y un test lo comprueba; el CI instala el backend como hasta ahora.
- [ ] «Registrar gasto» está activo; el botón desactivado y el texto «Próximamente» de SPEC-W-002 se han retirado y `gastos-subida.spec.ts` se ha actualizado donde los daba por hechos.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0012, 0015 y 0016 enlazados.
- [ ] Sin secretos ni documentos reales en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike de `python-stdnum` 2.2**: qué acepta y qué rechaza cada función con valores **sintéticos** (NIF, NIE, CIF y NIF-IVA de los países de la UE), el prefijo `ES`, `EL` de Grecia y `XI` de Irlanda del Norte (por defecto no se admite), mayúsculas, espacios y guiones, y confirmar que la validación no usa la red. Resultado al Anexo B.
   **Hecho el 2026-11-06** (resultado en el Anexo B.1; corrigió el tratamiento del NIF en §3.1, §5.1, §5.4, T3-03, AC-03 y AC-04).
1. **Validadores puros** (`cuadre.validators`) con sus tablas de pruebas, `Clock`, dependencias fijadas y `test_validators_boundary`, con mutaciones.
   **Hecho el 2026-11-06** (resultado en el Anexo B.2: 528 pruebas, 11 guardas y 81 mutaciones detectadas; la paridad con SQL pasa al hito 2).
2. **Base de datos**: enums, `expenses`, funciones, trigger, `documents_guard` ampliado, matriz y `test_expenses` / `test_expenses_states`, con mutaciones.
3. **API**: `cuadre.expenses`, `confirm_document` y las cinco rutas de gastos, `Document.validation` y `expense_id`, `openapi.json` y `schema.d.ts` regenerados, verbo `void`, con mutaciones.
4. **Frontend**: lista de comprobaciones, categoría, registrar, gastos registrados, gasto sin factura, detalle y anulación; unitarias.
5. **E2E y cierre**: `gastos-registro.spec.ts` (tres motores, dos anchos), actualizar `gastos-subida.spec.ts`, mutaciones, Anexo B, `tasks.json` y commit.

## Anexo B · Decisiones que esta spec dejó a la implementación

*(Se rellena al implementar.)*

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-008 (303).** Todo consumidor de `expenses` filtra `voided_at IS NULL`. Usa `deductible_vat` (no lo recalcula) y `supplier_scope`. **Hueco conocido (D-05):** los gastos con `supplier_scope = 'eu'` no tienen casilla en el 303 de la v1 (adquisiciones intracomunitarias, casillas propias); decidir allí cómo declararlos o avisar.
- **SPEC-W-009 (130).** Cuenta como gasto la base más el IVA no deducible; las fórmulas son suyas. Los gastos de la UE y los sin factura cuentan.
- **SPEC-W-005 (perfil).** Sin el NIF en `business_profiles.tax_id`, ninguna factura simplificada ni ticket es deducible y el aviso `recipient_mismatch` no puede darse. Conviene un aviso «completa tu perfil» junto a las simplificadas.
- **SPEC-W-010 (gestor).** La política de lectura de `expenses` ya existe; faltan la pantalla y el registro de cada lectura. El gestor ve también los anulados: la pantalla decide si los muestra.
- **SPEC-W-011 (MCP).** `gastos_por_categoria` devuelve `categoria` como la etiqueta en español: debe salir de la misma tabla que usa la interfaz (`cuadre.validators.categories`), no de una copia. `iva_cents` y `retencion_cents` son los de los gastos no anulados.
- **SPEC-W-012 (cierre mensual).** Registrar o anular un gasto con fecha de un mes ya cerrado exige reabrirlo; esta spec no mira los cierres.
- **SPEC-W-002.** Su AC-02 («no existe ninguna ruta que registre un gasto») queda superado por esta spec: el botón está desactivado mientras haya comprobaciones fallidas.

### B.1 Spike de `python-stdnum` · hito 0 · 2026-11-06

Entorno: `python-stdnum` 2.2 (rueda `python_stdnum-2.2-py3-none-any.whl`, 1.193.213 bytes, **sha256 idéntico al que publica PyPI**), Python 3.12.10 en Windows, instalada **aparte** (`pip install --target`): ni el `.venv` ni `backend/pyproject.toml` han cambiado. Script desechable, no commiteado, con semilla fija: tres ejecuciones dan el mismo resultado. Toda la batería corre bajo una guarda que hace fallar y cuenta cualquier intento de abrir un socket o resolver un nombre: **0 intentos**. Todo lo de abajo es lo observado, no lo leído en la documentación.

| Pregunta | Resultado |
|---|---|
| **Paquete** | LGPL-2.1+ (clasificador `LGPLv2+`); sin dependencias obligatorias (`zeep`, que usa la consulta a VIES, es el extra `soap`, que no se instala); Python ≥ 3.8. Importar `stdnum.es.nif` o `stdnum.eu.vat` en frío cuesta de 57 a 76 ms (tres repeticiones; incluye el paquete base) |
| **¿Sale a la red?** | No. Más de 200.000 comprobaciones con la guarda de red activa, 0 intentos. `check_vies`, que es aparte, falla con `ImportError` (no hay `zeep`) antes de tocar la red. Tras importar quedan cargados `ssl` y `urllib.parse` (biblioteca estándar); `socket` lo carga la propia guarda |
| **¿Qué valida `es.nif.validate`?** | DNI, NIE (X, Y, Z), CIF y los especiales K, L y M (estos solo con el algoritmo del DNI). Normaliza el `ES` inicial, las minúsculas, los espacios, los guiones y los blancos de los extremos. **No quita los puntos** (`12.345.678-Z` da `InvalidFormat`). Con 8 o 10 caracteres, `InvalidLength`; con el control equivocado, `InvalidChecksum`; vacío y `None`, `InvalidFormat`. Con `ES` delante, `eu.vat` devuelve el número **con** el prefijo |
| **CIF** | Para los 17 tipos de entidad (A a W) acepta **tanto el dígito como la letra de control**. La regla habitual (dígito en A, B, E y H; letra en N, P, Q, R, S y W; no contrastada aquí con la norma) es más estricta: la librería es más permisiva en 10 de los 17 tipos. No se arregla sin duplicar reglas (T3-04): queda como límite conocido |
| **K, L y M** | La librería los acepta; la rutina del prototipo, no. Son NIF reales de personas (menores, residentes en el extranjero, extranjeros sin NIE). Se aceptan, igual que la librería: una sola fuente |
| **Contraste con el prototipo** | 200.000 cadenas con forma de NIF: coinciden 199.638 (73.645 válidas y 125.993 inválidas). Las 362 que difieren son **todas K, L o M** y solo las acepta la librería; ninguna que el prototipo dé por buena y la librería no |
| **Ejemplos de `contracts/examples/`** | Los 8 identificadores fiscales (los CIF de proveedor `B00000042`, `B00000091`, `B00000075` y `B00000059`, y el DNI de destinatario `12345678Z` de cuatro ejemplos) **son válidos con la librería**, no solo con la rutina del prototipo: el E2E del hito 5 los usa tal cual |
| **UE: cobertura** | Se obtuvo un número sintético válido para los **26 países** distintos de España, que va por `es.nif`; ninguno quedó «no probado» |
| **UE: prefijo y separadores** | El prefijo de país es **obligatorio** (sin él o con una letra, `InvalidComponent`; con tres letras o solo el prefijo, `InvalidFormat`) y se acepta en minúsculas. Los separadores **no se quitan igual en todos los países**: con espacio, bien en los 26; con guion, falla en CZ y EE; con puntos, falla en 15 de los 26. El normalizador debe quitar espacios, puntos y guiones **antes** de llamar |
| **UE: control** | Cambiar el último dígito se rechaza 9 de cada 9 veces en casi todos los países. No aplica donde ese carácter no es de control (CZ de 9 dígitos y NL, cuyo sufijo `B` y dos cifras es libre; CY e IE terminan en letra) y en BG una de las nueve mutaciones sigue siendo válida. **RO** acepta de 2 a 10 dígitos con un solo control (módulo 11): `RO9573` es «válido». La validación de Rumanía es débil, y las pruebas de «control mal» deben comprobar que la mutación elegida se rechaza |
| **Grecia** | `EL` y `GR` se aceptan (misma validación) y **se devuelven tal como se escribieron**: sin tratarlo, `EL…` y `GR…` serían dos proveedores distintos. La clave se unifica en `EL`. Un número de 8 cifras se completa con un 0 delante |
| **Prefijos que no son un Estado miembro** | La librería acepta `XI` (Irlanda del Norte, con el algoritmo de GB) y `EU` (esquema OSS), y **rechaza `GB`** con el mismo cuerpo, `CHE…` (Suiza), `NO…MVA` y `US…` (`InvalidComponent`). Con `IM` (isla de Man) y 9 dígitos no salió ningún número válido en 40.000 intentos: no se sabe si lo acepta. Hace falta una **lista blanca propia**: España y los 26 países, con `EL` (y `GR` convertido a `EL`) y sin `XI`, `EU`, `IM` ni `GB` |
| **Caracteres raros insertados** | De 992 combinaciones: la librería recorta saltos de línea, tabuladores, tabulador vertical, avance de página, `NEL` y separador de línea al principio y al final, y quita el espacio de no separación en cualquier posición. Normaliza los dígitos de ancho completo (un `3` de ancho completo vale `3`) y la ligadura «ﬁ» (U+FB01) como `FI`. No acepta dígitos arábigos ni el superíndice. Siempre devuelve un resultado limpio (solo `A-Z` y `0-9`) y no lanzó excepciones fuera de `ValidationError` |
| **La rendija del `$` en `isdigits`** | **Confirmada.** De 610 entradas **fabricadas** con un salto de línea en la penúltima posición y la letra de control que corresponde a los dígitos anteriores (el algoritmo usa `int()`, que ignora el salto), **la librería valida las 440 de DNI, NIE y K/L/M y devuelve un resultado con el salto de línea dentro** (siete dígitos, un salto de línea y una letra). Las 170 de CIF lanzan **`ValueError`**, que no es `ValidationError`. Sin defensa propia, un identificador así llegaría a la clave de duplicados o rompería la API con un 500 |
| **Entradas largas** | 10.000 caracteres: rechazadas en menos de 3 ms |
| **Normalización candidata** | Prefiltro `[0-9A-Za-z .-]{1,32}` con `fullmatch`; se quitan espacios, puntos y guiones; mayúsculas; si empieza por `ES`, NIF español sin prefijo; si no, otro prefijo de la lista blanca (`GR` pasa a `EL`) y NIF-IVA con prefijo; cualquier excepción es «no válido» y el resultado ha de ser `[A-Z0-9]{5,20}`. Es idempotente; `ES B…` y `B…` dan la misma clave, y `GR…` y `EL…` también; `XI`, `EU` y `GB` se rechazan. **Ninguna de las 2.369 entradas con caracteres raros o fabricadas** (992 insertados, 767 sustituidos y 610 fabricadas) **pasa el prefiltro**. Las claves miden de 6 (RO) a 14 caracteres: caben en el `CHECK` de 5 a 20 de `expenses.supplier_tax_id` |

**Valores sintéticos** (calculados con la propia librería a partir de cuerpos aleatorios con semilla fija, sin copiar los de nadie, salvo `12345678Z`, el DNI de ejemplo que ya usan el prototipo y `contracts/`; pueden coincidir por azar con números reales y no identifican a nadie, RES-07):
- España: DNI `12345678Z` y `01230956L`; NIE `X4001342D`, `Y2492503F`, `Z8019878J`; K, L y M `K3315686Y`, `L1261942R`, `M6637350X`; CIF con control numérico `A30789028` y con letra `P7766239C`.
- UE (sin España): AT `ATU84543291`, BE `BE1981162939`, BG `BG1096398855`, CY `CY76957253G`, CZ `CZ532215599`, DE `DE534861408`, DK `DK11659721`, EE `EE050611436`, EL `EL333906790`, FI `FI14848328`, FR `FR89195505110`, HR `HR95593513929`, HU `HU46727594`, IE `IE9134973S`, IT `IT65531970062`, LT `LT709161183614`, LU `LU74142252`, LV `LV85251632718`, MT `MT55619217`, NL `NL131073515B49`, PL `PL8023132347`, PT `PT731220820`, RO `RO9573`, SE `SE768590534601`, SI `SI53348966`, SK `SK7592280674`.
- Fuera de la lista blanca, solo para las pruebas de rechazo: `XI722847175` (con `GB` y el mismo cuerpo, la librería lo rechaza) y `EU440138732`.

**Lo que no se ha comprobado:**
- **Otras formas de cada país.** Se obtuvo una forma válida por país; no se recorrieron todos los formatos oficiales (BE y CZ en otras longitudes, IE con `+` o `*`, FR con letras…).
- **`IM`**, por lo dicho arriba.
- **Las reglas de control de K, L, M y del CIF contra la norma.** La librería es la fuente única (T3-04); no se contrastó con el BOE.
- **Que el número exista**: la consulta a VIES queda fuera por diseño (D-05).
- **El arranque en frío en Vercel**: los 57 a 76 ms son de Windows; no se midió allí.
- **Otras versiones de la librería.** El pin es 2.2: subirlo exige repetir esta batería, y el hito 1 la deja como prueba.
- **La rendija del `$` no se ha notificado** a los mantenedores de `python-stdnum`.

**Consecuencias para los hitos siguientes** (ya reflejadas en §3.1, §5.1, §5.4, T3-03, AC-03 y AC-04):
- **Prefiltro ASCII antes de la librería**, `try` ancho (cualquier excepción es «no válido») y comprobación de que lo devuelto es solo `[A-Z0-9]`. El hito 1 guarda como prueba de regresión las entradas fabricadas: si se quita el prefiltro, tiene que fallar.
- **Lista blanca de 27 países** (España y los 26), con `EL` y `GR` convertido a `EL`; `XI`, `EU`, `IM` y `GB` quedan fuera.
- El normalizador quita espacios, puntos y guiones, y acepta K, L y M.
- Límites conocidos: el CIF acepta dígito o letra de control en todos los tipos y la validación de Rumanía es débil. Las pruebas de «control mal» eligen una mutación que la librería rechaza.
- E2E del hito 5: los ejemplos de `contracts/examples/` valen tal cual.

### B.2 Hito 1 · validadores puros · 2026-11-06

**Qué hay.** El paquete `backend/src/cuadre/validators/` (once módulos, sin base de datos, red, FastAPI ni reloj propio) y `backend/src/cuadre/core/clock.py` (`Clock`, `SystemClock`, `today_in_madrid`). `validate(data, context)` devuelve las once comprobaciones de §5.1 en su orden fijo, los tres avisos, la vista previa (ámbito, deducibilidad con su motivo, categoría sugerida) y, solo si se puede registrar, los valores ya normalizados que recibirá la función SQL del hito 2. `from_stored(mapping)` lee la forma guardada en `review` y `extraction` (SPEC-W-002 §5.3), de modo que el hito 3 solo pasa `review ?? extraction`. Dependencias fijadas en `backend/pyproject.toml`: `python-stdnum==2.2` (sin extras) y `tzdata==2026.6`. Ningún `float` en el paquete.

**Decisiones tomadas al escribirlo** (la spec las dejaba abiertas o no las nombraba):

| Tema | Decisión |
|---|---|
| Lectura tolerante (`from_stored`) | Un booleano no es un entero; un texto en blanco es «sin dato»; una fecha que no es `AAAA-MM-DD` real (30 de febrero, `2026/11/01`, dígitos de ancho completo, una marca de tiempo) es **malformada**, distinta de ausente, y tiene su propio motivo; un elemento del desglose que no es un objeto cuenta como línea sin datos; `withholding: {}` es una retención que no se entendió (falla `withholding`), no «sin retención» |
| Comprobaciones condicionales | `doubts_reviewed` solo aparece si hay datos dudosos y `withholding` solo si la factura trae retención; `vat_rates`, `vat_amounts` y `total` dicen «No se puede comprobar…» cuando faltan los datos, en vez de dar un motivo falso |
| Importes | Un total cero o negativo, o una línea con base o cuota negativa, no se registra: el motivo dice que los abonos no se registran todavía. Más de 10 líneas de IVA se rechazan (el mismo tope que la lectura guardada) |
| Moneda | Sin moneda se da por euros; cualquier otra falla `currency` y el motivo remite al gasto sin factura |
| Número de factura | Solo la factura completa lo exige; un ticket, un recibo y una simplificada pueden no llevarlo. La clave es el número sin nada que no sea `[0-9A-Za-z]`, en mayúsculas (vacío es nulo) |
| Duplicados | Un duplicado duro no se anuncia además como posible. El blando exige NIF, día y total y no se da si ya es duro |
| `recipient_mismatch` | Necesita los dos NIF; uno del destinatario que no se entiende cuenta como distinto del tuyo |
| NIF | Además del flujo del B.1, una guarda contra el doble prefijo: la librería quita un `ES` inicial por su cuenta, así que `ES ES 12345678Z` pasaría por válido |
| Categoría | Coincidencia por **inicio de palabra** y sin tildes: «app» no casa con «Happy»; con varias candidatas gana el orden `software`, `supplies`, `workspace`, `utilities`, `advisory`; `training` y `self_employed_fee` no tienen palabras clave y se eligen a mano |
| Nombres | `ValidationWarning` en lugar de `Warning` (no tapa el del lenguaje); `money.format_euros` es un módulo aparte para los importes de los motivos; `FixedClock` vive en `backend/tests/clocks.py` y no en `tests/support.py` |
| `injection_suspected` | Solo cambia `requires_acknowledgement`: las comprobaciones, los avisos y `can_register` son idénticos con y sin sospecha (NFR-07) |

**Pruebas.** 528 en `backend/tests/validators` (tablas de valores sintéticos; el corpus de B.1 regenerado con la misma semilla: **2.369 entradas hostiles** que ni lanzan ni pasan; 5.000 casos de cuota y total contrastados con un cálculo racional independiente; fronteras de ±1 y ±2 céntimos, empates de medio-arriba, la frontera de Madrid a las 23:30 UTC; los seis ejemplos de `contracts/examples/extract/` pasados por `normalize_extraction` y `validate` de punta a punta) y 11 en `backend/tests/rules` (`test_validators_boundary.py`, cuyos detectores se prueban a sí mismos, y `test_stdnum_dependency.py`). Una prueba deja constancia de que la librería **sola** acepta 440 de las entradas fabricadas y lanza `ValueError` con 170: si alguien quita el prefiltro, tiene que fallar.

**Mutaciones.** 81, con un ejecutor desechable fuera del repositorio: NIF (sin prefiltro, `match` por `fullmatch`, excepción que se propaga, resultado de la librería sin comprobar, doble prefijo, `XI`/`EU`/`GB`/`IM` admitidos, `GR` sin unificar, puntos sin quitar, K/L/M rechazados), IVA y total (tolerancia 1→0 y 1→2, `ROUND_HALF_EVEN`, `float`, 19 % como tipo español, tope de la UE, retención sobre la primera línea), fecha y reloj (`>` por `>=`, 1990, UTC en lugar de Madrid, reloj sin zona), duplicados, deducibilidad, categorías (subcadena en lugar de inicio de palabra, sin tildes, orden de prioridad), composición (`any` por `all`, valores aunque no se pueda registrar, `injection_suspected` que bloquea o que se pierde, nombre sin recortar, ámbito siempre nacional) y las guardas (importar `psycopg`, leer el reloj, otro módulo que importa `stdnum`, `check_vies`, `python-stdnum` sin fijar o con el extra `soap`, `tzdata` sin fijar). **Las 81 hacen fallar la suite**, ninguna sobrevive y los archivos quedan idénticos por huella sha256. Antes de ejecutarlas se añadieron tres ficheros de pruebas (`test_tax_id_defenses.py`, `test_registrable_values.py`, `test_money.py`) para los huecos que se preveían (la librería sustituida por una que devuelve basura, los valores a registrar y los importes de los motivos); no se comprobó qué habría pasado sin ellos.

**Lo que no se ha comprobado:**
- **Paridad con SQL.** Nada de esto ha tocado una base de datos: que `normalize_invoice_number` coincida con la columna generada y que `ExpenseCategory` coincida con el enum son pruebas del hito 2.
- **Los metadatos del paquete editable de la `.venv`.** `pip install -e "backend[dev]"` necesita descargar `setuptools` y no se hizo sin red; `python-stdnum` se instaló desde la rueda verificada en B.1, `pip check` no da conflictos y un test comprueba que las versiones instaladas son las fijadas. El CI instala desde `pyproject.toml` y aún no se ha ejecutado (sin remoto).
- **`injection_suspected` real.** Las pruebas lo pasan en el contexto; que `documents.injection_suspected` llegue ahí es del hito 3.
- **Rendimiento y arranque en frío** en Vercel (ya dicho en B.1). Las 2.369 entradas hostiles y los 5.000 casos de cuota corren en menos de un segundo en esta máquina.

**Para el hito 2:**
- La columna generada de §5.2 es `nullif(upper(regexp_replace(invoice_number, '[^0-9A-Za-z]', '', 'g')), '')`, igual que `normalize_invoice_number`. La prueba de paridad debe incluir acentos, ligaduras, dígitos de ancho completo y saltos de línea, porque los rangos `[A-Za-z]` pueden depender del *collation* de la base.
- `CHECK (supplier_tax_id ~ '^[A-Z0-9]{5,20}$')`: probarlo con un valor que acabe en salto de línea, que es justo la rendija del B.1 (el prefiltro de Python usa `fullmatch`; en SQL hay que comprobar que `$` se comporta igual).
- Los campos de `RegistrableValues` (`expense_date`, `supplier_name`, `supplier_tax_id`, `supplier_scope`, `invoice_number`, `invoice_number_key`, `doc_type`, `base_cents`, `vat_cents`, `withholding_cents`, `total_cents`, `tax_lines`, `deductible_vat`) deben corresponder uno a uno con los parámetros de `app.register_expense_from_document` y las columnas de §5.2. Si alguno sobra o falta, se corrige en el hito 2, antes de la API.
