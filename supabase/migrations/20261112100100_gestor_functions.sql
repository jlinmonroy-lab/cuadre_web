-- SPEC-W-010 §5.2 · Funciones del acceso del gestor. Todas son `SECURITY DEFINER` con `search_path = ''`, verifican `auth.uid()` y el rol (`42501` si no;
-- también con la cuenta suspendida, porque `private.app_role()` exige `status = 'active'`) y devuelven errores `P0001` con un código estable en el mensaje
-- y, si procede, el campo en el `DETAIL`. Escriben su rastro en `activity_log` EN LA MISMA TRANSACCIÓN (si la acción falla, no queda rastro).
--
-- Sin enumeración de cuentas (T10-04): ninguna revela si un correo pertenece a un gestor, a un autónomo o a nadie.

-- Invita a un gestor por correo (D-01). Pasa a minúsculas, comprueba lo barato, retira las invitaciones PENDIENTES CADUCADAS de esa pareja (el índice
-- parcial único las cuenta como abiertas y bloquearía para siempre volver a invitar) y respeta el límite de invitaciones abiertas (P-04: 5). Un cerrojo
-- asesor por persona evita que dos invitaciones a la vez pasen del límite.
create function app.invite_gestor_access(p_email text) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := auth.uid();
  v_email text := lower(btrim(coalesce(p_email, '')));
  v_id uuid;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('gestor_access:' || v_owner::text, 0));

  if char_length(v_email) not between 3 and 254 or v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' then
    raise exception 'invalid_email' using errcode = 'P0001';
  end if;
  if v_email = private.app_email() then
    raise exception 'cannot_invite_self' using errcode = 'P0001';
  end if;

  update public.gestor_access
     set status = 'revoked', revoked_at = now()
   where owner_id = v_owner and gestor_email = v_email and status = 'pending' and expires_at < now();

  if exists (
    select 1 from public.gestor_access g
     where g.owner_id = v_owner and g.gestor_email = v_email and g.status in ('pending', 'active')
  ) then
    raise exception 'gestor_access_already_open' using errcode = 'P0001';
  end if;
  if (
    select count(*) from public.gestor_access g
     where g.owner_id = v_owner and (g.status = 'active' or (g.status = 'pending' and g.expires_at >= now()))
  ) >= 5 then
    raise exception 'too_many_open_invitations' using errcode = 'P0001';
  end if;

  insert into public.gestor_access (owner_id, gestor_email) values (v_owner, v_email) returning id into v_id;

  perform private.log_activity('access', v_owner, 'usuario', v_owner, 'gestor_access.invited', 'gestor_access', v_id::text, '{}'::jsonb);
  return v_id;
end
$$;

-- Las invitaciones pendientes (no caducadas) dirigidas al gestor que llama, con el nombre de quien le invita. Hace falta una función: antes de aceptar,
-- el gestor NO puede leer el perfil del autónomo (su política exige vínculo activo).
create function app.list_gestor_invitations()
returns table (id uuid, owner_name text, invited_at timestamptz, expires_at timestamptz)
language plpgsql stable security definer set search_path = ''
as $$
begin
  if private.app_role() is distinct from 'gestor'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  return query
    select g.id, p.display_name, g.invited_at, g.expires_at
      from public.gestor_access g
      join public.profiles p on p.id = g.owner_id
     where g.status = 'pending' and g.expires_at >= now()
       and (g.gestor_email = private.app_email() or g.gestor_id = auth.uid())
     order by g.invited_at desc, g.id;
end
$$;

-- Registra una lectura del gestor (D-06). Es la ÚNICA vía para que un gestor escriba `gestor.read`: comprueba el vínculo activo. Solo ids, tipo y,
-- si procede, el periodo pedido; nunca importes, nombres, NIF ni IBAN.
create function app.log_gestor_read(p_owner uuid, p_entity_type text, p_entity_id text, p_metadata jsonb default null) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
begin
  if private.app_role() is distinct from 'gestor'::public.user_role or not private.gestor_has_access(p_owner) then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  if p_entity_type is null or p_entity_type not in (
       'portfolio', 'invoices', 'invoice', 'invoice_pdf', 'expenses', 'documents', 'document_original', 'profile', 'clients',
       'modelo_303', 'modelo_130', 'notes') then
    raise exception 'invalid_read' using errcode = 'P0001', detail = 'entity_type';
  end if;
  if p_entity_id is not null and char_length(p_entity_id) > 64 then
    raise exception 'invalid_read' using errcode = 'P0001', detail = 'entity_id';
  end if;
  if p_metadata is not null and (
       jsonb_typeof(p_metadata) <> 'object'
       or exists (
         select 1 from jsonb_each(p_metadata) e where e.key not in ('year', 'quarter') or jsonb_typeof(e.value) <> 'number')) then
    raise exception 'invalid_read' using errcode = 'P0001', detail = 'metadata';
  end if;

  perform private.log_activity('access', v_uid, 'gestor', p_owner, 'gestor.read', p_entity_type, p_entity_id, coalesce(p_metadata, '{}'::jsonb));
end
$$;

-- Añade una anotación de un gestor con vínculo activo (D-03). Si la liga a algo, comprueba que existe Y es de ese autónomo (no se puede anotar sobre lo
-- de otro). Inserta y registra `gestor.note_added` (solo ids) en la misma transacción.
create function app.add_gestor_note(p_owner uuid, p_body text, p_entity_type text default null, p_entity_id uuid default null) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_body text := btrim(coalesce(p_body, ''));
  v_id uuid;
  v_found boolean;
begin
  if private.app_role() is distinct from 'gestor'::public.user_role or not private.gestor_has_access(p_owner) then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  if char_length(v_body) not between 1 and 2000 then
    raise exception 'invalid_note' using errcode = 'P0001', detail = 'body';
  end if;
  if (p_entity_type is null) <> (p_entity_id is null) or p_entity_type not in ('invoice', 'expense', 'document') then
    raise exception 'invalid_note' using errcode = 'P0001', detail = 'entity';
  end if;
  if p_entity_type is not null then
    -- (el CASE va aparte: un `THEN` dentro de un `IF` confunde al analizador de PL/pgSQL)
    select case p_entity_type
             when 'invoice' then exists (select 1 from public.invoices i where i.id = p_entity_id and i.owner_id = p_owner)
             when 'expense' then exists (select 1 from public.expenses e where e.id = p_entity_id and e.owner_id = p_owner)
             else exists (select 1 from public.documents d where d.id = p_entity_id and d.owner_id = p_owner)
           end
      into v_found;
    if not v_found then
      raise exception 'invalid_note' using errcode = 'P0001', detail = 'entity';
    end if;
  end if;

  insert into public.gestor_notes (owner_id, gestor_id, body, entity_type, entity_id)
  values (p_owner, v_uid, v_body, p_entity_type, p_entity_id)
  returning id into v_id;

  perform private.log_activity('access', v_uid, 'gestor', p_owner, 'gestor.note_added', 'gestor_note', v_id::text, '{}'::jsonb);
  return v_id;
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function
  app.invite_gestor_access(text),
  app.list_gestor_invitations(),
  app.log_gestor_read(uuid, text, text, jsonb),
  app.add_gestor_note(uuid, text, text, uuid)
  to authenticated;
