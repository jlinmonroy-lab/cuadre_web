-- SPEC-W-001 §5.2.5 · Funciones de negocio que invoca el backend (esquema `app`).
--
-- Son SECURITY DEFINER: comprueban quién llama con auth.uid() y private.app_role(), hacen el cambio de estado y lo registran en
-- activity_log EN LA MISMA TRANSACCIÓN (si la acción falla, no queda rastro). Errores de negocio: SQLSTATE P0001 con un código estable
-- en el mensaje; privilegios insuficientes: 42501. Nunca revelan si existe una fila que el llamante no podría ver.

-- Acepta una invitación dirigida al correo del gestor que llama.
create function app.accept_gestor_access(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_row public.gestor_access%rowtype;
begin
  if private.app_role() is distinct from 'gestor'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select * into v_row from public.gestor_access g
   where g.id = p_id and (g.gestor_email = private.app_email() or g.gestor_id = v_uid)
   for update;
  if not found then
    raise exception 'gestor_access_not_found' using errcode = 'P0001';
  end if;
  if v_row.status <> 'pending' then
    raise exception 'gestor_access_not_pending' using errcode = 'P0001';
  end if;
  if v_row.expires_at < now() then
    raise exception 'gestor_access_expired' using errcode = 'P0001';
  end if;

  update public.gestor_access
     set gestor_id = v_uid, status = 'active', responded_at = now()
   where id = p_id;

  perform private.log_activity('access', v_uid, 'gestor', v_row.owner_id, 'gestor_access.accepted',
                               'gestor_access', p_id::text, '{}'::jsonb);
end
$$;

create function app.decline_gestor_access(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_row public.gestor_access%rowtype;
begin
  if private.app_role() is distinct from 'gestor'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select * into v_row from public.gestor_access g
   where g.id = p_id and (g.gestor_email = private.app_email() or g.gestor_id = v_uid)
   for update;
  if not found then
    raise exception 'gestor_access_not_found' using errcode = 'P0001';
  end if;
  if v_row.status <> 'pending' then
    raise exception 'gestor_access_not_pending' using errcode = 'P0001';
  end if;

  update public.gestor_access
     set gestor_id = v_uid, status = 'declined', responded_at = now()
   where id = p_id;

  perform private.log_activity('access', v_uid, 'gestor', v_row.owner_id, 'gestor_access.declined',
                               'gestor_access', p_id::text, '{}'::jsonb);
end
$$;

-- Solo el dueño revoca (o retira una invitación pendiente).
create function app.revoke_gestor_access(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_role public.user_role := private.app_role();
  v_row public.gestor_access%rowtype;
begin
  if v_role is null then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select * into v_row from public.gestor_access g where g.id = p_id for update;
  -- Un extraño recibe «no encontrado»: no se revela que la fila existe.
  if not found
     or (v_row.owner_id <> v_uid and v_row.gestor_id is distinct from v_uid and v_row.gestor_email <> private.app_email()) then
    raise exception 'gestor_access_not_found' using errcode = 'P0001';
  end if;
  if v_row.owner_id <> v_uid then
    raise exception 'not_the_owner' using errcode = 'P0001';
  end if;
  if v_row.status not in ('pending', 'active') then
    raise exception 'gestor_access_not_open' using errcode = 'P0001';
  end if;

  update public.gestor_access
     set status = 'revoked', revoked_at = now()
   where id = p_id;

  perform private.log_activity('access', v_uid, v_role, v_row.owner_id, 'gestor_access.revoked',
                               'gestor_access', p_id::text, '{}'::jsonb);
end
$$;

-- Administración de cuentas. Nunca sobre uno mismo (evita quedarse sin administradores por error).
create function app.admin_set_role(p_target uuid, p_role public.user_role) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_old public.user_role;
begin
  if not private.is_admin() then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  if p_target = v_uid then
    raise exception 'cannot_modify_self' using errcode = 'P0001';
  end if;

  select p.role into v_old from public.profiles p where p.id = p_target for update;
  if not found then
    raise exception 'target_not_found' using errcode = 'P0001';
  end if;

  update public.profiles set role = p_role where id = p_target;

  perform private.log_activity('account', v_uid, 'admin', p_target, 'account.role_changed', 'profile', p_target::text,
                               jsonb_build_object('from', v_old, 'to', p_role));
end
$$;

create function app.admin_set_status(p_target uuid, p_status public.account_status) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_old public.account_status;
begin
  if not private.is_admin() then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  if p_target = v_uid then
    raise exception 'cannot_modify_self' using errcode = 'P0001';
  end if;

  select p.status into v_old from public.profiles p where p.id = p_target for update;
  if not found then
    raise exception 'target_not_found' using errcode = 'P0001';
  end if;

  update public.profiles set status = p_status where id = p_target;

  perform private.log_activity('account', v_uid, 'admin', p_target, 'account.status_changed', 'profile', p_target::text,
                               jsonb_build_object('from', v_old, 'to', p_status));
end
$$;

revoke all on all functions in schema app from public;
grant execute on function
  app.accept_gestor_access(uuid),
  app.decline_gestor_access(uuid),
  app.revoke_gestor_access(uuid),
  app.admin_set_role(uuid, public.user_role),
  app.admin_set_status(uuid, public.account_status)
  to authenticated;
