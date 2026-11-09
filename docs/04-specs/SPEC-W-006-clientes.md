---
tipo: spec
id: SPEC-W-006
titulo: Clientes: NIF, ámbito y VIES simulado
estado: propuesta
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
| D-01 | **Decidida.** País en **ISO 3166-1 alfa-2 completo** (~250 códigos); el ámbito se deduce: `national` si `ES`, `eu` si es otro Estado miembro, `non_eu` el resto. La constante (`COUNTRIES`, `EU_COUNTRIES`) vive en `cuadre.clients.limits`, sin `pycountry`; los **nombres en español los pone el frontend** con `Intl.DisplayNames('es')` | Catálogo corto (UE y media docena de países): menos superficie, pero deja fuera a quien factura a otro país. Pasar de corto a completo es ampliar una constante y su CHECK |
| D-02 | **Enum del ámbito** `national \| eu \| non_eu` (tipo `public.client_scope`). El MCP de SPEC-W-011 usa `nacional \| ue \| fuera_ue`: un **solo módulo de mapeo** (`cuadre.clients.scope`). `public.supplier_scope` (`national \| eu`, de los gastos) **no se toca** | Reutilizar `supplier_scope` añadiéndole un valor: toca una tabla con datos y dos specs ya hechas |
| D-03 | **Tipo** `business` (empresa o profesional) o `individual` (particular). Los valores van en inglés; la pantalla los llama «Empresa o profesional» y «Particular» | Más tipos (administración pública, asociación): no hay regla fiscal que los distinga en la v1 |
| D-04 | **El NIF depende del ámbito y del tipo** (§5.1): nacional y empresa → NIF, NIE o CIF español **obligatorio y válido**; nacional y particular → opcional, pero si se escribe, válido; UE y empresa → NIF-IVA **obligatorio, válido y del país elegido** (Grecia: país `GR`, prefijo `EL`); UE y particular, y fuera de la UE y particular → opcional, texto libre; fuera de la UE y empresa → identificador fiscal **obligatorio**, texto libre. Se guarda **normalizado** (clave compacta) | Exigirlo siempre: bloquea facturar a un particular sin NIF. No validarlo: un NIF-IVA mal escrito pasa a la factura y a la declaración de operaciones intracomunitarias |
| D-05 | **Decidida.** **VIES simulado, sin red**: una empresa de la UE con NIF-IVA que pasa el control queda `valid_simulated` («Válido (simulado)»); `unchecked` («Sin comprobar») queda **reservado** para cuando exista la consulta real y VIES no responda (con el simulado no se produce, porque el NIF-IVA de una empresa de la UE es obligatorio); el resto, `not_applicable` («No aplica»). Se calcula **al guardar** y se guarda. Un puerto `ViesChecker` con `FakeViesChecker` determinista deja enchufar el real después (Should: fuera de la v1) | Mostrar siempre «Sin comprobar» hasta tener la consulta real: más honesto, pero la pantalla pierde el distintivo del prototipo. Llamar ya a VIES: red y dependencia nuevas |
| D-06 | **Archivar, no borrar** (`archived_at`): las facturas emitidas (W-007) referenciarán al cliente y son inmutables (RES-03, CONF-004). Un archivado no se ofrece para facturar, no se puede editar y se reactiva (`client_archived` 409 al editarlo) | Borrado físico: rompe las facturas. Editable aun archivado: una ficha «muerta» que cambia sin que nadie la vea |
| D-07 | **Un NIF por persona entre los clientes activos**: dos con la misma clave fiscal son el error `client_tax_id_taken` (409); los archivados no cuentan. Reactivar uno cuyo NIF ya usa un activo da el mismo error | Permitir repetidos: dos fichas del mismo cliente con series de facturas separadas |
| D-08 | **Todo es editable** (mientras esté activo): la factura (W-007) congela una **copia** de los datos del cliente al emitirse, así que cambiar país o tipo solo afecta a las facturas futuras; no hay noción de «en uso» | Bloquear país y tipo si hay facturas: obliga a duplicar fichas ante un error de alta |
| D-09 | Las escrituras van **solo por funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`, rol `usuario`, cerrojo asesor por persona); `authenticated` solo `SELECT` | Escritura directa con política `owner_id = auth.uid()`: sin cerrojo, dos altas a la vez con el mismo NIF dan un 23505 sin código útil |
| D-10 | **La validación fiscal vive en Python** (`cuadre.clients`); la base defiende solo lo barato (longitudes, `country ~ '^[A-Z]{2}$'`, `scope = 'national'` ⇔ `country = 'ES'`, tipos enumerados). **No** valida el NIF en SQL; un test de **paridad** compara las constantes | Validar también en SQL: dos fuentes de una regla (como en SPEC-W-005, D-14) |
| D-11 | **Fuera de esta spec:** la columna «Facturado en {año}», el texto de condiciones de la factura (`invoice_terms`: IVA, retención y mención) y los **territorios especiales** de España (Canarias, Ceuta, Melilla: `ES` se trata como nacional; pregunta abierta para W-007 y W-008) | Incluirlos aquí: necesita facturas que todavía no existen |
| D-12 | **Gestor y administrador no tienen pantalla de clientes.** El gestor lee por RLS con vínculo activo (su pantalla es SPEC-W-010); el administrador, nada (D3) | Pantalla de solo lectura del gestor aquí: W-010 la diseña con el resto de su cartera |

*Pendiente del visto bueno de la persona: D-02 a D-04 y D-06 a D-12. Con él, la spec pasa a `en-progreso` y se prepara el hito 0.*

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

**Ámbito** (`scope`, **no lo envía la persona**): `national` si `country = "ES"`; `eu` si `country` está en `EU_COUNTRIES` y no es `ES`; `non_eu` en cualquier otro caso. `EU_COUNTRIES` son los 27 Estados miembros (`AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK`); `GB`, `CH`, `XI` y el resto son `non_eu`.

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
UNIQUE INDEX clients_owner_tax_id_active ON clients (owner_id, tax_id) WHERE tax_id IS NOT NULL AND archived_at IS NULL
INDEX clients_owner_name ON clients (owner_id, lower(name))
```

Las restricciones llevan nombre propio para que la API las traduzca por nombre. Trigger `clients_guard` (`BEFORE UPDATE`): `owner_id` y `created_at` no cambian (`client_immutable_column`); `updated_at` lo mantiene `private.touch_updated_at`.

**Privilegios.** `authenticated`: `SELECT` y nada más; toda escritura por funciones.

| Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|
| SELECT | los suyos, archivados incluidos | los de usuarios con vínculo activo (`private.gestor_has_access(owner_id)`) | **ninguno** |
| INSERT / UPDATE / DELETE | denegado (solo `app.*`) | denegado | denegado |

**Funciones `app.*`** (`SECURITY DEFINER`, `search_path = ''`; verifican `auth.uid()` y `private.app_role() = 'usuario'`; `P0001` con código estable, `42501` si el rol no basta). Todas toman primero el cerrojo asesor por persona con un ayudante `private.clients_enter()` (como `private.series_enter()`):

| Función | Efecto |
|---|---|
| `app.create_client(p_name, p_kind, p_country, p_scope, p_tax_id, p_address, p_vies_status)` | Comprueba lo barato (`invalid_client`, campo en el `DETAIL`) y que `p_scope` es coherente con el país; `client_tax_id_taken` si ya hay un activo con esa clave. Devuelve el id |
| `app.update_client(p_id, …)` | Sustituye todos los campos de un cliente **activo** (`client_not_found` si no existe o es ajeno; `client_archived` si está archivado; `client_tax_id_taken`) |
| `app.set_client_archived(p_id, p_archived)` | Archiva o reactiva. Reactivar uno cuyo NIF ya usa un activo da `client_tax_id_taken` |

Ninguna escribe `activity_log`. Los errores `P0001` son `client_not_found`, `client_archived`, `client_tax_id_taken` e `invalid_client`.

**Matriz de RLS.** `clients`: `kind: financial`, `owner_column: owner_id`, privilegios `SELECT`, y un `seed` con clientes de los tres ámbitos por persona.

**Seed (sintético).** Dos o tres clientes por persona: uno nacional (empresa, con CIF válido), uno de la UE (empresa, con NIF-IVA alemán o francés válido) y uno fuera de la UE (empresa o particular); nombres y NIF inventados con dígitos de control válidos (los fija el hito 0). Ningún dato real (RES-07).

### 5.3 API HTTP

Todas exigen `Authorization: Bearer` y rol `usuario` (`forbidden` 403 para gestor y administrador); errores en `application/problem+json`.

| `operation_id` | Método y ruta | Cuerpo / respuesta |
|---|---|---|
| `list_clients` | `GET /api/clients` | Query `include_archived` (bool, por defecto `false`). **200** `[Client]` por nombre (sin distinguir mayúsculas ni acentos) |
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
  Given los códigos "ES", "DE", "GR", "GB", "CH", "XI" y "MX"
  When se crea un cliente en cada país
  Then el ámbito es "national", "eu", "eu", "non_eu", "non_eu", "non_eu" y "non_eu"
    And un cliente de Grecia exige un NIF-IVA con prefijo "EL"
    And un país que no es un código alfa-2 de la lista da 422

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
  Then todos tienen nombre en español en los tres motores, y el selector se ordena por nombre

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
1. **Dominio puro** (`cuadre.clients`): campos, ámbito, regla del NIF, VIES simulado, mapeo del MCP, `limits`, `test_clients_boundary`, con tablas de pruebas y mutaciones.
2. **Base de datos**: tipos, tabla con trigger y funciones, matriz de RLS, seed y pruebas de RLS, con mutaciones.
3. **API**: `cuadre.clients` (servicio y repositorio), las cinco rutas, `openapi.json` y `schema.d.ts` regenerados, con mutaciones.
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
