-- SPEC-W-007 §5.2 · Bucket privado `invoices` y sus políticas de `storage.objects` (D-03, ADR-0004, B.1-C).
--
-- Un PDF típico de factura mide de 8 a 18 KB: el límite es 1 MiB y solo `application/pdf`. Storage no mira el contenido (Anexo B.1): la
-- huella SHA-256 que guarda `invoice_files` manda en cada descarga (T7-10). Ruta: `{owner_id}/{invoice_id}-{sha256[:16]}.pdf`; el prefijo
-- de la huella hace IDEMPOTENTE la subida (el mismo contenido da siempre la misma ruta y un 409 de Storage significa «ya está»).
--
-- Mismo método que `logos` (SPEC-W-005): las políticas llaman a funciones `private.invoice_file_*` (SECURITY DEFINER, STABLE,
-- `search_path = ''`) que NUNCA lanzan una excepción: una carpeta que no sea un uuid es una denegación, no un error (B.1-C lo midió). Todas
-- son `to authenticated`; `anon` no tiene ninguna. Solo hay política de INSERT y de SELECT: sin UPDATE ni DELETE, reemplazar o borrar un PDF
-- ya subido da 403, así que nadie puede sustituirlo. Storage evalúa la política de INSERT al FIRMAR la URL de subida, no al subir: subir exige
-- el rol `usuario` (un gestor o un administrador no pueden firmar una subida a su propia carpeta). Leer: el dueño o un gestor con vínculo
-- ACTIVO; el administrador, nada (D3). Idempotente en el bucket: volver a aplicarlo restablece los límites y lo deja privado.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('invoices', 'invoices', false, 1048576, array['application/pdf'])
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- Dueño de la carpeta de una ruta `{uuid}/{uuid}-{16 hex}.pdf`, o NULL si no tiene exactamente esa forma. La expresión regular va DENTRO
-- del CASE: PostgreSQL no garantiza el orden de evaluación de un AND, y el cast a uuid de una carpeta rara lanzaría un error.
create function private.invoice_file_folder_owner(p_name text) returns uuid
language sql immutable set search_path = ''
as $$
  select case
           when cardinality(parts) = 2
                and parts[1] ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                and parts[2] ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9a-f]{16}\.pdf$'
           then parts[1]::uuid
         end
  from (select string_to_array(p_name, '/') as parts) s
$$;

-- Sube: un `usuario` a su propia carpeta.
create function private.invoice_file_can_upload(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    private.app_role() = 'usuario'::public.user_role and private.invoice_file_folder_owner(p_name) = (select auth.uid()),
    false)
$$;

-- Lee: el dueño de la carpeta, o un gestor con vínculo ACTIVO sobre él. El administrador, nada.
create function private.invoice_file_can_read(p_name text) returns boolean
language sql stable security definer set search_path = ''
as $$
  select coalesce(
    private.invoice_file_folder_owner(p_name) = (select auth.uid())
    or private.gestor_has_access(private.invoice_file_folder_owner(p_name)),
    false)
$$;

create policy invoices_objects_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'invoices' and private.invoice_file_can_upload(name));

create policy invoices_objects_select on storage.objects for select to authenticated
  using (bucket_id = 'invoices' and private.invoice_file_can_read(name));

revoke all on all functions in schema private from public;
grant execute on function private.invoice_file_can_upload(text), private.invoice_file_can_read(text)
  to authenticated, service_role;
