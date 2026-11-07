-- SPEC-W-003 §5.2 · Tabla `expenses` (gasto registrado: de una factura leída o anotado a mano).
--
-- Segunda tabla financiera: RLS activada y forzada, `authenticated` solo lee y TODA escritura pasa por `app.*` (migración 200).
-- La base defiende lo barato y lo que protege la contabilidad aunque la API se saltara (D-01, CLAUDE.md: las reglas críticas
-- van en la base, no solo en la API); lo fiscal (NIF, tipos de IVA, cuotas) es de `cuadre.validators`:
--   * importes enteros en céntimos, sin signo y de 15 cifras como mucho (RES-02, ADR-0006);
--   * total coherente con base + IVA − retención (±1 céntimo, D-03) y líneas de IVA que suman EXACTAMENTE base y cuota;
--   * IVA deducible solo de un proveedor nacional con cuota (D-05, D-06);
--   * un solo gasto vivo por documento y por NIF + número de factura normalizado (D-04);
--   * lo registrado no se edita ni se borra: solo cambia la categoría y solo se anula (T3-10).

create type public.expense_category as enum
  ('software', 'workspace', 'supplies', 'utilities', 'advisory', 'self_employed_fee', 'training', 'other');
create type public.expense_origin as enum ('document', 'manual');
create type public.supplier_scope as enum ('national', 'eu');

-- Constantes de la spec en un solo sitio (T3-04): un test las compara con `cuadre.validators.limits`.
create function private.expense_earliest_date() returns date
language sql immutable set search_path = ''
as $$ select date '2000-01-01' $$;

create function private.expense_max_tax_lines() returns integer
language sql immutable set search_path = ''
as $$ select 10 $$;

-- ¿Son las líneas de IVA una lista de 1 a 10 objetos `{vat_rate, base_cents, vat_cents}` con céntimos enteros no negativos
-- cuya suma es exactamente `p_base` y `p_vat`? Nunca lanza: cualquier otra forma es «no».
create function private.expense_breakdown_matches(p_lines jsonb, p_base bigint, p_vat bigint) returns boolean
language sql immutable set search_path = ''
as $$
  select case
    when jsonb_typeof(p_lines) is distinct from 'array' then false
    when jsonb_array_length(p_lines) not between 1 and private.expense_max_tax_lines() then false
    else coalesce((
      select bool_and(
               jsonb_typeof(l) = 'object'
               and jsonb_typeof(l -> 'vat_rate') = 'string'
               and jsonb_typeof(l -> 'base_cents') = 'number' and (l ->> 'base_cents') ~ '^[0-9]{1,15}$'
               and jsonb_typeof(l -> 'vat_cents') = 'number' and (l ->> 'vat_cents') ~ '^[0-9]{1,15}$')
             and sum(case when (l ->> 'base_cents') ~ '^[0-9]{1,15}$' then (l ->> 'base_cents')::bigint end) = p_base
             and sum(case when (l ->> 'vat_cents') ~ '^[0-9]{1,15}$' then (l ->> 'vat_cents')::bigint end) = p_vat
      from jsonb_array_elements(p_lines) as l
    ), false)
  end
$$;

create table public.expenses (
  id                  uuid primary key default gen_random_uuid(),
  owner_id            uuid not null references public.profiles (id) on delete cascade,
  origin              public.expense_origin not null,
  document_id         uuid references public.documents (id),          -- NULL si es manual
  expense_date        date not null,                                   -- la fecha de la factura, o la que se anota
  supplier_name       text not null,                                   -- el concepto, en los manuales
  supplier_tax_id     text,                                            -- normalizado (sin `ES`, Grecia como `EL`); NULL en los manuales
  invoice_number      text,
  invoice_number_key  text generated always as (nullif(upper(regexp_replace(invoice_number, '[^0-9A-Za-z]', '', 'g')), '')) stored,
  doc_type            text,                                            -- NULL en los manuales
  supplier_scope      public.supplier_scope,                           -- NULL en los manuales
  category            public.expense_category not null,
  base_cents          bigint not null,
  vat_cents           bigint not null,
  withholding_cents   bigint not null default 0,
  total_cents         bigint not null,
  tax_breakdown       jsonb not null default '[]',                     -- líneas validadas: solo céntimos enteros
  deductible_vat      boolean not null,
  suspicion_acknowledged boolean not null default false,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  voided_at           timestamptz,                                     -- NULL = cuenta; no NULL = anulado

  constraint expenses_supplier_name_length check (char_length(supplier_name) between 1 and 200),
  constraint expenses_tax_id_form check (supplier_tax_id ~ '^[A-Z0-9]{5,20}$'),
  constraint expenses_invoice_number_length check (char_length(invoice_number) between 1 and 64),
  constraint expenses_doc_type_known check (doc_type in ('full_invoice', 'simplified_invoice', 'ticket', 'receipt')),
  constraint expenses_date_not_ancient check (expense_date >= private.expense_earliest_date()),
  constraint expenses_amounts_range check (
    base_cents between 0 and 999999999999999 and vat_cents between 0 and 999999999999999
    and withholding_cents between 0 and 999999999999999 and total_cents between 1 and 999999999999999),
  constraint expenses_origin_matches_document check ((origin = 'document') = (document_id is not null)),
  -- Un gasto de documento lleva proveedor identificado, tipo y líneas que suman; uno manual, nada de eso.
  constraint expenses_document_shape check (
    origin <> 'document'
    or (supplier_tax_id is not null and supplier_scope is not null and doc_type is not null
        and private.expense_breakdown_matches(tax_breakdown, base_cents, vat_cents))),
  constraint expenses_manual_shape check (
    origin <> 'manual'
    or (supplier_tax_id is null and invoice_number is null and supplier_scope is null and doc_type is null
        and vat_cents = 0 and withholding_cents = 0 and base_cents = total_cents and not deductible_vat
        and tax_breakdown = '[]')),
  constraint expenses_total_coherent check (abs(total_cents - (base_cents + vat_cents - withholding_cents)) <= 1),
  constraint expenses_deductible_rule check (not deductible_vat or (supplier_scope = 'national' and vat_cents > 0))
);

create unique index expenses_one_active_per_document on public.expenses (document_id)
  where voided_at is null and document_id is not null;
create unique index expenses_duplicate_invoice on public.expenses (owner_id, supplier_tax_id, invoice_number_key)
  where voided_at is null and supplier_tax_id is not null and invoice_number_key is not null;
create index expenses_by_owner_date on public.expenses (owner_id, expense_date desc, created_at desc, id desc);

alter table public.expenses enable row level security;
alter table public.expenses force row level security;
revoke all on public.expenses from public, anon, authenticated, service_role;

-- Dueño: lee los suyos (también los anulados). Gestor: solo con vínculo activo (se evalúa en cada consulta). Administrador: ninguna (D3).
create policy expenses_select_owner on public.expenses for select to authenticated
  using (owner_id = (select auth.uid()));

create policy expenses_select_gestor on public.expenses for select to authenticated
  using (private.gestor_has_access(owner_id));

grant select on public.expenses to authenticated;

-- Trigger de seguridad: solo cambian `category`, `voided_at` y `updated_at`, venga la sentencia de donde venga.
-- (`invoice_number_key` no se compara: es una columna generada, que PostgreSQL calcula DESPUÉS de los triggers BEFORE; depende solo de
-- `invoice_number`, que sí se compara, y no se puede escribir.)
create function private.expenses_guard() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.origin is distinct from old.origin
     or new.document_id is distinct from old.document_id
     or new.expense_date is distinct from old.expense_date
     or new.supplier_name is distinct from old.supplier_name
     or new.supplier_tax_id is distinct from old.supplier_tax_id
     or new.invoice_number is distinct from old.invoice_number
     or new.doc_type is distinct from old.doc_type
     or new.supplier_scope is distinct from old.supplier_scope
     or new.base_cents is distinct from old.base_cents
     or new.vat_cents is distinct from old.vat_cents
     or new.withholding_cents is distinct from old.withholding_cents
     or new.total_cents is distinct from old.total_cents
     or new.tax_breakdown is distinct from old.tax_breakdown
     or new.deductible_vat is distinct from old.deductible_vat
     or new.suspicion_acknowledged is distinct from old.suspicion_acknowledged
     or new.created_at is distinct from old.created_at then
    raise exception 'expense_immutable_column' using errcode = 'P0001';
  end if;

  -- `voided_at` solo pasa de nulo a no nulo; un gasto anulado ya no cambia (tampoco de categoría).
  if old.voided_at is not null
     and (new.voided_at is distinct from old.voided_at or new.category is distinct from old.category) then
    raise exception 'expense_already_voided' using errcode = 'P0001';
  end if;

  -- updated_at se mantiene solo, salvo que la sentencia lo fije a propósito (los tests envejecen filas así).
  if new.updated_at is not distinct from old.updated_at then
    new.updated_at := now();
  end if;
  return new;
end
$$;

create trigger expenses_guard before update on public.expenses
  for each row execute function private.expenses_guard();

revoke all on all functions in schema private from public;
