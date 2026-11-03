-- SPEC-W-001 §5.2.2 · Tablas. Cada una nace con RLS activada y forzada y SIN privilegios para nadie salvo su dueño:
-- las políticas y los privilegios concretos llegan en 20261103100300_base_policies_grants.sql.

create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  email        text not null unique check (email = lower(email)),
  display_name text not null default '',
  role         public.user_role not null default 'usuario',
  status       public.account_status not null default 'active',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- Tabla «canario» financiera de NFR-06. Las columnas reproducen RF-004; su API y su pantalla son de SPEC-W-005.
create table public.business_profiles (
  owner_id            uuid primary key references public.profiles (id) on delete cascade,
  legal_name          text,
  tax_id              text,
  fiscal_address      text,
  activity            text,
  iae_epigraph        text,
  activity_start_date date,
  vat_regime          text not null default 'general',
  irpf_rate           numeric(5, 2) check (irpf_rate between 0 and 100),
  logo_path           text,
  iban                text,
  home_pct            numeric(5, 2) check (home_pct between 0 and 100),
  updated_at          timestamptz not null default now()
);

create table public.gestor_access (
  id           uuid primary key default gen_random_uuid(),
  owner_id     uuid not null references public.profiles (id) on delete cascade,
  gestor_email text not null check (gestor_email = lower(gestor_email)),
  gestor_id    uuid references public.profiles (id) on delete set null,
  status       public.gestor_access_status not null default 'pending',
  invited_at   timestamptz not null default now(),
  expires_at   timestamptz not null default now() + interval '14 days',
  responded_at timestamptz,
  revoked_at   timestamptz,
  check (status <> 'active' or gestor_id is not null)
);

-- Una sola invitación abierta (pendiente o activa) por pareja dueño-gestor.
create unique index gestor_access_one_open_per_pair
  on public.gestor_access (owner_id, gestor_email) where status in ('pending', 'active');
create index gestor_access_by_gestor on public.gestor_access (gestor_id) where gestor_id is not null;
create index gestor_access_by_email on public.gestor_access (gestor_email);

-- Solo se añade. Sin claves foráneas a propósito: el registro sobrevive al borrado de una cuenta (CONF-004 decidirá su retención).
create table public.activity_log (
  id          bigint generated always as identity primary key,
  occurred_at timestamptz not null default now(),
  category    public.activity_category not null,
  actor_id    uuid,
  actor_role  public.user_role,
  owner_id    uuid,
  action      text not null check (length(action) between 1 and 100),
  entity_type text,
  entity_id   text,
  metadata    jsonb not null default '{}'::jsonb   -- solo identificadores y estados; nunca importes, IBAN ni NIF
);

create index activity_log_by_owner on public.activity_log (owner_id, occurred_at desc);
create index activity_log_by_actor on public.activity_log (actor_id, occurred_at desc);

alter table public.profiles          enable row level security;
alter table public.business_profiles enable row level security;
alter table public.gestor_access     enable row level security;
alter table public.activity_log      enable row level security;

alter table public.profiles          force row level security;
alter table public.business_profiles force row level security;
alter table public.gestor_access     force row level security;
alter table public.activity_log      force row level security;

revoke all on public.profiles, public.business_profiles, public.gestor_access, public.activity_log
  from public, anon, authenticated, service_role;
