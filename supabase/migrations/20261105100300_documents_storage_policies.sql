-- SPEC-W-002 §5.2 · Políticas de `storage.objects` para el bucket privado `documents`.
--
-- Las políticas llaman a funciones `private.document_*` (SECURITY DEFINER, STABLE, `search_path = ''`) que NUNCA lanzan una excepción:
-- una carpeta que no sea un uuid es una denegación, no un error 500. Todas las políticas son `to authenticated`; `anon` no tiene
-- ninguna. Lo que no figura aquí está denegado, también el UPDATE (los archivos no se sobrescriben).
--
-- Storage evalúa la política de INSERT al FIRMAR la URL de subida, no al subir (spike del hito 0, Anexo B).

-- Dueño de la carpeta de una ruta `{uuid}/{archivo}`, o NULL si no tiene exactamente esa forma (una carpeta y un archivo).
create function private.document_folder_owner(p_name text) returns uuid
language sql immutable set search_path = ''
as $$
  select case
           when cardinality(parts) = 2 and parts[2] <> '' and parts[1] ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           then parts[1]::uuid
         end
  from (select string_to_array(p_name, '/') as parts) s
$$;

-- Sube: un `usuario` a una ruta que la API le reservó (fila suya en `uploading` con esa ruta exacta).
create function private.document_can_upload(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(private.app_role() = 'usuario'::public.user_role, false)
     and exists (
       select 1 from public.documents d
        where d.storage_path = p_name and d.owner_id = (select auth.uid()) and d.status = 'uploading'
     )
$$;

-- Lee: el dueño de la carpeta, o un gestor con vínculo ACTIVO sobre él. El administrador, nada.
create function private.document_can_read(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    private.document_folder_owner(p_name) = (select auth.uid())
    or private.gestor_has_access(private.document_folder_owner(p_name)),
    false)
$$;

-- Borra: el dueño de la carpeta, mientras ninguna fila `registered` use esa ruta. Sin fila (archivo huérfano) también puede.
create function private.document_can_delete(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
           private.app_role() = 'usuario'::public.user_role and private.document_folder_owner(p_name) = (select auth.uid()),
           false)
     and not exists (select 1 from public.documents d where d.storage_path = p_name and d.status = 'registered')
$$;

create policy documents_objects_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'documents' and private.document_can_upload(name));

create policy documents_objects_select on storage.objects for select to authenticated
  using (bucket_id = 'documents' and private.document_can_read(name));

create policy documents_objects_delete on storage.objects for delete to authenticated
  using (bucket_id = 'documents' and private.document_can_delete(name));

revoke all on all functions in schema private from public;
grant execute on function
  private.document_can_upload(text), private.document_can_read(text), private.document_can_delete(text)
  to authenticated, service_role;
