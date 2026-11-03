-- SPEC-W-001 §5.2.3 · Funciones auxiliares de las políticas (esquema `private`).
--
-- Todas son SECURITY DEFINER con `search_path = ''` (por eso todo va calificado) y las posee `postgres`, que tiene BYPASSRLS: leen
-- `profiles` y `gestor_access` aunque estén con FORCE ROW LEVEL SECURITY, sin recursión de políticas.
-- El rol sale SIEMPRE de `profiles.role`, nunca de claims del JWT (ADR-0005).

-- Rol de la cuenta que hace la petición, o NULL si es anónima, está suspendida o no tiene perfil.
create function private.app_role() returns public.user_role
language sql stable security definer set search_path = ''
as $$
  select p.role from public.profiles p where p.id = (select auth.uid()) and p.status = 'active'
$$;

create function private.is_admin() returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(private.app_role() = 'admin'::public.user_role, false)
$$;

create function private.app_email() returns text
language sql stable security definer set search_path = ''
as $$
  select p.email from public.profiles p where p.id = (select auth.uid())
$$;

-- ¿La cuenta actual es un gestor con vínculo ACTIVO con `p_owner`? Se evalúa en cada consulta: revocar, cambiar el rol del gestor
-- o suspenderlo corta el acceso en la petición siguiente, sin esperar a que caduque ningún token.
create function private.gestor_has_access(p_owner uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(private.app_role() = 'gestor'::public.user_role, false)
     and exists (
       select 1 from public.gestor_access g
       where g.owner_id = p_owner and g.gestor_id = (select auth.uid()) and g.status = 'active'
     )
$$;

-- Única vía de escritura en activity_log. NO es ejecutable por `authenticated`: si lo fuera, cualquiera falsificaría entradas.
-- La invocan las funciones de `app.*` (que son del mismo dueño) y los jobs (service_role).
create function private.log_activity(
  p_category    public.activity_category,
  p_actor_id    uuid,
  p_actor_role  public.user_role,
  p_owner_id    uuid,
  p_action      text,
  p_entity_type text,
  p_entity_id   text,
  p_metadata    jsonb
) returns void
language sql volatile security definer set search_path = ''
as $$
  insert into public.activity_log (category, actor_id, actor_role, owner_id, action, entity_type, entity_id, metadata)
  values (p_category, p_actor_id, p_actor_role, p_owner_id, p_action, p_entity_type, p_entity_id, coalesce(p_metadata, '{}'::jsonb))
$$;

revoke all on all functions in schema private from public;
grant execute on function private.app_role(), private.is_admin(), private.app_email(), private.gestor_has_access(uuid)
  to authenticated, service_role;
grant execute on function private.log_activity(public.activity_category, uuid, public.user_role, uuid, text, text, text, jsonb)
  to service_role;
