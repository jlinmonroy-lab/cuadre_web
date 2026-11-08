-- SPEC-W-005 §5.2 · Políticas de `storage.objects` para el bucket privado `logos`.
--
-- Las políticas llaman a funciones `private.logo_*` (SECURITY DEFINER, STABLE, `search_path = ''`) que NUNCA lanzan una excepción: una
-- carpeta que no sea un uuid es una denegación, no un error. El spike del hito 0 (Anexo B.1) midió que una política en línea con
-- `::uuid` falla con un error («invalid input syntax for type uuid») al consultar `not-a-uuid/x.png`. Todas son `to authenticated`; `anon`
-- no tiene ninguna. Lo que no figura aquí está denegado, también el UPDATE (los archivos no se sobrescriben: cada logo lleva un uuid nuevo).
--
-- Storage evalúa la política de INSERT al FIRMAR la URL de subida, no al subir. Subir y borrar exigen el rol `usuario`: sin esa condición,
-- una gestora o un administrador podrían firmar una subida a su propia carpeta aunque la API no se la ofrezca (T5-04). Leer: el dueño o
-- un gestor con vínculo ACTIVO. El administrador, nada (D3).

-- Dueño de la carpeta de una ruta `{uuid}/{uuid}.{png|jpg|webp}`, o NULL si no tiene exactamente esa forma. La expresión regular va
-- DENTRO del CASE: PostgreSQL no garantiza el orden de evaluación de un AND, y el cast a uuid de una carpeta rara lanzaría un error.
create function private.logo_folder_owner(p_name text) returns uuid
language sql immutable set search_path = ''
as $$
  select case
           when cardinality(parts) = 2
                and parts[1] ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                and parts[2] ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(png|jpg|webp)$'
           then parts[1]::uuid
         end
  from (select string_to_array(p_name, '/') as parts) s
$$;

-- Sube: un `usuario` a su propia carpeta.
create function private.logo_can_upload(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    private.app_role() = 'usuario'::public.user_role and private.logo_folder_owner(p_name) = (select auth.uid()),
    false)
$$;

-- Lee: el dueño de la carpeta, o un gestor con vínculo ACTIVO sobre él. El administrador, nada.
create function private.logo_can_read(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    private.logo_folder_owner(p_name) = (select auth.uid())
    or private.gestor_has_access(private.logo_folder_owner(p_name)),
    false)
$$;

-- Borra: el dueño de la carpeta, siendo `usuario`.
create function private.logo_can_delete(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    private.app_role() = 'usuario'::public.user_role and private.logo_folder_owner(p_name) = (select auth.uid()),
    false)
$$;

create policy logos_objects_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'logos' and private.logo_can_upload(name));

create policy logos_objects_select on storage.objects for select to authenticated
  using (bucket_id = 'logos' and private.logo_can_read(name));

create policy logos_objects_delete on storage.objects for delete to authenticated
  using (bucket_id = 'logos' and private.logo_can_delete(name));

revoke all on all functions in schema private from public;
grant execute on function
  private.logo_can_upload(text), private.logo_can_read(text), private.logo_can_delete(text)
  to authenticated, service_role;
