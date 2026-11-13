-- SPEC-W-014 §5.2 · Escrituras de los recordatorios. `SECURITY DEFINER` con `search_path = ''`; errores `P0001` con código estable.
--
-- `app.set_reminder_settings`: el usuario guarda sus ajustes (upsert). `42501` si no es `usuario` activo.
-- `private.reminder_claim` / `private.reminder_mark`: solo para el job (`service_role`). Reservar ANTES de enviar (D-03) hace que dos ejecuciones a la vez no
-- dupliquen el correo; como `service_role` no puede borrar, un envío fallido deja la fila en `failed` y la siguiente ejecución la reclama.

create function app.set_reminder_settings(p_enabled boolean, p_lead_days integer) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  if p_enabled is null or p_lead_days is null or p_lead_days not between 1 and 30 then
    raise exception 'invalid_lead_days' using errcode = 'P0001';
  end if;

  insert into public.reminder_settings (owner_id, enabled, lead_days)
  values (v_owner, p_enabled, p_lead_days)
  on conflict (owner_id) do update
    set enabled = excluded.enabled, lead_days = excluded.lead_days, updated_at = now();
end
$$;

-- ¿Debe este proceso enviar el recordatorio? `true` = lo ha reservado (fila nueva, o una `failed`, o una `pending` abandonada hace más de 15 minutos).
-- `false` = ya se envió o lo está enviando otro proceso. Una sola sentencia por camino: es atómica, sin carreras.
create function private.reminder_claim(p_owner uuid, p_period text, p_kind text) returns boolean
language plpgsql security definer set search_path = ''
as $$
declare
  v_id uuid;
begin
  insert into public.reminder_log (owner_id, period, kind)
  values (p_owner, p_period, p_kind)
  on conflict (owner_id, period, kind) do nothing
  returning id into v_id;
  if v_id is not null then
    return true;
  end if;

  update public.reminder_log
     set status = 'pending', claimed_at = now()
   where owner_id = p_owner and period = p_period and kind = p_kind
     and (status = 'failed' or (status = 'pending' and claimed_at < now() - interval '15 minutes'))
  returning id into v_id;
  return v_id is not null;
end
$$;

-- Cierra una reserva: `pending` -> `sent` (con su hora) o `failed`. No toca filas que ya no están `pending`.
create function private.reminder_mark(p_owner uuid, p_period text, p_kind text, p_sent boolean) returns void
language plpgsql security definer set search_path = ''
as $$
begin
  update public.reminder_log
     set status = case when p_sent then 'sent' else 'failed' end,
         sent_at = case when p_sent then now() else null end
   where owner_id = p_owner and period = p_period and kind = p_kind and status = 'pending';
end
$$;

revoke all on function app.set_reminder_settings(boolean, integer) from public;
grant execute on function app.set_reminder_settings(boolean, integer) to authenticated;
revoke all on function private.reminder_claim(uuid, text, text) from public;
revoke all on function private.reminder_mark(uuid, text, text, boolean) from public;
grant execute on function private.reminder_claim(uuid, text, text) to service_role;
grant execute on function private.reminder_mark(uuid, text, text, boolean) to service_role;
