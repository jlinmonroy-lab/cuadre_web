-- SPEC-W-012 §5.2 · Cierre mensual (RF-012, NFR-09). Una fila por persona y mes terminado: la FOTO del cierre (facturas, importes por ámbito, total, gastos y
-- desglose por cliente), con `revision` (1 al cerrar; +1 cada vez que un recálculo cambia algo, p. ej. por una factura o un gasto atrasado) y las fechas del
-- primer cierre y del último.
--
-- El acumulado del año NO se guarda (D-03): la API lo suma de los cierres, así que reabrir un mes antiguo no deja desfasados los siguientes.
-- Nadie escribe la tabla directamente, ni el dueño ni `service_role` (que además no tiene DELETE en ninguna tabla): la escritura pasa por
-- `private.close_month` (migración siguiente). El gestor lee con vínculo activo (como el resto de datos financieros); el administrador, nada (D3).
-- `by_client` lleva nombres de clientes del dueño: es dato suyo y solo lo ven quienes ya ven sus facturas.

create table public.monthly_closings (
  owner_id        uuid not null references public.profiles (id) on delete cascade,
  year            integer not null,
  month           integer not null,
  invoice_count   integer not null,
  national_cents  bigint not null,
  eu_cents        bigint not null,
  non_eu_cents    bigint not null,
  total_cents     bigint not null,
  expenses_cents  bigint not null,
  by_client       jsonb not null default '[]',
  revision        integer not null default 1,
  first_closed_at timestamptz not null default now(),
  closed_at       timestamptz not null default now(),
  primary key (owner_id, year, month),
  constraint monthly_closings_year_range check (year between 2000 and 9998),
  constraint monthly_closings_month_range check (month between 1 and 12),
  constraint monthly_closings_invoice_count_nonneg check (invoice_count >= 0),
  constraint monthly_closings_revision_positive check (revision >= 1),
  constraint monthly_closings_total_matches check (total_cents = national_cents + eu_cents + non_eu_cents),
  constraint monthly_closings_by_client_is_array check (jsonb_typeof(by_client) = 'array')
);

alter table public.monthly_closings enable row level security;
alter table public.monthly_closings force row level security;
revoke all on public.monthly_closings from public, anon, authenticated, service_role;

-- Dueño: los suyos. Gestor: los de quien le dio acceso activo (se evalúa en cada consulta: revocar corta la lectura al instante). Administrador: ninguno.
create policy monthly_closings_select_owner on public.monthly_closings for select to authenticated
  using (owner_id = (select auth.uid()));

create policy monthly_closings_select_gestor on public.monthly_closings for select to authenticated
  using (private.gestor_has_access(owner_id));

grant select on public.monthly_closings to authenticated;
