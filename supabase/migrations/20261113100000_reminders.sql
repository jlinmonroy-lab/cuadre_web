-- SPEC-W-014 §5.2 · Recordatorios por correo antes de cada plazo trimestral (RF-015, NFR-09).
--
-- `reminder_settings`: ajustes de cada usuario (activado, días de antelación). SIN FILA = activado y 10 días (D-01), así que no hace falta tocar el alta
-- de cuentas ni rellenar las existentes.
-- `reminder_log`: qué recordatorios se han reservado o enviado, único por (dueño, periodo, tipo) (ADR-0007): es lo que hace al job idempotente.
--
-- Ninguna de las dos se escribe directamente, ni el dueño ni `service_role` (que además no tiene DELETE en ninguna tabla): la escritura pasa por las
-- funciones de la migración siguiente. Gestor y administrador no tienen ninguna política (D3). Sin cuerpo ni dirección de correo en ninguna columna.

create table public.reminder_settings (
  owner_id   uuid primary key references public.profiles (id) on delete cascade,
  enabled    boolean not null default true,
  lead_days  integer not null default 10,
  updated_at timestamptz not null default now(),
  constraint reminder_settings_lead_days_range check (lead_days between 1 and 30)
);

create table public.reminder_log (
  id         uuid primary key default gen_random_uuid(),
  owner_id   uuid not null references public.profiles (id) on delete cascade,
  period     text not null,
  kind       text not null,
  status     text not null default 'pending',
  claimed_at timestamptz not null default now(),
  sent_at    timestamptz,
  constraint reminder_log_period_format check (period ~ '^[0-9]{4}-Q[1-4]$'),
  constraint reminder_log_kind_known check (kind in ('quarter_deadline')),
  constraint reminder_log_status_known check (status in ('pending', 'sent', 'failed')),
  constraint reminder_log_sent_at_iff_sent check ((status = 'sent') = (sent_at is not null)),
  constraint reminder_log_once unique (owner_id, period, kind)
);

alter table public.reminder_settings enable row level security;
alter table public.reminder_settings force row level security;
alter table public.reminder_log enable row level security;
alter table public.reminder_log force row level security;
revoke all on public.reminder_settings from public, anon, authenticated, service_role;
revoke all on public.reminder_log from public, anon, authenticated, service_role;

-- Dueño: lo suyo. Gestor y administrador: nada.
create policy reminder_settings_select_owner on public.reminder_settings for select to authenticated
  using (owner_id = (select auth.uid()));
create policy reminder_log_select_owner on public.reminder_log for select to authenticated
  using (owner_id = (select auth.uid()));

grant select on public.reminder_settings to authenticated;
grant select on public.reminder_log to authenticated;
