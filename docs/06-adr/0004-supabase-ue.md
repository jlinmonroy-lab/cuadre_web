# ADR-0004 · Supabase en la UE: PostgreSQL, Auth, RLS y Storage privado

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

La aplicación es 100 % online y trata datos fiscales y personales (RES-08, NFR-11): los datos deben estar en la UE y
cada proveedor debe firmar un contrato de encargado del tratamiento (DEP-06). El charter supone que los servicios
gestionados de Supabase evitan construir autenticación, permisos y almacenamiento desde cero (SUP-05).

## Decisión

- **Supabase** (proyecto en una región de la UE) para PostgreSQL, Auth, seguridad por fila y Storage. En local, la
  pila de Supabase CLI sobre Docker.
- **Las migraciones SQL de `supabase/migrations/` son la única fuente del esquema**, incluidas políticas, funciones y
  triggers. El backend no crea ni altera tablas. Datos de prueba solo sintéticos en `supabase/seed.sql` (RES-07).
- **RLS activada y forzada (`FORCE ROW LEVEL SECURITY`) en toda tabla de `public`.** Una guardia de test falla si
  aparece una tabla sin RLS o sin registrar en `rls_matrix.yaml` (SPEC-W-001, AC-13).
- **El único camino a los datos es el backend.** La Data API de Supabase (PostgREST) se desactiva en local y, en el
  proyecto alojado, no se exponen esquemas. La RLS sigue siendo la barrera de último recurso, pero no se confía en que
  un cliente no vaya a saltarse la API: las reglas críticas están en la base (ADR-0003).
- **Storage con un bucket privado `documents`**, ruta `{owner_id}/{document_id}.{ext}`, con políticas por carpeta del
  dueño y lectura del gestor con vínculo activo. El navegador sube con URL firmada de subida; el servicio de agentes
  lee con URL firmada de corta duración (≈120 s) que emite el backend con el token del usuario.
- **Esquema `private`** para funciones auxiliares (`private.app_role()`, `private.gestor_has_access(...)`, ...),
  sin permisos para `anon` ni `authenticated` salvo `EXECUTE` en las funciones que lo necesitan.
- **Extensiones:** `citext` para correos.

## Alternativas descartadas

- **Postgres propio + autenticación propia.** Contradice SUP-05 y alarga el desarrollo.
- **Firebase u otros BaaS.** Sin RLS en SQL ni región UE equivalente, y el PRD asume Postgres.
- **Exponer PostgREST al frontend.** Reduce código, pero reparte las reglas de negocio y rompe la generación del cliente
  tipado (ADR-0002, ADR-0011).

## Consecuencias

- Las políticas RLS son código de producto: se escriben, se revisan y se prueban como cualquier otro.
- La región exacta y el resto del despliegue se deciden en ADR-0014 (propuesto) cuando existan las cuentas.
- El IBAN del perfil es hoy una columna de texto; su cifrado en reposo queda como pregunta abierta. Los logs lo excluyen
  (NFR-11).
