-- SPEC-W-005 §5.2 · Funciones `app.*` de series de facturación y del logo. Son la ÚNICA vía de escritura en `invoice_series` y en
-- `business_profiles.logo_path`.
--
-- Mismo patrón que SPEC-W-002 y SPEC-W-003: SECURITY DEFINER con `search_path = ''`, comprueban quién llama con auth.uid() y
-- private.app_role() (solo `usuario`: un gestor o un administrador reciben 42501), errores P0001 con un código estable en el mensaje
-- (`series_not_found`, `series_code_taken`, `series_in_use`, `series_is_default`, `series_archived`, `invalid_series` con el campo en el
-- DETAIL, `invalid_logo`, `profile_not_found`). Una serie ajena responde igual que una inexistente. No escriben `activity_log` (§4).
--
-- TODAS toman primero un cerrojo asesor por persona (`private.series_enter`), como `documents.processing`: el spike del hito 0 (Anexo B.1)
-- midió que `ensure_year_series` y `create_invoice_series(…, predeterminada)` a la vez hacían fallar a una con 23505 en el índice de la
-- predeterminada. Con el cerrojo la segunda espera y ve lo que hizo la primera.
--
-- Lo que estas funciones NO garantizan (de eso se ocupa `cuadre.profile`): los mensajes, la normalización del código a mayúsculas o que el
-- logo sea una imagen de verdad. Comprueban lo barato; el resto lo defienden las CHECK y el trigger de `invoice_series`.

-- Comprueba el rol, toma el cerrojo de la persona y devuelve su id.
create function private.series_enter() returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('invoice_series:' || v_owner::text, 0));
  return v_owner;
end
$$;

-- Bloquea y devuelve la serie de quien llama. Mismo error si no existe o es de otra persona.
create function private.series_lock_own(p_id uuid) returns public.invoice_series
language plpgsql security definer set search_path = ''
as $$
declare
  v_series public.invoice_series%rowtype;
begin
  select * into v_series from public.invoice_series s where s.id = p_id and s.owner_id = (select auth.uid()) for update;
  if not found then
    raise exception 'series_not_found' using errcode = 'P0001';
  end if;
  return v_series;
end
$$;

-- Crea la serie del año si no existe (código = año de hoy en Europe/Madrid). Idempotente. Es la predeterminada solo si la persona no
-- tiene otra. Devuelve su id. La llama `update_profile` y, antes de emitir, SPEC-W-007.
create function app.ensure_year_series() returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_code text := to_char(private.today_madrid(), 'YYYY');
  v_id uuid;
begin
  insert into public.invoice_series (owner_id, code, description, is_default)
  values (v_owner, v_code, 'Serie del año',
          not exists (select 1 from public.invoice_series s where s.owner_id = v_owner and s.is_default))
  on conflict on constraint invoice_series_owner_code_key do nothing;

  select s.id into v_id from public.invoice_series s where s.owner_id = v_owner and s.code = v_code;
  return v_id;
end
$$;

-- Crea una serie. `p_description` se guarda recortada (vacía = NULL); `p_first_number` vacío vale 1; si es predeterminada, quita la marca
-- a la anterior. Un código repetido, también entre las archivadas, es `series_code_taken`.
create function app.create_invoice_series(p_code text, p_description text, p_first_number integer, p_make_default boolean)
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

-- Cambia el código, la descripción y/o el número inicial. `p_changes` es un objeto JSON con solo lo que cambia: una clave ausente no se toca
-- y `"description": null` la borra. `code` y `first_number` solo cambian si la serie no está en uso (`series_in_use`); cambiar el número
-- inicial fija también el siguiente.
create function app.update_invoice_series(p_id uuid, p_changes jsonb) returns void
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

-- La hace predeterminada y quita la marca a la anterior. Una archivada no puede serlo.
create function app.set_default_invoice_series(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_series public.invoice_series := private.series_lock_own(p_id);
begin
  if v_series.archived_at is not null then
    raise exception 'series_archived' using errcode = 'P0001';
  end if;
  if v_series.is_default then
    return;
  end if;
  update public.invoice_series set is_default = false where owner_id = v_owner and is_default;
  update public.invoice_series set is_default = true where id = p_id;
end
$$;

-- Archiva o reactiva. Archivar la predeterminada es `series_is_default` (hay que elegir otra antes): se comprueba aquí y no se deja que
-- salte la CHECK de la tabla, que daría un 23514 sin un código útil.
create function app.set_invoice_series_archived(p_id uuid, p_archived boolean) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_series public.invoice_series := private.series_lock_own(p_id);
begin
  if p_archived is null then
    raise exception 'invalid_series' using errcode = 'P0001', detail = 'archived';
  end if;
  if p_archived and v_series.is_default then
    raise exception 'series_is_default' using errcode = 'P0001';
  end if;
  update public.invoice_series
     set archived_at = case when p_archived then coalesce(archived_at, now()) else null end
   where id = p_id;
end
$$;

-- Guarda la ruta del logo de quien llama y devuelve la ANTERIOR (o NULL) para que la API borre ese objeto. La ruta ha de ser
-- `{auth.uid()}/{uuid}.{png|jpg|webp}`: `logo_path` no se puede escribir directamente (D-13).
create function app.set_business_logo(p_path text) returns text
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_old text;
begin
  if p_path is null
     or p_path !~ ('^' || v_owner::text || '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(png|jpg|webp)$') then
    raise exception 'invalid_logo' using errcode = 'P0001';
  end if;
  select b.logo_path into v_old from public.business_profiles b where b.owner_id = v_owner for update;
  if not found then
    raise exception 'profile_not_found' using errcode = 'P0001';
  end if;
  update public.business_profiles set logo_path = p_path where owner_id = v_owner;
  return v_old;
end
$$;

-- Quita el logo y devuelve la ruta que tenía (o NULL). Sin logo no hace nada.
create function app.clear_business_logo() returns text
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_old text;
begin
  select b.logo_path into v_old from public.business_profiles b where b.owner_id = v_owner for update;
  if not found then
    raise exception 'profile_not_found' using errcode = 'P0001';
  end if;
  if v_old is not null then
    update public.business_profiles set logo_path = null where owner_id = v_owner;
  end if;
  return v_old;
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function
  app.ensure_year_series(),
  app.create_invoice_series(text, text, integer, boolean),
  app.update_invoice_series(uuid, jsonb),
  app.set_default_invoice_series(uuid),
  app.set_invoice_series_archived(uuid, boolean),
  app.set_business_logo(text),
  app.clear_business_logo()
  to authenticated;
