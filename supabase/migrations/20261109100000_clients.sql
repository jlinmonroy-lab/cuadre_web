-- SPEC-W-006 §5.2 · Clientes (RF-005). La ficha de cada cliente de la persona: nombre, tipo, país, ámbito deducido, identificador fiscal,
-- domicilio y el estado de VIES simulado (D-05).
--
-- Esta tabla no se escribe directamente (ni el dueño): todo pasa por `app.*`, que toman un cerrojo asesor por persona (migración siguiente).
-- La clave a `profiles` es ON DELETE CASCADE porque es la ficha de la persona; las facturas de SPEC-W-007 referenciarán al cliente SIN
-- cascada (CONF-004). Un cliente no se borra: se archiva (D-06).
--
-- La base defiende solo lo barato (D-10): longitudes, el formato del país, que `national` sea España y que el VIES simulado solo marque a
-- una empresa de la UE. Qué países son de la UE, y el NIF o NIF-IVA, lo valida `cuadre.clients` (Anexo B.1). Las restricciones llevan
-- nombre propio para que la API las traduzca por nombre; las probó el spike del hito 0.

create type public.client_scope as enum ('national', 'eu', 'non_eu');
create type public.client_kind as enum ('business', 'individual');
create type public.client_vies_status as enum ('valid_simulated', 'unchecked', 'not_applicable');

create table public.clients (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null references public.profiles (id) on delete cascade,
  name        text not null,
  kind        public.client_kind not null,
  country     text not null,
  scope       public.client_scope not null,
  tax_id      text,            -- clave compacta (el NIF español sin ES, el NIF-IVA con su prefijo, el texto libre en mayúsculas)
  address     text,
  vies_status public.client_vies_status not null default 'not_applicable',
  archived_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint clients_name_length check (char_length(name) between 2 and 200),
  constraint clients_country_format check (country ~ '^[A-Z]{2}$'),
  constraint clients_tax_id_length check (char_length(tax_id) between 1 and 32),
  constraint clients_address_length check (char_length(address) <= 300),
  constraint clients_scope_matches_country check ((scope = 'national') = (country = 'ES')),
  constraint clients_vies_matches_scope check (vies_status = 'not_applicable' or (scope = 'eu' and kind = 'business'))
);

-- Un NIF por persona entre los clientes activos (D-07): los archivados no cuentan y los NULL no chocan.
create unique index clients_owner_tax_id_active on public.clients (owner_id, tax_id)
  where tax_id is not null and archived_at is null;
create index clients_owner on public.clients (owner_id);

alter table public.clients enable row level security;
alter table public.clients force row level security;
revoke all on public.clients from public, anon, authenticated, service_role;

-- Dueño: los suyos, archivados incluidos. Gestor: solo con vínculo activo (se evalúa en cada consulta). Administrador: ninguno (D3).
create policy clients_select_owner on public.clients for select to authenticated
  using (owner_id = (select auth.uid()));

create policy clients_select_gestor on public.clients for select to authenticated
  using (private.gestor_has_access(owner_id));

grant select on public.clients to authenticated;

-- Trigger de seguridad, venga la sentencia de donde venga.
create function private.clients_guard() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.created_at is distinct from old.created_at then
    raise exception 'client_immutable_column' using errcode = 'P0001';
  end if;
  return new;
end
$$;

create trigger clients_guard before update on public.clients
  for each row execute function private.clients_guard();
create trigger clients_touch_updated_at before update on public.clients
  for each row execute function private.touch_updated_at();
