# ADR-0005 · Autenticación, roles y autorización

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

Hay tres roles (usuario, gestor, administrador) y un riesgo de impacto alto (R-04): fuga de datos entre usuarios o
acceso indebido de un gestor o del administrador. NFR-06 exige 0 accesos indebidos, incluido el gestor tras revocar.
Decisiones de producto vigentes: CONF-001 opción (a), y las respuestas D1–D3 de la sesión de arranque.

## Decisión

**Autenticación.** Supabase Auth con correo y contraseña (registro, login, recuperación). La API valida el JWT en cada
petición: firma por JWKS (algoritmos asimétricos), `iss`, `aud=authenticated` y `exp`. Si el CLI local aún firmara con
secreto simétrico (HS256), se admite solo en desarrollo; se confirma en SPEC-W-001.

**Roles.** El rol vive en `profiles.role` (`usuario`, `gestor`, `admin`) y se lee de la base de datos con
`private.app_role()`, nunca de claims del JWT: así una baja o un cambio de rol surte efecto en la petición siguiente,
sin esperar a que caduque el token. Ninguna política usa `user_metadata`.

- El registro libre crea siempre `usuario` (D1).
- El administrador da de alta o promueve cuentas de gestor.
- El primer administrador se crea con `cuadre.cli create-admin`.
- Un administrador no puede cambiar su propio rol ni su estado.

**Acceso del gestor (CONF-001 a + D1 + D2).**

- El usuario invita por correo; el gestor acepta dentro de la aplicación, autenticado y con el correo coincidente.
  No hay tokens de invitación, y así no se revela si un correo tiene cuenta.
- El vínculo (`gestor_access.status = 'active'`) se comprueba **en cada consulta** (`private.gestor_has_access`), de modo
  que revocar corta el acceso de inmediato.
- El gestor **solo lee**. La única tabla en la que escribe es `gestor_notes` (anotaciones y marcas de revisión), visible
  para el usuario.
- Cada acción del gestor queda en `activity_log`. Las lecturas se registran en la API con un `owner_scope`, porque la
  base de datos no puede auditar un SELECT.

**Administrador (D3).** Sin ninguna política sobre tablas financieras. Ve metadatos de cuenta, los eventos de actividad de
categoría `account` y la base de conocimiento. El acceso de soporte con consentimiento queda fuera de la v1.

**Reglas de implementación.** `FORCE ROW LEVEL SECURITY` en todo; las funciones `SECURITY DEFINER` fijan
`search_path = ''`; los cambios de estado sensibles (aceptar o revocar un acceso, cambiar un rol) son funciones que
escriben `activity_log` en la misma transacción; `activity_log` solo admite inserciones (`REVOKE UPDATE, DELETE`
incluso para `service_role`).

**La service key de Supabase** solo se usa en `cuadre.jobs` y `cuadre.cli`. Nunca en el frontend ni en rutas que actúan
en nombre de un usuario. Un test lo comprueba leyendo el código.

## Alternativas descartadas

- **Rol como claim del JWT mediante un hook de Auth.** Más cómodo en el cliente, pero hereda el retraso del token: un
  gestor revocado seguiría con acceso hasta que renovase la sesión.
- **Roles de Postgres distintos por rol de aplicación.** Complica el pool y no aporta frente a las políticas por
  función.
- **Invitaciones con enlace y token.** Útiles si el gestor no tuviera cuenta; con el alta por el administrador solo
  añaden superficie de ataque.

## Consecuencias

- `test_rls_roles` (NFR-06) es puerta de despliegue y se amplía en cada spec que añade una tabla.
- El panel del administrador no puede mostrar importes de nadie en esta versión.
- Hay una pequeña carga por petición: una lectura de `profiles` para el rol. Es despreciable frente al riesgo que evita.
