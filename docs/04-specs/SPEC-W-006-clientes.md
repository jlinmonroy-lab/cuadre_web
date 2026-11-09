---
tipo: spec
id: SPEC-W-006
titulo: Clientes: NIF, ámbito y VIES simulado
estado: en-progreso
prioridad: must
riesgo: bajo
historias: [US-006]
requisitos: [RF-005]
nfr: [NFR-06, NFR-10, NFR-11]
restricciones: [RES-02, RES-07]
adr: [0003, 0004, 0006, 0011, 0015, 0016]
depende_de: [SPEC-W-005]
bloquea: [SPEC-W-007]
fecha: 2026-11-09
---

# SPEC-W-006 · Clientes: NIF, ámbito y VIES simulado

> Segundo paso de la cadena **perfil → clientes → facturas**. La persona guarda la ficha de cada cliente (nombre, tipo, país, NIF o NIF-IVA, domicilio) y la aplicación **deduce el ámbito** (nacional, UE o fuera de la UE), valida el identificador fiscal con código y marca el estado de VIES como **simulado**.
> Lo que **no** hace es facturar: qué IVA, retención y mención lleva una factura según el ámbito, y cuánto se ha facturado a cada cliente, son SPEC-W-007. Esta spec deja preparado el dato que esa regla necesita (`scope`, `kind`, `tax_id`) y el selector de clientes activos.

## 1. Contexto

**Situación de partida.** No hay tabla, ruta ni pantalla de clientes: en el menú del autónomo «Clientes» sale desactivado («Próximamente»). SPEC-W-003 y SPEC-W-005 dejaron lo que hace falta para validar: `cuadre.validators.normalize_tax_id` (NIF, NIE y CIF españoles y NIF-IVA de los 27 Estados miembros, con el prefijo de Grecia como `EL`) y el patrón de funciones `app.*` con cerrojo asesor por persona de `invoice_series`. El prototipo (`docs/cuadre-interfaz.html`) trae la pantalla (`renderClientes`, `create_client`, `scopeOf`) y los tokens de diseño `scope-eu` y `scope-non-eu`; su tabla lleva dos columnas que esta spec **no** implementa («Facturado en {año}» y la nota «qué llevará la factura»), porque dependen de las facturas.

**Por qué es de riesgo bajo, y dónde no lo es.** Es datos de formulario sobre una tabla nueva, sin agentes ni cálculo de impuestos. Merecen cuidado tres puntos: (1) el **ámbito** decide después el IVA y las casillas del 303 (W-007, W-008), y un cliente mal clasificado es una factura mal hecha: por eso se deduce con código y con tabla de pruebas, no a mano; (2) el nombre, el NIF y el domicilio de un cliente son **datos personales de terceros** (NFR-11, CONF-004), y no deben salir en registros ni en errores; (3) el **enum del ámbito** es contrato con otras specs (B.0 de SPEC-W-005: el MCP usa `nacional | ue | fuera_ue`, los gastos usan `national | eu`) y cambiarlo después cuesta una migración con facturas emitidas.

**Decisiones vigentes** (no se reabren aquí): ADR-0003 y ADR-0015 (SQL explícito, reglas críticas en la base); ADR-0004 (Supabase UE); ADR-0006 (importes en céntimos; aquí no hay importes); ADR-0011 (cliente generado y `operation_id`); ADR-0016 (backend en Vercel: sin trabajo posterior a la respuesta); CONF-001 (a) y D3 (el gestor solo lee, el administrador no ve datos financieros); RES-04 (nada sale hacia la AEAT: tampoco hacia VIES en la v1); de SPEC-W-005, el rol único `usuario` y el cerrojo asesor por persona.

**Decisiones que propone esta spec.** **D-01 y D-05 las decidió la persona el 2026-11-09**; el resto queda a su visto bueno.

| ID | Decisión | Alternativa y coste de cambiarla |
|---|---|---|
| D-01 | **Decidida.** País en **ISO 3166-1 alfa-2 completo** (~250 códigos); el ámbito se deduce: `national` si `ES`, `eu` si es otro Estado miembro, `non_eu` el resto. La constante (`COUNTRIES`, `EU_COUNTRIES`) vive en `cuadre.clients.countries`, sin `pycountry`; los **nombres en español los pone el frontend** con `Intl.DisplayNames('es')` | Catálogo corto (UE y media docena de países): menos superficie, pero deja fuera a quien factura a otro país. Pasar de corto a completo es ampliar una constante y su CHECK |
| D-02 | **Enum del ámbito** `national \| eu \| non_eu` (tipo `public.client_scope`). El MCP de SPEC-W-011 usa `nacional \| ue \| fuera_ue`: un **solo módulo de mapeo** (`cuadre.clients.scope`). `public.supplier_scope` (`national \| eu`, de los gastos) **no se toca** | Reutilizar `supplier_scope` añadiéndole un valor: toca una tabla con datos y dos specs ya hechas |
| D-03 | **Tipo** `business` (empresa o profesional) o `individual` (particular). Los valores van en inglés; la pantalla los llama «Empresa o profesional» y «Particular» | Más tipos (administración pública, asociación): no hay regla fiscal que los distinga en la v1 |
| D-04 | **El NIF depende del ámbito y del tipo** (§5.1): nacional y empresa → NIF, NIE o CIF español **obligatorio y válido**; nacional y particular → opcional, pero si se escribe, válido; UE y empresa → NIF-IVA **obligatorio, válido y del país elegido** (Grecia: país `GR`, prefijo `EL`); UE y particular, y fuera de la UE y particular → opcional, texto libre; fuera de la UE y empresa → identificador fiscal **obligatorio**, texto libre. Se guarda **normalizado** (clave compacta) | Exigirlo siempre: bloquea facturar a un particular sin NIF. No validarlo: un NIF-IVA mal escrito pasa a la factura y a la declaración de operaciones intracomunitarias |
| D-05 | **Decidida.** **VIES simulado, sin red**: una empresa de la UE con NIF-IVA que pasa el control queda `valid_simulated` («Válido (simulado)»); `unchecked` («Sin comprobar») queda **reservado** para cuando exista la consulta real y VIES no responda (con el simulado no se produce, porque el NIF-IVA de una empresa de la UE es obligatorio); el resto, `not_applicable` («No aplica»). Se calcula **al guardar** y se guarda. Un puerto `ViesChecker` con `FakeViesChecker` determinista deja enchufar el real después (Should: fuera de la v1) | Mostrar siempre «Sin comprobar» hasta tener la consulta real: más honesto, pero la pantalla pierde el distintivo del prototipo. Llamar ya a VIES: red y dependencia nuevas |
| D-06 | **Archivar, no borrar** (`archived_at`): las facturas emitidas (W-007) referenciarán al cliente y son inmutables (RES-03, CONF-004). Un archivado no se ofrece para facturar, no se puede editar y se reactiva (`client_archived` 409 al editarlo) | Borrado físico: rompe las facturas. Editable aun archivado: una ficha «muerta» que cambia sin que nadie la vea |
| D-07 | **Un NIF por persona entre los clientes activos**: dos con la misma clave fiscal son el error `client_tax_id_taken` (409); los archivados no cuentan. Reactivar uno cuyo NIF ya usa un activo da el mismo error | Permitir repetidos: dos fichas del mismo cliente con series de facturas separadas |
| D-08 | **Todo es editable** (mientras esté activo): la factura (W-007) congela una **copia** de los datos del cliente al emitirse, así que cambiar país o tipo solo afecta a las facturas futuras; no hay noción de «en uso» | Bloquear país y tipo si hay facturas: obliga a duplicar fichas ante un error de alta |
| D-09 | Las escrituras van **solo por funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`, rol `usuario`, cerrojo asesor por persona); `authenticated` solo `SELECT` | Escritura directa con política `owner_id = auth.uid()`: sin cerrojo, dos altas a la vez con el mismo NIF dan un 23505 sin código útil |
| D-10 | **La validación fiscal vive en Python** (`cuadre.clients`); la base defiende solo lo barato (longitudes, `country ~ '^[A-Z]{2}$'`, `scope = 'national'` ⇔ `country = 'ES'`, que el VIES simulado solo marque a una empresa de la UE, tipos enumerados). **No** valida el NIF en SQL; un test de **paridad** compara las constantes | Validar también en SQL: dos fuentes de una regla (como en SPEC-W-005, D-14) |
| D-11 | **Fuera de esta spec:** la columna «Facturado en {año}», el texto de condiciones de la factura (`invoice_terms`: IVA, retención y mención) y los **territorios especiales** de España (Canarias, Ceuta, Melilla: `ES` se trata como nacional; pregunta abierta para W-007 y W-008) | Incluirlos aquí: necesita facturas que todavía no existen |
| D-12 | **Gestor y administrador no tienen pantalla de clientes.** El gestor lee por RLS con vínculo activo (su pantalla es SPEC-W-010); el administrador, nada (D3) | Pantalla de solo lectura del gestor aquí: W-010 la diseña con el resto de su cartera |

*Visto bueno del 2026-11-09: la persona pidió el plan del hito 0 sin cambios a D-02 a D-12 (D-01 y D-05 ya estaban decididas); se tratan como aprobadas y la spec pasa a `en-progreso`. El spike del hito 0 comprobó los NIF-IVA de los 27 Estados miembros, el catálogo de países, el DDL de §5.2 y la forma de la API, y corrigió §5.1, §5.2, §5.3, §5.4, AC-07, AC-17 y la propuesta de seed (Anexo B.1).*

## 2. Objetivo

Al terminar esta spec:

1. La persona tiene una pantalla **Clientes** (`/clientes`, activa en el menú) donde crea, edita, archiva y reactiva clientes con nombre, tipo, país, NIF o NIF-IVA y domicilio (RF-005).
2. El **ámbito** (nacional, UE o fuera de la UE) se **deduce** del país y se enseña como insignia con texto, nunca a mano.
3. El **identificador fiscal se valida con código** según D-04; un valor inválido no se guarda y el error aparece junto a su campo, con todos los errores a la vez.
4. Los clientes de la UE con NIF-IVA válido muestran **«Válido (simulado)»** en VIES; nada se consulta fuera de la aplicación (RES-04).
5. Un NIF no se repite entre los clientes activos de una persona.
6. Todo está **aislado por RLS** (NFR-06) y ni el nombre, ni el NIF, ni el domicilio de un cliente salen en registros, trazas o errores (NFR-11).
7. SPEC-W-007 recibe lo que necesita: la lista de clientes activos, su `scope` y su `kind`.

## 3. Alcance explícito

### 3.1 Dominio puro (`cuadre.clients`)
- Funciones sin base de datos, sin red y sin reloj: validación y normalización de los campos (§5.1), deducción del ámbito, regla del NIF por ámbito y tipo, estado de VIES simulado y mapeo del ámbito a los nombres del MCP. `limits` (longitudes, patrón del identificador libre, `COUNTRIES`, `EU_COUNTRIES`) en un solo sitio. El puerto `ViesChecker` y `FakeViesChecker`.

### 3.2 Base de datos (migraciones nuevas)
- Tipos `client_scope`, `client_kind` y `client_vies_status`; tabla `clients` con RLS activada y forzada; trigger de guarda; funciones `app.create_client`, `app.update_client` y `app.set_client_archived`; entrada en `backend/tests/rls/rls_matrix.yaml`; seed con clientes sintéticos de los tres ámbitos.

### 3.3 Backend (FastAPI)
- Rutas `list_clients`, `get_client`, `create_client`, `update_client` y `set_client_archived` (§5.3), solo para el rol `usuario`. Paquete `cuadre.clients` (servicio, repositorio, modelos, errores).

### 3.4 Frontend (Next.js)
- `/clientes` con la lista (tarjetas hasta 1.279 px y tabla desde 1.280 px), «Añadir cliente», editar, archivar y reactivar, filtro de archivados; «Clientes» activo en el menú del autónomo.

### 3.5 Pruebas
- `backend/tests/clients/`, ampliación de `backend/tests/rls/`, `backend/tests/rules/test_clients_boundary.py`, unitarias del frontend, `frontend/e2e/clientes.spec.ts` en los tres motores y los dos anchos, y los ajustes de `roles.spec.ts`, `responsive.spec.ts` y `e2e/helpers/env.ts`.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Emitir facturas y aplicar IVA, retención y mención legal según el ámbito (`invoice_terms`); congelar la copia del cliente; la columna «Facturado en {año}» | SPEC-W-007 |
| Casillas del 303 por ámbito (59, 120…) y modelo 349 | SPEC-W-008 |
| Consulta real a VIES (en tiempo real) | Futura (Should del PRD); el puerto `ViesChecker` lo permite |
| Territorios especiales de España (Canarias, Ceuta, Melilla) y otros regímenes especiales | W-007 / W-008 (pregunta abierta) |
| Pantalla del gestor para ver los clientes de sus autónomos (aquí solo la política de lectura) | SPEC-W-010 |
| Importar clientes desde un archivo; contactos (correo, teléfono); varios domicilios | Futura |
| Borrado de la cuenta y exportación de los clientes | SPEC-W-017 (CONF-004) |
| Registro de actividad de los cambios de la ficha | No hay criterio que lo pida |

## 5. Contrato de interfaces

### 5.1 Campos y reglas

Los textos de error van en español, **no repiten el valor escrito** y salen del servidor. Un campo vacío o con solo espacios se guarda como `NULL`. `PUT /api/clients/{id}` y `POST /api/clients` validan **todos** los campos a la vez y, si alguno falla, **no guardan nada** y devuelven todos los errores.

| Campo (API) | Columna | Regla | Mensaje si falla |
|---|---|---|---|
| `name` | `name` | texto de 2 a 200, recortado, sin caracteres de control (`Cc`, `Cf`, `Zl`, `Zp`) | «Escribe el nombre o la razón social del cliente.» · «El nombre admite hasta 200 caracteres.» · «No puede llevar saltos de línea ni caracteres de control.» |
| `kind` | `kind` | `"business"` o `"individual"` | «Elige si es una empresa o profesional, o un particular.» |
| `country` | `country` | código alfa-2 en mayúsculas de `COUNTRIES` (se recorta y se pasa a mayúsculas) | «Elige un país de la lista.» |
| `tax_id` | `tax_id` | **según D-04**, ver abajo. Se guarda normalizado | ver abajo |
| `address` | `address` | texto de 0 a 300, recortado, sin caracteres de control | «El domicilio admite hasta 300 caracteres.» · «No puede llevar saltos de línea ni caracteres de control.» |

**Ámbito** (`scope`, **no lo envía la persona**): `national` si `country = "ES"`; `eu` si `country` está en `EU_COUNTRIES` y no es `ES`; `non_eu` en cualquier otro caso. `EU_COUNTRIES` son los 27 Estados miembros (`AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK`); `GB`, `CH` y el resto del catálogo son `non_eu`. `XI` (Irlanda del Norte), `XK` (Kosovo) y `EU` **no son códigos ISO asignados**: no están en `COUNTRIES` y dan el error «Elige un país de la lista.» (B.1).

**Identificador fiscal** (`tax_id`), por ámbito y tipo:

| Ámbito | Empresa (`business`) | Particular (`individual`) |
|---|---|---|
| `national` | **Obligatorio.** `normalize_tax_id` no nulo y de `scope = national` (NIF, NIE o CIF) | Opcional; si se escribe, el mismo control |
| `eu` | **Obligatorio.** `normalize_tax_id` no nulo, de `scope = eu` y con el prefijo del país (`GR` ↔ `EL`; el resto, el propio código) | Opcional; texto libre |
| `non_eu` | **Obligatorio.** Texto libre | Opcional; texto libre |

El **texto libre** admite `[0-9A-Za-z .,/-]`, hasta 32 caracteres, y se guarda en mayúsculas y sin espacios, puntos ni guiones (clave compacta, que es la que compara D-07). Mensajes: «Escribe el NIF del cliente.» (nacional, vacío) · «El NIF no es válido: revisa el dígito o la letra de control.» · «Escribe un NIF, NIE o CIF español.» (uno de la UE en un cliente nacional) · «Escribe el NIF-IVA del cliente.» (UE, vacío) · «El NIF-IVA no es válido o no corresponde al país elegido.» · «Escribe el identificador fiscal del cliente.» (fuera de la UE, vacío) · «El identificador fiscal solo lleva letras, números y guiones, hasta 32 caracteres.»

**Estado de VIES** (`vies_status`, calculado al guardar, D-05): `valid_simulated` si `scope = eu`, `kind = business` y `tax_id` pasó el control; `not_applicable` en el resto. `unchecked` existe en el tipo pero **no lo produce el simulado** (reservado para la consulta real cuando VIES no responda).

**Mapeo del MCP** (`cuadre.clients.scope`): `national → nacional`, `eu → ue`, `non_eu → fuera_ue`, en un solo sitio.

### 5.2 Base de datos

Migraciones nuevas (`YYYYMMDDHHMMSS_descripcion.sql`, sin destructivas; las ya aplicadas no se tocan). Patrón de `CLAUDE.md`: RLS activada y forzada, registro en `rls_matrix.yaml`.

```
TYPE client_scope       AS ENUM ('national', 'eu', 'non_eu')
TYPE client_kind        AS ENUM ('business', 'individual')
TYPE client_vies_status AS ENUM ('valid_simulated', 'unchecked', 'not_applicable')

clients
  id          uuid PK DEFAULT gen_random_uuid()
  owner_id    uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE   -- ficha de la persona; las facturas (W-007) no cascadearán (CONF-004)
  name        text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 200)
  kind        client_kind NOT NULL
  country     text NOT NULL CHECK (country ~ '^[A-Z]{2}$')
  scope       client_scope NOT NULL
  tax_id      text CHECK (char_length(tax_id) BETWEEN 1 AND 32)         -- clave compacta
  address     text CHECK (char_length(address) <= 300)
  vies_status client_vies_status NOT NULL DEFAULT 'not_applicable'
  archived_at timestamptz
  created_at, updated_at timestamptz NOT NULL DEFAULT now()
  CHECK ((scope = 'national') = (country = 'ES'))
  CHECK (vies_status = 'not_applicable' OR (scope = 'eu' AND kind = 'business'))   -- el simulado solo marca a una empresa de la UE
UNIQUE INDEX clients_owner_tax_id_active ON clients (owner_id, tax_id) WHERE tax_id IS NOT NULL AND archived_at IS NULL
INDEX clients_owner ON clients (owner_id)
```

Las restricciones llevan nombre propio para que la API las traduzca por nombre: `clients_name_length`, `clients_country_format`, `clients_tax_id_length`, `clients_address_length`, `clients_scope_matches_country`, `clients_vies_matches_scope` y el índice `clients_owner_tax_id_active` (B.1 y B.3). El CHECK de ámbito solo sabe que `national` ⇔ `ES`: qué países son de la UE lo decide `cuadre.clients` (D-10). Trigger `clients_guard` (`BEFORE UPDATE`): `owner_id` y `created_at` no cambian (`client_immutable_column`); `updated_at` lo mantiene `private.touch_updated_at`.

**Privilegios.** `authenticated`: `SELECT` y nada más; toda escritura por funciones.

| Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|
| SELECT | los suyos, archivados incluidos | los de usuarios con vínculo activo (`private.gestor_has_access(owner_id)`) | **ninguno** |
| INSERT / UPDATE / DELETE | denegado (solo `app.*`) | denegado | denegado |

**Funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`; verifican `auth.uid()` y `private.app_role() = 'usuario'`; `P0001` con código estable, `42501` si el rol no basta). Todas toman primero el cerrojo asesor por persona con un ayudante `private.clients_enter()` (como `private.series_enter()`):

| Función | Efecto |
|---|---|
| `app.create_client(p_name, p_kind, p_country, p_scope, p_tax_id, p_address, p_vies_status)` | Recibe `kind`, `scope` y `vies_status` como **texto** y los valida antes de convertirlos (B.3). Comprueba lo barato (`invalid_client`, campo en el `DETAIL`) y que `p_scope` es coherente con el país; `client_tax_id_taken` si ya hay un activo con esa clave. Devuelve el id |
| `app.update_client(p_id, …)` | Sustituye todos los campos de un cliente **activo** (`client_not_found` si no existe o es ajeno; `client_archived` si está archivado; `client_tax_id_taken`, comprobado **antes** de escribir) |
| `app.set_client_archived(p_id, p_archived)` | Archiva o reactiva. Reactivar uno cuyo NIF ya usa un activo da `client_tax_id_taken`: la función lo comprueba **antes**, porque el índice daría un `23505` sin código útil (B.1) |

Ninguna escribe `activity_log`. La API traduce además el `23505` de `clients_owner_tax_id_active` como `client_tax_id_taken` (red de seguridad; con el cerrojo no debería darse). Los errores `P0001` son `client_not_found`, `client_archived`, `client_tax_id_taken` e `invalid_client`.

**Matriz de RLS.** `clients`: `kind: financial`, `owner_column: owner_id`, privilegios `SELECT`, y un `seed` con clientes de los tres ámbitos por persona.

**Seed (sintético).** Dos o tres clientes por persona: uno nacional (empresa, con CIF válido), uno de la UE (empresa, con NIF-IVA alemán o francés válido) y uno fuera de la UE (empresa o particular); nombres y NIF inventados con dígitos de control válidos (los fija el hito 0). Ningún dato real (RES-07).

### 5.3 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador); errores en `application/problem+json`.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `list_clients` | `GET /api/clients` | Query `include_archived` (bool, por defecto `false`). **200** `[Client]` por nombre, en el orden alfabético del español (`ORDER BY name COLLATE "es-x-icu", id`: la ñ va después de la n; B.1) |
| `get_client` | `GET /api/clients/{client_id}` | **200** `Client`; **404** `client_not_found` |
| `create_client` | `POST /api/clients` | Cuerpo `ClientInput`. Valida todo y guarda; **201** `Client`; **422** `invalid_client`; **409** `client_tax_id_taken` |
| `update_client` | `PUT /api/clients/{client_id}` | Cuerpo `ClientInput`. **200** `Client`; **404**, **409** `client_archived` o `client_tax_id_taken`, **422** |
| `set_client_archived` | `PUT /api/clients/{client_id}/archived` | Cuerpo `{ "archived": bool }`. **200** `Client`; **404**; **409** `client_tax_id_taken` al reactivar |

```
ClientInput { name, kind: "business"|"individual", country, tax_id: string|null, address: string|null }
Client { id, name, kind, country, scope: "national"|"eu"|"non_eu", tax_id: string|null, address: string|null,
         vies_status: "valid_simulated"|"unchecked"|"not_applicable", archived: bool, created_at, updated_at }
```

**Códigos de error nuevos** (`code`, HTTP): `invalid_client` 422 (con el miembro extra `fields: [ { field, message } ]`, **todos** los que fallan) · `client_tax_id_taken` 409 · `client_archived` 409 · `client_not_found` 404 (también si es de otra persona) · `forbidden` 403. Los errores de forma del cuerpo son el `validation_error` 422 de siempre. Los textos van en español y no repiten el valor escrito.

### 5.4 Backend

- **Paquetes.** `cuadre.clients` (puros: `limits`, `types`, `countries`, `scope`, `rules`, `vies`; con base de datos, a partir del hito 3: `service`, `repository`, `models`, `errors`) y `api/routes_clients.py`. `rules` importa de `cuadre.validators` solo `normalize_tax_id` y **no importa `stdnum`**, ni base de datos, red, FastAPI ni reloj; lo vigila `backend/tests/rules/test_clients_boundary.py`, como `test_profile_boundary.py`.
- **Flujo de `create_client` y `update_client`.** Una transacción corta: validar todo con `cuadre.clients` → llamar a `app.create_client` o `app.update_client` con el ámbito y el estado de VIES ya calculados → leer la fila → confirmar. Nunca una conexión retenida mientras se espera a algo externo (no hay nada externo).
- **Modelos.** La **entrada es suelta**: `ClientInput` con `str` y `max_length` y `extra="forbid"`, sin `Literal` ni patrón, para que `tipo`, `país` y los demás campos pasen por el dominio y se devuelvan **todos los errores a la vez** como `invalid_client` (con `Literal`, Pydantic respondería un `validation_error` por separado: B.1). `archived` va con `StrictBool` (un `"yes"` no es `true`). La salida (`Client`) sí lleva uniones de literales para el cliente generado.
- **VIES.** `ViesChecker` (puerto) y `FakeViesChecker`; el servicio usa el simulado salvo que el despliegue configure otro; esta spec no añade ninguno.
- **Sin dependencias nuevas:** `python-stdnum` ya está fijado. Sin `pycountry`.

### 5.5 Frontend

| Ruta | Quién | Contenido |
|---|---|---|
| `/clientes` | `usuario` | Cabecera con «Añadir cliente». Lista de clientes activos: tarjetas hasta 1.279 px y tabla desde 1.280 px (Cliente con su tipo, NIF, País, Ámbito, VIES). El ámbito y el estado de VIES son **texto con insignia** («Nacional», «UE», «Fuera de la UE»; «Válido (simulado)», «Sin comprobar», «No aplica»); la UE y la de fuera usan los tokens `scope-eu` y `scope-non-eu` del prototipo. Filtro «Mostrar archivados». Acciones «Editar», «Archivar» y «Reactivar». Formulario (en una sección desplegable o en su propia pantalla) con Nombre o razón social, Tipo, País, NIF o NIF-IVA y Domicilio; el rótulo del identificador cambia según el ámbito («NIF», «NIF-IVA», «Identificador fiscal»). Pie: «Los NIF-IVA de la UE se comprueban en VIES (simulado en esta versión).» |

Crear, editar y archivar son **Server Actions** (`useActionState`, errores junto a cada campo con `aria-describedby`, resumen de errores que recibe el foco, como `profile-form`). La interfaz **muestra** lo que dice el servidor y no valida nada fiscal. Los nombres de país salen de `Intl.DisplayNames('es')` con el código alfa-2 que guarda la API; la lista del selector se ordena por nombre. Ni el NIF ni el nombre ni el domicilio se escriben en la consola ni en ningún registro del navegador. «Clientes» pasa de `FUTURE` a enlace en `navFor('usuario')` y a `SECTIONS.usuario`; gestor y administrador no lo ven y `/clientes` para ellos lleva a `/403`. Hay que actualizar `lib/roles.test.ts` y `PEOPLE.alicia.nav` / `enabledNav` en `e2e/helpers/env.ts`.

## 6. Restricciones técnicas

| ID | Restricción |
|---|---|
| T6-01 | **Sin red ni modelos de lenguaje**: ni VIES, ni para el NIF, ni para el ámbito (RES-01, RES-04); `cuadre.clients` no importa base de datos, `httpx`, FastAPI ni `stdnum` y no usa `datetime.now()` |
| T6-02 | **Una fuente por regla.** Longitudes, `COUNTRIES`, `EU_COUNTRIES`, el patrón del identificador libre y el mapeo del MCP viven en `cuadre.clients`; los CHECK de la base los repiten y un test de paridad los compara |
| T6-03 | **Solo `usuario`** lee y escribe sus clientes por la API; el gestor con vínculo activo lee por RLS (revocar corta el acceso en la petición siguiente) y el administrador no ve los de otros (D3, NFR-06). La service key no interviene |
| T6-04 | **Sin datos de terceros en logs, trazas, errores ni `activity_log`**: ni nombre, ni NIF, ni domicilio del cliente. Los `422` dicen qué campo falla, no qué se escribió. Un test captura los registros de todo el flujo |
| T6-05 | **Una lectura no escribe**: `list_clients` y `get_client` no crean ni cambian nada |
| T6-06 | **Archivar, no borrar**: no hay ruta ni `DELETE` de clientes; las facturas (W-007) dependerán de la ficha |
| T6-07 | **Sin trabajo posterior a la respuesta** (ADR-0016); `test_vercel_compat` sigue verde |
| T6-08 | **Interfaz** como T5-10: tokens del prototipo, etiquetas, foco visible, estado con texto además de color, anuncios con `aria-live`, sin scroll horizontal a 390 y 1.440 px en los tres navegadores |
| T6-09 | **Migraciones sin datos reales y sin destructivas**; no se editan las aplicadas; el seed es sintético (RES-07) |
| T6-10 | Una prueba E2E que cree clientes en la cuenta compartida del worker **los archiva** al empezar y al terminar (no se pueden borrar): ninguna depende de lo que dejó otra |

## 7. Criterios de aceptación (Given-When-Then)

```gherkin
AC-01  Cliente nacional (RF-005)
  Given una persona con sesión
  When crea una empresa en España con un CIF válido ("b00000018" con espacios y minúscula)
  Then la respuesta es 201 con scope "national", el NIF guardado en mayúsculas y compacto y vies_status "not_applicable"
    And aparece en /clientes con la insignia «Nacional»

AC-02  Cliente de la UE con NIF-IVA (US-006)
  Given una persona con sesión
  When crea una empresa en Alemania con un NIF-IVA alemán válido
  Then scope es "eu" y vies_status "valid_simulated"
    And /clientes enseña «UE» y «Válido (simulado)», y ninguna petición sale de la aplicación

AC-03  Cliente de fuera de la UE
  Given una persona con sesión
  When crea una empresa en México con un identificador fiscal escrito a mano, y un particular de Estados Unidos sin identificador
  Then ambos se crean con scope "non_eu" y vies_status "not_applicable"
    And la empresa sin identificador da 422 "invalid_client" con field "tax_id"

AC-04  NIF inválido, de otro ámbito o con otro prefijo
  Given una persona con sesión
  When guarda un cliente nacional con la letra de control equivocada, uno nacional con un NIF-IVA de la UE, y uno alemán con un NIF-IVA francés
  Then cada uno da 422 "invalid_client" con fields = [{ field: "tax_id", message }] y el mensaje de §5.1 que corresponda
    And no se guarda nada y el mensaje no repite el valor escrito

AC-05  Todos los errores a la vez
  Given una persona con sesión
  When envía un nombre vacío, un tipo desconocido, un país que no existe y un domicilio de 301 caracteres
  Then la respuesta es 422 "invalid_client" con fields que enumera los cuatro, en el orden de la pantalla
    And no se crea ningún cliente

AC-06  Particular sin NIF o con NIF malo
  Given una persona con sesión
  When crea un particular español sin NIF, y otro con el NIF mal
  Then el primero se crea y el segundo da 422 con field "tax_id"

AC-07  Ámbito deducido
  Given los códigos "ES", "DE", "GR", "GB", "CH" y "MX"
  When se crea un cliente en cada país
  Then el ámbito es "national", "eu", "eu", "non_eu", "non_eu" y "non_eu"
    And un cliente de Grecia exige un NIF-IVA con prefijo "EL"
    And "XI", "XK", "EU", "ZZ", "es" sin mayúsculas válidas o un código de tres letras dan 422 "invalid_client" con field "country"

AC-08  Un NIF por persona
  Given un cliente activo con un NIF
  When la persona crea o edita otro con el mismo NIF, y reactiva un archivado cuyo NIF ya usa uno activo
  Then cada intento da 409 "client_tax_id_taken"
    And el mismo NIF en un cliente archivado no cuenta, y el de otra persona tampoco

AC-09  Editar
  Given un cliente nacional activo
  When la persona cambia su país a Francia y su NIF a un NIF-IVA francés válido
  Then el ámbito pasa a "eu" y vies_status a "valid_simulated", y updated_at cambia
    And editar uno ajeno da 404 "client_not_found" y editar uno archivado da 409 "client_archived"

AC-10  Archivar y reactivar
  Given un cliente activo
  When la persona lo archiva y después lo reactiva
  Then archived es verdadero y después falso; el archivado no sale en list_clients salvo con include_archived
    And ningún cliente se puede borrar (no hay ruta ni DELETE)

AC-11  Una lectura no escribe
  Given una cuenta con clientes
  When consulta list_clients y get_client
  Then ni updated_at ni ninguna fila cambian

AC-12  Aislamiento (NFR-06)
  Given Alicia y Beto (usuarios), Gina (gestora con vínculo activo con Alicia) y Adán (administrador)
  When cada uno intenta leer o escribir los clientes de otro
  Then Beto no ve nada de Alicia y no puede escribirlo; Gina lee los de Alicia y no escribe nada; tras revocar, no ve nada
    And Adán no ve ningún cliente de nadie (D3)
    And Gina y Adán reciben 403 "forbidden" en las rutas de clientes
    And un INSERT, UPDATE o DELETE directo sobre clients es rechazado (privilegio)

AC-13  Concurrencia
  Given una persona sin clientes
  When dos peticiones crean a la vez un cliente con el mismo NIF
  Then una responde 201 y la otra 409 "client_tax_id_taken" (nunca un 500), y queda un solo cliente

AC-14  Sin datos de terceros en los registros
  Given el flujo completo (alta, errores, edición, archivado, 403 y 404)
  When se capturan todos los registros
  Then ni el nombre, ni el NIF, ni el domicilio de ningún cliente aparecen en ellos ni en el cuerpo de ningún error

AC-15  Interfaz de Clientes (NFR-10)
  Given la persona en /clientes con la sesión de un usuario
  When crea un cliente de cada ámbito, edita uno, lo archiva y lo reactiva, a 390 y a 1.440 px
  Then no hay scroll horizontal, todo campo tiene su etiqueta, cada error sale junto a su campo y en un resumen que recibe el foco
    And el ámbito y VIES se distinguen por su texto, y el rótulo del identificador cambia según el país
    And se puede hacer todo con el teclado, el foco siempre se ve y no hay errores de consola en Chromium, Firefox ni WebKit

AC-16  Menú y portadas
  Given un usuario, una gestora y un administrador con sesión
  When ven su menú y entran en /clientes
  Then el usuario ve «Clientes» activo; la gestora y el administrador no lo ven y /clientes los lleva a /403
    And las portadas /inicio, /cartera, /admin y /perfil siguen mostrando lo de SPEC-W-001 y SPEC-W-005

AC-17  Nombres de país
  Given los 249 códigos de COUNTRIES
  When la interfaz los traduce con Intl.DisplayNames("es")
  Then todos tienen un nombre en español distinto del código en Node, Chromium, Firefox y WebKit, y el selector se ordena por nombre
    And las pruebas no comparan nombres exactos entre motores (Chromium nombra distinto cuatro códigos: B.1)

AC-18  Guardas (T6-01, T6-02, T6-07)
  Given el repositorio entero
  When corren las guardas
  Then cuadre.clients no importa base de datos, httpx, FastAPI ni stdnum, ni usa el reloj del sistema
    And las constantes de limits y los CHECK de la base coinciden
    And test_rls_guard exige clients en la matriz y test_vercel_compat, test_no_float y test_operation_ids siguen verdes
```

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos
Los de SPEC-W-005 §8.1, con la pila de Supabase en marcha y los puertos 3000 (o `E2E_WEB_PORT`), 8000 y 8765 (o `E2E_AGENTS_PORT`) libres. Sin red: los NIF y NIF-IVA de las pruebas son inventados con dígitos de control válidos y nada sale a Internet. Los E2E de clientes usan la cuenta del worker y **archivan** sus clientes al empezar y al terminar (T6-10).

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
pip install -e contracts/python ; pip install -e "backend[dev]"
npx supabase db reset                                                  # migraciones + seed
pytest backend/tests/clients -q                                        # AC-01 a AC-11, AC-13, AC-14 y AC-18 (lado API)
pytest backend/tests/rls -m rls -q                                     # AC-12 (tabla, privilegios, funciones)
pytest backend/tests -m "not rls" -q
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend exec -- playwright test e2e/clientes.spec.ts     # AC-15 a AC-17 en 3 motores x 2 anchos
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/clients` y `npm --prefix frontend exec -- playwright test e2e/clientes.spec.ts`, además de las secuencias completas de SPEC-W-001, 002, 003 y 005 §8.2, que deben seguir en verde (la batería de E2E se ejecuta con `--workers=1` y un motor por invocación si hay poca memoria libre).

### 8.3 Correspondencia criterio → prueba

| AC | Prueba |
|---|---|
| AC-01 a AC-07 | `backend/tests/clients/test_rules.py` (tablas de NIF, NIF-IVA y países, sin red), `test_clients_api.py`; `frontend/src/lib/clients-form.test.ts`; `clientes.spec.ts` · «un cliente de cada ámbito» y «NIF inválido» |
| AC-08, AC-13 | `backend/tests/clients/test_clients_api.py`, `test_concurrency.py`; `backend/tests/rls/test_clients.py` (índice parcial con dos transacciones) |
| AC-09, AC-10, AC-11 | `backend/tests/clients/test_clients_api.py`; `clientes.spec.ts` · «editar, archivar y reactivar» |
| AC-12 | `backend/tests/rls/test_clients.py` y `rls_matrix.yaml`; `backend/tests/clients/test_roles.py` |
| AC-14 | `backend/tests/clients/test_no_sensitive_logs.py` |
| AC-15, AC-16 | `frontend/e2e/clientes.spec.ts` (seis proyectos), `responsive.spec.ts` (`/clientes`), `roles.spec.ts`; `frontend/src/lib/roles.test.ts` |
| AC-17 | `frontend/src/lib/countries.test.ts` y `clientes.spec.ts` en cada motor |
| AC-18 | `backend/tests/rules/test_clients_boundary.py`, `backend/tests/clients/test_limits_parity.py`, `backend/tests/rls/test_rls_guard.py` y las guardas de `backend/tests/rules/` |

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local y en el CI, y las de SPEC-W-001, 002, 003 y 005 §8.2 siguen en verde.
- [ ] `pytest backend/tests/rls -m rls` incluye `clients` y sus funciones.
- [ ] «Clientes» está activo en el menú del autónomo y `/clientes` hace todo lo de AC-15.
- [ ] El seed lleva clientes sintéticos de los tres ámbitos y las pruebas que dependían del menú se han revisado.
- [ ] `docs/04-specs/tasks.json` actualizado; los ADR 0003, 0004, 0006, 0011, 0015 y 0016 enlazados.
- [ ] Sin secretos, NIF reales ni datos de terceros en el cambio; `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido (un plan y un commit por hito)

0. **Spike**: con valores **sintéticos**, qué acepta `normalize_tax_id` para el NIF-IVA de cada uno de los 27 Estados miembros (incluidos `EL`/`GR`, y que `XI` y `EU` no valen); que `Intl.DisplayNames('es')` da nombre a los 249 códigos en Node, Chromium, Firefox y WebKit; la lista de países UE contra una fuente oficial; el DDL de §5.2 en seco, incluido el índice parcial y el CHECK `scope`/`country`; y los NIF y NIF-IVA del seed. Resultado al Anexo B.
   **Hecho el 2026-11-09** (resultado en el Anexo B.1; corrigió §5.1, §5.2, §5.3, §5.4, AC-07 y AC-17, y fijó el catálogo a mano, el orden `es-x-icu`, la entrada suelta y el seed).
1. **Dominio puro** (`cuadre.clients`): campos, ámbito, regla del NIF, VIES simulado, mapeo del MCP, `limits`, `test_clients_boundary`, con tablas de pruebas y mutaciones.
   **Hecho el 2026-11-09** (`backend/src/cuadre/clients/`; decisiones, pruebas y mutaciones en el Anexo B.2).
2. **Base de datos**: tipos, tabla con trigger y funciones, matriz de RLS, seed y pruebas de RLS, con mutaciones.
   **Hecho el 2026-11-09** (dos migraciones, el seed y la matriz; decisiones, pruebas y mutaciones en el Anexo B.3).
3. **API**: `cuadre.clients` (servicio y repositorio), las cinco rutas, `openapi.json` y `schema.d.ts` regenerados, con mutaciones.
   **Hecho el 2026-11-09** (`cuadre/clients/{errors,models,repository,service}.py` y `api/routes_clients.py`; decisiones, pruebas y mutaciones en el Anexo B.4).
4. **Frontend**: `/clientes` (lista, formulario, archivar), menú, nombres de país; unitarias.
5. **E2E y cierre**: `clientes.spec.ts` en tres motores y dos anchos, ajustes de `roles.spec.ts`, `responsive.spec.ts` y `env.ts`, fixture que archiva los clientes del worker, mutaciones, Anexo B, `tasks.json`.

## Anexo B · Decisiones que esta spec dejó a la implementación

*(Se rellena al implementar.)*

### B.0 Notas que esta spec deja a otras specs

- **SPEC-W-007 (facturas).** (1) El selector de cliente ofrece solo los **activos** (`list_clients`). (2) Congela en la factura una **copia** del cliente (nombre, NIF, país, domicilio, ámbito y tipo), porque la ficha es editable y la factura no. (3) La regla de `invoice_terms(scope, kind, irpf_rate)` es suya: nacional → IVA (21 % por defecto) y retención solo a empresa con la del perfil; UE y empresa → sin IVA ni retención y con «Inversión del sujeto pasivo»; UE y particular → IVA español; fuera de la UE → sin IVA y con el artículo 69 de la Ley del IVA. (4) Decide si exige **domicilio** del cliente para emitir (RD 1619/2012 lo pide en la factura completa); aquí es opcional. (5) La columna «Facturado en {año}» del prototipo.
- **SPEC-W-008 (303).** Las casillas 59 y 120 y el modelo 349 salen del `scope` y del `kind` de la copia congelada. Los territorios especiales de España (Canarias, Ceuta, Melilla) no se distinguen aquí: pregunta abierta.
- **SPEC-W-010 (gestor).** La política de lectura de `clients` para el gestor ya existe; faltan la pantalla y el registro de cada lectura.
- **SPEC-W-011 (MCP).** Usa `cuadre.clients.scope` para el mapeo `non_eu ↔ fuera_ue`; no lo duplica.
- **SPEC-W-017 (cierre de cuenta).** Los clientes son datos personales de terceros (CONF-004): la exportación y el borrado de la cuenta deben incluirlos. `clients` se borra en cascada con la cuenta; las facturas, no.

### B.1 Spike · hito 0 · 2026-11-09

Entorno: Windows 11, Python 3.12, `python-stdnum` 2.2 (ya fijado; no se ha instalado nada), FastAPI 0.162.0, Pydantic 2.14.2, `openapi-typescript` 7.13.0 (el del repositorio), PostgreSQL 17.11 del Supabase local (collation de la base `en_US.UTF-8`), Node 24.16.0 (ICU 78.3, CLDR 48.0) y, con Playwright, Chromium 156.0.8078.4, Firefox 157.0 y WebKit 27.2. Cuatro guiones desechables fuera del repositorio (A, B, C y D); los valores son sintéticos y el esquema de pruebas `spike_w006` se creó y se borró (la base queda con las mismas 7 tablas de `public` y sin `public.clients`).

**A · NIF y NIF-IVA con `normalize_tax_id`**

| Pregunta | Resultado |
|---|---|
| ¿`normalize_tax_id` valida un NIF-IVA de cada Estado miembro? | **Sí, los 26 distintos de España**: se fabricó uno sintético con dígito de control válido por país (probando candidatos con `stdnum`) y todos entran **compactos, con separadores y en minúsculas**, con la misma clave y `scope = "eu"`. Con un guion inicial no pasan (el prefiltro de `tax_id.py` lo impide) |
| ¿Cabe la clave en las columnas? | Sí: de **10 a 14** caracteres, dentro de `TAX_ID_KEY` (5 a 20) y de `char_length(tax_id) BETWEEN 1 AND 32` |
| Grecia (D-04) | País `GR`, prefijo `EL`: la clave es `EL…` tanto si se escribe `GR…` como `EL…`. El dominio compara el prefijo con `{"GR": "EL"}` y con el propio código en los demás |
| ¿Qué no vale? | `XI`, `EU`, `GB`, `CH`, `NO`, `US` y `MX` dan `None` con un cuerpo de NIF-IVA alemán. `stdnum` lista `xi` entre sus Estados miembros y `EU_VAT_PREFIXES` del repositorio **no** lo incluye: así sigue |
| ¿Rechaza la librería un NIF-IVA de otro país? | **No**: un NIF-IVA francés para un cliente alemán lo da por bueno (`scope = "eu"`). **La regla del prefijo la pone `cuadre.clients`**, como pide D-04 |
| NIF españoles del seed | `B00000018`, `B00000026` (CIF) y la familia `B000000NN` del prototipo pasan; también `X1234567L`, `Y1234567X` (NIE), `00000000T` y `99999999R` (DNI). `es b00000018` y ` b-0000 0018 ` se normalizan a `B00000018` |

**B · Catálogo de países**

| Pregunta | Resultado |
|---|---|
| ¿De dónde sale la lista de 249 códigos? | **De ningún paquete ya instalado**: no hay `pycountry`, `babel` ni `iso3166` y `stdnum` no trae la lista. Se escribe **a mano** en `cuadre.clients.limits` (249 únicos, ISO 3166-1 alfa-2, contados a mano) y un test la cruza con `Intl.DisplayNames` en el frontend |
| ¿`Intl.DisplayNames('es', { type: 'region' })` nombra los 249? | **Sí en los cuatro**: Node, Chromium, Firefox y WebKit dan un nombre distinto del código a los 249, y los 27 de la UE están en el catálogo |
| ¿Devuelve ICU códigos que no son del catálogo? | Sí: 31 en Node y Chromium, 42 en Firefox y 30 en WebKit (`AC`, `EU`, `UK`, `UN`, `ZZ`, `XK` Kosovo, códigos históricos como `YU` o `SU`…). **El catálogo lo define la constante, no ICU**; `XK` y `EU` no entran (no son ISO asignados) |
| ¿Dan los motores el mismo nombre? | **No siempre**: Chromium difiere de Node, Firefox y WebKit en cuatro (`FK` «Islas Malvinas (Islas Falkland)», `HK` «Hong Kong», `MO` «Macao», `PS` «Palestina»). Las pruebas **no comparan nombres exactos entre motores**: comprueban que cada código tiene un nombre y que no es el código |
| Longitud y orden | El nombre más largo mide 40 caracteres (`GS` «Islas Georgia del Sur y Sandwich del Sur»; luego `IO` con 38 y `UM` con 33). Con `localeCompare('es')` el orden sale igual en los tres motores (Afganistán, Albania, Alemania, Andorra, Angola…) |
| ¿Los 27 de la UE coinciden con `stdnum`? | Sí, salvo que `stdnum` añade `xi`: los 27 de la spec equivalen a sus Estados miembros con `GR` ↔ `EL` y sin `XI` |

**C · Base de datos (DDL en seco, esquema desechable)**

| Pregunta | Resultado |
|---|---|
| ¿Compila el DDL de §5.2? | Sí: los tres tipos, la tabla y los índices, con las restricciones **con nombre**: `clients_name_length`, `clients_country_format`, `clients_tax_id_length`, `clients_address_length`, `clients_scope_matches_country` y el índice `clients_owner_tax_id_active` |
| Índice único parcial | Dos clientes sin NIF del mismo dueño: bien (los `NULL` no chocan). Mismo NIF, mismo dueño y ambos activos: **`23505` `clients_owner_tax_id_active`**. Mismo NIF en otro dueño: bien. **Archivar libera el NIF**. **Reactivar uno cuyo NIF ya usa un activo también da `23505`**, no un código útil: las funciones tienen que comprobarlo **antes** (como `series_is_default` en W-005) |
| CHECK `scope` ⇔ `country = 'ES'` | Rechaza `national` con `DE`, `eu` con `ES` y `non_eu` con `ES` (`23514` con su nombre) y admite `eu`/`DE`, `non_eu`/`MX` y `national`/`ES`. **No sabe qué países son de la UE**: `eu` con `XX` pasa (de eso se ocupa `cuadre.clients`, D-10). `country` en minúsculas y un nombre de un carácter dan `23514` con su nombre |
| Carrera: dos altas a la vez con el mismo NIF | **Sin cerrojo**, una gana y la otra recibe `23505` en el índice. **Con `pg_advisory_xact_lock(hashtextextended('clients:' \|\| owner, 0))`** la segunda espera y recibe el código estable `client_tax_id_taken` (`P0001`): justifica el cerrojo de D-09 |
| Orden de la lista | `ORDER BY lower(name)` con la collation `en_US.UTF-8` ya deja los acentos y las mayúsculas como desempate, pero **coloca «Ñandú» entre «Éxito» y «nube»** (trata la ñ como n con tilde). `COLLATE "es-x-icu"` lo coloca **después de «nube»**, que es el orden del español, y `und-x-icu` repite el de `en_US`. Hay 29 collations ICU `es-*`. **`unaccent` está disponible pero no instalada y no hace falta.** Python con `casefold` y sin acentos da otro desempate («Árbol SL» antes de «arbol sl») |
| Ayudantes para políticas y funciones | Existen `private.app_role`, `private.gestor_has_access`, `private.touch_updated_at`, `private.today_madrid` y `private.series_enter` (el modelo de `private.clients_enter`) |

**D · Forma de la API**

| Pregunta | Resultado |
|---|---|
| Entrada con `Literal` y patrón | Un tipo desconocido o un país en minúsculas dan el **`validation_error` 422 de Pydantic**, con una sola ubicación cada uno y **sin pasar por el dominio**: AC-05 («todos los errores a la vez») no se cumpliría. La entrada es **suelta**: `str` con `max_length` y `extra="forbid"`; el contenido lo valida `cuadre.clients` y responde `invalid_client` |
| Campo de más | `extra="forbid"` lo rechaza con 422 |
| Booleanos | **Pydantic acepta `"yes"` como `true`** en un `bool` normal: `archived` va con `StrictBool`, como en SPEC-W-005 |
| Cliente TypeScript | `Client` sale con las uniones de literales `"business" \| "individual"`, `"national" \| "eu" \| "non_eu"` y `"valid_simulated" \| "unchecked" \| "not_applicable"`, `tax_id: string \| null` y fechas como cadenas; **sin `number` ni `any`**. La entrada suelta sale como `kind: string`, que es lo que se quiere |

**Lo que no se ha comprobado:**
- **`COLLATE "es-x-icu"` en el Supabase de producción** (UE): en el local hay 29 collations ICU; si el despliegue no tuviera `es-x-icu`, la lista se ordena en Python o en la interfaz con `Intl.Collator('es')`.
- **El NIF-IVA fabricado frente a un registro real**: son números sintéticos con dígito de control válido; podrían coincidir por azar con uno real (el seed usa solo nombres inventados).
- **Países con un NIF-IVA especial** (Irlanda con letras finales, Países Bajos con `B`, Suecia con `01`): los valores sintéticos de cada país pasan, pero no se ha probado cada forma distinta que admite la ley de cada Estado.
- **WebKit y Firefox en un ICU más antiguo o más nuevo** que los de esta máquina: los cuatro entornos de aquí nombran los 249, pero otros ICU podrían dejar un código sin nombre; AC-17 lo vigila en el CI.
- **Territorios especiales** (Canarias, Ceuta, Melilla) y **Kosovo**: no se tratan (D-11; `XK` fuera del catálogo).

**Consecuencias para los hitos siguientes** (ya reflejadas en §5.1, §5.2, §5.3, §5.4, AC-07 y el seed):
- **Hito 1.** `COUNTRIES` (249, a mano) y `EU_COUNTRIES` (27) en `limits`; la regla del prefijo con `GR → EL`; `XI`, `XK` y `EU` fuera del catálogo; el texto libre con su clave compacta; tablas de pruebas con los 26 NIF-IVA sintéticos de A.
- **Hito 2.** Restricciones con los nombres de C; `app.update_client` y `app.set_client_archived` comprueban `client_tax_id_taken` **antes** de escribir y la API traduce también el `23505` de `clients_owner_tax_id_active` como red de seguridad; cerrojo por persona; `clients_owner_name` pasa a `(owner_id)` (el orden lo da la consulta); seed con los NIF de A.
- **Hito 3.** Entrada suelta con `StrictBool` en `archived`; salida con literales; lista con `ORDER BY name COLLATE "es-x-icu", id`.
- **Hito 4.** Nombres de país con `Intl.DisplayNames('es')`; el selector se ordena con `localeCompare('es')`; las pruebas no comparan nombres entre motores.

**Seed (sintético) propuesto:** Alicia, «Estudio Norte S.L.» (ES, empresa, `B00000018`), «Kreativ GmbH» (DE, empresa, el NIF-IVA alemán de A) y «Taller Zócalo» (MX, empresa, `MXTEST0001`); Beto, «Café Liebre S.L.» (ES, empresa, `B00000026`), «Atelier Lune SARL» (FR, empresa, el NIF-IVA francés de A) y «Sam Rivers» (US, particular, sin identificador).

### B.2 Hito 1 · dominio puro de clientes · 2026-11-09

**Qué hay.** El paquete `backend/src/cuadre/clients/` (siete módulos, 389 líneas): `limits` (longitudes, patrones, tipos y separadores de la clave libre), `countries` (`COUNTRIES`, 249 códigos, y `EU_COUNTRIES`, 27), `types` (`RawClient`, `ClientValues`, `FieldError`, `ClientResult` y los literales `Scope`, `McpScope`, `Kind`, `ViesStatus`), `scope` (`scope_of`, `to_mcp_scope`, `from_mcp_scope`), `vies` (`ViesChecker` y `FakeViesChecker`), `rules` (`validate_client`, `tax_id_rule`, `vat_prefix`, `MESSAGES`) y `__init__`. Nada de base de datos, red, FastAPI, Pydantic, `stdnum` ni reloj. No cambian migraciones, API, frontend, `contracts/`, `openapi.json` ni `schema.d.ts`.

**Decisiones tomadas al escribirlo** (ya reflejadas en D-01, §5.1 y §5.4):

| Tema | Decisión |
|---|---|
| Dónde viven los países | D-01 decía `cuadre.clients.limits`; son una constante de 249 códigos y van en `countries.py`, que es la única fuente (`limits` guarda lo que repetirá el CHECK). D-01 se corrige |
| El prefijo del NIF-IVA | Un solo hecho en dos sitios: `vat_prefix` usa `PREFIX_ALIASES` de `cuadre.validators.limits` (`GR → EL`) y una prueba cruza `EU_COUNTRIES` (menos España) con `EU_VAT_PREFIXES`, así que si alguien cambia uno sin el otro, falla |
| El identificador no se juzga sin tipo ni país | La regla depende de los dos: si fallan, no se añade un error sobre `tax_id` (coincide con AC-05, que lista nombre, tipo, país y domicilio) |
| Un tipo no texto | Como en el perfil, un número, `bytes`, una lista o un `bool` donde se espera texto es un error **de campo**, nunca una excepción; una prueba recorre 118.800 combinaciones hostiles y nada lanza |
| Clave libre | `[0-9A-Za-z .,/-]` hasta 32; se guarda en mayúsculas y **sin espacios, puntos ni guiones**; la coma y la barra se conservan (como dice §5.1). Una clave que queda vacía al compactar (`"..."`) es el error de formato, no «falta» |
| UE y particular | El identificador libre **no** necesita el prefijo del país: nadie lo valida (se prueba con un NIF-IVA francés en un particular alemán) |
| `validate_client(raw, checker=None)` | El verificador entra por parámetro (por defecto el simulado): es la costura para enchufar el real sin tocar la regla, y una prueba comprueba que solo se le pregunta por una empresa de la UE con NIF-IVA válido y que recibe el país y la clave |
| Un NIF-IVA corto | `RO9573` (el de Rumanía del corpus de SPEC-W-003, 6 caracteres) es válido: la clave de la UE mide de 6 a 14, dentro del CHECK de 1 a 32 |

**Pruebas.** **675 nuevas**: `test_rules.py` (508: los campos y sus fronteras, los 249 países, las seis celdas de la tabla de D-04, los **26 NIF-IVA del corpus de SPEC-W-003 en cada variante** y rechazados con el prefijo de cada uno de los otros 25, Grecia con `GR` y con `EL`, texto libre, todos los errores a la vez y su orden, que los mensajes no repiten lo escrito, idempotencia y la batería hostil), `test_countries.py` (90: 249 distintos, los 43 códigos que ICU nombra pero no son ISO fuera, los 27 de la UE y el cruce con `cuadre.validators`), `test_scope.py` (54), `test_vies.py` (10), `test_limits.py` (5) y `backend/tests/rules/test_clients_boundary.py` (8: el dominio no importa base de datos, red, FastAPI, Pydantic ni `stdnum`, no lee el reloj y cada módulo está declarado). Suite sin RLS: **2.746** (2.071 antes), `ruff check` y `ruff format --check` limpios.

**Mutaciones.** **49**, con un ejecutor desechable fuera del repositorio (método de SPEC-W-005 B.2): longitudes y categorías de texto (M01 a M06), país (sin prefiltro, sin mayúsculas, fuera del catálogo), tipo, cada celda de obligatoriedad de D-04 (M12 a M16), prefijo del NIF-IVA y Grecia, el NIF-IVA que vale como nacional, la clave libre (mayúsculas, separadores, vacía, 33, coma), tipo sin juzgar, orden y solo el primer error, VIES (particular, nacional, verificador ignorado, `unchecked`), ámbito y catálogo (España en la UE, Grecia fuera, Reino Unido dentro, Kosovo, un país menos), el mapeo del MCP y las guardas (`stdnum`, reloj, Pydantic, red y un módulo sin declarar). **48 detectadas y 1 equivalente por diseño**: M19 (quitar la comprobación de que el NIF-IVA es de la UE) no cambia nada porque una clave española empieza por **una** letra como mucho y la comprobación del prefijo de dos letras ya la rechaza; si algún día `normalize_tax_id` devolviera una clave nacional que empieza por un prefijo de la UE, dejaría de ser equivalente. El ejecutor restaura cada archivo y compara su huella (sin avisos).

**Lo que no se ha comprobado:**
- **Paridad con SQL.** Que las longitudes, el patrón del país, el `scope` ⇔ `ES` y el límite de 32 de `limits.py` coincidan con los CHECK de la base es del hito 2 (`test_limits_parity.py`); aquí solo se fijan los valores.
- **La API.** Que la entrada suelta (`str` con `max_length`, `StrictBool` en `archived`) produzca `invalid_client` con estos mensajes es del hito 3.
- **El catálogo frente a ISO.** Los 249 códigos se escribieron a mano y se cruzaron con `Intl.DisplayNames` en el spike y con la lista de ICU de las pruebas; no hay una segunda fuente ISO independiente (no hay paquete instalado).
- **Los textos con una persona.** Se escribieron siguiendo §5.1 y el prototipo, no se han revisado en pantalla.
- **La batería hostil** no entra en las mutaciones (tarda unos 12 s): se ejecutó completa en la suite, no en cada mutante.

**Para el hito 2:**
- `limits.py` fija lo que la base repite: nombre 2–200, domicilio ≤ 300, país `^[A-Z]{2}$`, identificador 1–32, `scope = 'national'` ⇔ `country = 'ES'`, tipos `business | individual` y `valid_simulated | unchecked | not_applicable`; `test_limits_parity.py` los compara con la base.
- El dominio entrega `tax_id` ya en clave compacta y `vies_status` calculado: las funciones `app.*` los reciben tal cual y solo comprueban lo barato y `client_tax_id_taken` **antes** de escribir (B.1-C).
- `scope_of(country)` y el CHECK de la base deben coincidir para `ES`; qué países son de la UE lo decide solo `EU_COUNTRIES` (D-10).

### B.3 Hito 2 · base de datos de los clientes · 2026-11-09

Dos migraciones nuevas (`supabase/migrations/20261109100000` y `…100100`), el seed y la matriz: `…_clients.sql` (los tres tipos, la tabla con sus seis restricciones con nombre y el índice único parcial, RLS forzada, las dos políticas de lectura, `grant select` y los triggers `clients_guard` y `clients_touch_updated_at`) y `…_clients_functions.sql` (los ayudantes `private.clients_enter`, `clients_lock_own`, `clients_tax_id_taken` y `clients_validate`, y `app.create_client`, `app.update_client` y `app.set_client_archived`). `supabase/seed.sql` gana una sección 6 con seis clientes sintéticos, uno de cada ámbito por persona (los propuestos en B.1). `rls_matrix.yaml` gana `clients`. No cambia ninguna ruta: `openapi.json`, `schema.d.ts` y `contracts/` siguen igual.

**Decisiones tomadas al implementar** (completan §5.2, que ya las recoge):

| Tema | Decisión |
|---|---|
| Las funciones reciben texto | `kind`, `scope` y `vies_status` entran como `text` y se validan **antes** de convertirlos: con el tipo enumerado, un valor desconocido sería un `22P02` sin código útil. Cada fallo es `invalid_client` con el campo en el `DETAIL` (`name`, `kind`, `country`, `scope`, `tax_id`, `address`, `vies_status`, `archived`). El orden es el de la pantalla |
| Un CHECK que no estaba | `clients_vies_matches_scope`: `vies_status = 'not_applicable'` **o** (`scope = 'eu'` y `kind = 'business'`). El dominio ya lo cumple; la base lo repite porque es barato y deja fuera un estado absurdo escrito a mano. Se añade a §5.2 y D-10. Admite `unchecked` en una empresa de la UE (lo reserva la consulta real) |
| `client_tax_id_taken` antes de escribir | Lo comprueban `create`, `update` (sin contar la propia fila) y `set_client_archived` al reactivar, con un ayudante (`clients_tax_id_taken`) que mira solo los clientes **activos de la misma persona** y trata el `NULL` como «nada que comparar». El índice parcial queda como red de seguridad (`23505` en `clients_owner_tax_id_active`) |
| Orden de las comprobaciones | `update`: no existe o es ajeno → archivado (`client_archived`, antes de mirar la forma) → forma de los campos → identificador repetido. `set_client_archived`: no existe → indicador nulo → colisión al reactivar |
| Archivar es idempotente | Archivar uno archivado no cambia `archived_at`; reactivar uno activo no hace nada |
| Un solo cerrojo por persona | `private.clients_enter` (rol `usuario` o `42501`, también con la cuenta suspendida) toma `pg_advisory_xact_lock(hashtextextended('clients:' \|\| owner, 0))`; lo toman las tres funciones, también las que no crean (una prueba lo demuestra con un archivado frente a una edición) |
| Trigger | Solo la identidad: `id`, `owner_id` y `created_at` no cambian (`client_immutable_column`). No hay noción de «en uso» (D-08). `updated_at` lo mueve `private.touch_updated_at` |
| Una huella antes y después | **`migration up` y `db reset` dan la misma huella** del esquema (funciones con sus privilegios, políticas, restricciones, triggers, índices, privilegios de tabla, RLS, enums y columnas de `public`, `app` y `private`): lo que en SPEC-W-005 B.3 no pudo comprobarse. El `reset` borra la base local: se pararon antes mi API y mi web |

**Pruebas.** **173 nuevas en `backend/tests/rls/`** (RLS pasa de 922 a **1.095**; el resto del backend, 2.746, no cambia): `test_clients.py` (134: nadie escribe directo —dueño, gestor, administrador y los demás—, los privilegios y las dos únicas políticas, cada CHECK por el nombre de su restricción con los valores de B.1, el índice parcial en todas sus formas incluida la reactivación que choca, el trigger, cada función con sus errores y su campo, los roles y la cuenta suspendida, ajeno = no existe, la visibilidad por rol y por **los cinco estados del vínculo**, que no escriben en `activity_log`, que las funciones son `SECURITY DEFINER` con `search_path` vacío y solo las de `app` llegan a `authenticated`, y **cuatro pruebas de concurrencia con hilos**: dos altas con el mismo NIF, un alta frente a una reactivación, que el cerrojo es por persona y que lo toman también las funciones que no crean), `test_clients_limits_parity.py` (20: las fronteras salen de `cuadre.clients.limits` y se comprueban contra los CHECK, **los 249 países se aceptan con el ámbito que deduce el dominio**, `ES` es el único `national`, la base no sabe qué países son de la UE y los tres enums son exactamente los tipos del dominio), `test_clients_seed.py` (5: el seed pasa `validate_client` y guardarlo por el dominio no cambia nada) y 14 que la matriz añade sola para la tabla nueva. `ruff check` y `ruff format --check` limpios.

**Mutaciones.** **70**, con un ejecutor desechable fuera del repositorio (método de B.3 de SPEC-W-005: funciones reescritas desde `pg_get_functiondef`, políticas, restricciones, índices, triggers y privilegios rotos a propósito, y una **huella** del esquema comparada tras restaurar cada una): ayudantes y cerrojo (F01 a F08, incluida la retirada del cerrojo y su clave global), validación (F09 a F18), `create` (F19 a F24), `update` (F25 a F32), `set_client_archived` (F33 a F37), trigger (T01 a T05), privilegios de las funciones (G01 a G04), políticas, privilegios y RLS (P01 a P06, R01 a R08) y las seis CHECK, el índice, su variante con archivados, su variante sin el dueño y la cascada (C01 a C10). **68 detectadas y 2 equivalentes por diseño.** La primera pasada dejó **4 supervivientes**; dos eran huecos de mis pruebas y se cerraron: **F14 y F18** (un ámbito o un estado de VIES desconocido solo lo frenaba por casualidad otra comprobación cuando los demás campos no encajaban; ahora una prueba los manda con todo lo demás correcto). Los equivalentes: **F08** (`tax_id_taken` sin el `is not null`: con `NULL`, `c.tax_id = NULL` ya no es verdadero y el `exists` da falso) y **F36** (reactivar sin mirar que estaba archivado: un cliente activo no puede chocar consigo mismo porque el ayudante excluye su fila, y el índice impide que haya otro activo con ese NIF). No se mutó el enum con una etiqueta de más: PostgreSQL no permite quitar una etiqueta una vez añadida; una prueba compara las etiquetas exactas.

**Lo que no se ha comprobado:**
- **El `COLLATE "es-x-icu"` de la lista** en el Supabase de producción (B.1): la consulta de listado es del hito 3.
- **El borrado real de una cuenta** con clientes: se comprueba que la clave a `profiles` es `ON DELETE CASCADE`, no se borra una cuenta (el borrado y la exportación son de SPEC-W-017, CONF-004).
- **El tiempo de espera del cerrojo** con muchas peticiones a la vez, ni el **rendimiento** de las políticas con volumen: las pruebas usan dos hilos y un segundo de espera, y hay decenas de clientes por persona.
- **La suite completa corriendo en el CI**: no se ve desde aquí.

**Para el hito 3** (API):
- **Funciones → rutas.** Las tres reciben texto, en este orden: `create_client(p_name, p_kind, p_country, p_scope, p_tax_id, p_address, p_vies_status)` devuelve el id; `update_client(p_id, …los mismos siete)` y `set_client_archived(p_id, p_archived)` no devuelven nada y la ruta relee la fila. La API calcula antes el ámbito, la clave del NIF y el VIES con `cuadre.clients` y pasa los valores ya normalizados.
- **Traducción de errores.** `P0001` por el mensaje: `client_not_found` → 404 (también si es ajeno), `client_archived` y `client_tax_id_taken` → 409, `invalid_client` → error **interno** (la API valida antes con el dominio; llegar aquí es un fallo de construcción), `client_immutable_column` → error interno. `42501` → 403. `23505` con `constraint_name = clients_owner_tax_id_active` → `client_tax_id_taken` (red de seguridad). `23514` y `22P02` solo aparecen si la validación falló antes: error interno.
- **Lecturas.** `list_clients` lee `public.clients where owner_id = (select auth.uid())`, sin los archivados salvo `include_archived`, `ORDER BY name COLLATE "es-x-icu", id`; `archived` es `archived_at IS NOT NULL`. Una lectura no escribe.
- **Seed y E2E.** Las cuentas del seed (Alicia y Beto) ya tienen clientes: las pruebas de E2E del hito 5 usan una cuenta propia del worker y la **archivan** al empezar y al terminar (T6-10).

### B.4 Hito 3 · API de los clientes · 2026-11-09

**Qué hay.** Las cinco rutas de §5.3 en `api/routes_clients.py` (solo `usuario`: `require_role_detached`) y los módulos con base de datos de `cuadre.clients`: `errors`, `models`, `repository` y `service`, declarados como no puros en `test_clients_boundary.py`. `main.py` guarda el verificador de VIES en `app.state.vies_checker` (el simulado) y monta el router. `backend/openapi.json` y `frontend/src/api/schema.d.ts` se regeneraron con sus scripts. No hay frontend ni migraciones nuevas.

**Decisiones tomadas al implementar** (completan §5.3 y §5.4):

| Tema | Decisión |
|---|---|
| El dominio valida, la base repite | `create` y `update` validan con `validate_client` **antes** de tocar la base y devuelven todos los errores a la vez en `fields` (`invalid_client`); la función `app.*` solo recibe valores ya normalizados y, si aun así respondiera `invalid_client`, sería un fallo de construcción: **500 sin detalles**, no un 422 |
| El ámbito y el VIES no se envían | `ClientInput` no tiene `scope`, `vies_status`, `id` ni `archived`: con `extra="forbid"` enviarlos es un `validation_error`. Los calcula el dominio |
| Entrada suelta, salida tipada | Todos los campos de `ClientInput` son opcionales (`str \| None` con `max_length`): una petición vacía da los tres errores de campo (`name`, `kind`, `country`) y no un error de forma. `Client` lleva las uniones de literales y el cliente TypeScript no tiene `number` ni `any` |
| `archived` es booleano de verdad | `StrictBool`: `"yes"`, `"true"`, `1`, `0`, `null`, `[]` y `{}` son un `validation_error` y no cambian nada |
| Traducción de errores | `P0001` por el mensaje: `client_not_found` 404 (también si es ajeno), `client_archived` y `client_tax_id_taken` 409; `42501` → 403 `forbidden`; `23505` de `clients_owner_tax_id_active` → `client_tax_id_taken` (red de seguridad); `invalid_client`, `client_immutable_column`, `23514` y `22P02` se propagan |
| Orden de la lista | `ORDER BY name COLLATE "es-x-icu", id`: la ñ después de la n y los acentos como desempate (B.1-C) |
| Una lectura no escribe | `list_clients` y `get_client` solo leen (una prueba compara `updated_at` y las filas antes y después) |
| El servicio usa el verificador de la app | `ClientService(pool, checker)` lo recibe de `app.state`; una prueba lo sustituye por un espía y comprueba que solo se le pregunta por una empresa de la UE con NIF-IVA válido, que se le vuelve a preguntar al editar, que archivar no lo llama y que lo que devuelve (`unchecked`) es lo que se guarda |

**Pruebas.** **117 nuevas** (el dominio, 675, no cambia): `test_clients_api.py` (69: un cliente de cada ámbito, normalización, Grecia con `GR` y con `EL`, la tabla de países, cada error de NIF, todos los errores a la vez y su orden, los campos que no se pueden enviar, el NIF único entre activos y no entre archivados ni personas, editar con cambio de ámbito, editar archivado o ajeno, archivar y reactivar con colisión, `archived` estricto, que no hay `DELETE`, que una lectura no escribe y la forma del cliente), `test_listing.py` (6), `test_roles.py` (19: gestor y administrador `403` en las cinco rutas, sin sesión `401`, ajeno = no existe, cuenta suspendida), `test_concurrency.py` (4: cinco altas a la vez con el mismo NIF dan un `201` y cuatro `409`, nunca un 500; alta frente a reactivación), `test_vies_wiring.py` (5), `test_no_sensitive_logs.py` (1: ni nombre, ni NIF, ni domicilio de un cliente en los registros ni en el cuerpo de ningún error, con el flujo completo), `test_error_mapping.py` (13: la traducción con errores reales de PostgreSQL) y una guarda más en `test_clients_boundary.py`. Suite sin RLS: **2.864**; RLS, 1.095 sin cambios; `ruff`, `export_openapi --check`, `gen:api --check` y el `typecheck` del frontend verdes.

**Mutaciones.** **30**, con un ejecutor desechable fuera del repositorio (método de B.4 de SPEC-W-005): validación (errores sin devolver, solo el primero, al revés), el verificador ignorado, el listado (archivados invertidos, sin la collation, sin filtrar por dueño), `archived` al revés, cada traducción de error (cinco), el orden de los campos al guardar, el indicador de archivar invertido, la ruta abierta a otros roles, `extra="allow"`, `bool` normal, el alta con 200, el verificador de la app, una lectura que escribe, los errores sin traducir, el nombre en los registros, editar sin releer, el ámbito tomado de otro sitio, el borrado, y las guardas (`stdnum`, red y un módulo sin declarar). **28 detectadas y 2 equivalentes por diseño**: **S07** y **S08** (`get_client` y el listado sin filtrar por dueño): la RLS ya limita las filas al dueño y los filtros del SQL son defensa en profundidad. La primera pasada dejó **5 supervivientes**; dos eran huecos de mis pruebas y se cerraron: **S25** (con un solo cliente, devolver «el primero» pasaba por el editado: ahora hay dos y se edita el segundo) y **S28** (la guarda de red solo miraba los módulos puros: ahora mira todo el paquete); S27 fue un mutante mal escrito por mí (no cambiaba nada) y, reescrito, se detecta.

**Comprobación a mano** con la API real y los tokens de GoTrue de Alicia y Gina (cuentas del seed): la lista trae sus tres clientes sintéticos con su ámbito y su VIES; un NIF malo da `422` con `fields` en `tax_id`; un cuerpo con todo mal enumera `name`, `kind` y `country`; un alta en Grecia con `gr` y `EL…` da `eu` y `valid_simulated`; repetir el NIF con el prefijo `GR` da `409`; archivar libera el NIF y reactivar con colisión da `409`; la gestora recibe `403`. La comprobación dejó dos clientes de prueba en la cuenta local de Alicia (el siguiente `db reset` los quita).

**Lo que no se ha comprobado:**
- **`COLLATE "es-x-icu"` en el Supabase de producción** (B.1): si el despliegue no tuviera esa collation, el listado fallaría con un 500. Habría que ordenar en Python o en la interfaz con `Intl.Collator('es')`.
- **El navegador**: ni CORS ni la pantalla; son del hito 4.
- **Los tiempos de espera del cerrojo** con muchas peticiones a la vez: la prueba usa cinco hilos.
- **El CI**: no se ve desde aquí.

**Para el hito 4** (frontend):
- **Lecturas y escrituras.** `list_clients` (con `include_archived`), `get_client`, `create_client`, `update_client` y `set_client_archived`; la lista llega ya ordenada.
- **Errores de campo.** `invalid_client` trae `fields: [{ field, message }]` con `name`, `kind`, `country`, `tax_id` o `address`, **todos a la vez y en el orden de la pantalla**: se pintan junto a cada campo y en el resumen que recibe el foco. `409 client_tax_id_taken` se pinta junto al NIF; `409 client_archived` y `404` son errores generales.
- **Lo que muestra la pantalla.** `scope` (`national`, `eu`, `non_eu`) y `vies_status` (`valid_simulated`, `unchecked`, `not_applicable`) vienen calculados: la interfaz los muestra con texto y no valida nada fiscal. El rótulo del identificador cambia según el país (NIF, NIF-IVA, identificador fiscal) y el nombre del país sale de `Intl.DisplayNames('es')`.
- **`describeProblem`** (`lib/problems.ts`) debe aceptar `fields` de `invalid_client` con los campos del cliente de una lista cerrada, como hizo con `invalid_profile`.
