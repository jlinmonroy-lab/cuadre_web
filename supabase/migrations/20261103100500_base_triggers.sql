-- SPEC-W-001 §5.2.5 · Triggers: alta de perfil, sincronía del correo, updated_at y registro de actividad de solo inserción.

-- Alta de perfil. Es lo ÚNICO que lee de raw_user_meta_data: el nombre para mostrar. El rol y el estado NUNCA salen de los metadatos
-- (los controla el usuario al registrarse): toda cuenta nace como `usuario` y solo cambia por app.admin_set_role (ADR-0005).
create function private.handle_new_user() returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (new.id, lower(new.email), coalesce(new.raw_user_meta_data ->> 'display_name', ''));

  insert into public.business_profiles (owner_id) values (new.id);

  perform private.log_activity('account', null, null, new.id, 'account.created', 'profile', new.id::text, '{}'::jsonb);
  return new;
end
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

create function private.sync_user_email() returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  update public.profiles set email = lower(new.email) where id = new.id;
  return new;
end
$$;

create trigger on_auth_user_email_changed
  after update of email on auth.users
  for each row when (old.email is distinct from new.email)
  execute function private.sync_user_email();

create function private.touch_updated_at() returns trigger
language plpgsql set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end
$$;

create trigger profiles_touch_updated_at before update on public.profiles
  for each row execute function private.touch_updated_at();
create trigger business_profiles_touch_updated_at before update on public.business_profiles
  for each row execute function private.touch_updated_at();

-- activity_log es de solo inserción para todos, también para el dueño de la tabla y para service_role.
create function private.activity_log_is_append_only() returns trigger
language plpgsql set search_path = ''
as $$
begin
  raise exception 'activity_log_is_append_only' using errcode = 'P0001';
end
$$;

create trigger activity_log_no_update_delete before update or delete on public.activity_log
  for each row execute function private.activity_log_is_append_only();
create trigger activity_log_no_truncate before truncate on public.activity_log
  for each statement execute function private.activity_log_is_append_only();

-- Las funciones nuevas de `private` (triggers) nacen con EXECUTE para PUBLIC: se retira. Las de las políticas conservan
-- el EXECUTE de authenticated y service_role que les dio la migración anterior.
revoke all on all functions in schema private from public;
