-- SPEC-W-002 §5.2 · Tabla `documents` (factura de compra subida por la persona y su lectura por el agente).
--
-- Tabla financiera: RLS activada y forzada, `authenticated` solo lee y TODA escritura pasa por `app.*` (migración siguiente).
-- Tres cierres que la API no puede saltarse (CLAUDE.md: las reglas críticas van en la base, no solo en la API):
--   * la ruta de Storage es `{owner_id}/{id}.{ext}` y nada más: nunca lleva el nombre del archivo de la persona (T2-07);
--   * los importes de la lectura y de las correcciones son enteros en céntimos (RES-02, ADR-0006);
--   * el trigger solo admite las transiciones de estado de §5.1 y congela la lectura original (AC-14).

create type public.document_status as enum ('uploading', 'processing', 'review', 'extraction_failed', 'discarded', 'registered');
create type public.upload_source as enum ('file', 'camera');

-- ¿Es `p` un entero JSON (o ausente / null)? Rechaza decimales (12.5, 12.0), cadenas ("120.00") y números de más de 15 cifras.
create function private.jsonb_is_cents(p jsonb) returns boolean
language sql immutable set search_path = ''
as $$
  select p is null or jsonb_typeof(p) = 'null' or (jsonb_typeof(p) = 'number' and p::text ~ '^-?[0-9]{1,15}$')
$$;

-- ¿Todos los importes de una lectura (o de unas correcciones) son céntimos enteros? NULL vale; si no es NULL, ha de ser un objeto.
create function private.document_amounts_are_cents(p jsonb) returns boolean
language sql immutable set search_path = ''
as $$
  select p is null or (
    jsonb_typeof(p) = 'object'
    and private.jsonb_is_cents(p -> 'total_cents')
    and private.jsonb_is_cents(p #> '{withholding,amount_cents}')
    and coalesce((
      select bool_and(private.jsonb_is_cents(l -> 'base_cents') and private.jsonb_is_cents(l -> 'vat_cents'))
      from jsonb_array_elements(
        case when jsonb_typeof(p -> 'tax_breakdown') = 'array' then p -> 'tax_breakdown' else '[]'::jsonb end
      ) as l
    ), true)
  )
$$;

create table public.documents (
  id                  uuid primary key default gen_random_uuid(),
  owner_id            uuid not null references public.profiles (id) on delete cascade,
  status              public.document_status not null default 'uploading',
  source              public.upload_source not null,
  original_filename   text not null check (char_length(original_filename) between 1 and 255),
  mime_type           text not null check (mime_type in ('application/pdf', 'image/jpeg', 'image/png', 'image/heic', 'image/webp')),
  size_bytes          bigint not null check (size_bytes between 1 and 15728640),   -- 15 MiB: igual que el bucket y la API
  storage_path        text not null unique,
  extraction          jsonb,                       -- lectura normalizada (§5.3); NULL hasta que la hay. Congelada tras `review`
  review              jsonb,                       -- correcciones de la persona; NULL hasta que guarda
  injection_suspected boolean not null default false,
  error_code          text check (error_code in (
                        'unreadable', 'unsupported_media_type', 'payload_too_large', 'timeout',
                        'upstream_error', 'agents_unavailable', 'invalid_response', 'internal')),
  agent_trace_id      text check (char_length(agent_trace_id) <= 200),
  agent_cost_eur      numeric(9, 6) check (agent_cost_eur >= 0),
  created_at          timestamptz not null default now(),
  uploaded_at         timestamptz,
  extracted_at        timestamptz,
  updated_at          timestamptz not null default now(),
  check (status <> 'review' or extraction is not null),
  check (status <> 'extraction_failed' or error_code is not null),
  check (storage_path = owner_id::text || '/' || id::text || '.' || case mime_type
           when 'application/pdf' then 'pdf' when 'image/jpeg' then 'jpg' when 'image/png' then 'png'
           when 'image/heic' then 'heic' when 'image/webp' then 'webp' end),
  check (private.document_amounts_are_cents(extraction)),
  check (private.document_amounts_are_cents(review))
);

create index documents_by_owner on public.documents (owner_id, created_at desc);
create index documents_processing_by_owner on public.documents (owner_id) where status = 'processing';

alter table public.documents enable row level security;
alter table public.documents force row level security;
revoke all on public.documents from public, anon, authenticated, service_role;

-- Dueño: lee las suyas. Gestor: solo con vínculo activo (se evalúa en cada consulta). Administrador: ninguna política (D3).
create policy documents_select_owner on public.documents for select to authenticated
  using (owner_id = (select auth.uid()));

create policy documents_select_gestor on public.documents for select to authenticated
  using (private.gestor_has_access(owner_id));

grant select on public.documents to authenticated;

-- Trigger de seguridad: aunque `app.*` ya comprueba el estado, la tabla no admite una transición ilegal venga de donde venga.
create function private.documents_guard() returns trigger
language plpgsql set search_path = ''
as $$
declare
  v_move text := old.status::text || '>' || new.status::text;
begin
  -- Identidad inmutable.
  if new.id is distinct from old.id
     or new.owner_id is distinct from old.owner_id
     or new.source is distinct from old.source
     or new.original_filename is distinct from old.original_filename
     or new.mime_type is distinct from old.mime_type
     or new.size_bytes is distinct from old.size_bytes
     or new.storage_path is distinct from old.storage_path
     or new.created_at is distinct from old.created_at then
    raise exception 'document_immutable_column' using errcode = 'P0001';
  end if;

  -- `discarded` y `registered` son terminales (`registered` lo introduce SPEC-W-003 ampliando este trigger).
  if old.status in ('discarded', 'registered') then
    raise exception 'document_invalid_transition' using errcode = 'P0001';
  end if;

  if new.status is distinct from old.status then
    if not (v_move = any (array[
         'uploading>processing', 'uploading>discarded',
         'processing>review', 'processing>extraction_failed', 'processing>discarded',
         'review>discarded',
         'extraction_failed>processing', 'extraction_failed>discarded'
       ])) then
      raise exception 'document_invalid_transition' using errcode = 'P0001';
    end if;
  elsif old.status = 'uploading' then
    raise exception 'document_invalid_transition' using errcode = 'P0001';  -- sin cambio de estado: solo processing, review y extraction_failed
  end if;

  -- La lectura original solo se escribe al pasar de `processing` a `review`: guardar correcciones no la toca (AC-14).
  if not (old.status = 'processing' and new.status = 'review')
     and (new.extraction is distinct from old.extraction
          or new.injection_suspected is distinct from old.injection_suspected
          or new.agent_trace_id is distinct from old.agent_trace_id
          or new.agent_cost_eur is distinct from old.agent_cost_eur) then
    raise exception 'document_extraction_frozen' using errcode = 'P0001';
  end if;

  -- updated_at se mantiene solo, salvo que la sentencia lo fije a propósito (los tests envejecen filas así).
  if new.updated_at is not distinct from old.updated_at then
    new.updated_at := now();
  end if;
  return new;
end
$$;

create trigger documents_guard before update on public.documents
  for each row execute function private.documents_guard();

revoke all on all functions in schema private from public;
