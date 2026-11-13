-- SPEC-W-014 §5.2 · A quién puede avisar el job. `service_role` no lee `reminder_settings` (hito 2: nadie escribe ni lee esas tablas salvo por funciones),
-- así que esta función le da lo mínimo: las cuentas `usuario` activas con su correo, su nombre y sus ajustes (sin fila = activado y 10 días, D-01).
-- No devuelve nada financiero. Las cifras del recordatorio las calcula el job con la identidad de cada persona, como las pantallas.

create function private.reminder_candidates()
returns table (owner_id uuid, email text, display_name text, enabled boolean, lead_days integer)
language sql stable security definer set search_path = ''
as $$
  select p.id, p.email, p.display_name, coalesce(s.enabled, true), coalesce(s.lead_days, 10)
    from public.profiles p
    left join public.reminder_settings s on s.owner_id = p.id
   where p.role = 'usuario'::public.user_role and p.status = 'active'::public.account_status
   order by p.id
$$;

revoke all on function private.reminder_candidates() from public;
grant execute on function private.reminder_candidates() to service_role;
