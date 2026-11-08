-- SPEC-W-005 §5.2 · Series de facturación (D-03). Configuración por persona: el código, un número inicial y cuál es la predeterminada.
--
-- SPEC-W-007 numerará de forma correlativa dentro de cada serie y avanzará `next_number` al emitir; por eso aquí no hace falta saber de
-- facturas: «en uso» es `next_number > first_number`. Esta tabla no se escribe directamente (ni el dueño): todo pasa por `app.*`, que toman
-- un cerrojo asesor por persona (migración siguiente). La clave a `profiles` es ON DELETE CASCADE porque es configuración; las facturas de
-- SPEC-W-007 referenciarán la serie SIN cascada (CONF-004).
--
-- Todas las restricciones llevan nombre propio para que la API las traduzca por nombre. El trigger es la v2 del spike (Anexo B.1): la v1
-- dejaba bajar `first_number` sin tocar `next_number` y la serie quedaba «en uso» sin haberse emitido nada.

create table public.invoice_series (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid not null references public.profiles (id) on delete cascade,
  code         text not null,
  description  text,
  first_number integer not null default 1,
  next_number  integer not null default 1,
  is_default   boolean not null default false,
  archived_at  timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint invoice_series_code_format check (code ~ '^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$'),
  constraint invoice_series_description_length check (char_length(description) <= 80),
  constraint invoice_series_first_number_range check (first_number between 1 and 999999),
  constraint invoice_series_next_number_range check (next_number <= 1000000),
  constraint invoice_series_next_not_below_first check (next_number >= first_number),
  constraint invoice_series_default_not_archived check (not (is_default and archived_at is not null)),
  constraint invoice_series_owner_code_key unique (owner_id, code)   -- también las archivadas: un código no se reutiliza
);

-- Una sola predeterminada por persona.
create unique index invoice_series_one_default on public.invoice_series (owner_id) where is_default;

alter table public.invoice_series enable row level security;
alter table public.invoice_series force row level security;
revoke all on public.invoice_series from public, anon, authenticated, service_role;

-- Dueño: las suyas, archivadas incluidas. Gestor: solo con vínculo activo (se evalúa en cada consulta). Administrador: ninguna (D3).
create policy invoice_series_select_owner on public.invoice_series for select to authenticated
  using (owner_id = (select auth.uid()));

create policy invoice_series_select_gestor on public.invoice_series for select to authenticated
  using (private.gestor_has_access(owner_id));

grant select on public.invoice_series to authenticated;

-- Trigger de seguridad, venga la sentencia de donde venga.
create function private.invoice_series_guard() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.created_at is distinct from old.created_at then
    raise exception 'series_immutable_column' using errcode = 'P0001';
  end if;

  -- Una serie con facturas emitidas no cambia de código ni de número inicial.
  if (new.code is distinct from old.code or new.first_number is distinct from old.first_number)
     and old.next_number > old.first_number then
    raise exception 'series_in_use' using errcode = 'P0001';
  end if;

  -- Si cambia el número inicial, el siguiente es ese mismo: sin esto, bajarlo dejaba una serie sin uso con next_number > first_number,
  -- es decir, «en uso» sin haberse emitido nada.
  if new.first_number is distinct from old.first_number and new.next_number is distinct from new.first_number then
    raise exception 'series_first_number_mismatch' using errcode = 'P0001';
  end if;

  -- El siguiente número no baja nunca, salvo en una serie sin uso a la que se cambia el número inicial (comprobado arriba).
  if new.next_number < old.next_number
     and not (old.next_number = old.first_number and new.next_number = new.first_number) then
    raise exception 'series_number_regression' using errcode = 'P0001';
  end if;
  return new;
end
$$;

create trigger invoice_series_guard before update on public.invoice_series
  for each row execute function private.invoice_series_guard();
create trigger invoice_series_touch_updated_at before update on public.invoice_series
  for each row execute function private.touch_updated_at();

revoke all on all functions in schema private from public;
