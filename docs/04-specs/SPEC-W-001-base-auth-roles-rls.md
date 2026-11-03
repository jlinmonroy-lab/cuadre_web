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
- Archivos de raíz: `README.md`, `package.json` (CLI de Supabase y scripts), `.github/workflows/ci.yml`; `CLAUDE.md`,
  `.gitignore`, `.env.example` y `.editorconfig` ya existen y se ajustan si hace falta.
- `backend/` con `pyproject.toml` (extra `dev`, versiones fijadas, `contracts/python` como dependencia local) y el paquete
  `backend/src/cuadre/` descrito en §5.6.
- `frontend/` creado con `create-next-app` (App Router, TypeScript estricto, Tailwind v4, ESLint), `shadcn/ui` inicializado,
  `@supabase/ssr`, `openapi-typescript`, `openapi-fetch` y Playwright configurado.
- `supabase/` con `config.toml` y migraciones (§5.2).

### 3.2 Base de datos (migraciones SQL en `supabase/migrations/`)
- Tipos enumerados, extensión `citext`, esquemas `private` y `app`.
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
- Middleware y *layouts* con protección por rol, redirección a la portada de cada rol y página 403.
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
| `internal_error` | 500 | Cualquier otro; `detail` genérico y sin trazas |

**Autenticación del backend.**

1. Se lee `Authorization: Bearer <jwt>`.
2. Se verifica con `PyJWT`: firma contra el JWKS de `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (con caché), algoritmos
   `ES256` y `RS256` únicamente; `aud = "authenticated"`; `iss = {SUPABASE_URL}/auth/v1`; `exp` y `nbf`. `alg: none` se
   rechaza. **No existe camino HS256.** Comprobado el 2026-11-03 con la CLI 3.0: con `[auth] signing_keys_path` apuntando
   a una clave ES256 de desarrollo (`supabase/signing_keys.json`, generada con `npm run gen:signing-key`, gitignorada; el CI la
   genera antes de `supabase start`), la pila local firma con ES256, su JWKS publica esa clave y los tokens llevan
   `iss = http://127.0.0.1:54321/auth/v1` y `aud = authenticated`. Es el mismo camino que usa producción.
3. Se construye `CurrentUser(id, role, status, email, claims)` leyendo `profiles` **dentro de la transacción del usuario**
   (el rol sale de la base de datos, no del token; ADR-0005).
4. `require_role(*roles)` devuelve 403 `forbidden` si el rol no está en la lista; cualquier ruta autenticada devuelve 403
   `account_suspended` si la cuenta no está activa.

### 5.2 Base de datos

Todo en migraciones; el nombre sigue `YYYYMMDDHHMMSS_descripcion.sql`; sin migraciones destructivas.

#### 5.2.1 Tipos y esquemas

```
CREATE EXTENSION IF NOT EXISTS citext;
CREATE SCHEMA private;  -- auxiliares de políticas; sin acceso de lectura directa
CREATE SCHEMA app;      -- funciones que invoca el backend

CREATE TYPE user_role             AS ENUM ('usuario', 'gestor', 'admin');
CREATE TYPE account_status        AS ENUM ('active', 'suspended');
CREATE TYPE gestor_access_status  AS ENUM ('pending', 'active', 'revoked', 'declined');
CREATE TYPE activity_category     AS ENUM ('access', 'account', 'data');
```

#### 5.2.2 Tablas

```
profiles
  id           uuid PK  REFERENCES auth.users(id) ON DELETE CASCADE
  email        citext   NOT NULL UNIQUE
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
  gestor_email  citext NOT NULL
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
| `private.log_activity(p_category, p_actor_id, p_actor_role, p_owner_id, p_action, p_entity_type, p_entity_id, p_metadata)` | inserta en `activity_log` |

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
| `activity_log` | SELECT | filas con `owner_id = auth.uid()` | filas con `actor_id = auth.uid()` | filas con `category = 'account'` |
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
`not_the_owner`, `cannot_modify_self`, `target_not_found`.

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
- `cuadre_jobs`: `LOGIN` con `GRANT service_role TO cuadre_jobs WITH INHERIT TRUE, SET TRUE`. Solo `cuadre.jobs` y `cuadre.cli`.
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
| `/restablecer` | Con el enlace | Fija la nueva contraseña |
| `/inicio` | `usuario` | Portada del autónomo |
| `/cartera` | `gestor` | Portada del gestor |
| `/admin` | `admin` | Portada del administrador |
| `/403` | Con sesión | «No tienes acceso a esta sección», con enlace a su portada |
| `/auth/confirm` | Con el enlace del correo | *Route handler* (sin interfaz): lee `token_hash`, `type` y `next` y llama a `verifyOtp`; con éxito redirige a `next` (por defecto, la portada del rol) y con error, a `/login` con un mensaje |

Los correos de confirmación y de recuperación los envía Supabase Auth con plantillas en español (`supabase/templates/confirmation.html`
y `recovery.html`) cuyos enlaces apuntan a `/auth/confirm` (flujo PKCE de `@supabase/ssr`).

El middleware solo mejora la experiencia (evita parpadeos y redirige); la autorización real está en la API y en la RLS. Un
usuario que abre la portada de otro rol ve `/403`.

**Navegación** (barra lateral ≥ 901 px; barra superior desplazable ≤ 900 px, como el prototipo):

- `usuario`: Inicio, Clientes, Facturas, Gastos, Contabilidad mensual, Trimestres. Solo Inicio está activo; el resto aparece
  desactivado con la etiqueta «Próximamente» y `aria-disabled="true"`.
- `gestor`: Cartera (activa).
- `admin`: Cuentas (desactivada, «Próximamente»).

Pie de la barra: nombre y rol de la persona, y «Cerrar sesión».

**Textos** en español neutro, errores junto al campo y un resumen de errores con `role="alert"`. Los mensajes no revelan si un
correo existe: el fallo de inicio de sesión es siempre «Correo o contraseña incorrectos.» y la recuperación responde igual
exista o no la cuenta.

### 5.4 Variables de entorno

| Variable | La leen | Obligatoria | Notas |
|---|---|---|---|
| `APP_ENV` | backend | sí | `local`, `staging` o `production` |
| `SUPABASE_URL` | backend, jobs | sí | |
| `TEST_DATABASE_ADMIN_URL` | solo los tests | solo para las pruebas | Conexión con el rol `postgres` de la pila local, para crear usuarios y estados de prueba. Ningún código de la aplicación la lee |
| `SUPABASE_SERVICE_ROLE_KEY` | `cuadre.cli` | solo para la CLI | **Nunca** otro módulo ni el frontend |
| `ADMIN_PASSWORD` | `cuadre.cli` | solo para `create-admin` | Contraseña del primer administrador; no se pasa por argumento para que no quede en el historial del terminal |
| `DATABASE_URL` | backend | sí | Rol `cuadre_app` |
| `DATABASE_SERVICE_URL` | `cuadre.jobs`, `cuadre.cli` | solo para ellos | Rol `cuadre_jobs` |
| `FRONTEND_ORIGIN` | backend | sí | Único origen CORS permitido |
| `LOG_LEVEL` | backend | no | Por defecto `INFO` |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | frontend | sí | Públicas por naturaleza |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | sí | URL de la API |

`.env.example` las documenta con marcadores de posición.

### 5.5 Comandos

Con el entorno virtual activado y desde la raíz del repositorio (valen igual en CI):

| Para… | Comando |
|---|---|
| Arrancar Supabase local | `npx supabase start` |
| Recrear la base con migraciones y seed | `npx supabase db reset` |
| Parar Supabase | `npx supabase stop` |
| Arrancar la API | `uvicorn cuadre.main:app --reload --port 8000 --app-dir backend/src` |
| Arrancar el frontend | `npm --prefix frontend run dev` |
| Crear el primer administrador | `python -m cuadre.cli create-admin --email <correo>` (lee la contraseña de `ADMIN_PASSWORD`) |
| Regenerar OpenAPI y cliente | `python backend/scripts/export_openapi.py` y `npm --prefix frontend run gen:api` |

### 5.6 Paquetes del backend

```
backend/src/cuadre/
  main.py          create_app(), registro de rutas y errores; `app = create_app()` para uvicorn
  config.py        Settings (pydantic-settings)
  core/            errors.py (problem+json), auth.py (JWT, CurrentUser, require_role), logging.py
  db/              session.py: user_transaction(claims) y service_connection() — ÚNICO sitio que abre conexiones
  api/             routes_health.py, routes_me.py
  jobs/            __init__.py (vacío; reservado para SPEC-W-012 y 014)
  cli.py           create-admin
backend/tests/
  conftest.py  rls/  api/  rules/
```

## 6. Restricciones técnicas

Cada una tiene un test o una comprobación asociada (§8).

| ID | Restricción |
|---|---|
| T-01 | **Versiones fijadas** (consultadas el 2026-11-03; se confirman al instalar): Python 3.12; FastAPI 0.162; Pydantic 2.14; psycopg 3.3; PyJWT 2.15; pytest 9.2; ruff 0.17; Node 24; Next.js 16.4; React 19.3; Tailwind 4.3; Supabase CLI 3.0; supabase-js 2.118; `@supabase/ssr` 0.12; Playwright 1.64; openapi-typescript 7.13; openapi-fetch 0.17. **TypeScript 5.9.3**: la 7.0.2 (la más reciente) es incompatible, porque `typescript-eslint` 8.72 exige `typescript <6.1` y `openapi-typescript` 7.13 pide `^5.x`. Versiones definitivas de Python y Node: las instaladas en el hito 0; se actualizan aquí al cerrar la spec |
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
| T-13 | **Logs sin tokens, contraseñas ni correos**: solo `request_id`, `user_id`, ruta, código y duración |
| T-14 | **Interfaz** en español, con los tokens de diseño del prototipo, fuentes con `next/font` (nada se pide a Google desde el navegador), sin scroll horizontal a 390 y 1.440 px, foco visible y etiquetas asociadas a cada campo |
| T-15 | **El frontend nunca importa la clave de servicio ni la URL de la base de datos**; solo `NEXT_PUBLIC_*` |
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
    Then ve 0 filas
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
npx supabase start
npx supabase db reset                                   # migraciones + seed sin errores

# 2 · Calidad estática
ruff check backend contracts/tools contracts/python
ruff format --check backend contracts/tools contracts/python
npm --prefix frontend run lint
npm --prefix frontend run typecheck

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
| AC-04 | `frontend/e2e/auth.spec.ts` · «sin sesión»; `backend/tests/api/test_auth.py::test_missing_token` |
| AC-05 | `backend/tests/api/test_auth.py::test_invalid_tokens`, `::test_suspended_account` |
| AC-06 | `backend/tests/rls/test_rls_roles.py::test_no_privilege_escalation` |
| AC-07 | `backend/tests/rls/test_rls_roles.py` (parametrizada con `rls_matrix.yaml`) |
| AC-08 | `backend/tests/rls/test_gestor_access.py::test_active_link` |
| AC-09 | `backend/tests/rls/test_gestor_access.py::test_lifecycle`, `::test_role_change_cuts_access` |
| AC-10 | `backend/tests/rls/test_gestor_access.py::test_gestor_cannot_write` |
| AC-11 | `backend/tests/rls/test_admin.py` |
| AC-12 | `backend/tests/rls/test_activity_log.py` |
| AC-13 | `backend/tests/rls/test_rls_guard.py` |
| AC-14 | `frontend/e2e/responsive.spec.ts` (proyectos 390 y 1.440 px) |
| AC-15 | `backend/tests/rules/test_openapi_drift.py`; `frontend/e2e/bundle.spec.ts` o `npm run check:bundle` |
| T-02 a T-11 | `backend/tests/rules/` (`test_no_float`, `test_service_key_scope`, `test_db_access_scope`, `test_data_api_off`, `test_no_llm_sdk`, `test_operation_ids`, `test_no_secrets_tracked`) |

**`rls_matrix.yaml`** vive en `backend/tests/rls/` y registra, por tabla, su tipo (`identity`, `financial` o `log`), la columna
de dueño y la expectativa de cada rol según §5.2.4. `test_rls_roles` la recorre con un reparto de cinco usuarios creado por la *factory* de cada test y
los estados del vínculo (sin vínculo, pendiente, activo, revocado, rechazado) y comprueba lectura, inserción, actualización y
borrado. `cuadre.db.session` tiene además su propio test de que el rol de una petición **no se filtra** a la siguiente que reutiliza
la misma conexión del pool. Cada spec
posterior que añada una tabla la añade aquí; sin eso, `test_rls_guard` falla.

### 8.4 Definición de hecho

- [ ] La secuencia de §8.2 termina con código 0 en local **y** en el CI.
- [ ] `pytest backend/tests/rls -m rls` marcado como requisito obligatorio de fusión.
- [x] §5.1 actualizado con el resultado de la comprobación JWKS (ES256, sin HS256) y T-01 con el veredicto sobre TypeScript (hito 0).
- [ ] T-01 con las versiones definitivas de todo lo instalado.
- [ ] `docs/04-specs/tasks.json`: SPEC-W-001 en `hecha`.
- [ ] `README.md` con los comandos de §5.5 comprobados en un clon limpio.
- [ ] `docs/00-charter.md` y `docs/03-prd.md` sin cambios.

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
- **Pooler local:** Supavisor en el puerto 54329 con usuarios `<rol>.pooler-dev` (p. ej. `postgres.pooler-dev`); `SET LOCAL ROLE` y las
  claims funcionan a través de él con `prepare_threshold=None`.
- **Seed de usuarios:** `auth.users` solo exige `id` sin valor por defecto; las columnas de token (`confirmation_token`, `recovery_token`,
  `email_change_token_new`, `email_change`, `phone_change`, `phone_change_token`, `email_change_token_current`, `reauthentication_token`)
  se siembran con `''`. Falta comprobar que el inicio de sesión funciona con el seed (hito 1).

Pendientes: la forma exacta del *helper* de Playwright para Mailpit (hito 4) y las versiones definitivas de T-01 (hito 5).
