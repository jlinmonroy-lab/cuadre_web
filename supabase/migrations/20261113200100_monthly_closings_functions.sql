-- SPEC-W-012 §5.2 · Escritura del cierre mensual. `SECURITY DEFINER` con `search_path = ''`; errores `P0001` con código estable y sin repetir datos.
--
-- `private.close_month`: solo para el job (`service_role`). Valida la forma y la coherencia del payload ANTES de escribir y lo guarda en una sola sentencia
-- (`INSERT … ON CONFLICT … DO UPDATE … WHERE` la foto difiere): atómica, así que dos ejecuciones a la vez no duplican ni se pisan. Devuelve `'closed'` (fila
-- nueva), `'reopened'` (la foto cambió: `revision + 1`, `closed_at` nuevo, `first_closed_at` intacto) o `'unchanged'` (idéntica: no se toca nada, NFR-09).
-- NO compara el mes con el reloj de la base de datos: el reloj lo inyecta el job (las pruebas simulan fechas de otro año).
--
-- `private.closing_candidates`: a quién se cierra. Solo cuentas `usuario` activas, con su fecha de alta. Nada financiero: las cifras las calcula el job con la
-- identidad de cada persona, como las pantallas.

create function private.close_month(p_owner uuid, p_year integer, p_month integer, p_payload jsonb) returns text
language plpgsql security definer set search_path = ''
as $$
declare
  v_key       text;
  v_item      jsonb;
  v_scope     text;
  v_by_client jsonb;
  v_sum_nat   bigint := 0;
  v_sum_eu    bigint := 0;
  v_sum_non   bigint := 0;
  v_sum_count bigint := 0;
  v_inserted  boolean;
begin
  if p_owner is null or p_year is null or p_month is null or p_year not between 2000 and 9998 or p_month not between 1 and 12
     or p_payload is null or jsonb_typeof(p_payload) is distinct from 'object' then
    raise exception 'invalid_closing' using errcode = 'P0001';
  end if;

  foreach v_key in array array['invoice_count', 'national_cents', 'eu_cents', 'non_eu_cents', 'total_cents', 'expenses_cents'] loop
    if jsonb_typeof(p_payload -> v_key) is distinct from 'number' or (p_payload ->> v_key) !~ '^-?[0-9]{1,15}$' then
      raise exception 'invalid_closing' using errcode = 'P0001';
    end if;
  end loop;

  if (p_payload ->> 'invoice_count')::bigint < 0
     or (p_payload ->> 'total_cents')::bigint is distinct from
        (p_payload ->> 'national_cents')::bigint + (p_payload ->> 'eu_cents')::bigint + (p_payload ->> 'non_eu_cents')::bigint then
    raise exception 'invalid_closing' using errcode = 'P0001';
  end if;

  v_by_client := p_payload -> 'by_client';
  if jsonb_typeof(v_by_client) is distinct from 'array' then
    raise exception 'invalid_closing' using errcode = 'P0001';
  end if;

  for v_item in select value from jsonb_array_elements(v_by_client) loop
    if jsonb_typeof(v_item) is distinct from 'object'
       or jsonb_typeof(v_item -> 'client_id') is distinct from 'string'
       or (v_item ->> 'client_id') !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
       or jsonb_typeof(v_item -> 'name') is distinct from 'string'
       or jsonb_typeof(v_item -> 'scope') is distinct from 'string'
       or (v_item ->> 'scope') not in ('national', 'eu', 'non_eu')
       or jsonb_typeof(v_item -> 'base_cents') is distinct from 'number'
       or (v_item ->> 'base_cents') !~ '^-?[0-9]{1,15}$'
       or jsonb_typeof(v_item -> 'invoice_count') is distinct from 'number'
       or (v_item ->> 'invoice_count') !~ '^[0-9]{1,9}$' then
      raise exception 'invalid_closing' using errcode = 'P0001';
    end if;
    v_scope := v_item ->> 'scope';
    if v_scope = 'national' then
      v_sum_nat := v_sum_nat + (v_item ->> 'base_cents')::bigint;
    elsif v_scope = 'eu' then
      v_sum_eu := v_sum_eu + (v_item ->> 'base_cents')::bigint;
    else
      v_sum_non := v_sum_non + (v_item ->> 'base_cents')::bigint;
    end if;
    v_sum_count := v_sum_count + (v_item ->> 'invoice_count')::bigint;
  end loop;

  -- El desglose por cliente tiene que sumar cada ámbito (y por tanto el total) y el número de facturas ordinarias.
  if v_sum_nat is distinct from (p_payload ->> 'national_cents')::bigint
     or v_sum_eu is distinct from (p_payload ->> 'eu_cents')::bigint
     or v_sum_non is distinct from (p_payload ->> 'non_eu_cents')::bigint
     or v_sum_count is distinct from (p_payload ->> 'invoice_count')::bigint then
    raise exception 'invalid_closing' using errcode = 'P0001';
  end if;

  insert into public.monthly_closings as m
    (owner_id, year, month, invoice_count, national_cents, eu_cents, non_eu_cents, total_cents, expenses_cents, by_client)
  values
    (p_owner, p_year, p_month,
     (p_payload ->> 'invoice_count')::integer, (p_payload ->> 'national_cents')::bigint, (p_payload ->> 'eu_cents')::bigint,
     (p_payload ->> 'non_eu_cents')::bigint, (p_payload ->> 'total_cents')::bigint, (p_payload ->> 'expenses_cents')::bigint,
     v_by_client)
  on conflict (owner_id, year, month) do update
    set invoice_count = excluded.invoice_count,
        national_cents = excluded.national_cents,
        eu_cents = excluded.eu_cents,
        non_eu_cents = excluded.non_eu_cents,
        total_cents = excluded.total_cents,
        expenses_cents = excluded.expenses_cents,
        by_client = excluded.by_client,
        revision = m.revision + 1,
        closed_at = now()
    where (m.invoice_count, m.national_cents, m.eu_cents, m.non_eu_cents, m.total_cents, m.expenses_cents, m.by_client)
          is distinct from
          (excluded.invoice_count, excluded.national_cents, excluded.eu_cents, excluded.non_eu_cents, excluded.total_cents,
           excluded.expenses_cents, excluded.by_client)
  returning (m.xmax = 0) into v_inserted;

  if not found then
    return 'unchanged';
  end if;
  return case when v_inserted then 'closed' else 'reopened' end;
end
$$;

create function private.closing_candidates()
returns table (owner_id uuid, created_at timestamptz)
language sql stable security definer set search_path = ''
as $$
  select p.id, p.created_at
    from public.profiles p
   where p.role = 'usuario'::public.user_role and p.status = 'active'::public.account_status
   order by p.id
$$;

revoke all on function private.close_month(uuid, integer, integer, jsonb) from public;
revoke all on function private.closing_candidates() from public;
grant execute on function private.close_month(uuid, integer, integer, jsonb) to service_role;
grant execute on function private.closing_candidates() to service_role;
