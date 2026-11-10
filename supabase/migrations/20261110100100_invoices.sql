-- SPEC-W-007 §5.2 · Facturas emitidas (RF-006, RES-03) y el registro de su PDF.
--
-- Una factura emitida NO se edita ni se borra: lo garantiza un trigger (aquí, no en la API) que solo deja pasar un cambio de `paid_at`. Se
-- corrige con una rectificativa, que es otra fila. Nada cascadea hacia las facturas ni desde ellas (CONF-004): borrar la cuenta, la serie o
-- el cliente de una factura es imposible mientras la factura exista.
--
-- Esta tabla no se escribe directamente (ni el dueño): todo pasa por `app.*` (migración siguiente), que toman los cerrojos de la emisión.
-- La base defiende solo lo barato (D-10 de SPEC-W-006): longitudes, rangos, tipos permitidos, la identidad `total = base + IVA − retención`
-- y los signos. Qué tratamiento corresponde a un cliente lo calcula `cuadre.tax`; las funciones solo comprueban que las condiciones que
-- reciben son coherentes con la copia del cliente. Las restricciones llevan nombre propio para que la API las traduzca por nombre.
--
-- Las claves foráneas a la serie y al cliente incluyen `owner_id` (y `kind` en la serie): una factura no puede colgar de la serie o del
-- cliente de otra persona, ni una rectificativa de una serie ordinaria, ni al revés, aunque alguien llegue por otro camino.

alter table public.clients
  add constraint clients_id_owner_key unique (id, owner_id);
alter table public.invoice_series
  add constraint invoice_series_id_owner_kind_key unique (id, owner_id, kind);

create table public.invoices (
  id                   uuid primary key default gen_random_uuid(),
  owner_id             uuid not null references public.profiles (id) on delete restrict,   -- no cascadea (CONF-004, RES-03)
  series_id            uuid not null,
  series_code          text not null,                 -- copia: el código de una serie usada no cambia, pero la factura no depende de ello
  number               integer not null,
  kind                 public.invoice_kind not null,
  issue_date           date not null,
  client_id            uuid not null,
  -- Copia congelada del cliente (D-09)
  client_name          text not null,
  client_kind          public.client_kind not null,
  client_country       text not null,
  client_scope         public.client_scope not null,
  client_tax_id        text,
  client_address       text not null,
  -- Copia congelada del emisor (el perfil en el momento de emitir)
  issuer_name          text not null,
  issuer_tax_id        text not null,
  issuer_address       text not null,
  issuer_iban          text,
  concept              text not null,
  tax_treatment        public.invoice_tax_treatment not null,
  base_cents           bigint not null,
  vat_rate             numeric(5, 2) not null default 0,
  vat_cents            bigint not null default 0,
  irpf_rate            numeric(5, 2) not null default 0,
  irpf_cents           bigint not null default 0,
  total_cents          bigint not null,
  legal_note           text,
  rectifies_id         uuid,
  rectification_reason text,
  paid_at              timestamptz,                  -- lo ÚNICO modificable
  created_at           timestamptz not null default now(),
  constraint invoices_series_fk foreign key (series_id, owner_id, kind)
    references public.invoice_series (id, owner_id, kind) on delete restrict,
  constraint invoices_client_fk foreign key (client_id, owner_id)
    references public.clients (id, owner_id) on delete restrict,
  constraint invoices_rectifies_fk foreign key (rectifies_id, owner_id)
    references public.invoices (id, owner_id) on delete restrict,
  constraint invoices_id_owner_key unique (id, owner_id),
  constraint invoices_owner_series_number_key unique (owner_id, series_id, number),
  constraint invoices_number_range check (number between 1 and 999999),
  constraint invoices_issue_date_min check (issue_date >= date '2000-01-01'),
  constraint invoices_concept_length check (char_length(concept) between 2 and 300),
  constraint invoices_reason_length check (char_length(rectification_reason) between 2 and 300),
  constraint invoices_client_address_length check (char_length(client_address) between 1 and 300),
  constraint invoices_issuer_name_length check (char_length(issuer_name) between 2 and 200),
  constraint invoices_issuer_address_length check (char_length(issuer_address) between 5 and 300),
  constraint invoices_legal_note_length check (char_length(legal_note) <= 300),
  constraint invoices_vat_rate_values check (vat_rate in (0, 4, 10, 21)),
  constraint invoices_irpf_rate_values check (irpf_rate in (0, 7, 15)),
  constraint invoices_base_range check (base_cents between -9999999999 and 9999999999),
  constraint invoices_total_matches check (total_cents = base_cents + vat_cents - irpf_cents),
  -- La ordinaria suma; la rectificativa resta: su base, su IVA y su retención no son positivas (y su base no es cero).
  constraint invoices_base_positive check (kind = 'rectifying' or base_cents > 0),
  constraint invoices_rectifying_base_negative check (kind = 'standard' or base_cents < 0),
  constraint invoices_amounts_sign check (
    (kind = 'standard' and vat_cents >= 0 and irpf_cents >= 0) or (kind = 'rectifying' and vat_cents <= 0 and irpf_cents <= 0)),
  -- B.1-D: el CHECK único de la rectificativa admitía dos combinaciones inválidas; son dos.
  constraint invoices_rectification_ref check ((kind = 'rectifying') = (rectifies_id is not null)),
  constraint invoices_rectification_reason check ((kind = 'rectifying') = (rectification_reason is not null)),
  constraint invoices_rectifying_not_paid check (kind = 'standard' or paid_at is null)
);

create index invoices_owner_date on public.invoices (owner_id, issue_date desc, id);
create index invoices_rectifies on public.invoices (rectifies_id) where rectifies_id is not null;

create table public.invoice_files (
  invoice_id   uuid primary key,
  owner_id     uuid not null,                        -- el de la factura (la clave compuesta lo obliga): la política es de una columna
  storage_path text not null,
  sha256       text not null,
  size_bytes   integer not null,
  created_at   timestamptz not null default now(),
  constraint invoice_files_invoice_fk foreign key (invoice_id, owner_id)
    references public.invoices (id, owner_id) on delete restrict,
  constraint invoice_files_sha256_format check (sha256 ~ '^[0-9a-f]{64}$'),
  constraint invoice_files_size_range check (size_bytes between 1 and 1048576),
  -- `{owner_id}/{invoice_id}-{sha256[:16]}.pdf`: la ruta se deduce de lo que ya está en la fila (B.1-C).
  constraint invoice_files_path_matches check (
    storage_path = owner_id::text || '/' || invoice_id::text || '-' || substr(sha256, 1, 16) || '.pdf')
);

alter table public.invoices enable row level security;
alter table public.invoices force row level security;
alter table public.invoice_files enable row level security;
alter table public.invoice_files force row level security;
revoke all on public.invoices, public.invoice_files from public, anon, authenticated, service_role;

-- Dueño: las suyas. Gestor: solo con vínculo activo (se evalúa en cada consulta). Administrador: ninguna (D3).
create policy invoices_select_owner on public.invoices for select to authenticated
  using (owner_id = (select auth.uid()));
create policy invoices_select_gestor on public.invoices for select to authenticated
  using (private.gestor_has_access(owner_id));
create policy invoice_files_select_owner on public.invoice_files for select to authenticated
  using (owner_id = (select auth.uid()));
create policy invoice_files_select_gestor on public.invoice_files for select to authenticated
  using (private.gestor_has_access(owner_id));

grant select on public.invoices, public.invoice_files to authenticated;

-- Inmutabilidad (RES-03), venga la sentencia de donde venga. Sin lista de columnas que mantener: la fila, sin `paid_at`, no cambia.
-- B.1-D: el dueño de la base puede hacer `ALTER TABLE … DISABLE TRIGGER`; ningún trigger puede impedirlo.
create function private.invoices_immutable() returns trigger
language plpgsql set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' and (to_jsonb(new) - 'paid_at') is not distinct from (to_jsonb(old) - 'paid_at') then
    return new;
  end if;
  raise exception 'invoice_immutable' using errcode = 'P0001';
end
$$;

create trigger invoices_immutable before update or delete on public.invoices
  for each row execute function private.invoices_immutable();
create trigger invoices_no_truncate before truncate on public.invoices
  for each statement execute function private.invoices_immutable();

-- El registro del PDF es de solo inserción: una vez guardado, la huella manda (T7-10).
create function private.invoice_files_append_only() returns trigger
language plpgsql set search_path = ''
as $$
begin
  raise exception 'invoice_immutable' using errcode = 'P0001';
end
$$;

create trigger invoice_files_append_only before update or delete on public.invoice_files
  for each row execute function private.invoice_files_append_only();
create trigger invoice_files_no_truncate before truncate on public.invoice_files
  for each statement execute function private.invoice_files_append_only();
