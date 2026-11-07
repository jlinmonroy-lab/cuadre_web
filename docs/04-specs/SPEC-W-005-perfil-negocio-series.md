---
tipo: spec
id: SPEC-W-005
titulo: Perfil personal y del negocio y series de facturación
estado: especificada
prioridad: must
riesgo: bajo
historias: [US-007]
requisitos: [RF-004]
nfr: [NFR-06, NFR-10, NFR-11]
restricciones: [RES-02, RES-07]
adr: [0003, 0004, 0006, 0011, 0015, 0016]
depende_de: [SPEC-W-001]
bloquea: [SPEC-W-006, SPEC-W-007]
fecha: 2026-11-07
---

# SPEC-W-005 · Perfil personal y del negocio y series de facturación

> Primer paso de la cadena **perfil → clientes → facturas**. La persona completa **una vez** sus datos fiscales y los de su negocio, y la aplicación los usa después: en las facturas emitidas (SPEC-W-007) y en las reglas fiscales de los gastos (SPEC-W-003).
> Lo que **no** hace es emitir facturas ni numerarlas: deja preparadas las **series** (su código y su número inicial) y la regla que dice qué falta para poder emitir. Emitir, numerar y bloquear son SPEC-W-007.

## 1. Contexto

**Situación de partida.** SPEC-W-001 creó la tabla `business_profiles` con las columnas de RF-004 (`legal_name`, `tax_id`, `fiscal_address`, `activity`, `iae_epigraph`, `activity_start_date`, `vat_regime`, `irpf_rate`, `logo_path`, `iban`, `home_pct`), su RLS (el dueño y el gestor con vínculo activo leen; el administrador solo la suya, D3), el `UPDATE` por columna para el dueño y un trigger de alta que crea la fila vacía con cada cuenta. **Nada más:** no hay ruta ni pantalla de perfil, ni entrada «Perfil» en el menú, ni series, ni bucket para el logo. El seed trae dos perfiles de ejemplo con un NIF (`TEST-0001`) y un IBAN (`ES00 0000 …`) que no son válidos.
SPEC-W-003 ya **lee** el perfil: `expenses/repository.py` (`profile_tax_id`) pasa el NIF de la persona a los validadores. Con el perfil vacío, ninguna factura simplificada ni ticket es deducible y el aviso `recipient_mismatch` no puede darse (B.0 de SPEC-W-003); esta spec cierra esa carencia. El prototipo (`docs/cuadre-interfaz.html`) no tiene pantalla de perfil: solo un objeto `db.profile` y el pie de la barra lateral («Diseño gráfico, retención del 7 %»); la pantalla se diseña aquí con los tokens y los patrones de Gastos.

**Por qué es de riesgo bajo, y dónde no lo es.** Es datos de formulario sobre una tabla que ya existe, sin cálculo fiscal ni agentes. Los puntos que merecen cuidado son tres: (1) el **NIF y el IBAN** son datos personales que no deben salir en logs ni en errores (NFR-11); (2) las **series** son el cimiento de la numeración correlativa sin huecos de SPEC-W-007 (RES-03): su modelo se decide aquí y cambiarlo después cuesta una migración con facturas emitidas; (3) el **logo** es el primer archivo que sube la persona que no es un documento fiscal, y exige un bucket y políticas propios.

**Decisiones vigentes** (no se reabren aquí): ADR-0003 y ADR-0015 (SQL explícito, reglas críticas en la base); ADR-0004 (Supabase UE; el cifrado en reposo del IBAN quedó como pregunta abierta); ADR-0006 (importes en céntimos; tipos y porcentajes en `Decimal`); ADR-0011 (cliente generado y `operation_id`); ADR-0016 (backend en Vercel: sin archivos por la API ni trabajo posterior a la respuesta); CONF-001 (a) y D3 (el gestor solo lee, el administrador no ve datos financieros); de SPEC-W-002, la subida directa a Storage con URL firmada y el rol único `usuario`; de SPEC-W-003, `cuadre.validators.normalize_tax_id` y el reloj inyectable.

**Decisiones de diseño que esta spec propone** (cada una con su alternativa y lo que cuesta cambiarla). **D-01 a D-04 las decidió la persona el 2026-11-07**; el resto queda a su visto bueno:

| ID | Decisión | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Decidida.** **El logo entra en esta spec**: bucket privado `logos` (PNG, JPEG o WebP, hasta 1 MiB), subida directa por URL firmada, vista previa y borrado. Reutiliza el patrón de `StorageGateway` de SPEC-W-002 | Dejarlo para SPEC-W-007, que es la que lo usa en el PDF: spec más corta, pero RF-004 quedaría incompleto hasta entonces. Añadirlo después es la misma obra en otra spec |
| D-02 | **Decidida.** **El IBAN es texto bajo RLS, sin cifrar** en la v1: se valida (dígitos de control), se guarda normalizado y solo lo ven su dueño y su gestor con vínculo activo; nunca sale en logs, trazas ni errores (NFR-11). El cifrado en reposo se decidirá en un ADR aparte | Cifrarlo ya (pgcrypto o Vault): más seguro, pero añade gestión de clave y una función de lectura que hoy no existen. Cambiarlo después es una migración que cifra la columna y una función de lectura; los datos ya guardados se migran |
| D-03 | **Decidida.** **Series: una por año más las propias.** Se crea sola la serie del año (código `2026`); la persona puede añadir otras (código de 1 a 8 caracteres), elegir la **predeterminada**, **archivar** las que no use y fijar el **número inicial** (para quien migra de otra herramienta) mientras no haya emitido ninguna factura en esa serie | Solo la serie del año, fija: más simple, pero no sirve a quien ya numera de otra manera ni a quien quiere series separadas. Pasar de eso a lo elegido exige la tabla y las funciones de este hito; de lo elegido a eso, ocultar la pantalla |
| D-04 | **Decidida.** **La retención la elige la persona**: un selector con 15 % y 7 %. La app **sugiere** el 7 % el año del alta y los dos siguientes y **avisa** si se elige 7 % fuera de plazo, pero no lo impide. Es orientativo (RES-05 en espíritu: no se comprueba la otra condición legal, no haber ejercido la actividad el año anterior) | Deducirla de la fecha de alta: más cómodo, pero falla con quien no cumple las condiciones del 7 % aunque esté en plazo, y el perfil quedaría supeditado a una fecha que puede faltar |
| D-05 | **Obligatorios para poder emitir:** nombre o razón social, NIF (válido y **español**: NIF, NIE o CIF) y domicilio fiscal. Todo lo demás es opcional. La app «lo impide y enumera por nombre los campos que faltan» (US-007) con `missing_for_invoicing` | Exigir también la retención o la fecha de alta: más fricción para un dato que no cambia el contenido legal de la factura. Exigir menos (solo el NIF) incumple RD 1619/2012, que pide domicilio y nombre del expedidor |
| D-06 | **Régimen de IVA: solo `general` en la v1.** La columna admite un único valor y la pantalla lo enseña como dato fijo («Régimen general»). El 303 de SPEC-W-008 es del régimen general | Admitir recargo de equivalencia o exentos: otras casillas y otros cálculos, otra spec. Ampliarlo es quitar un CHECK y añadir valores a una constante |
| D-07 | **La serie del año la crea `update_profile`** de forma idempotente (`app.ensure_year_series`), en la misma transacción; **una lectura nunca escribe**. SPEC-W-007 llama a la misma función antes de emitir, así que el primer año nuevo no se queda sin serie. La serie creada es la predeterminada **solo si no hay otra predeterminada** | Crearla al registrarse: toca el trigger de alta de SPEC-W-001 y crea series a cuentas de gestor y administrador. Crearla al leer: una lectura con efectos |
| D-08 | **Retención: solo 7 o 15** (`"7.00"` o `"15.00"`, o ninguna mientras no se elija), en la API y con un CHECK en la base | Cualquier valor de 0 a 100, como hoy la columna: dejaría pasar un 1 por un 7. Cambiarlo es una constante y un CHECK |
| D-09 | **El IBAN puede ser de cualquier país** con dígitos de control válidos (`python-stdnum`, ya fijado), no solo español; se guarda en mayúsculas y sin espacios | Solo `ES`: bloquea a quien cobra en una cuenta europea. Cambiarlo es una condición en el validador |
| D-10 | **Gestor y administrador no tienen pantalla de perfil.** Su fila de `business_profiles` existe (la crea el trigger) pero no se usa: las rutas son solo del rol `usuario`. El gestor lee el perfil del autónomo por RLS cuando SPEC-W-010 le dé pantalla | Perfil propio para el gestor (despacho, datos de contacto): no está en RF-004 ni en el PRD |
| D-11 | **Aviso «Completa tu perfil»** en Inicio mientras no se pueda emitir (con los campos que faltan) y en la revisión de una **factura simplificada o ticket** cuando falta el NIF, que es lo que hace deducible su IVA (nota B.0 de SPEC-W-003) | Sin avisos: la persona descubriría la carencia al intentar emitir (SPEC-W-007). Avisos en todas las pantallas: ruido |
| D-12 | **La cuota de autónomos mensual del prototipo (`monthlyFee`) no es un campo del perfil**: no está en RF-004 ni en `business_profiles`. Su sitio es un gasto recurrente (SPEC-W-012 / W-009) | Añadir la columna: duplicaría lo que ya registra SPEC-W-003 como gasto sin factura |
| D-13 | **`logo_path` deja de ser editable por escritura directa**: se quita de las columnas con `UPDATE` y solo cambian `app.set_business_logo` y `app.clear_business_logo`, que comprueban la ruta (`{owner_id}/{uuid}.{png\|jpg\|webp}`). Un CHECK de la tabla lo repite | Dejar la columna editable y confiar en la API: una escritura directa podría apuntar a una ruta ajena (la política de Storage la denegaría al leer, pero el dato quedaría sucio) |
| D-14 | **La validación fiscal vive en Python** (`cuadre.profile`); la base defiende solo lo barato: longitudes, rangos, el 7 o el 15, el régimen y el formato de la ruta del logo y del código de serie. **No** valida NIF ni IBAN en SQL (`python-stdnum` es Python, como en SPEC-W-003, D-01). El seed pasa a llevar NIF e IBAN válidos (sintéticos) | Validar también en SQL: duplicar los dígitos de control y romper el principio de una fuente por regla (T5-03) |

## 2. Objetivo

Al terminar esta spec:

1. La persona tiene una pantalla **Perfil** (`/perfil`, en el menú) donde guarda nombre o razón social, NIF, domicilio fiscal, actividad y epígrafe del IAE, fecha de alta, régimen de IVA, retención, IBAN y porcentaje de vivienda afecto (RF-004).
2. La aplicación sabe **qué falta para poder emitir** y lo dice por nombre (US-007): `GET /api/profile` devuelve `missing_for_invoicing` y `can_issue`, y es la regla que SPEC-W-007 aplica al emitir.
3. Los datos se **validan con código** (NIF, IBAN, rangos, retención); un valor inválido no se guarda y el error aparece junto a su campo.
4. La retención se **sugiere** según la fecha de alta y se **avisa** si no corresponde, sin imponerse (D-04).
5. La persona puede **subir, ver y borrar su logo** (PNG, JPEG o WebP de hasta 1 MiB), que se sube directo a Storage.
6. La persona gestiona sus **series de facturación**: la del año aparece sola, puede añadir otras, elegir la predeterminada, archivar y fijar el número inicial mientras no se haya emitido nada.
7. Con el NIF en el perfil, las facturas simplificadas y los tickets a ese NIF pasan a ser **deducibles** en SPEC-W-003, y una factura a otro NIF avisa (`recipient_mismatch`).
8. Todo está **aislado por RLS** (NFR-06) y ni el NIF ni el IBAN ni el domicilio salen en logs, trazas o errores (NFR-11).

## 3. Alcance explícito

### 3.1 Dominio puro (`cuadre.profile`)
- Funciones sin base de datos, sin red y sin reloj propio: validación y normalización de los campos del perfil (§5.1), `missing_for_invoicing`, sugerencia y aviso de retención (con `today` como parámetro), normalización del IBAN y validación del código de serie. `Decimal` para `irpf_rate` y `home_pct`.
- Constantes en un solo sitio (`limits`): longitudes, el 7 y el 15, la ventana de la retención reducida, el patrón del código de serie, los tipos y el tamaño del logo.

### 3.2 Base de datos (migraciones nuevas)
- CHECK nuevos en `business_profiles` (§5.2); `logo_path` sale de las columnas editables y gana sus funciones.
- Tabla `invoice_series` con RLS activada y forzada; funciones `app.*` para crear, editar, predeterminar y archivar; `app.ensure_year_series`; registrada en `backend/tests/rls/rls_matrix.yaml`; la entrada de `business_profiles` se actualiza.
- Bucket privado `logos` con sus límites y las políticas de `storage.objects` por carpeta de dueño.
- El seed pasa a llevar NIF e IBAN válidos y sintéticos, y una serie por persona.

### 3.3 Backend (FastAPI)
- Rutas `get_profile`, `update_profile`, `upload_logo`, `complete_logo_upload`, `get_logo`, `delete_logo`, `list_invoice_series`, `create_invoice_series`, `update_invoice_series` y `set_default_invoice_series` (§5.3), solo para el rol `usuario`.
- Paquete `cuadre.profile` (servicio, repositorio, modelos, errores) y `HttpStorage` parametrizado por bucket para el logo.

### 3.4 Frontend (Next.js)
- `/perfil` con el formulario del perfil, el estado de «listo para emitir», el logo y las series; entrada «Perfil» en el menú del autónomo; aviso «Completa tu perfil» en `/inicio` y en la revisión de una simplificada o ticket sin NIF.

### 3.5 Pruebas
- `backend/tests/profile/`, ampliación de `backend/tests/rls/` (series, CHECK de `business_profiles`, políticas del bucket), `backend/tests/rules/test_profile_boundary.py`, unitarias del frontend, `frontend/e2e/perfil.spec.ts` en los tres motores y los dos anchos y los ajustes de `roles.spec.ts`, `responsive.spec.ts` y `e2e/helpers/env.ts`.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Emitir, numerar y bloquear facturas; aplicar la regla «perfil incompleto impide emitir»; congelar los datos del emisor en la factura; elegir la serie por fecha | SPEC-W-007 (nota B.0) |
| Clientes y su NIF | SPEC-W-006 |
| Cifrado en reposo del IBAN | ADR futuro (D-02) |
| Regímenes de IVA distintos del general; varios negocios o actividades por cuenta | Futura (D-06) |
| Cuota de autónomos mensual como campo o como gasto recurrente | SPEC-W-009 / W-012 (D-12) |
| Deducción limitada de la vivienda afecta (`home_pct` solo se guarda; no se calcula nada con él) | SPEC-W-009 |
| Comprobar el NIF contra la AEAT o el censo | Fuera de la v1 (RES-04: nada sale hacia la AEAT) |
| Pantalla del gestor para ver el perfil y las series de sus autónomos (aquí solo la política de lectura que ya existe) | SPEC-W-010 |
| Logo en SVG o en otros formatos; recorte o redimensionado de la imagen | Futura (SVG puede contener scripts: T5-06) |
| Limpieza de logos subidos y no completados (objetos huérfanos) | Mantenimiento futuro (ADR-0016: sin trabajo posterior a la respuesta); el límite es un logo por persona y 1 MiB |
| Borrado de la cuenta y exportación de los datos del perfil | SPEC-W-017 (CONF-004) |
| Registro de actividad de los cambios del perfil | No hay criterio que lo pida; el de lecturas del gestor es SPEC-W-010 |

## 5. Contrato de interfaces

### 5.1 Campos y reglas

Los textos de error van en español, **no repiten el valor escrito** (T5-05) y salen del servidor. Un campo vacío o con solo espacios se guarda como `NULL`. `PUT /api/profile` valida **todos** los campos a la vez y, si alguno falla, **no guarda ninguno** y devuelve todos los errores.

| Campo (API) | Columna | Tipo | Regla | Mensaje si falla |
|---|---|---|---|---|
| `legal_name` | `legal_name` | texto, 2 a 200 | recortado | «Escribe tu nombre o razón social.» |
| `tax_id` | `tax_id` | texto | `normalize_tax_id` no nulo y de `scope = national` (NIF, NIE, CIF). Se **guarda normalizado** (mayúsculas, sin espacios ni guiones) | «El NIF no es válido: revisa el dígito o la letra de control.» · «Escribe un NIF, NIE o CIF español.» (uno de la UE) |
| `fiscal_address` | `fiscal_address` | texto, 5 a 300 | recortado | «Escribe tu domicilio fiscal.» |
| `activity` | `activity` | texto, 0 a 200 | | «La actividad admite hasta 200 caracteres.» |
| `iae_epigraph` | `iae_epigraph` | texto, 0 a 20 | solo letras, números, puntos, guiones y espacios | «El epígrafe del IAE solo lleva letras, números y puntos.» |
| `activity_start_date` | `activity_start_date` | fecha | desde 1950-01-01 hasta un año después de hoy (Europe/Madrid) | «La fecha de alta no puede ser anterior a 1950 ni estar a más de un año.» |
| `vat_regime` | `vat_regime` | `"general"` | único valor admitido (D-06) | «En esta versión solo está disponible el régimen general.» |
| `irpf_rate` | `irpf_rate` | `"7.00"`, `"15.00"` o `null` | solo esos dos (D-08) | «Elige 7 % o 15 %.» |
| `home_pct` | `home_pct` | decimal de 0 a 100 con hasta 2 decimales, o `null` | `Decimal`, nunca `float` | «Escribe un porcentaje entre 0 y 100, por ejemplo 30.» |
| `iban` | `iban` | texto o `null` | IBAN con dígitos de control válidos (`python-stdnum`, cualquier país: D-09). Se **guarda normalizado** (mayúsculas, sin espacios) | «El IBAN no es válido: revisa los dígitos de control.» |

**Campos que faltan para emitir** (`missing_for_invoicing`, en este orden y con estas etiquetas; D-05): `legal_name` → «Nombre o razón social», `tax_id` → «NIF», `fiscal_address` → «Domicilio fiscal». Un NIF guardado que ya no se entiende como español (p. ej. el del seed antiguo) cuenta como **faltante**. `can_issue` = la lista está vacía.

**Retención** (`retention`, orientativo; D-04). Con `activity_start_date` conocida y `y` su año: `reduced_until_year = y + 2`; `suggested_rate = "7.00"` si el año de hoy (Europe/Madrid) es ≤ `reduced_until_year`, `"15.00"` si no. Sin fecha de alta, `suggested_rate` y `reduced_until_year` son `null`. `warning` es texto cuando está guardado `irpf_rate = "7.00"` y (no hay fecha de alta o el año de hoy es mayor que `reduced_until_year`): «El 7 % solo se aplica el año del alta y los dos siguientes. Con tu fecha de alta ya no te corresponde: compruébalo con tu gestor o asesor.» (o, sin fecha: «Indica tu fecha de alta para comprobar que te corresponde el 7 %.»). Elegir 15 % nunca avisa. No se comprueba la condición legal de no haber ejercido la actividad el año anterior; el aviso dice «orientativo».

**Series.** Código: 1 a 8 caracteres, mayúsculas, números y guion, sin guion al principio ni al final; lo que se escribe en minúsculas se pasa a mayúsculas. Descripción: hasta 80 caracteres, opcional. Número inicial: entero de 1 a 999999. El formato del número de factura (`{código}-{NNN}`) lo fija SPEC-W-007.

**Logo.** `image/png`, `image/jpeg` o `image/webp`; de 1 byte a 1 MiB (1.048.576 bytes); la firma del archivo (sus primeros bytes) debe corresponder al tipo declarado.

### 5.2 Base de datos

Migraciones nuevas (`YYYYMMDDHHMMSS_descripcion.sql`, sin destructivas; **las ya aplicadas no se tocan**). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`.

**`business_profiles`** (CHECK nuevos; D-06, D-08, D-13, D-14):

```
CHECK (irpf_rate IS NULL OR irpf_rate IN (7, 15))
CHECK (vat_regime = 'general')
CHECK (char_length(legal_name) BETWEEN 2 AND 200), fiscal_address 5-300, activity <= 200, iae_epigraph <= 20 con ^[0-9A-Za-z. -]+$   -- cada uno admite NULL
CHECK (logo_path IS NULL OR logo_path ~ ('^' || owner_id::text || '/[0-9a-f-]{36}\.(png|jpg|webp)$'))
REVOKE UPDATE (logo_path) ON business_profiles FROM authenticated      -- el resto de columnas editables sigue igual
```

La migración falla si alguna fila existente incumple un CHECK (en la v1 no hay datos reales; el seed se corrige en el mismo cambio). No hay CHECK de NIF ni de IBAN (D-14).

**`invoice_series`** (tabla financiera de configuración):

```
invoice_series
  id            uuid PK DEFAULT gen_random_uuid()
  owner_id      uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE      -- configuración, no factura; las facturas de SPEC-W-007 referenciarán la serie sin cascada (CONF-004)
  code          text NOT NULL CHECK (code ~ '^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$')
  description   text CHECK (char_length(description) <= 80)
  first_number  integer NOT NULL DEFAULT 1 CHECK (first_number BETWEEN 1 AND 999999)
  next_number   integer NOT NULL DEFAULT 1 CHECK (next_number >= first_number AND next_number <= 1000000)   -- lo avanza SPEC-W-007, nunca baja
  is_default    boolean NOT NULL DEFAULT false
  archived_at   timestamptz
  created_at, updated_at  timestamptz NOT NULL DEFAULT now()
  UNIQUE (owner_id, code)                                                      -- también las archivadas: un código no se reutiliza
  CHECK (NOT (is_default AND archived_at IS NOT NULL))
UNIQUE INDEX invoice_series_one_default ON invoice_series (owner_id) WHERE is_default
```

«**En uso**» = `next_number > first_number`: SPEC-W-007 avanza `next_number` al emitir y por eso esta spec no necesita saber de facturas. Trigger `invoice_series_guard` (`BEFORE UPDATE`): `owner_id` y `created_at` no cambian; `code` y `first_number` solo cambian si la serie no está en uso (`series_in_use`); `next_number` **no baja nunca** (`series_number_regression`), con una sola excepción: una serie sin uso a la que se cambia `first_number` fija `next_number` igual al nuevo `first_number` (la serie sigue sin uso, así que no se «retrocede» ninguna factura).

**Privilegios.** `authenticated`: `SELECT` y nada más; toda escritura por funciones (como `documents` y `expenses`).

| Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|
| SELECT | las suyas, archivadas incluidas | las de usuarios con vínculo activo (`private.gestor_has_access(owner_id)`) | **ninguna** |
| INSERT / UPDATE / DELETE | denegado (solo `app.*`) | denegado | denegado |

**Funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`, verifican `auth.uid()` y `private.app_role() = 'usuario'`; `P0001` con código estable, `42501` si el rol no basta):

| Función | Efecto |
|---|---|
| `app.ensure_year_series()` | Crea la serie con código = año de hoy en Europe/Madrid (`private.today_madrid()`) y descripción «Serie del año» si no existe; es la predeterminada solo si la persona no tiene otra. **Idempotente**: dos llamadas a la vez dejan una (`ON CONFLICT (owner_id, code) DO NOTHING`). Devuelve el id |
| `app.create_invoice_series(p_code, p_description, p_first_number, p_make_default)` | Código válido y no usado (`series_code_taken`, también entre archivadas), `next_number = first_number`. Si `p_make_default`, quita la marca a la anterior en la misma transacción |
| `app.update_invoice_series(p_id, p_code, p_description, p_first_number)` | Cualquiera de los tres, o ninguno. `code` y `first_number` solo si la serie no está en uso (`series_in_use`); al cambiar `first_number` también se pone `next_number`. `series_not_found` si no existe o es ajena |
| `app.set_default_invoice_series(p_id)` | La hace predeterminada y quita la marca a la anterior. Una archivada da `series_archived` |
| `app.set_invoice_series_archived(p_id, p_archived)` | Archiva o reactiva. Archivar la predeterminada da `series_is_default` (hay que elegir otra antes). Una archivada no se ofrece para emitir (SPEC-W-007) |
| `app.set_business_logo(p_path)` | Comprueba que `p_path` es `{auth.uid()}/{uuid}.{png\|jpg\|webp}` y lo guarda en `business_profiles.logo_path`; devuelve la ruta **anterior** (o nulo) para que la API borre ese objeto |
| `app.clear_business_logo()` | Pone `logo_path` a nulo y devuelve la ruta anterior |

**Storage.** Bucket `logos` privado, `file_size_limit = 1048576`, `allowed_mime_types = {image/png, image/jpeg, image/webp}`. Políticas de `storage.objects` (`to authenticated`, `(select auth.uid())`): `INSERT` y `DELETE` solo en `{auth.uid()}/…` con nombre `{uuid}.{png|jpg|webp}`; `SELECT` para el dueño y para el gestor con vínculo activo sobre esa carpeta; el administrador, ninguna. Mientras no haya política, nadie lee ni escribe.

**Matriz de RLS.** `invoice_series`: `kind: financial`, `owner_column: owner_id`, privilegios `SELECT`, y un `seed` con una serie por persona. `business_profiles`: se quita `logo_path` de `grants.columns.UPDATE` y la sonda de `UPDATE` sigue usando `legal_name`.

**Seed (sintético).** NIF e IBAN de Alicia y Beto con dígitos de control válidos y una serie por persona; ningún dato real (RES-07).

### 5.3 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador); errores en `application/problem+json` como en SPEC-W-001.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `get_profile` | `GET /api/profile` | **200** `Profile`. Solo lee: no crea la serie del año |
| `update_profile` | `PUT /api/profile` | Cuerpo `ProfileInput` (los campos de §5.1; los ausentes valen `null`). En **una transacción**: valida, actualiza `business_profiles` y llama a `app.ensure_year_series()`. **200** `Profile`; **422** `invalid_profile` si falla algo |
| `upload_logo` | `POST /api/profile/logo` | Cuerpo `{ "mime_type": string, "size_bytes": int }`. Valida tipo y tamaño y firma una URL de subida para `{owner_id}/{upload_id}.{ext}`. **201** `{ "upload_id": uuid, "upload": { "url", "headers" } }` |
| `complete_logo_upload` | `POST /api/profile/logo/{upload_id}/complete` | Comprueba en Storage que el objeto existe, que su tamaño y tipo coinciden con lo registrado y que sus primeros bytes tienen la firma del tipo; llama a `app.set_business_logo` y borra el logo anterior (en la misma petición). **200** `Profile` |
| `get_logo` | `GET /api/profile/logo` | **200** `{ "url": string, "expires_in": 60 }` (URL de lectura firmada); **404** `logo_not_found` si no hay |
| `delete_logo` | `DELETE /api/profile/logo` | **204**. Idempotente: sin logo también es 204. Llama a `app.clear_business_logo` y borra el objeto |
| `list_invoice_series` | `GET /api/invoice-series` | **200** `[InvoiceSeries]`, la predeterminada primero y después por código; incluye las archivadas |
| `create_invoice_series` | `POST /api/invoice-series` | Cuerpo `{ "code", "description"?: string, "first_number"?: int, "make_default"?: bool }`. **201** `InvoiceSeries` |
| `update_invoice_series` | `PATCH /api/invoice-series/{id}` | Cuerpo con cualquiera de `code`, `description`, `first_number` y `archived` (bool). **200** `InvoiceSeries` |
| `set_default_invoice_series` | `PUT /api/invoice-series/{id}/default` | Sin cuerpo. **200** `InvoiceSeries` |

```
Profile {
  legal_name, tax_id, fiscal_address, activity, iae_epigraph: string|null,
  activity_start_date: date|null, vat_regime: "general",
  irpf_rate: "7.00"|"15.00"|null, home_pct: string|null, iban: string|null,        # decimales como cadenas (ADR-0006)
  has_logo: bool, updated_at: datetime,
  completeness: { can_issue: bool, missing_for_invoicing: [ { field: "legal_name"|"tax_id"|"fiscal_address", label: string } ] },
  retention:    { suggested_rate: "7.00"|"15.00"|null, reduced_until_year: int|null, warning: string|null }
}
InvoiceSeries { id, code, description: string|null, first_number: int, next_number: int, is_default: bool, archived: bool, in_use: bool, created_at }
```

**Códigos de error nuevos** (`code`, HTTP): `invalid_profile` 422 (con el miembro extra `fields: [ { field, message } ]`, **todos** los que fallan) · `invalid_series` 422 (con `field`) · `series_code_taken` 409 · `series_in_use` 409 · `series_is_default` 409 · `series_archived` 409 · `series_not_found` 404 (también si es de otra persona: no se distingue) · `logo_unsupported_type` 415 · `logo_too_large` 413 · `logo_invalid` 422 (no se subió, no coincide con lo anunciado o la firma no es del tipo) · `logo_not_found` 404. Los errores de forma del cuerpo son el `validation_error` 422 de siempre. Los textos van en español y no repiten el valor escrito.

### 5.4 Backend

- **Paquetes.** `cuadre.profile` (`rules` y `limits` puros; `service`, `repository`, `models`, `errors`, `logo`) y `api/routes_profile.py` (perfil, logo y series). `rules` importa `cuadre.validators` (NIF) y `stdnum.iban`, nada de base de datos, red ni FastAPI; lo vigila `backend/tests/rules/test_profile_boundary.py`, como `test_validators_boundary`.
- **Flujo de `update_profile`.** Una transacción corta: validar todo → `UPDATE business_profiles` con las columnas permitidas → `app.ensure_year_series()` → leer el perfil y calcular `completeness` y `retention` con el reloj inyectado (`cuadre.core.clock`) → confirmar. El NIF y el IBAN se guardan normalizados.
- **Logo.** `HttpStorage` recibe el bucket (hoy lleva `BUCKET = "documents"` y su expresión de ruta fijos); el logo usa el bucket `logos` y su propia expresión de ruta. La firma del archivo se lee con `read_head` (nunca se descarga el archivo: Vercel limita el cuerpo a 4,5 MB, ADR-0016). El borrado del logo anterior ocurre dentro de la petición; si Storage falla, la ruta nueva ya está guardada y el objeto viejo queda huérfano (T5-06).
- **`test_operation_ids`** no cambia: `get`, `update`, `upload`, `complete`, `delete`, `list`, `create` y `set` ya existen.
- **Sin dependencias nuevas:** `python-stdnum` ya está fijado desde SPEC-W-003.

### 5.5 Frontend

| Ruta | Quién | Contenido |
|---|---|---|
| `/perfil` | `usuario` | Estado arriba: «Tu perfil está listo para emitir facturas.» o «Para emitir facturas te falta: NIF y Domicilio fiscal.» (texto, no solo color). Formulario en secciones: **Datos fiscales** (nombre o razón social, NIF, domicilio fiscal, actividad, epígrafe del IAE, fecha de alta, régimen de IVA como dato fijo «Régimen general»), **Retención y vivienda** (selector 15 % / 7 % con la sugerencia y el aviso; porcentaje de vivienda afecto), **Cobros** (IBAN, agrupado de cuatro en cuatro al mostrarlo) y **Guardar** con «Cambios guardados.»; **Logo** (elegir archivo, vista previa, «Quitar logo»); **Series de facturación** (tarjetas hasta 1.279 px y tabla desde 1.280 px, como Gastos: código, descripción, siguiente número, «Predeterminada» y «Archivada» en texto, y las acciones «Hacer predeterminada», «Editar» y «Archivar» / «Reactivar»; «Añadir serie») |
| `/inicio` | `usuario` | Aviso «Completa tu perfil» con los campos que faltan y un enlace a `/perfil`, mientras `can_issue` sea falso; desaparece al completarlo |
| `/gastos/[id]` | `usuario` | En una factura simplificada o ticket sin NIF en el perfil, junto a la nota de deducibilidad: «Para deducir el IVA de un ticket o una simplificada tu NIF tiene que estar en el perfil» con enlace a `/perfil` |

Guardar el perfil y gestionar las series son **Server Actions** (`useActionState`, errores junto a cada campo con `aria-describedby`, resumen de errores que recibe el foco, como `expense-form`); la subida del logo va **directa del navegador a Storage** con la URL firmada (ADR-0016), igual que los documentos, y después `complete_logo_upload` por Server Action. La interfaz **muestra** lo que dice el servidor y no valida nada fiscal. Ni el IBAN ni el NIF se escriben en la consola ni en ningún registro del navegador. «Perfil» se añade a `navFor('usuario')` (activo, tras «Trimestres») y a `SECTIONS.usuario`; gestor y administrador no lo ven, y `/perfil` para ellos lleva a `/403`. Hay que actualizar `lib/roles.test.ts` y `PEOPLE.alicia.nav` / `enabledNav` en `e2e/helpers/env.ts`.

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T5-01 | **Sin `float`** en código, migraciones ni JSON: `irpf_rate` y `home_pct` son `Decimal` y viajan como cadenas; `test_no_float` sigue verde (RES-02) |
| T5-02 | **Sin modelos de lenguaje ni red**: ni para el NIF, ni para el IBAN, ni para la sugerencia de retención (RES-01); `cuadre.profile` no importa base de datos, `httpx`, FastAPI ni usa `datetime.now()` (el reloj entra como parámetro) |
| T5-03 | **Una fuente por regla.** Longitudes, el 7 y el 15, el patrón del código de serie y los límites del logo viven en `cuadre.profile.limits`; los CHECK de la base los repiten y un test de paridad los compara |
| T5-04 | **Solo `usuario`** lee y escribe su perfil por la API; el gestor con vínculo activo lee por RLS (revocar corta el acceso en la petición siguiente) y el administrador no ve el de otros (D3, NFR-06). La service key no interviene |
| T5-05 | **Sin datos personales en logs, trazas, errores ni `activity_log`**: ni NIF, ni IBAN, ni nombre, ni domicilio, ni URLs firmadas (NFR-11). Los `422` dicen qué campo falla, no qué se escribió. Un test captura los registros de todo el flujo |
| T5-06 | **Logo**: solo PNG, JPEG y WebP de hasta 1 MiB (**sin SVG**: puede llevar scripts); nunca pasa por la API (ADR-0016); la firma del archivo se comprueba con sus primeros bytes; se muestra solo con `<img>` y una URL firmada de 60 s; el logo anterior se borra dentro de la petición. Un objeto subido y no completado queda huérfano, y se acepta (un logo por persona, 1 MiB) |
| T5-07 | **La numeración no se rompe**: esta spec nunca baja `next_number` de una serie en uso (lo defiende el trigger; solo se mueve junto con `first_number` en una serie sin uso), no asigna números y no borra series (se archivan) |
| T5-08 | **Una lectura no escribe** (D-07): `get_profile` y `list_invoice_series` no crean nada |
| T5-09 | **Sin trabajo posterior a la respuesta** (ADR-0016); `test_vercel_compat` sigue verde |
| T5-10 | **Interfaz** como T3-11: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, anuncios con `aria-live`, sin scroll horizontal a 390 y 1.440 px en los tres navegadores |
| T5-11 | **Migraciones sin datos reales y sin destructivas**; no se editan las aplicadas; el seed es sintético (RES-07). Una prueba que escriba el perfil de una cuenta compartida del E2E **lo restaura** al terminar (la cuenta es del worker y SPEC-W-003 depende del NIF) |

## 7. Criterios de aceptación (Given-When-Then)

```gherkin
AC-01  Perfil vacío (US-007)
  Given una cuenta recién registrada, con su perfil vacío
  When la persona consulta su perfil (GET /api/profile)
  Then can_issue es falso
    And missing_for_invoicing enumera, por nombre y en este orden, "Nombre o razón social", "NIF" y "Domicilio fiscal"
    And /inicio muestra "Completa tu perfil" con esos tres campos y un enlace a /perfil

AC-02  Perfil completo
  Given un perfil vacío
  When la persona guarda un nombre, un NIF español válido ("12345678z" con espacios y minúscula) y un domicilio
  Then la respuesta es 200 con can_issue verdadero y missing_for_invoicing vacío
    And el NIF queda guardado normalizado ("12345678Z")
    And el aviso de /inicio desaparece

AC-03  NIF inválido o extranjero
  Given un perfil cualquiera
  When la persona guarda un NIF con la letra de control equivocada, o un NIF-IVA de la UE ("FR…")
  Then la respuesta es 422 "invalid_profile" con fields = [{ field: "tax_id", message }], con el mensaje de §5.1 que corresponda
    And no se guarda ningún campo del formulario, aunque los demás fueran válidos
    And el mensaje no repite el valor escrito

AC-04  Sugerencia y aviso de retención (D-04)
  Given el 2026-11-07 (reloj fijo)
  When la fecha de alta es 2026-03-01 / 2024-12-31 / 2023-12-31 / no hay
  Then reduced_until_year es 2028 / 2026 / 2025 / nulo, y suggested_rate es "7.00" / "7.00" / "15.00" / nulo
    And con irpf_rate "7.00" guardado, warning aparece en los dos últimos casos y no en los dos primeros
    And con irpf_rate "15.00" nunca hay aviso
    And con el reloj en 2027-01-01 y alta 2024-12-31, suggested_rate pasa a "15.00" (frontera de año)

AC-05  Solo 7 o 15 (D-08)
  Given un perfil cualquiera
  When la persona guarda irpf_rate "10.00", o intenta fijarlo en la base con un UPDATE directo
  Then la API responde 422 "invalid_profile" con field "irpf_rate" y la base lo rechaza con el CHECK
    And "7.00", "15.00" y null se aceptan

AC-06  IBAN
  Given un perfil cualquiera
  When la persona guarda "es91 2100 0418 4502 0005 1332" (con espacios y minúsculas, de ejemplo y válido) o un IBAN con un dígito de control mal
  Then el primero queda guardado como "ES9121000418450200051332" y el segundo da 422 con field "iban"
    And ni el IBAN ni el NIF ni el domicilio aparecen en ningún registro del flujo, ni en el cuerpo de ningún error (NFR-11)

AC-07  Porcentaje de vivienda
  Given un perfil cualquiera
  When la persona guarda home_pct "30.00" / "30" / "100.01" / "-1" / "abc"
  Then se aceptan los dos primeros ("30.00") y los tres últimos dan 422 con field "home_pct"
    And el valor viaja y se guarda como Decimal, nunca como float

AC-08  Régimen de IVA (D-06)
  Given un perfil cualquiera
  When la persona envía vat_regime distinto de "general"
  Then la respuesta es 422 con field "vat_regime"
    And la base también lo rechaza (CHECK)

AC-09  Serie del año (D-07)
  Given una cuenta sin series y el 2026-11-07 (reloj fijo)
  When la persona guarda su perfil por primera vez
  Then existe una serie con código "2026", descripción "Serie del año", first_number 1, next_number 1, predeterminada y no archivada
    And guardar otra vez no crea ninguna más
    And dos guardados a la vez dejan una sola (UNIQUE y ON CONFLICT)
    And GET /api/profile y GET /api/invoice-series sobre una cuenta sin series no crean nada

AC-10  Crear serie
  Given una cuenta con la serie "2026"
  When la persona crea "fac" con descripción y número inicial 100
  Then se crea "FAC" con next_number 100 y no es predeterminada
    And repetir "FAC", o un código archivado, da 409 "series_code_taken"
    And "AB CD", "-A", "A-", un código de 9 caracteres o uno vacío dan 422 "invalid_series"

AC-11  Una sola predeterminada
  Given dos series activas, "2026" predeterminada y "FAC"
  When la persona hace predeterminada "FAC"
  Then "FAC" lo es y "2026" ya no; en ningún momento hay dos (índice único parcial, también con dos peticiones a la vez)
    And hacer predeterminada una archivada da 409 "series_archived"

AC-12  Número inicial y código (D-03)
  Given una serie sin usar (next_number = first_number) y otra en uso (next_number > first_number, simulado en la prueba)
  When la persona cambia first_number o code de cada una
  Then la primera se actualiza (y next_number con ella) y la segunda da 409 "series_in_use"
    And la descripción sí se puede cambiar en las dos
    And next_number de una serie en uso no puede bajar (trigger, probado con un UPDATE directo), y en una sin uso solo se mueve junto con first_number

AC-13  Archivar
  Given una serie no predeterminada, en uso o no, y la predeterminada
  When la persona archiva cada una
  Then la primera queda archivada (archived verdadero) y reactivarla la deja activa
    And archivar la predeterminada da 409 "series_is_default"
    And ninguna serie se puede borrar (no hay ruta ni DELETE)

AC-14  Logo
  Given un PNG sintético de menos de 1 MiB
  When la persona lo sube (upload_logo, PUT a la URL firmada, complete_logo_upload)
  Then has_logo es verdadero y get_logo devuelve una URL firmada de 60 s que sirve la imagen
    And al subir otro, el primero se borra de Storage
    And la URL firmada no aparece en ningún registro

AC-15  Logo rechazado
  Given un archivo que no vale
  When la persona anuncia un SVG o un GIF / anuncia más de 1 MiB / sube un texto con extensión .png / completa sin haber subido nada
  Then responde 415 "logo_unsupported_type" / 413 "logo_too_large" / 422 "logo_invalid" / 422 "logo_invalid"
    And logo_path no cambia y no queda ninguna referencia al objeto rechazado

AC-16  Quitar el logo
  Given un perfil con logo
  When la persona lo quita (delete_logo)
  Then responde 204, has_logo es falso, el objeto desaparece de Storage y get_logo da 404 "logo_not_found"
    And repetirlo también da 204

AC-17  Aislamiento (NFR-06)
  Given Alicia y Beto (usuarios), Gina (gestora con vínculo activo con Alicia) y Adán (administrador)
  When cada uno intenta leer o escribir el perfil, las series y el logo de otro
  Then Beto no ve nada de Alicia y no puede escribirlo; Gina lee el perfil, las series y el logo de Alicia y no escribe nada; tras revocar, no ve nada
    And Adán solo ve su propia fila de perfil y ninguna serie ni logo de nadie (D3)
    And Gina y Adán reciben 403 "forbidden" en las rutas de perfil y de series
    And un UPDATE directo de logo_path, o una ruta de otra carpeta, es rechazado (privilegio y CHECK)

AC-18  Integración con SPEC-W-003 (D-11)
  Given una factura simplificada cuyo NIF de destinatario es el de la persona / otro distinto, y una factura completa con destinatario 12345678Z
  When el perfil lleva ese NIF / otro / ninguno
  Then con el mismo NIF el IVA es deducible y no hay aviso; con otro NIF no es deducible y aparece el aviso recipient_mismatch; sin NIF en el perfil la simplificada no es deducible y la revisión muestra el enlace "Completa tu perfil"
    And con 12345678Z en el perfil la factura completa no lleva aviso, y con otro NIF lleva recipient_mismatch

AC-19  Interfaz del perfil (NFR-10)
  Given la persona en /perfil con la sesión de un usuario
  When recorre y guarda el formulario, sube un logo y gestiona una serie, a 390 y a 1.440 px
  Then no hay scroll horizontal, todo campo tiene su etiqueta, cada error sale junto a su campo y en un resumen que recibe el foco, el guardado dice "Cambios guardados." y el estado "listo para emitir" se distingue por su texto
    And no hay errores de consola en Chromium, Firefox ni WebKit
    And se puede hacer todo con el teclado y el foco siempre se ve

AC-20  Menú y portadas
  Given un usuario, una gestora y un administrador con sesión
  When ven su menú y entran en /perfil
  Then el usuario ve "Perfil" activo; la gestora y el administrador no lo ven y /perfil los lleva a /403
    And las portadas /inicio, /cartera y /admin siguen mostrando lo de SPEC-W-001

AC-21  Guardas (T5-02, T5-03, T5-09)
  Given el repositorio entero
  When corren las guardas
  Then cuadre.profile no importa base de datos, httpx ni FastAPI, ni usa el reloj del sistema
    And las constantes de limits y los CHECK de la base coinciden
    And test_rls_guard exige invoice_series en la matriz y test_vercel_compat, test_no_float y test_operation_ids siguen verdes
```

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-003 §8.1, con la pila de Supabase en marcha y los puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 (o `E2E_AGENTS_PORT`) libres. Sin red: el NIF y el IBAN de las pruebas son de ejemplo con dígitos de control válidos y nada sale a Internet. Los E2E de perfil usan una cuenta propia del worker y restauran su perfil al terminar (T5-11).

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                                  # migraciones + seed
pytest backend/tests/profile -q                                        # AC-01 a AC-16, AC-18 (lado API) y AC-21
pytest backend/tests/rls -m rls -q                                     # AC-05, AC-08, AC-11 a AC-13, AC-17 (series, CHECK, Storage)
pytest backend/tests -m "not rls" -q
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/perfil.spec.ts       # AC-19 y AC-20 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/profile` y `npm --prefix frontend exec -- playwright test e2e/perfil.spec.ts`, además de las secuencias completas de SPEC-W-001 §8.2, SPEC-W-002 §8.2 y SPEC-W-003 §8.2, que deben seguir en verde (la batería de E2E se ejecuta con `--workers=1` y un motor por invocación si hay poca memoria libre).

### 8.3 Correspondencia criterio → prueba

| AC | Prueba |
|---|---|
| AC-01 | `backend/tests/profile/test_rules.py` (`missing_for_invoicing`); `backend/tests/profile/test_profile_api.py`; `frontend/e2e/perfil.spec.ts` · «perfil vacío» |
| AC-02, AC-03 | `backend/tests/profile/test_rules.py` (tabla de NIF sintéticos, sin red); `test_profile_api.py` (422 sin guardar nada); `frontend/e2e/perfil.spec.ts` · «completar el perfil» y «NIF inválido» |
| AC-04 | `backend/tests/profile/test_retention.py` (reloj fijo, fronteras de año); `frontend/src/lib/profile.test.ts`; `perfil.spec.ts` · «retención» |
| AC-05, AC-08 | `backend/tests/profile/test_profile_api.py`; `backend/tests/rls/test_profile_constraints.py` (CHECK con UPDATE directo) |
| AC-06 | `backend/tests/profile/test_iban.py`; `backend/tests/profile/test_no_sensitive_logs.py` |
| AC-07 | `backend/tests/profile/test_rules.py` (trampas de coma flotante); `frontend/src/lib/profile-form.test.ts` |
| AC-09 | `backend/tests/profile/test_series_api.py`; `backend/tests/profile/test_concurrency.py` (dos guardados a la vez); `backend/tests/rls/test_invoice_series.py` |
| AC-10, AC-11 | `backend/tests/profile/test_series_domain.py`; `test_series_api.py`; `backend/tests/rls/test_invoice_series.py` (índice y UNIQUE con dos transacciones); `perfil.spec.ts` · «series» |
| AC-12, AC-13 | `backend/tests/rls/test_invoice_series.py` (trigger `invoice_series_guard`, `next_number` simulado); `test_series_api.py`; `perfil.spec.ts` · «series» |
| AC-14, AC-15, AC-16 | `backend/tests/profile/test_logo_api.py` (Storage real o en memoria, como `tests/documents`); `backend/tests/rls/test_logo_storage.py`; `perfil.spec.ts` · «logo» |
| AC-17 | `backend/tests/rls/test_invoice_series.py` y `rls_matrix.yaml` (series, `business_profiles`); `test_logo_storage.py`; `backend/tests/profile/test_roles.py` |
| AC-18 | `backend/tests/profile/test_expenses_integration.py` (extracción simulada; deducibilidad y `recipient_mismatch`); `frontend/e2e/perfil.spec.ts` · «el NIF del perfil y los gastos» (con `invoice_ok`) |
| AC-19 | `frontend/e2e/perfil.spec.ts` (seis proyectos) y `frontend/e2e/responsive.spec.ts` (`/perfil`); `frontend/src/lib/profile-form.test.ts` |
| AC-20 | `frontend/src/lib/roles.test.ts`; `frontend/e2e/roles.spec.ts` y `responsive.spec.ts` con `PEOPLE.*.nav` actualizado |
| AC-21 | `backend/tests/rules/test_profile_boundary.py`, `backend/tests/profile/test_limits_parity.py`, `backend/tests/rls/test_rls_guard.py` y las guardas de `backend/tests/rules/` |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, SPEC-W-002 y SPEC-W-003 §8.2 siguen en verde.
- [ ] `pytest backend/tests/rls -m rls` incluye `invoice_series`, los CHECK de `business_profiles` y las políticas del bucket `logos`.
- [ ] «Perfil» está activo en el menú del autónomo y el aviso «Completa tu perfil» sale en `/inicio` y en la revisión de una simplificada sin NIF.
- [ ] El seed lleva NIF e IBAN válidos y sintéticos, y las pruebas de SPEC-W-003 que dependían del NIF de Alicia se han revisado.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0011, 0015 y 0016 enlazados.
- [ ] Sin secretos, NIF, IBAN ni imágenes reales en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike**: con valores **sintéticos**, qué acepta y rechaza `stdnum.iban` (espacios, minúsculas, longitudes por país, dígitos de control) y que no usa la red; y en el Supabase local, que el bucket `logos` con sus políticas por carpeta permite firmar una subida, subir una imagen de unos KB y leerla con URL firmada, y que `Range` devuelve los primeros bytes. Resultado al Anexo B.
1. **Dominio puro** (`cuadre.profile`): campos, `missing_for_invoicing`, retención con reloj, IBAN, código de serie, `limits`, `test_profile_boundary`, con tablas de pruebas y mutaciones.
2. **Base de datos**: CHECK de `business_profiles`, `invoice_series` con trigger y funciones, `app.*` del logo, bucket y políticas, seed, matriz y pruebas de RLS, con mutaciones.
3. **API**: `cuadre.profile` (servicio y repositorio), `HttpStorage` por bucket, las diez rutas, `openapi.json` y `schema.d.ts` regenerados, con mutaciones.
4. **Frontend**: `/perfil` (formulario, retención, logo, series), menú, avisos de `/inicio` y de la revisión; unitarias.
5. **E2E y cierre**: `perfil.spec.ts` en tres motores y dos anchos, ajustes de `roles.spec.ts`, `responsive.spec.ts` y `env.ts`, mutaciones, Anexo B, `tasks.json` y commit.

## Anexo B · Decisiones que esta spec dejó a la implementación

*(Se rellena al implementar.)*

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-006 (clientes).** El ámbito de un cliente necesita un tercer valor que `supplier_scope` (`national`/`eu`) no tiene: el prototipo usa `non_eu`, C3 usa `nacional|ue|fuera_ue` y la interfaz ya tiene los tokens `scope-eu` y `scope-non-eu`. W-006 debe definir su enum y mapear los tres nombres en un solo sitio. `normalize_tax_id` solo distingue nacional y UE; «fuera de la UE» es la ausencia de un NIF-IVA reconocido.
- **SPEC-W-007 (facturas).** (1) Llama a `app.ensure_year_series()` antes de emitir. (2) **Aplica la regla de US-007**: usa `cuadre.profile.rules.missing_for_invoicing` en la API y comprueba lo mismo en la función SQL de emisión, y devuelve los campos que faltan por nombre. (3) Numera con una función `SECURITY DEFINER` que bloquea la fila de la serie (`SELECT … FOR UPDATE`) y avanza `next_number` de uno en uno, sin huecos; no puede bajarlo (el trigger lo impide) y no emite en una serie archivada. (4) Congela en la factura una **copia** de los datos del emisor (nombre, NIF, domicilio, logo, IBAN) y del cliente, porque el perfil es editable y la factura no. (5) Decide el formato del número (`{código}-{NNN}`, tres cifras como mínimo) y qué serie se propone por defecto cuando cambia el año (hoy la del año nuevo solo es predeterminada si no hay otra: D-07). (6) Lee el logo con una URL firmada o el objeto, sin pasarlo por la API (4,5 MB). (7) `in_use` sale de `next_number > first_number`: si cambia ese contrato, hay que cambiar el trigger.
- **SPEC-W-008 y W-009 (303 y 130).** Usan `irpf_rate` (7 o 15) y `home_pct`. `vat_regime` es siempre `general` (D-06): otros regímenes necesitan su propia spec. `home_pct` solo se guarda aquí; la deducción de la vivienda afecta es de W-009.
- **SPEC-W-009 / W-012.** La cuota de autónomos mensual (`monthlyFee` del prototipo) no es un campo del perfil (D-12): si se quiere automática, es un gasto recurrente.
- **SPEC-W-010 (gestor).** Las políticas de lectura de `business_profiles`, `invoice_series` y el bucket `logos` para el gestor ya existen; faltan la pantalla y el registro de cada lectura. El IBAN lo ve el gestor con vínculo activo (D-02).
- **SPEC-W-017 (cierre de cuenta).** El perfil, las series y el logo son datos de la persona: la exportación y el borrado de la cuenta deben incluirlos y borrar el objeto de Storage. `invoice_series` se borra en cascada con la cuenta; las facturas (W-007) no, por CONF-004.
- **SPEC-W-003.** Esta spec cierra la carencia de B.0 («sin el NIF en `business_profiles.tax_id`, ninguna simplificada es deducible»). Las pruebas y los E2E de W-003 que dependen del NIF de la cuenta deben dejar el perfil como lo encontraron (T5-11).
- **ADR pendiente.** Cifrado en reposo del IBAN (D-02): decide si se cifra la columna, con qué clave y quién la lee.
