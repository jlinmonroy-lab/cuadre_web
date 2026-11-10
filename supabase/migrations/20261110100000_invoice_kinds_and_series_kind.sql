-- SPEC-W-007 §5.2 · Tipos de factura y series rectificativas. Migración NUEVA sobre SPEC-W-005: las aplicadas no se tocan; lo que cambia de
-- ellas se sustituye con `create or replace`.
--
-- Una serie es ordinaria (`standard`) o rectificativa (`rectifying`, `R-AAAA`). La rectificativa la crea la emisión, no la persona: no se
-- edita, no es predeterminada y no se archiva (`private.series_lock_own` solo ve las ordinarias), y su código está reservado para que una
-- serie ordinaria no lo use (`series_code_reserved`). La CHECK lo repite por si alguien llega por otro camino. El spike del hito 0 (Anexo
-- B.1-D) midió que el trigger de series ya deja avanzar `next_number` (lo que hace la emisión) y rechaza bajarlo; aquí solo gana `kind`
-- entre las columnas que no cambian nunca.

create type public.invoice_kind as enum ('standard', 'rectifying');
create type public.invoice_tax_treatment as enum
  ('national_vat', 'eu_reverse_charge', 'eu_consumer_vat', 'non_eu_consumer_vat', 'non_eu_not_subject');

alter table public.invoice_series
  add column kind public.invoice_kind not null default 'standard',
  add constraint invoice_series_kind_matches_code check ((kind = 'rectifying') = (code ~ '^R-[0-9]{4}$')),
  add constraint invoice_series_rectifying_not_default check (kind = 'standard' or not is_default);

create or replace function private.invoice_series_guard() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.kind is distinct from old.kind
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

-- Bloquea y devuelve la serie ORDINARIA de quien llama. Mismo error si no existe, es de otra persona o es una rectificativa.
create or replace function private.series_lock_own(p_id uuid) returns public.invoice_series
language plpgsql security definer set search_path = ''
as $$
declare
  v_series public.invoice_series%rowtype;
begin
  select * into v_series from public.invoice_series s
   where s.id = p_id and s.owner_id = (select auth.uid()) and s.kind = 'standard' for update;
  if not found then
    raise exception 'series_not_found' using errcode = 'P0001';
  end if;
  return v_series;
end
$$;

-- Bloquea la serie sobre la que se va a EMITIR: del tipo pedido y activa. Mismo error si no existe, es ajena, es de otro tipo o está
-- archivada. Orden de cerrojos de la emisión: persona (`series_enter`) → esta fila → el cliente → la original.
create function private.series_lock_for_issue(p_id uuid, p_kind public.invoice_kind) returns public.invoice_series
language plpgsql security definer set search_path = ''
as $$
declare
  v_series public.invoice_series%rowtype;
begin
  select * into v_series from public.invoice_series s
   where s.id = p_id and s.owner_id = (select auth.uid()) and s.kind = p_kind and s.archived_at is null for update;
  if not found then
    raise exception 'series_not_found' using errcode = 'P0001';
  end if;
  return v_series;
end
$$;

-- Crea la serie rectificativa del año (`R-AAAA`) si no existe. Idempotente; nunca es la predeterminada. Devuelve su id.
create function app.ensure_rectifying_series(p_year integer) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_code text;
  v_id uuid;
begin
  if p_year is null or p_year not between 2000 and 9999 then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'issue_date';
  end if;
  v_code := 'R-' || p_year::text;
  insert into public.invoice_series (owner_id, code, description, kind, is_default)
  values (v_owner, v_code, 'Rectificativas del año', 'rectifying', false)
  on conflict on constraint invoice_series_owner_code_key do nothing;

  select s.id into v_id from public.invoice_series s where s.owner_id = v_owner and s.code = v_code and s.kind = 'rectifying';
  return v_id;
end
$$;

create or replace function app.create_invoice_series(p_code text, p_description text, p_first_number integer, p_make_default boolean)
returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_description text := nullif(btrim(p_description), '');
  v_first integer := coalesce(p_first_number, 1);
  v_id uuid;
begin
  if p_code is null or p_code !~ '^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$' then
    raise exception 'invalid_series' using errcode = 'P0001', detail = 'code';
  end if;
  if p_code ~ '^R-[0-9]{4}$' then
    raise exception 'series_code_reserved' using errcode = 'P0001';
  end if;
  if char_length(v_description) > 80 then
    raise exception 'invalid_series' using errcode = 'P0001', detail = 'description';
  end if;
  if v_first not between 1 and 999999 then
    raise exception 'invalid_series' using errcode = 'P0001', detail = 'first_number';
  end if;
  if exists (select 1 from public.invoice_series s where s.owner_id = v_owner and s.code = p_code) then
    raise exception 'series_code_taken' using errcode = 'P0001';
  end if;

  if coalesce(p_make_default, false) then
    update public.invoice_series set is_default = false where owner_id = v_owner and is_default;
  end if;
  insert into public.invoice_series (owner_id, code, description, first_number, next_number, is_default)
  values (v_owner, p_code, v_description, v_first, v_first, coalesce(p_make_default, false))
  returning id into v_id;
  return v_id;
end
$$;

create or replace function app.update_invoice_series(p_id uuid, p_changes jsonb) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_series public.invoice_series := private.series_lock_own(p_id);
  v_key text;
  v_code text := v_series.code;
  v_description text := v_series.description;
  v_first integer := v_series.first_number;
  v_next integer := v_series.next_number;
begin
  if p_changes is null or jsonb_typeof(p_changes) <> 'object' then
    raise exception 'invalid_series' using errcode = 'P0001', detail = 'changes';
  end if;
  for v_key in select jsonb_object_keys(p_changes) loop
    if v_key not in ('code', 'description', 'first_number') then
      raise exception 'invalid_series' using errcode = 'P0001', detail = 'changes';
    end if;
  end loop;

  if p_changes ? 'code' then
    if jsonb_typeof(p_changes -> 'code') <> 'string' or (p_changes ->> 'code') !~ '^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$' then
      raise exception 'invalid_series' using errcode = 'P0001', detail = 'code';
    end if;
    if (p_changes ->> 'code') ~ '^R-[0-9]{4}$' then
      raise exception 'series_code_reserved' using errcode = 'P0001';
    end if;
    v_code := p_changes ->> 'code';
  end if;

  if p_changes ? 'description' then
    case jsonb_typeof(p_changes -> 'description')
      when 'null' then v_description := null;
      when 'string' then v_description := nullif(btrim(p_changes ->> 'description'), '');
      else raise exception 'invalid_series' using errcode = 'P0001', detail = 'description';
    end case;
    if char_length(v_description) > 80 then
      raise exception 'invalid_series' using errcode = 'P0001', detail = 'description';
    end if;
  end if;

  if p_changes ? 'first_number' then
    -- Un entero JSON de 1 a 7 cifras: 5.5 y "5" no valen. El cast va DESPUÉS de comprobar la forma, en otra sentencia: PostgreSQL no
    -- garantiza el orden de evaluación de un OR.
    if jsonb_typeof(p_changes -> 'first_number') <> 'number' or (p_changes ->> 'first_number') !~ '^[0-9]{1,7}$' then
      raise exception 'invalid_series' using errcode = 'P0001', detail = 'first_number';
    end if;
    v_first := (p_changes ->> 'first_number')::integer;
    if v_first not between 1 and 999999 then
      raise exception 'invalid_series' using errcode = 'P0001', detail = 'first_number';
    end if;
    -- Solo un número inicial DISTINTO fija el siguiente; el mismo valor no es un cambio (en una serie en uso reiniciaría el contador).
    if v_first <> v_series.first_number then
      v_next := v_first;
    end if;
  end if;

  if (v_code <> v_series.code or v_first <> v_series.first_number) and v_series.next_number > v_series.first_number then
    raise exception 'series_in_use' using errcode = 'P0001';
  end if;
  if v_code <> v_series.code
     and exists (select 1 from public.invoice_series s where s.owner_id = v_owner and s.code = v_code) then
    raise exception 'series_code_taken' using errcode = 'P0001';
  end if;

  update public.invoice_series
     set code = v_code, description = v_description, first_number = v_first, next_number = v_next
   where id = p_id;
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function app.ensure_rectifying_series(integer) to authenticated;
