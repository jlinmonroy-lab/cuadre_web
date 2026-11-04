---
tipo: spec
id: SPEC-W-001
titulo: Base del monorepo, autenticación con tres roles y RLS probada
estado: en-progreso
prioridad: must
riesgo: alto
historias: [US-004]
requisitos: [RF-001, RF-002]
nfr: [NFR-06]
restricciones: [RES-02, RES-07, RES-08]
adr: [0001, 0002, 0003, 0004, 0005, 0009, 0010, 0011]
depende_de: []
bloquea: [SPEC-W-002, SPEC-W-004, SPEC-W-005, SPEC-W-010, SPEC-W-015]
fecha: 2026-11-03
---

# SPEC-W-001 · Base del monorepo, autenticación con tres roles y RLS probada

> Primera spec de `cuadre-web`. Todo lo demás depende de ella: sin un esqueleto que arranque, sin identidad y sin una
> demostración ejecutable de que cada rol ve solo lo suyo, ninguna spec posterior puede dar datos fiscales por buenos.

## 1. Contexto

**Situación de partida.** El repositorio contiene el charter, el PRD y el prototipo `docs/cuadre-interfaz.html`. No hay
código, ni base de datos, ni autenticación. El entorno virtual de Python (`.venv/`), los contratos con cuadre-agents
(`contracts/`) y los ADRs 0001–0014 ya existen (sesión de arranque).

**Por qué esta spec es la primera.** R-04 (fuga de datos entre usuarios o acceso indebido de un gestor o del administrador)
es un riesgo de impacto alto, y NFR-06 lo convierte en una puerta de despliegue: 0 accesos indebidos para usuario, gestor
(también tras revocar) y administrador. Las demás specs añaden tablas; esta fija el patrón de seguridad que todas
repiten y el test que lo vigila.

**Decisiones de producto vigentes** (no se reabren aquí):

- **CONF-001 opción (a).** En esta versión el gestor consulta, revisa y descarga; no escribe en la contabilidad del
  usuario. «Revisa» se materializa en anotaciones en una tabla aparte (`gestor_notes`, SPEC-W-010) que el usuario ve.
- **D1.** El registro libre crea siempre `usuario`. El administrador da de alta o promueve a los gestores. El usuario
  invita por correo a un gestor ya existente y el gestor acepta dentro de la aplicación.
- **D3.** El administrador no tiene acceso a ningún dato financiero. Solo ve metadatos de cuenta.
- **D4.** El servicio de agentes recibe un token derivado y acotado; no afecta a esta spec, pero condiciona que la base
  de datos admita lecturas con identidad de usuario (ADR-0003, ADR-0013).

**Entradas de diseño.** Charter §4 (roles), PRD US-004, RF-001, RF-002, RF-003, NFR-06, R-04; ADR-0003 a 0005; prototipo
(tokens de diseño y navegación).

## 2. Objetivo

Al terminar esta spec:

1. Una persona puede **registrarse, iniciar sesión, cerrar sesión y recuperar su contraseña** (RF-001), y el sistema le
   asigna el rol `usuario`, un perfil de negocio vacío y un registro de actividad.
2. La aplicación distingue **tres roles** y cada uno aterriza en su portada: `usuario` en `/inicio`, `gestor` en
   `/cartera`, `admin` en `/admin`.
3. Una batería de tests ejecutable (`test_rls_roles`) demuestra **0 accesos indebidos** entre usuario, gestor (con vínculo
   activo, pendiente, revocado y sin vínculo) y administrador sobre las cuatro tablas de la spec, y una guardia impide
   que una tabla futura entre en `public` sin RLS ni registro.
4. Cada parte del monorepo **arranca con un comando** y el CI ejecuta lo anterior.

El valor entregable es la **confianza demostrada** en el aislamiento. La interfaz de esta spec es deliberadamente mínima.

## 3. Alcance explícito

### 3.1 Esqueleto y herramientas
- Archivos de raíz: `README.md`, `package.json` (CLI de Supabase y scripts), `scripts/` (clave de firma local y generador de entornos),
  `.github/workflows/ci.yml` y `.github/actions/` (acciones compuestas); `CLAUDE.md`,
  `.gitignore`, `.env.example` y `.editorconfig` ya existen y se ajustan si hace falta.
- `backend/` con `pyproject.toml` (extra `dev`, versiones fijadas, `contracts/python` como dependencia local) y el paquete
  `backend/src/cuadre/` descrito en §5.6.
- `frontend/` creado con `create-next-app` (App Router, TypeScript estricto, Tailwind v4, ESLint), `shadcn/ui` inicializado,
  `@supabase/ssr`, `openapi-typescript`, `openapi-fetch` y Playwright configurado.
- `supabase/` con `config.toml` y migraciones (§5.2).

### 3.2 Base de datos (migraciones SQL en `supabase/migrations/`)
- Tipos enumerados, esquemas `private` y `app`.
- Tablas `profiles`, `business_profiles`, `gestor_access` y `activity_log` con RLS activada y forzada.
- Funciones auxiliares de las políticas (`private.*`) y funciones de negocio invocables por el backend (`app.*`):
  aceptar, rechazar y revocar un acceso de gestor; cambiar rol y estado de una cuenta.
- Triggers: alta de perfil al crear un usuario en `auth.users`, sincronización del correo, `updated_at` y
  `activity_log` de solo inserción.
- Roles de login `cuadre_app` y `cuadre_jobs` (ADR-0003).
- `supabase/seed.sql` con cinco usuarios sintéticos que pueden iniciar sesión (§5.2.6).

### 3.3 Backend (FastAPI)
- `create_app()`, configuración por entorno, CORS limitado a `FRONTEND_ORIGIN`, identificador de petición, registro
  estructurado sin datos personales.
- Validación del JWT de Supabase (JWKS), `CurrentUser`, `require_role(...)` y bloqueo de cuentas suspendidas.
- Módulo `cuadre.db.session`: transacción por petición con la identidad del usuario (ADR-0003).
- Errores `application/problem+json` en español con `code` estable.
- Rutas `GET /healthz` (`get_health`) y `GET /api/me` (`get_me`).
- `backend/scripts/export_openapi.py` (con `--check`) y `backend/openapi.json` versionado.
- `cuadre.cli create-admin` para crear el primer administrador.

### 3.4 Frontend (Next.js)
- Páginas de autenticación: `/login`, `/registro`, `/recuperar`, `/restablecer`.
- Proxy (`src/proxy.ts`: en Next.js 16 el «middleware» se llama «proxy») y *layouts* con protección por rol, redirección a la portada de cada rol y página 403.
- Layout autenticado con la navegación del prototipo (barra lateral en escritorio, barra superior desplazable en móvil),
  tokens de diseño del prototipo en el tema de Tailwind y fuentes con `next/font`.
- Portadas mínimas `/inicio`, `/cartera` y `/admin` con el nombre de la persona, su rol y las secciones futuras
  desactivadas («Próximamente»).
- Cliente de API generado (`src/api/schema.d.ts`) y un cliente `openapi-fetch` que añade el `Bearer` de la sesión.

### 3.5 Pruebas y CI
- Todos los tests de §8, incluidas las guardas de reglas del proyecto (sin `float`, sin SDK de modelos, service key
  acotada, acceso a base de datos acotado, Data API desactivada).
- Workflow de CI con los trabajos de §8.

## 4. Alcance excluido

| Queda fuera | Va a |
|---|---|
| Rutas HTTP y pantallas para **invitar, aceptar, rechazar y revocar** un gestor, cartera con datos, anotaciones del gestor y registro de las lecturas del gestor | SPEC-W-010 (en esta spec solo existen las funciones SQL y se prueban a nivel de base de datos) |
| CRUD y pantalla del perfil del negocio, series de facturación | SPEC-W-005 |
| Pantallas del administrador (listar cuentas, cambiar roles, base de conocimiento) | SPEC-W-015 (aquí solo las funciones SQL `app.admin_set_*`) |
| Cualquier tabla financiera distinta de `business_profiles` (clientes, facturas, gastos, documentos…) | SPEC-W-002 y siguientes |
| Storage, cliente de agentes, chat y MCP | SPEC-W-002, 004 y 011 |
| Correos propios (invitaciones, recordatorios); solo se usan los de Auth de Supabase | SPEC-W-010 y 014 |
| Autenticación de segundo factor, inicio de sesión social, SSO | Fuera de la v1 |
| Despliegue, dominios, monitorización | ADR-0014 (propuesto) |
| Exportación de datos y cierre de cuenta (RGPD) | SPEC-W-017, bloqueada por CONF-004 |
| Cifrado en reposo del IBAN | Pregunta abierta |
| Acceso de soporte del administrador con consentimiento | Fuera de la v1 (D3) |

## 5. Contrato de interfaces

### 5.1 API HTTP

| `operation_id` | Método y ruta | Auth | Respuesta 200 |
|---|---|---|---|
| `get_health` | `GET /healthz` | Pública | `{ "status": "ok", "version": "<semver>" }` |
| `get_me` | `GET /api/me` | Bearer, cualquier rol activo | `{ "id": uuid, "email": string, "display_name": string, "role": "usuario"\|"gestor"\|"admin", "status": "active" }` |

**Cabeceras.** Toda respuesta incluye `X-Request-Id` (se reutiliza el de la petición si viene). CORS permite solo el origen
`FRONTEND_ORIGIN`, los métodos `GET, POST, PUT, PATCH, DELETE, OPTIONS` y las cabeceras `Authorization, Content-Type,
X-Request-Id`; no usa cookies.

**Errores** (`Content-Type: application/problem+json`):

```json
{ "type": "about:blank", "title": "No autenticado", "status": 401, "code": "unauthenticated",
  "detail": "Tu sesión no es válida o ha caducado. Inicia sesión de nuevo.", "request_id": "..." }
```

| `code` | HTTP | Cuándo |
|---|---|---|
| `unauthenticated` | 401 | Sin `Authorization`, token mal formado, caducado, firma o algoritmo inválidos, `iss` o `aud` incorrectos |
| `forbidden` | 403 | El rol no está permitido en la ruta |
| `account_suspended` | 403 | La cuenta existe pero `status = 'suspended'` |
| `profile_missing` | 403 | Token válido sin fila en `profiles` (no debería ocurrir; se registra como incidencia) |
| `validation_error` | 422 | Cuerpo o parámetros inválidos, con `errors: [{loc, msg}]` |
| `not_found` | 404 | Ruta o recurso inexistente (o inaccesible por RLS: no se distingue) |
| `method_not_allowed` | 405 | Método HTTP no admitido en la ruta (lleva la cabecera `Allow`) |
| `http_error` | otro 4xx | Cualquier otro error HTTP de Starlette no previsto arriba |
| `internal_error` | 500 | Cualquier otro; `detail` genérico y sin trazas. Lleva `X-Request-Id` y las cabeceras de CORS |
| `auth_unavailable` | 503 | No se puede alcanzar el JWKS de Supabase para verificar el token (lleva `Retry-After`) |
| `database_busy` | 503 | El pool de conexiones está saturado: esperar una conexión más de 5 s (lleva `Retry-After`) |

El cuerpo es siempre `{type, title, status, code, detail, request_id}`; `validation_error` añade `errors: [{loc, msg}]` **sin el dato
enviado** (`input`), que podría ser sensible. Los errores de FastAPI (404/405/422) se convierten a este formato.

**Autenticación del backend.**

1. Se lee `Authorization: Bearer <jwt>`.
2. Se verifica con `PyJWT`: firma contra el JWKS de `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (con caché), algoritmos
   `ES256` y `RS256` únicamente; `aud = "authenticated"`; `iss = {SUPABASE_URL}/auth/v1`; `exp` y `nbf`. `alg: none` se
   rechaza. **No existe camino HS256.** Comprobado el 2026-11-03 con la CLI 3.0: con `[auth] signing_keys_path` apuntando
   a una clave ES256 de desarrollo (`supabase/signing_keys.json`, generada con `npm run gen:signing-key`, gitignorada; el CI la
   genera antes de `supabase start`), la pila local firma con ES256, su JWKS publica esa clave y los tokens llevan
   `iss = http://127.0.0.1:54321/auth/v1` y `aud = authenticated`. Es el mismo camino que usa producción.
3. Se construye `CurrentUser(id, email, display_name, role, status, claims)` leyendo `profiles` **dentro de la transacción del
   usuario** (el rol sale de la base de datos, no del token; ADR-0005). Esa transacción la abre la dependencia `get_tx` con
   `Depends(get_tx, scope="function")`: se confirma **antes** de enviar la respuesta, de modo que un fallo de commit llega al
   cliente como un 500 en vez de un 200 falso (test `test_the_transaction_is_committed_before_the_response_is_sent`).
4. `require_role(*roles)` devuelve 403 `forbidden` si el rol no está en la lista; cualquier ruta autenticada devuelve 403
   `account_suspended` si la cuenta no está activa.

### 5.2 Base de datos

Todo en migraciones; el nombre sigue `YYYYMMDDHHMMSS_descripcion.sql`; sin migraciones destructivas.

#### 5.2.1 Tipos y esquemas

```
CREATE SCHEMA private;  -- auxiliares de políticas; sin acceso de lectura directa
CREATE SCHEMA app;      -- funciones que invoca el backend

CREATE TYPE user_role             AS ENUM ('usuario', 'gestor', 'admin');
CREATE TYPE account_status        AS ENUM ('active', 'suspended');
CREATE TYPE gestor_access_status  AS ENUM ('pending', 'active', 'revoked', 'declined');
CREATE TYPE activity_category     AS ENUM ('access', 'account', 'data');
```

**Correos: `text` en minúsculas con `CHECK (email = lower(email))`, no `citext`.** Las funciones `SECURITY DEFINER` fijan
`search_path = ''` (ADR-0005) y, sin el esquema de la extensión en la ruta, el operador `=` de `citext` no se resuelve: PostgreSQL cae en
silencio a `text = text`, que distingue mayúsculas. Normalizar a minúsculas en la entrada (el trigger de alta lo hace; el backend lo hará
al invitar) evita esa trampa sin depender de la ruta de búsqueda.

#### 5.2.2 Tablas

```
profiles
  id           uuid PK  REFERENCES auth.users(id) ON DELETE CASCADE
  email        text     NOT NULL UNIQUE CHECK (email = lower(email))
  display_name text     NOT NULL DEFAULT ''
  role         user_role       NOT NULL DEFAULT 'usuario'
  status       account_status  NOT NULL DEFAULT 'active'
  created_at   timestamptz NOT NULL DEFAULT now()
  updated_at   timestamptz NOT NULL DEFAULT now()

business_profiles                                   -- tabla «canario» financiera de NFR-06
  owner_id     uuid PK  REFERENCES profiles(id) ON DELETE CASCADE
  legal_name text, tax_id text, fiscal_address text, activity text, iae_epigraph text,
  activity_start_date date, vat_regime text NOT NULL DEFAULT 'general',
  irpf_rate numeric(5,2) CHECK (irpf_rate BETWEEN 0 AND 100),
  logo_path text, iban text,
  home_pct numeric(5,2) CHECK (home_pct BETWEEN 0 AND 100),
  updated_at timestamptz NOT NULL DEFAULT now()

gestor_access
  id            uuid PK DEFAULT gen_random_uuid()
  owner_id      uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE
  gestor_email  text NOT NULL CHECK (gestor_email = lower(gestor_email))
  gestor_id     uuid REFERENCES profiles(id) ON DELETE SET NULL
  status        gestor_access_status NOT NULL DEFAULT 'pending'
  invited_at    timestamptz NOT NULL DEFAULT now()
  expires_at    timestamptz NOT NULL DEFAULT now() + interval '14 days'
  responded_at  timestamptz
  revoked_at    timestamptz
  CHECK (status <> 'active' OR gestor_id IS NOT NULL)
  UNIQUE (owner_id, gestor_email) WHERE status IN ('pending', 'active')     -- índice parcial

activity_log                                         -- solo inserción (§5.2.5)
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
  occurred_at timestamptz NOT NULL DEFAULT now()
  category    activity_category NOT NULL
  actor_id    uuid                       -- null: sistema o job
  actor_role  user_role
  owner_id    uuid                       -- cuenta afectada; sin FK, para sobrevivir a un borrado de cuenta
  action      text NOT NULL              -- p. ej. 'account.created', 'gestor_access.revoked'
  entity_type text, entity_id text
  metadata    jsonb NOT NULL DEFAULT '{}'    -- solo identificadores y estados; nunca importes, IBAN ni NIF
```

Las columnas de `business_profiles` reproducen RF-004. Su API y su pantalla pertenecen a SPEC-W-005.

#### 5.2.3 Funciones auxiliares (esquema `private`)

Todas `SECURITY DEFINER`, `STABLE` (salvo `log_activity`), con `SET search_path = ''`, `REVOKE ALL … FROM PUBLIC` y
`GRANT EXECUTE` solo a `authenticated` y `service_role`.

| Función | Devuelve |
|---|---|
| `private.app_role()` | `user_role` del `auth.uid()` si su cuenta está `active`; `NULL` si es anónimo, está suspendido o no tiene perfil |
| `private.is_admin()` | `app_role() = 'admin'` |
| `private.app_email()` | correo del `auth.uid()` |
| `private.gestor_has_access(p_owner uuid)` | `true` si `app_role() = 'gestor'` **y** existe un `gestor_access` con `owner_id = p_owner`, `gestor_id = auth.uid()` y `status = 'active'`. Se evalúa en cada consulta |
| `private.log_activity(p_category, p_actor_id, p_actor_role, p_owner_id, p_action, p_entity_type, p_entity_id, p_metadata)` | inserta en `activity_log`. **`EXECUTE` solo para `service_role`** (y para el dueño de las funciones `app.*`, que la invocan): si `authenticated` pudiera ejecutarla, cualquiera falsificaría entradas del registro |

#### 5.2.4 Políticas RLS (normativas)

`ENABLE` y `FORCE ROW LEVEL SECURITY` en las cuatro tablas. Lo que no figura aquí **está denegado**.

| Tabla | Operación | `usuario` (dueño) | `gestor` | `admin` |
|---|---|---|---|---|
| `profiles` | SELECT | su fila | su fila y la de los usuarios con vínculo activo | todas las filas (metadatos) |
| `profiles` | UPDATE | solo su `display_name` (privilegio de columna) | solo su `display_name` | solo su `display_name` |
| `profiles` | INSERT / DELETE | denegado | denegado | denegado (el alta la hace el trigger; el rol y el estado cambian solo por `app.admin_set_*`) |
| `business_profiles` | SELECT | la suya | la de los usuarios con vínculo activo (`private.gestor_has_access`) | **ninguna** |
| `business_profiles` | UPDATE | la suya (todas las columnas salvo `owner_id`) | denegado | denegado |
| `business_profiles` | INSERT / DELETE | denegado (la crea el trigger) | denegado | denegado |
| `gestor_access` | SELECT | las suyas (`owner_id = auth.uid()`) | siempre que `private.app_role() = 'gestor'`: las suyas (`gestor_id = auth.uid()`) y las dirigidas a su correo (`gestor_email = private.app_email()`) | **ninguna** |
| `gestor_access` | INSERT | `owner_id = auth.uid()`, `status = 'pending'`, `gestor_id IS NULL`, `expires_at` por defecto, y el correo no es el suyo | denegado | denegado |
| `gestor_access` | UPDATE / DELETE | denegado (solo `app.revoke_gestor_access`) | denegado (solo `app.accept_…` y `app.decline_…`) | denegado |
| `activity_log` | SELECT | filas con `owner_id = auth.uid()` | filas con `actor_id = auth.uid()` (esta política no depende del rol) | filas con `category = 'account'` |
| `activity_log` | INSERT / UPDATE / DELETE | denegado | denegado | denegado (solo `private.log_activity`) |

`anon` no tiene ninguna política: no ve ni escribe nada.

**Privilegios de tabla (defensa en profundidad).** Comprobado en el spike: aunque `auto_expose_new_tables = false` retira
SELECT/INSERT/UPDATE/DELETE, los privilegios por defecto de Supabase siguen concediendo `TRUNCATE`, `REFERENCES`, `TRIGGER` y
`MAINTAIN` a `anon`, `authenticated` y `service_role` sobre las tablas nuevas de `public`, y `TRUNCATE` **no está sujeto a la RLS**.
Por eso la migración (1) ejecuta `ALTER DEFAULT PRIVILEGES … IN SCHEMA public REVOKE ALL ON TABLES, SEQUENCES FROM anon, authenticated,
service_role` para los creadores relevantes, (2) hace `REVOKE ALL` explícito sobre cada tabla creada y (3) concede únicamente lo
siguiente, y nada más:

| Tabla | `authenticated` |
|---|---|
| `profiles` | `SELECT`; `UPDATE (display_name)` |
| `business_profiles` | `SELECT`; `UPDATE` de todas las columnas salvo `owner_id` |
| `gestor_access` | `SELECT`; `INSERT (owner_id, gestor_email)` |
| `activity_log` | `SELECT` |

`anon` no tiene ningún privilegio sobre ninguna tabla de `public`. `service_role` recibe lo estrictamente necesario para `cuadre.cli`
y se amplía por spec cuando un job lo necesite.

#### 5.2.5 Funciones de negocio (esquema `app`) y triggers

Cada función es `SECURITY DEFINER` con `search_path = ''`, verifica quién llama con `auth.uid()` y `private.app_role()`, escribe
`activity_log` en la misma transacción y falla con un mensaje de la forma `ERRCODE='P0001'`, `MESSAGE='<code>'`
(códigos estables) o `42501` si el rol no basta.

| Función | Quién | Efecto |
|---|---|---|
| `app.accept_gestor_access(p_id uuid)` | `gestor` activo | Si la fila está `pending`, no ha caducado y `gestor_email = private.app_email()`: `gestor_id = auth.uid()`, `status = 'active'`, `responded_at = now()`. Registra `gestor_access.accepted` (`category = 'access'`, `owner_id` = dueño) |
| `app.decline_gestor_access(p_id uuid)` | `gestor` activo | Igual, pasando a `declined`. Registra `gestor_access.declined` |
| `app.revoke_gestor_access(p_id uuid)` | el **dueño** | Si la fila está `pending` o `active`: `status = 'revoked'`, `revoked_at = now()`. Registra `gestor_access.revoked` |
| `app.admin_set_role(p_target uuid, p_role user_role)` | `admin` | Cambia el rol. **No puede ser sobre sí mismo.** Registra `account.role_changed` con `{from, to}` (`category = 'account'`) |
| `app.admin_set_status(p_target uuid, p_status account_status)` | `admin` | Igual para el estado. No sobre sí mismo. Registra `account.status_changed` |

Códigos de error de negocio: `gestor_access_not_found`, `gestor_access_not_pending`, `gestor_access_expired`,
`gestor_access_not_open` (revocar un vínculo que ya está revocado o rechazado), `not_the_owner`, `cannot_modify_self`,
`target_not_found`. Quien no es parte de un vínculo recibe `gestor_access_not_found`, igual que si no existiera: no se revela su existencia.

Al cambiar un usuario de `gestor` a otro rol, sus vínculos dejan de dar acceso **en la petición siguiente** porque
`private.gestor_has_access` exige `app_role() = 'gestor'`; no hace falta tocar `gestor_access`.

**Triggers.**

- `AFTER INSERT ON auth.users` → `private.handle_new_user()`: inserta `profiles` (rol `usuario`, `display_name` de
  `raw_user_meta_data->>'display_name'` o vacío; **nunca** se lee un rol de los metadatos), inserta `business_profiles` vacío
  y registra `account.created` (`category = 'account'`).
- `AFTER UPDATE OF email ON auth.users` → mantiene `profiles.email`.
- `BEFORE UPDATE` en `profiles` y `business_profiles` → `updated_at = now()`.
- `BEFORE UPDATE OR DELETE ON activity_log` → `RAISE EXCEPTION 'activity_log_is_append_only'`; y
  `REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON activity_log FROM PUBLIC, anon, authenticated, service_role`.

#### 5.2.6 Roles de login y datos de prueba

- `cuadre_app`: `LOGIN NOBYPASSRLS` con `GRANT authenticated, anon TO cuadre_app WITH INHERIT FALSE, SET TRUE` (PostgreSQL 17:
  puede hacer `SET ROLE` pero no hereda sus privilegios). Sin privilegios propios sobre tablas.
- `cuadre_jobs`: `LOGIN NOBYPASSRLS` con `GRANT service_role TO cuadre_jobs WITH INHERIT FALSE, SET TRUE`. Tampoco tiene privilegios propios:
  `cuadre.db.service_transaction` hace `SET LOCAL ROLE service_role`. Solo `cuadre.jobs` y `cuadre.cli`.
- Las contraseñas **no** están en las migraciones: en local las fija `supabase/seed.sql` con un valor de desarrollo; en cualquier
  otro entorno, la plataforma.
- `supabase/seed.sql` crea cinco usuarios sintéticos con identidad de correo (pueden iniciar sesión), contraseña de desarrollo
  `cuadre-demo-2026` y correo confirmado:

| Usuario | Correo | Rol | Notas |
|---|---|---|---|
| Alicia | `alicia@example.test` | `usuario` | Con perfil de negocio de ejemplo |
| Beto | `beto@example.test` | `usuario` | Con perfil de negocio de ejemplo |
| Gina | `gina@example.test` | `gestor` | Sin vínculos (los tests los crean) |
| Gus | `gus@example.test` | `gestor` | Sin vínculos |
| Adán | `adan@example.test` | `admin` | |

Los NIF, IBAN y direcciones del seed son inventados y no válidos (RES-07).

**El seed es para desarrollo y E2E, no para los tests de RLS.** Cada test de RLS crea con una *factory* su propio reparto de cinco
usuarios (mismos roles, correos únicos) mediante `TEST_DATABASE_ADMIN_URL`, de modo que ningún test depende del estado que dejó otro.

### 5.3 Autenticación en el frontend

| Ruta | Quién | Comportamiento |
|---|---|---|
| `/` | Todos | Redirige a la portada del rol o a `/login` |
| `/login` | Anónimo | Correo y contraseña. Con sesión, redirige a la portada del rol. Admite `?next=` relativo |
| `/registro` | Anónimo | Nombre, correo y contraseña (≥ 10 caracteres). Pide confirmar el correo |
| `/recuperar` | Anónimo | Pide el correo y envía el enlace de recuperación. La respuesta es la misma exista o no la cuenta |
| `/restablecer` | Con el enlace | Fija la nueva contraseña. Al terminar cierra todas las sesiones y lleva a `/login?aviso=restablecida`; sin la sesión que crea el enlace, lleva a `/recuperar?aviso=enlace` |
| `/inicio` | `usuario` | Portada del autónomo |
| `/cartera` | `gestor` | Portada del gestor |
| `/admin` | `admin` | Portada del administrador |
| `/403` | Con sesión | «No tienes acceso a esta sección», con enlace a su portada |
| `/auth/confirm` | Con el enlace del correo | *Route handler* (sin interfaz): lee `token_hash`, `type` (solo `email` o `recovery`) y `next` (solo ruta relativa de la propia aplicación: `safeNext`) y llama a `verifyOtp`; con éxito redirige a `next` (por defecto, la portada del rol) y con error, a `/login` con un mensaje |
| `/auth/cerrar` | Interna | *Route handler*: cierra la sesión local y redirige a `/login?aviso=…`. Solo lo usa `getMe()` cuando la API rechaza la sesión (no se pueden borrar cookies al renderizar); rechaza las peticiones `Sec-Fetch-Site: cross-site`. El cierre voluntario es la acción `logout` |

Los correos de confirmación y de recuperación los envía Supabase Auth con plantillas en español (`supabase/templates/confirmation.html`
y `recovery.html`) cuyos enlaces apuntan a `/auth/confirm` (flujo PKCE de `@supabase/ssr`).

El *proxy* (`src/proxy.ts`) refresca la sesión con `getClaims()` (verifica la firma del JWT por JWKS; `getSession()` no se usa para
autorizar) y aplica `routeGuard`, una función pura con tests: sin sesión, una portada lleva a `/login?next=<ruta>`; con sesión,
`/login`, `/registro` y `/recuperar` devuelven a `/`, que lleva a la portada del rol. Solo mejora la experiencia: **las Server Functions no
pasan por el *matcher* del proxy**, así que cada layout y cada acción comprueban lo suyo, y la autorización real está en la API y en la RLS.
El rol no sale del JWT: el layout autenticado llama a `GET /api/me` y de ahí salen la portada, la navegación y la comprobación de rol.
Quien abre la portada de otro rol ve `/403`. Con *Cache Components* (valor por defecto de Next.js 16) la sesión es un dato de la petición y se
lee dentro de `<Suspense>`.

**Casos límite** (definidos para evitar bucles de redirección y sesiones perdidas):

- API caída (red, 5xx, 429, `auth_unavailable`…): `app/error.tsx` («Servicio no disponible» con «Reintentar»), con la sesión intacta. **Nunca**
  se redirige a `/login` con sesión, porque el proxy la devolvería a `/` y se formaría un bucle.
- `GET /api/me` → 401: `/auth/cerrar?aviso=sesion`; 403 `account_suspended`: aviso `suspendida`; 403 `profile_missing`: aviso `perfil`.
  Las tres cierran la sesión local y terminan en `/login` con el aviso.
- `?aviso=` elige un texto de una lista cerrada (`lib/notices.ts`): nunca se pinta lo que llegue en la URL. `?next=` solo admite rutas
  relativas que empiecen por un único `/` (sin `//`, barra invertida, esquema, caracteres de control ni más de 512 caracteres; se comprueba
  también decodificada).

**Navegación** (barra lateral ≥ 901 px; barra superior desplazable ≤ 900 px, como el prototipo):

- `usuario`: Inicio, Clientes, Facturas, Gastos, Contabilidad mensual, Trimestres. Solo Inicio está activo; el resto aparece
  desactivado con la etiqueta «Próximamente» y `aria-disabled="true"`.
- `gestor`: Cartera (activa).
- `admin`: Cuentas (desactivada, «Próximamente»).

Pie de la barra: nombre y rol de la persona, y «Cerrar sesión».

**Textos** en español neutro, errores junto al campo y un resumen de errores con `role="alert"`. Los mensajes no revelan si un
correo existe: el fallo de inicio de sesión es siempre «Correo o contraseña incorrectos.» (también con el correo sin confirmar) y la
recuperación y el registro responden igual exista o no la cuenta. Los formularios son Server Actions; las contraseñas no se devuelven
nunca al navegador y su máximo es de 72 bytes (límite de bcrypt, comprobado contra Auth local).

### 5.4 Variables de entorno

| Variable | La leen | Obligatoria | Notas |
|---|---|---|---|
| `APP_ENV` | backend | sí | `local`, `staging` o `production` |
| `SUPABASE_URL` | backend, jobs | sí | |
| `TEST_DATABASE_ADMIN_URL` | solo los tests | solo para las pruebas | Conexión con el rol `postgres` de la pila local, para crear usuarios y estados de prueba. Ningún código de la aplicación la lee |
| `TEST_SUPABASE_ANON_KEY` | solo los tests `live` | solo para las pruebas | Clave publicable (`sb_publishable_…`) de la pila local; permite pedir tokens reales a GoTrue. Sin ella, los tests `live` se omiten |

`conftest.py` carga primero las variables ya definidas (CI), después el `.env` local de la raíz (gitignorado) y por último unos valores por
defecto de la pila local; así `pytest` funciona tras `supabase start` y `db reset` sin configurar nada. `SUPABASE_SERVICE_ROLE_KEY` acepta tanto la
clave secreta nueva (`sb_secret_…`, solo cabecera `apikey`) como el JWT de servicio.
| `SUPABASE_SERVICE_ROLE_KEY` | `cuadre.cli` | solo para la CLI | **Nunca** otro módulo ni el frontend |
| `ADMIN_PASSWORD` | `cuadre.cli` | solo para `create-admin` | Contraseña del primer administrador; no se pasa por argumento para que no quede en el historial del terminal |
| `DATABASE_URL` | backend | sí | Rol `cuadre_app` |
| `DATABASE_SERVICE_URL` | `cuadre.jobs`, `cuadre.cli` | solo para ellos | Rol `cuadre_jobs` |
| `FRONTEND_ORIGIN` | backend | sí | Único origen CORS permitido |
| `LOG_LEVEL` | backend | no | Por defecto `INFO` |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | frontend | sí | Públicas por naturaleza (la segunda es la clave publicable `sb_publishable_…`). Viven en `frontend/.env.local` (plantilla `frontend/.env.example`): Next.js solo lee el `.env` de su carpeta y el `.env` de la raíz no debe llegar nunca al frontend |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | sí | URL de la API (`http://127.0.0.1:8000` en local) |

`.env.example` las documenta con marcadores de posición. `npm run env:local` genera `.env` y `frontend/.env.local` con las claves de la
pila local en marcha (`supabase status -o env`); no pisa los archivos existentes salvo con `--force`.

### 5.5 Comandos

Con el entorno virtual activado y desde la raíz del repositorio (valen igual en CI):

| Para… | Comando |
|---|---|
| Arrancar Supabase local | `npx supabase start` |
| Recrear la base con migraciones y seed | `npx supabase db reset` |
| Parar Supabase | `npx supabase stop` |
| Clave de firma local (una vez por clon) | `npm run gen:signing-key` |
| Generar `.env` y `frontend/.env.local` desde la pila en marcha | `npm run env:local` (`-- --force` para rehacerlos) |
| Pruebas de los scripts de la raíz | `npm run test:scripts` |
| Arrancar la API | `uvicorn cuadre.main:app --reload --port 8000 --app-dir backend/src` |
| Arrancar el frontend | `npm --prefix frontend run dev` (abrir siempre `http://localhost:3000`: las cookies de sesión van por host) |
| Pruebas unitarias del frontend | `npm --prefix frontend run test:unit` (`node --test`, sin dependencias) |
| Comprobar el resultado del build | `npm --prefix frontend run build` y `npm --prefix frontend run check:bundle` |
| Crear el primer administrador | `python -m cuadre.cli create-admin --email <correo>` (lee la contraseña de `ADMIN_PASSWORD`) |
| Regenerar OpenAPI y cliente | `python backend/scripts/export_openapi.py` y `npm --prefix frontend run gen:api` |

### 5.6 Paquetes del backend

```
backend/src/cuadre/
  main.py          create_app(), registro de rutas y errores; `app = create_app()` para uvicorn
  config.py        Settings (pydantic-settings)
  core/            errors.py (problem+json), auth.py (verificación JWKS, CurrentUser, get_tx, require_role),
                   observability.py (registro JSON y middleware de contexto de petición), routing.py (new_router, exige operation_id)
  db/              session.py: user_transaction() y service_transaction() — ÚNICO sitio que abre conexiones
  api/             routes_health.py, routes_me.py (los routers se crean solo con core.routing.new_router)
  jobs/            __init__.py (vacío; reservado para SPEC-W-012 y 014)
  cli.py           create-admin
backend/scripts/   export_openapi.py
backend/openapi.json
backend/tests/
  conftest.py  support.py  rls/  api/  rules/  test_session.py  test_cli_create_admin.py
```

El cliente HTTP del backend (CLI y tests) es `httpx2` y no `httpx`: Starlette 1.x lo exige para su `TestClient` sin avisos de obsolescencia
y es el sucesor mantenido por el autor original (Pydantic Services Inc.).

## 6. Restricciones técnicas

Cada una tiene un test o una comprobación asociada (§8).

| ID | Restricción |
|---|---|
| T-01 | **Versiones fijadas** (instaladas y comprobadas el 2026-11-04 al cerrar la spec; las de `pyproject.toml` y `package.json` son exactas): Python 3.12.10; FastAPI 0.162.0 (Starlette 1.10.0); Pydantic 2.14.2 (pydantic-settings 2.16.2); psycopg 3.3.7 (psycopg-pool 3.3.3); PyJWT 2.15.1; Uvicorn 0.54.0; httpx2 2.16.0; pytest 9.2.0; ruff 0.17.3; PyYAML 6.0.3; Node 24.16.0 (npm 11.17.0); Next.js 16.4.5; React 19.3.0; Tailwind 4.3.4; ESLint 10.14.0; shadcn 4.23.0; supabase-js 2.118.0; `@supabase/ssr` 0.12.7; openapi-typescript 7.13.0; openapi-fetch 0.17.0; Playwright 1.64.1 (Chromium 156, Firefox 157, WebKit 27.2); Supabase CLI 3.0.0 con PostgreSQL 17.11, GoTrue 2.197.0 y Mailpit 1.31.3. **TypeScript 5.9.3**: la 7.0.2 (la más reciente) es incompatible, porque `typescript-eslint` 8.72 exige `typescript <6.1` y `openapi-typescript` 7.13 pide `^5.x`. En el CI: Python 3.12 y Node 24 (`setup-python` y `setup-node`) sobre `ubuntu-24.04` |
| T-02 | **Sin `float`** (RES-02, ADR-0006): ni en `backend/src/cuadre/` ni en `supabase/migrations/` (`real`, `double precision`, `float`). Test `test_no_float` |
| T-03 | **Solo datos sintéticos y ningún secreto en git** (RES-07). `.env` y `.env.local` en `.gitignore`; `.env.example` solo con marcadores. Test `test_no_secrets_tracked` |
| T-04 | **La service key y `DATABASE_SERVICE_URL` solo se usan en `cuadre.jobs` y `cuadre.cli`** (`cuadre.config` únicamente los declara como ajustes). Nunca en rutas que actúan en nombre de un usuario ni en el frontend. Test `test_service_key_scope` (analiza el código) y comprobación del *bundle* |
| T-05 | **Solo `cuadre.db` abre conexiones** y toda petición de usuario usa `user_transaction` (ADR-0003). Test `test_db_access_scope` |
| T-06 | **RLS activada y forzada en toda tabla de `public`**, funciones `SECURITY DEFINER` con `search_path = ''`, y ninguna política menciona `user_metadata` ni `raw_user_meta_data`. Tests `test_rls_guard` y `test_policies_hygiene` |
| T-07 | **Data API (PostgREST) desactivada** en `supabase/config.toml` (`[api] enabled = false`). Test `test_data_api_off` |
| T-08 | **Migraciones hacia delante y sin secretos**; el esquema solo cambia desde `supabase/migrations/` |
| T-09 | **Ninguna dependencia de SDK de modelos de lenguaje** (`anthropic`, `openai`, `langchain*`, `google-generativeai`, `mistralai`, `cohere`, `ollama`…) en `pyproject.toml` ni en `package.json`. Test `test_no_llm_sdk` |
| T-10 | **Errores `problem+json`** con `code` estable y `detail` en español, sin trazas ni datos internos |
| T-11 | **`operation_id` explícito, único y `verbo_objeto`** en todas las rutas. Test `test_operation_ids` |
| T-12 | **El rol sale de la base de datos**, nunca de claims del JWT. Los tokens con `aud` distinto, `alg: none` o sin firma se rechazan |
| T-13 | **Logs sin tokens, contraseñas ni correos**: solo `request_id`, `user_id`, la plantilla de la ruta (nunca la query), código y duración. El registro de accesos propio de `uvicorn` imprime la query y se desactiva al configurar la aplicación (`uvicorn.access`), arranque como arranque. Test `test_requests_are_logged_without_tokens_or_emails` |
| T-14 | **Interfaz** en español, con los tokens de diseño del prototipo, fuentes con `next/font` (nada se pide a Google desde el navegador), sin scroll horizontal a 390 y 1.440 px, foco visible y etiquetas asociadas a cada campo |
| T-15 | **El frontend nunca importa la clave de servicio ni la URL de la base de datos**; solo `NEXT_PUBLIC_*`, y no usa los datos de Supabase (solo la sesión). Tests `test_frontend_scope` (código fuente) y `check:bundle` (resultado del build) |
| T-16 | **Contraseñas** de al menos 10 caracteres (`minimum_password_length` en `config.toml`); confirmación de correo activa también en local, para que el entorno se parezca a producción |
| T-17 | **Sin llamadas a la AEAT ni a modelos** desde este repositorio |
| T-18 | **No se modifican** `docs/00-charter.md` ni `docs/03-prd.md` |

## 7. Criterios de aceptación (Given-When-Then)

Los usuarios son los del seed (§5.2.6). «Como X» significa conectar con la identidad de X a través de `cuadre.db.session`.

```gherkin
Feature: Base, autenticación con tres roles y RLS (SPEC-W-001)

  Scenario: AC-01 · El registro crea un usuario con su perfil vacío
    Given un visitante sin cuenta
    When se registra con nombre, correo y una contraseña de 10 caracteres o más y confirma el enlace recibido
    Then existe su fila en profiles con rol "usuario" y estado "active"
      And existe su business_profiles con todos los campos vacíos
      And activity_log contiene "account.created" con su identificador
      And al iniciar sesión aterriza en /inicio

  Scenario: AC-02 · Cada rol aterriza en su portada
    Given los usuarios Alicia (usuario), Gina (gestor) y Adán (admin)
    When cada uno inicia sesión
    Then Alicia ve /inicio con la navegación del autónomo
      And Gina ve /cartera con la navegación del gestor
      And Adán ve /admin con la navegación del administrador

  Scenario: AC-03 · Recuperación de contraseña
    Given un usuario registrado
    When pide recuperar su contraseña, abre el enlace del correo y fija una nueva
    Then puede iniciar sesión con la nueva contraseña y no con la anterior
      And pedir la recuperación de un correo inexistente muestra el mismo mensaje

  Scenario: AC-04 · Sin sesión no se accede
    Given una persona sin sesión
    When abre /inicio
    Then es redirigida a /login?next=/inicio
    When se hace GET /api/me sin cabecera Authorization
    Then la respuesta es 401 problem+json con code "unauthenticated"

  Scenario: AC-05 · Tokens inválidos y cuentas suspendidas
    Given un token caducado, otro con audiencia distinta, otro con la firma alterada y otro con alg "none"
    When se hace GET /api/me con cada uno
    Then todos reciben 401 con code "unauthenticated"
    Given un token válido de una cuenta con estado "suspended"
    When se hace GET /api/me
    Then la respuesta es 403 con code "account_suspended"

  Scenario: AC-06 · Un usuario no puede escalar su rol ni su estado
    Given Alicia con rol "usuario"
    When intenta actualizar su propia fila de profiles con role = 'admin' o status distinto
      And intenta ejecutar app.admin_set_role sobre sí misma o sobre Beto
    Then ambas operaciones se rechazan (privilegio denegado) y su rol sigue siendo "usuario"

  Scenario: AC-07 · Los usuarios no ven ni tocan lo de los demás
    Given Alicia y Beto con perfil de negocio, un vínculo de gestor y entradas en activity_log cada uno
    When Beto consulta, actualiza o borra filas de profiles, business_profiles, gestor_access y activity_log de Alicia
    Then ve 0 filas ajenas y ninguna operación modifica datos de Alicia

  Scenario: AC-08 · Un gestor con vínculo activo ve solo a su cliente
    Given Gina con un vínculo activo con Alicia y ninguno con Beto
    When Gina consulta profiles y business_profiles
    Then ve la fila de Gina, la de Alicia y el perfil de negocio de Alicia
      And no ve nada de Beto
      And al llamar a GET /api/me su rol es "gestor"

  Scenario: AC-09 · Pendiente, rechazado, revocado o ajeno no dan acceso
    Given una invitación pendiente de Alicia a Gina
    When Gina consulta el perfil de negocio de Alicia
    Then ve 0 filas
    When Gina acepta la invitación con app.accept_gestor_access
    Then ve el perfil de negocio de Alicia
    When Alicia revoca el vínculo con app.revoke_gestor_access
      And Gina repite la consulta con el mismo token, sin volver a iniciar sesión
    Then ve 0 filas de inmediato
      And activity_log contiene "gestor_access.accepted" y "gestor_access.revoked" con owner_id de Alicia
    Given un vínculo activo y que un administrador cambia el rol de Gina a "usuario"
    When Gina consulta el perfil de negocio de Alicia
    Then ve 0 filas
    Given Gus, que no tiene ningún vínculo, o una invitación a otro correo
    When intenta aceptarla con app.accept_gestor_access
    Then falla con "gestor_access_not_found" o privilegio denegado

  Scenario: AC-10 · El gestor no escribe en las tablas del usuario
    Given Gina con un vínculo activo con Alicia
    When Gina intenta INSERT, UPDATE o DELETE sobre business_profiles de Alicia, sobre profiles de Alicia
      And intenta UPDATE o DELETE directo sobre gestor_access
    Then todas las operaciones se rechazan o afectan a 0 filas y los datos no cambian

  Scenario: AC-11 · El administrador no ve datos financieros
    Given Adán con rol "admin"
    When consulta profiles
    Then ve todas las cuentas con id, correo, rol, estado y fecha de alta
    When consulta business_profiles y gestor_access
    Then no ve ninguna fila de otra cuenta (solo, en su caso, su propia ficha de negocio vacía, que crea el alta de toda cuenta)
    When consulta activity_log
    Then solo ve filas con category "account"
    When ejecuta app.admin_set_role sobre Beto para convertirlo en "gestor"
    Then el cambio se aplica y activity_log contiene "account.role_changed" con {from, to}
    When ejecuta app.admin_set_role o app.admin_set_status sobre sí mismo
    Then falla con "cannot_modify_self"

  Scenario: AC-12 · El registro de actividad solo admite inserciones
    Given una fila existente en activity_log
    When cualquier rol (usuario, gestor, admin, service_role) o el propietario de la función intenta UPDATE o DELETE
    Then se rechaza con "activity_log_is_append_only" o por privilegios
    When authenticated intenta un INSERT directo
    Then se rechaza; solo private.log_activity inserta

  Scenario: AC-13 · Ninguna tabla queda sin RLS ni sin registrar
    Given la base de datos migrada
    When se listan las tablas del esquema public
    Then todas tienen RLS activada y forzada
      And todas figuran en backend/tests/rls/rls_matrix.yaml
      And ninguna política menciona user_metadata ni raw_user_meta_data
      And anon no tiene ningún privilegio sobre ninguna tabla de public
      And authenticated solo tiene los privilegios de la tabla de §5.2.4 (ni TRUNCATE, REFERENCES, TRIGGER ni MAINTAIN)
    When se crea en una prueba una tabla de public sin RLS
    Then la guardia falla

  Scenario: AC-14 · Interfaz adaptable y accesible
    Given ventanas de 390 × 844 y 1.440 × 900 píxeles
    When se abren /login, /registro, /recuperar y el layout autenticado de cada rol
    Then la anchura del documento no supera la de la ventana (sin scroll horizontal)
      And a 390 px la navegación pasa a la barra superior desplazable
      And todo campo tiene su etiqueta y el foco se ve al tabular

  Scenario: AC-15 · El cliente generado no se desvía y no se filtra la clave de servicio
    Given backend/openapi.json y frontend/src/api/schema.d.ts versionados
    When se regeneran desde las rutas
    Then no hay diferencias
    When se construye el frontend
    Then el resultado no contiene el valor de SUPABASE_SERVICE_ROLE_KEY ni la cadena "SERVICE_ROLE"
```

## 8. Criterios de verificación ejecutables

### 8.1 Requisitos previos

Docker Desktop **en marcha** (`docker info` responde); Python 3.12 con `.venv/` activado; Node 24; `.env` creado a partir de
`.env.example`.

### 8.2 Secuencia (desde la raíz; todos terminan con código 0)

```powershell
# 0 · Entorno (una vez)
.\.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
npm ci
npm --prefix frontend ci
npm --prefix frontend exec -- playwright install chromium firefox webkit

# 1 · Pila local
npm run gen:signing-key                                 # clave ES256 de desarrollo (gitignorada); una vez por clon
npx supabase start
npx supabase db reset                                   # migraciones + seed sin errores
npm run env:local                                       # .env y frontend/.env.local a partir de la pila (no pisa los existentes)

# 2 · Calidad estática
ruff check backend contracts/tools contracts/python
ruff format --check backend contracts/tools contracts/python
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test:unit
npm run test:scripts                                    # scripts de la raíz (generador de entornos)

# 3 · Contratos y deriva
python contracts/tools/export_schemas.py --check
python contracts/tools/validate_examples.py
python backend/scripts/export_openapi.py --check
npm --prefix frontend run gen:api -- --check

# 4 · Puerta NFR-06
pytest backend/tests/rls -m rls -q                      # esperado: 0 failed, 0 error

# 5 · Resto del backend
pytest backend/tests -m "not rls" -q                    # api/ y rules/

# 6 · Frontend
npm --prefix frontend run build
npm --prefix frontend run check:bundle
npm --prefix frontend run test:e2e                      # Playwright: chromium, firefox y webkit
```

**Comando único de la spec** (lo que cita `tasks.json`): `pytest backend/tests/rls -m rls -q` para la puerta de seguridad, más la
secuencia anterior para dar la spec por hecha.

### 8.3 Correspondencia criterio → prueba

| AC | Prueba |
|---|---|
| AC-01 | `frontend/e2e/auth.spec.ts` · «registro»; `backend/tests/rls/test_signup_trigger.py` |
| AC-02 | `frontend/e2e/roles.spec.ts` · «portada por rol» |
| AC-03 | `frontend/e2e/auth.spec.ts` · «recuperación» (lee el buzón de pruebas de Supabase local) |
| AC-04 | `frontend/e2e/auth.spec.ts` · «sin sesión»; `backend/tests/api/test_auth.py::test_no_authorization_header_is_401`, `::test_wrong_scheme_or_empty_credentials_is_401`, `::test_a_malformed_token_is_401`; `frontend/src/lib/route-guard.test.ts` |
| AC-05 | `backend/tests/api/test_auth.py` (caducado, no vigente, audiencia/emisor/`exp`/`sub` inválidos, firma ajena o alterada, `kid` desconocido, `alg: none`, confusión HS256, JWKS caído, `::test_a_suspended_account_is_403`, `::test_a_valid_token_without_a_profile_is_403`); `test_me_live.py` (token real de GoTrue) |
| AC-06 | `backend/tests/rls/test_rls_roles.py::test_no_privilege_escalation` |
| AC-07 | `backend/tests/rls/test_rls_roles.py` (parametrizada con `rls_matrix.yaml`) |
| AC-08 | `backend/tests/rls/test_gestor_access.py::test_an_active_link_reads_only_the_client` |
| AC-09 | `backend/tests/rls/test_gestor_access.py::test_the_full_lifecycle_and_its_audit_trail`, `::test_changing_the_gestor_role_cuts_access_immediately`, `::test_only_the_addressed_gestor_can_accept` |
| AC-10 | `backend/tests/rls/test_gestor_access.py::test_a_gestor_cannot_write_in_the_users_tables`; `test_rls_roles.py::test_nobody_else_can_write_alicias_rows` |
| AC-11 | `backend/tests/rls/test_admin.py` |
| AC-12 | `backend/tests/rls/test_activity_log.py` |
| AC-13 | `backend/tests/rls/test_rls_guard.py` |
| AC-14 | `frontend/e2e/responsive.spec.ts` (proyectos 390 y 1.440 px) |
| AC-15 | `backend/tests/rules/test_openapi_drift.py`; `npm --prefix frontend run gen:api -- --check`; `npm --prefix frontend run check:bundle` (con `frontend/scripts/bundle-scan.test.mjs`); `frontend/e2e/bundle.spec.ts` (lo que `next start` sirve de verdad) |
| §3.5 (CI) | `backend/tests/rules/test_ci_workflow.py` (forma del workflow y deriva spec ↔ CI); `backend/tests/rules/test_ci_gate.py` (en el CI un test omitido falla la sesión); `scripts/write-env.test.mjs` (`npm run test:scripts`) |
| T-02 a T-11, T-15 | `backend/tests/rules/` (`test_no_float`, `test_service_key_scope`, `test_db_access_scope`, `test_data_api_off`, `test_no_llm_sdk`, `test_operation_ids`, `test_no_secrets_tracked`, `test_frontend_scope`) |

**`rls_matrix.yaml`** vive en `backend/tests/rls/` y registra, por tabla, su tipo (`identity`, `financial` o `log`), la columna
de dueño y la expectativa de cada rol según §5.2.4. `test_rls_roles` la recorre con un reparto de cinco usuarios creado por la *factory* de cada test y
los estados del vínculo (sin vínculo, pendiente, activo, revocado, rechazado) y comprueba lectura, inserción, actualización y
borrado. `cuadre.db.session` tiene además su propio test de que el rol de una petición **no se filtra** a la siguiente que reutiliza
la misma conexión del pool. Cada spec
posterior que añada una tabla la añade aquí; sin eso, `test_rls_guard` falla.

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local **y** en el CI. *En local, hecho (clon limpio, hito 5). En el CI, pendiente de la primera ejecución en GitHub: aún no hay repositorio remoto.*
- [ ] `pytest backend/tests/rls -m rls` marcado como requisito obligatorio de fusión. *Pendiente del remoto: el trabajo es «RLS (NFR-06)», `test_ci_workflow` impide que se pueda saltar y el README explica cómo marcarlo.*
- [x] §5.1 actualizado con el resultado de la comprobación JWKS (ES256, sin HS256) y T-01 con el veredicto sobre TypeScript (hito 0).
- [x] T-01 con las versiones definitivas de todo lo instalado.
- [ ] `docs/04-specs/tasks.json`: SPEC-W-001 en `hecha`. *Ahora `en-revision` (su comando de verificación termina con 0 en local); pasa a `hecha` cuando la revisión la acepte, tras la primera ejecución del CI.*
- [x] `README.md` con los comandos de §5.5 comprobados en un clon limpio.
- [x] `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

## Anexo A · Orden de implementación sugerido

1. `supabase/config.toml` (Data API fuera, confirmaciones y longitud de contraseña) y migraciones de tipos, tablas y roles; `db reset` limpio.
2. Funciones `private.*`, políticas y funciones `app.*`; seed; `test_rls_guard` y `test_rls_roles` en rojo y luego en verde.
3. `cuadre.db.session` con sus tests; después `config`, `errors`, `auth` y las dos rutas; `test_auth`.
4. Tests de reglas (`rules/`); `export_openapi.py` y `backend/openapi.json`.
5. Frontend: `create-next-app`, tokens y fuentes; sesión con `@supabase/ssr`; páginas de autenticación; layout por rol.
6. Cliente generado; Playwright (`auth`, `roles`, `responsive`, `bundle`).
7. CI y README; pasada completa de §8.2.

## Anexo B · Decisiones que esta spec dejó a la implementación

Resueltas en el hito 0 (spike del 2026-11-03, CLI 3.0.0, PostgreSQL 17.11, GoTrue 2.197):

- **Firma del JWT local:** ES256 con `signing_keys_path` y JWKS (§5.1, punto 2). Sin camino HS256.
- **Buzón de pruebas:** sección `[local_smtp]` (Mailpit), interfaz y API en `http://127.0.0.1:54324` (`GET /api/v1/messages`,
  `GET /api/v1/message/{id}`). `[inbucket]` está obsoleto.
- **TypeScript:** 5.9.3 (T-01).
- **Data API desactivada (`[api] enabled = false`):** Auth y Storage siguen funcionando; solo desaparece `/rest/v1` (T-07).
- **Dueño de las funciones `SECURITY DEFINER`:** el rol `postgres` tiene `BYPASSRLS` (no es superusuario) y sus funciones leen tablas con
  `FORCE ROW LEVEL SECURITY` sin políticas. Comprobado.
- **Triggers sobre `auth.users`:** `postgres` puede crearlos aunque el dueño de la tabla sea `supabase_auth_admin`.
- **Privilegios por defecto:** ver §5.2.4, «Privilegios de tabla»: `Dxtm` para `anon`/`authenticated`/`service_role` hay que revocarlo.
- **Pooler local:** Supavisor en el puerto 54329 con usuarios `<rol>.pooler-dev`. Comprobado en el hito 1 con el propio `cuadre_app`
  (`cuadre_app.pooler-dev`): `SET LOCAL ROLE`, las claims y la RLS funcionan a través de él con `prepare_threshold=None`
  (`test_the_identity_survives_a_transaction_pooler`, marcador `pooler`).
- **Seed de usuarios:** `auth.users` solo exige `id` sin valor por defecto; las columnas de token (`confirmation_token`, `recovery_token`,
  `email_change_token_new`, `email_change`, `phone_change`, `phone_change_token`, `email_change_token_current`, `reauthentication_token`)
  se siembran con `''`. Comprobado en el hito 1: los cinco usuarios del seed inician sesión con GoTrue (`password` grant) y una contraseña
  incorrecta devuelve `invalid_credentials`.
- **Mutaciones (hito 1):** se rompió a propósito la RLS de 12 maneras (política abierta, vínculo que ignora el estado o el rol,
  `TRUNCATE` concedido, `FORCE RLS` retirada, `log_activity` ejecutable, trigger de solo-inserción eliminado, política extra para el
  administrador, escalada de `role`, `anon` con `SELECT`, política de escritura del gestor, `search_path` sin fijar). Las 12 hacen
  fallar la suite; tras revertirlas, vuelve a verde.

Resueltas en el hito 3 (frontend, 2026-11-04; Next.js 16.4.5, React 19.3, Tailwind 4.3, shadcn 4.23 con base Radix):

- **«Middleware» es «proxy»:** `src/proxy.ts` con la función `proxy` (entorno Node). El ADR-0002 dice «middleware»; un ADR aceptado no se
  edita, vale esta spec. Detalle de diseño en §5.3.
- **Cache Components activado** (valor por defecto de `create-next-app` 16): la sesión se lee dentro de `<Suspense>` (layout de `(app)` y
  `/`), `getMe()` declara con `connection()` que depende de la petición, y los apartados autenticados llevan `export const instant = false`
  (no hay nada que cachear entre personas). Sin esto, la validación de desarrollo de Next los señala como fallos.
- **Sesión en servidor:** `getClaims()` (firma verificada por JWKS) para saber si hay sesión; `getSession()` solo para reenviar el
  `access_token` a la API, que lo vuelve a verificar. No existe cliente de Supabase en el navegador: ningún componente lo necesita (los
  formularios son Server Actions).
- **Pruebas unitarias sin dependencias:** `node --test` con la eliminación de tipos de Node 24; módulos puros en `src/lib` sin alias de
  importación. 55 tests; **38 mutaciones** (redirecciones abiertas, prefijos sin límite de segmento, mensajes que distinguen cuentas, un 503
  que cierra la sesión…) y 6 de `test_frontend_scope`, todas detectadas.
- **`check:bundle`:** `supabase-js` incluye en su código la comprobación de prefijo `startsWith("sb_secret_")`; por eso la búsqueda es de una
  clave entera (`sb_secret_` + 20 caracteres) y del valor real de cada secreto del `.env`, no del prefijo suelto.
- **Contraseñas:** mínimo 10 caracteres (T-16) y máximo 72 bytes; Auth local rechaza 73 (`validation_failed`).
- **Registro real comprobado:** GoTrue → trigger → perfil (`usuario`, `active`, nombre desde `user_metadata.display_name`), ficha de negocio
  con `vat_regime = 'general'` por defecto, `account.created` en `activity_log` y confirmación por enlace (`/auth/confirm`, `type=email`).
- **Avisos de desarrollo ajenos:** una extensión del navegador (LanguageTool) añade atributos a `<html>`; `suppressHydrationWarning` en
  `<html>` y `<body>` evita el falso error de hidratación.
- **Auditoría npm:** `npm audit --omit=dev` da 0. `shadcn init` deja `shadcn` y `tw-animate-css` en `dependencies`, pero solo se usan al
  compilar (el CSS que se importa y la CLI): se pasaron a `devDependencies`. Quedan avisos moderados en herramientas de desarrollo
  (`minimatch < 11.0.1` y `deepmerge` vía `eslint-config-next`, `openapi-typescript` y la CLI de shadcn); no llegan al build.

Resueltas en el hito 4 (pruebas de extremo a extremo; Playwright 1.64.1 con Chromium 156, Firefox 157 y WebKit 27.2):

- **Matriz:** tres motores × dos anchos (390 y 1.440 px) = seis proyectos, más un proyecto de preparación por motor. 221 pruebas: 9 de preparación,
  35 por proyecto (`roles` 9, `responsive` 9, `auth` 17) y 2 de `bundle`, que corren solo en `chromium-1440`. Solo `viewport` (sin `isMobile`, que Firefox no admite).
- **Contra producción:** el `webServer` construye y arranca `next start` y arranca la API con el Python del `.venv`. No reutiliza un servidor ya levantado
  (podría ser el de desarrollo); `E2E_REUSE_SERVER=1` lo permite. `E2E_DEBUG_SERVERS=1` muestra los registros de los servidores.
- **Mailpit:** `e2e/helpers/mailpit.ts` sondea cada 250 ms hasta 15 s y elige el correo por el `type` del enlace (`email` o `recovery`); `countMessagesTo`
  comprueba que a una cuenta inexistente no se envía nada. Sin dependencias.
- **Sesiones:** una por rol y motor, iniciada por la interfaz y guardada en `e2e/.auth/` (gitignorada); las pruebas que cierran sesión o prueban el acceso hacen la suya.
  Cuentas nuevas con correo único `e2e-…@example.test`; las pruebas no tocan la base de datos (lo del trigger lo cubre `backend/tests/rls`).
- **Guarda de consola:** una *fixture* falla la prueba si el navegador registra `console.error` o una excepción de página.
- **WebKit** (como Safari) no detiene el Tab en los enlaces por defecto: el enlace «Saltar al contenido» se comprueba en Chromium y Firefox; en WebKit, los campos y el botón.
- **Mutaciones sobre la aplicación (12, con su `next build` cada una):** todas detectadas. Dos casos instructivos: quitar `safeNext` de la acción de entrar **no** fallaba
  ninguna prueba (la página ya saneaba `next` antes de pintar el formulario), así que se añadió una prueba que manipula el campo oculto al enviar y comprueba la segunda
  capa; y quitar `htmlFor` de las etiquetas lo detecta ya la preparación (usa `getByLabel`), de modo que la prueba específica se verificó con una variante (`aria-label` sin etiqueta asociada).
- **Fuera de las pruebas E2E:** cuenta suspendida y API caída (necesitan escribir en la base o parar la API; se comprobaron a mano en el hito 3), accesibilidad automática y Lighthouse.
- **Guarda del backend:** la regla «solo `NEXT_PUBLIC_*`» de `test_frontend_scope` aplica al código de la aplicación (`frontend/src`); las pruebas E2E y su configuración leen variables propias (`CI`, `E2E_*`).

Resueltas en el hito 5 (CI y cierre, 2026-11-04):

- **Workflow** `.github/workflows/ci.yml`: cinco trabajos independientes y en paralelo (`python`, **`rls`** «RLS (NFR-06)», `backend`, `frontend`, `e2e`) sobre `ubuntu-24.04`, con dos
  acciones compuestas (`.github/actions/python-env` y `local-stack`). Permisos `contents: read`, sin secretos de repositorio, `timeout-minutes` en cada trabajo y las actions de terceros
  fijadas por SHA (checkout 7.0.1, setup-node 7.1.0, setup-python 7.1.0, upload-artifact 7.0.2). El informe de Playwright se sube solo si el trabajo falla.
- **Sin filtros de ruta** (ADR-0001 los sugería): un check obligatorio que no se dispara deja el PR bloqueado, y la puerta RLS debe correr siempre. Un ADR aceptado no se edita; manda esta spec.
- **Entorno generado:** `npm run env:local` (`scripts/write-env.mjs`) escribe `.env` y `frontend/.env.local` desde `supabase status -o env`. La clave de servicio es la secreta nueva (`sb_secret_…`) y los tests
  `live` usan la publicable. Con `--ci` enmascara las claves. `supabase start` imprime las claves de la pila en la salida estándar (no son secretas, pero un registro no es sitio para ellas):
  se redirige a `/dev/null`; el progreso y los errores salen por la de error. Sustituye el paso manual del README.
- **Sin omitidos en el CI:** `backend/tests/ci_gate.py` (plugin cargado desde `conftest.py`) termina la sesión con código 1 si existe `CI` y algún test se omitió. Sin él, que faltase
  `TEST_SUPABASE_ANON_KEY` o `SUPABASE_SERVICE_ROLE_KEY` omitía en silencio los tests `live` y `create-admin`: la puerta NFR-06 podía dar un falso verde.
- **La forma del workflow la vigila un test** (`test_ci_workflow.py`): la puerta RLS ejecuta exactamente `pytest backend/tests/rls -m rls -q`, con la pila real y sin `if` ni `continue-on-error`;
  permisos de solo lectura; sin `secrets.`, `pull_request_target` ni expresiones dentro de `run`; SHA con su versión; tiempo máximo; sin filtros de ruta; y **cada comando de §8.2 aparece en el
  workflow** (deriva spec ↔ CI). Dos líneas de §8.2 se ejecutan distinto: el venv (`setup-python` ya deja el intérprete en el PATH) y `playwright install --with-deps` (librerías del sistema de Linux).
- **Validación sin remoto:** `actionlint` 1.7.12 (imagen de Docker Hub, puntual; no se versiona) no da hallazgos y sí detecta errores en una copia rota. **Clon limpio** en `C:\cuadre-clean`: el árbol
  exacto del commit (`git archive` del índice), un `.venv` nuevo, `npm ci`, clave de firma nueva y `CI=true`, repitiendo los pasos de cada trabajo: `python`, `frontend`, pila + `rls` (111), `backend`
  (123) y `e2e` (221 en 2,2 min), todo en verde y con 0 omitidos. El único fallo fue del propio clon (no era un repositorio de git y `test_no_secrets_tracked` necesita `git ls-files`;
  `actions/checkout` sí deja uno). `supabase start -x studio` funciona, `npm run test:scripts` no necesita instalar la raíz y la compilación del frontend se hace con la plantilla `.env.example`.
- **Mutaciones sobre lo nuevo (25):** `ci_gate` (3), `write-env` (6) y workflow, acciones y README (16: puerta sin `-m rls`, `continue-on-error`, `if: false`, action sin SHA o sin versión, permisos de
  escritura, secreto o expresión en `run`, trabajo sin `timeout`, comando de §8.2 ausente, filtro de rutas, RLS sin pila, nombre cambiado, acción sin `shell`, trabajo sin documentar, `supabase start` que
  imprime las claves…). Las 25 las detecta algún test.
- **Sin verificar: la ejecución en un runner de GitHub.** Riesgos conocidos: rutas sensibles a mayúsculas, `localhost` por IPv6, el WebKit de Linux (el salto con Tab ya se comprueba solo en Chromium y
  Firefox), `playwright install --with-deps`, el tiempo (tres trabajos arrancan Supabase: se esperan 10-15 minutos) y los límites de Docker Hub o de la red al bajar las imágenes. Lo normal es que la
  primera ejecución pida algún ajuste.
- **Pendiente, requiere remoto:** primera ejecución del CI y marcar «RLS (NFR-06)» como obligatorio en la protección de `main`. Fuera de esta spec: Lighthouse CI (ADR-0010, propuesto), Dependabot para las
  actions, cachés de imágenes y navegadores, y `npm audit` en el CI.
