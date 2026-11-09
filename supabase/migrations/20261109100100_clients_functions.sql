-- SPEC-W-006 §5.2 · Escrituras de clientes. Todas son `SECURITY DEFINER` con `search_path = ''`, verifican `auth.uid()` y que el rol es
-- `usuario` (`42501` si no; también con la cuenta suspendida, porque `private.app_role()` exige `status = 'active'`) y devuelven errores
-- `P0001` con un código estable en el mensaje y, si procede, el campo en el `DETAIL`.
--
-- TODAS toman primero un cerrojo asesor por persona (`private.clients_enter`), como `private.series_enter` de SPEC-W-005: el spike del hito 0
-- (Anexo B.1-C) midió que dos altas a la vez con el mismo NIF, sin cerrojo, hacían fallar a una con 23505 en el índice, y con él la segunda
-- espera y recibe `client_tax_id_taken`. Por la misma razón, `client_tax_id_taken` se comprueba ANTES de escribir (también al reactivar:
-- el índice daría un 23505 sin código útil).
--
-- Lo que estas funciones NO garantizan (de eso se ocupa `cuadre.clients`): que el NIF sea válido, qué países son de la UE o el texto de los
-- mensajes. Comprueban lo barato; el resto lo defienden las CHECK. `kind`, `scope` y `vies_status` entran como texto y se validan antes de
-- convertirlos: un valor desconocido sería un 22P02 sin código útil.

-- Comprueba el rol, toma el cerrojo de la persona y devuelve su id.
create function private.clients_enter() returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('clients:' || v_owner::text, 0));
  return v_owner;
end
$$;

-- Bloquea y devuelve el cliente de quien llama. Mismo error si no existe o es de otra persona.
create function private.clients_lock_own(p_id uuid) returns public.clients
language plpgsql security definer set search_path = ''
as $$
declare
  v_client public.clients%rowtype;
begin
  select * into v_client from public.clients c where c.id = p_id and c.owner_id = (select auth.uid()) for update;
  if not found then
    raise exception 'client_not_found' using errcode = 'P0001';
  end if;
  return v_client;
end
$$;

-- ¿Hay otro cliente ACTIVO de la persona con ese identificador? `p_except` excluye la propia fila al editar o reactivar.
create function private.clients_tax_id_taken(p_owner uuid, p_tax_id text, p_except uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select p_tax_id is not null and exists (
    select 1 from public.clients c
     where c.owner_id = p_owner and c.tax_id = p_tax_id and c.archived_at is null and (p_except is null or c.id <> p_except)
  )
$$;

-- Lo barato, con el campo en el `DETAIL`. Recibe los valores ya recortados.
create function private.clients_validate(
  p_name text, p_kind text, p_country text, p_scope text, p_tax_id text, p_address text, p_vies_status text
) returns void
language plpgsql set search_path = ''
as $$
begin
  if p_name is null or char_length(p_name) not between 2 and 200 then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'name';
  end if;
  if p_kind is null or p_kind not in ('business', 'individual') then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'kind';
  end if;
  if p_country is null or p_country !~ '^[A-Z]{2}$' then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'country';
  end if;
  if p_scope is null or p_scope not in ('national', 'eu', 'non_eu') or (p_scope = 'national') <> (p_country = 'ES') then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'scope';
  end if;
  if p_tax_id is not null and char_length(p_tax_id) not between 1 and 32 then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'tax_id';
  end if;
  if char_length(p_address) > 300 then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'address';
  end if;
  if p_vies_status is null or p_vies_status not in ('valid_simulated', 'unchecked', 'not_applicable')
     or (p_vies_status <> 'not_applicable' and not (p_scope = 'eu' and p_kind = 'business')) then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'vies_status';
  end if;
end
$$;

-- Crea un cliente. El nombre y el domicilio se guardan recortados (el domicilio vacío es NULL). Un identificador ya usado por otro cliente
-- activo es `client_tax_id_taken`. Devuelve su id.
create function app.create_client(
  p_name text, p_kind text, p_country text, p_scope text, p_tax_id text, p_address text, p_vies_status text
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.clients_enter();
  v_name text := btrim(p_name);
  v_tax text := nullif(btrim(p_tax_id), '');
  v_address text := nullif(btrim(p_address), '');
  v_id uuid;
begin
  perform private.clients_validate(v_name, p_kind, p_country, p_scope, v_tax, v_address, p_vies_status);
  if private.clients_tax_id_taken(v_owner, v_tax, null) then
    raise exception 'client_tax_id_taken' using errcode = 'P0001';
  end if;
  insert into public.clients (owner_id, name, kind, country, scope, tax_id, address, vies_status)
  values (v_owner, v_name, p_kind::public.client_kind, p_country, p_scope::public.client_scope, v_tax, v_address,
          p_vies_status::public.client_vies_status)
  returning id into v_id;
  return v_id;
end
$$;

-- Sustituye todos los campos de un cliente ACTIVO (`client_archived` si está archivado: se reactiva antes). Orden de las comprobaciones:
-- no existe o es ajeno, archivado, forma de los campos y, por último, identificador repetido (sin contar la propia fila).
create function app.update_client(
  p_id uuid, p_name text, p_kind text, p_country text, p_scope text, p_tax_id text, p_address text, p_vies_status text
) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.clients_enter();
  v_client public.clients := private.clients_lock_own(p_id);
  v_name text := btrim(p_name);
  v_tax text := nullif(btrim(p_tax_id), '');
  v_address text := nullif(btrim(p_address), '');
begin
  if v_client.archived_at is not null then
    raise exception 'client_archived' using errcode = 'P0001';
  end if;
  perform private.clients_validate(v_name, p_kind, p_country, p_scope, v_tax, v_address, p_vies_status);
  if private.clients_tax_id_taken(v_owner, v_tax, p_id) then
    raise exception 'client_tax_id_taken' using errcode = 'P0001';
  end if;
  update public.clients
     set name = v_name, kind = p_kind::public.client_kind, country = p_country, scope = p_scope::public.client_scope,
         tax_id = v_tax, address = v_address, vies_status = p_vies_status::public.client_vies_status
   where id = p_id;
end
$$;

-- Archiva o reactiva. Archivar uno ya archivado no cambia `archived_at` (idempotente). Reactivar uno cuyo identificador ya usa un cliente
-- activo es `client_tax_id_taken`: se comprueba antes, porque el índice parcial daría un 23505 sin código útil (Anexo B.1-C).
create function app.set_client_archived(p_id uuid, p_archived boolean) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.clients_enter();
  v_client public.clients := private.clients_lock_own(p_id);
begin
  if p_archived is null then
    raise exception 'invalid_client' using errcode = 'P0001', detail = 'archived';
  end if;
  if not p_archived and v_client.archived_at is not null
     and private.clients_tax_id_taken(v_owner, v_client.tax_id, p_id) then
    raise exception 'client_tax_id_taken' using errcode = 'P0001';
  end if;
  update public.clients
     set archived_at = case when p_archived then coalesce(archived_at, now()) else null end
   where id = p_id;
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function
  app.create_client(text, text, text, text, text, text, text),
  app.update_client(uuid, text, text, text, text, text, text, text),
  app.set_client_archived(uuid, boolean)
  to authenticated;
