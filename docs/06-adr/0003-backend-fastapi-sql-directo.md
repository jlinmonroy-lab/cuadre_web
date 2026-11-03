# ADR-0003 · Backend: FastAPI + Pydantic v2, PostgreSQL por SQL directo con la identidad del usuario

- **Estado:** Aceptado. Parcialmente sustituido por [ADR-0015](0015-psycopg-sincrono.md): el acceso a Postgres es
  **síncrono**, no asíncrono. El resto de esta decisión sigue vigente.
- **Fecha:** 2026-11-03
- **Cambia el enunciado inicial en un punto:** no se accede a los datos a través de PostgREST ni de `supabase-py`.

## Contexto

La API debe cumplir a la vez: RLS aplicada en todo acceso (NFR-06), transacciones (la numeración correlativa de
facturas por serie no admite huecos ni duplicados), importes exactos (RES-02) y trazabilidad de cada casilla fiscal.
El stack de partida es FastAPI + Pydantic v2 sobre Python 3.12.

## Decisión

- **FastAPI + Pydantic v2** sobre Python 3.12, con `operation_id` explícito por ruta (ADR-0011).
- **Postgres por SQL directo con psycopg 3** (con pool; síncrono según ADR-0015), sin ORM. Las consultas se escriben a mano y
  devuelven modelos Pydantic.
- **La identidad del usuario llega a la base de datos en cada petición.** Un único módulo, `cuadre.db.session`,
  abre una transacción y ejecuta, dentro de ella, `SET LOCAL ROLE authenticated` y
  `set_config('request.jwt.claims', <claims>, true)`. Así `auth.uid()` y las políticas RLS se comportan exactamente
  igual que con PostgREST. Al terminar la petición la transacción se cierra y el rol vuelve al original.
- **Dos roles de login, ninguno con `BYPASSRLS`.** `cuadre_app` (`DATABASE_URL`) es el que usa toda petición de usuario:
  no hereda privilegios (`NOINHERIT`) y solo puede hacer `SET ROLE authenticated`, así que una consulta que olvidara
  cambiar de rol falla con «permission denied» en vez de saltarse la RLS en silencio. `cuadre_jobs`
  (`DATABASE_SERVICE_URL`) es miembro de `service_role` y solo lo leen `cuadre.jobs` y `cuadre.cli`.
- **Las funciones que el backend invoca** (aceptar o revocar un acceso, cambiar un rol) viven en el esquema `app`; las
  auxiliares de las políticas, en `private` (ADR-0004).
- **Compatible con el pooler de Supabase en modo transacción:** `SET LOCAL` solo vive dentro de la transacción y se
  desactivan las sentencias preparadas (`prepare_threshold=None`).
- **Ninguna otra parte del código crea conexiones.** Un test comprueba que solo `cuadre.db` abre conexiones y que la
  service key solo aparece en `cuadre.jobs` y `cuadre.cli` (ADR-0005).
- **Las reglas que no pueden saltarse viven en la base de datos**, no solo en la API: inmutabilidad de facturas
  emitidas (RES-03) por trigger, numeración por función `SECURITY DEFINER`, transiciones de acceso del gestor por
  función. Así un acceso por otra vía sigue sin poder romperlas.

## Alternativas descartadas

- **`supabase-py` / PostgREST con el JWT del usuario.** Aplica la RLS sin esfuerzo, pero cada llamada HTTP es una
  transacción distinta: la emisión de factura (comprobar fecha, reservar número, insertar) tendría que escribirse como
  función SQL entera. Además serializa los `numeric` como números JSON, un riesgo de `float` evitable con enteros pero
  que conviene no tener cerca.
- **SQLAlchemy (ORM o Core) + Alembic.** El esquema ya vive en migraciones SQL de Supabase junto con políticas, triggers
  y funciones; un ORM duplicaría el modelo sin aportar a la seguridad. Se reconsidera si el volumen de consultas lo pide.
- **asyncpg.** Más rápido, pero maneja peor las sentencias preparadas con el pooler en modo transacción.

## Consecuencias

- Más SQL escrito a mano; a cambio, cada consulta es explícita y revisable, y los tests ejercitan la base real.
- El código que cambia de rol es crítico para la seguridad: está aislado, tiene tests propios (`tests/rls/`) y se
  revisa con especial atención en cada cambio.
- Los tests de integración necesitan Postgres con el esquema `auth` de Supabase: se usa la pila local de Supabase
  (ADR-0009 y ADR-0010).
