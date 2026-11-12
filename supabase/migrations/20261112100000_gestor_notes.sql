-- SPEC-W-010 §5.2 · Anotaciones del gestor (D-03). La «revisión» de CONF-001 (a): el gestor deja comentarios que el autónomo lee; no escribe en la
-- contabilidad.
--
-- No se escribe directamente (ni el gestor): todo pasa por `app.add_gestor_note` (migración siguiente), que comprueba el vínculo y que lo anotado es del
-- autónomo, y registra la anotación en la misma transacción. Solo de añadir (P-03): ni una función `SECURITY DEFINER` las edita o las borra.
-- Sin claves foráneas a `profiles` a propósito: como `activity_log`, sobreviven al borrado de una cuenta (CONF-004 decidirá su retención).

create table public.gestor_notes (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null,
  gestor_id   uuid not null,
  body        text not null,
  entity_type text,
  entity_id   uuid,
  created_at  timestamptz not null default now(),
  constraint gestor_notes_body_length check (char_length(body) between 1 and 2000),
  constraint gestor_notes_entity_type_known check (entity_type in ('invoice', 'expense', 'document')),
  constraint gestor_notes_entity_pair check ((entity_type is null) = (entity_id is null))
);

create index gestor_notes_by_owner on public.gestor_notes (owner_id, created_at desc);
create index gestor_notes_by_gestor on public.gestor_notes (gestor_id, created_at desc);

alter table public.gestor_notes enable row level security;
alter table public.gestor_notes force row level security;
revoke all on public.gestor_notes from public, anon, authenticated, service_role;

-- Dueño: las de su cuenta. Gestor: las suyas, solo con vínculo activo (se evalúa en cada consulta: revocar corta la lectura al instante).
-- Administrador: ninguna (D3).
create policy gestor_notes_select_owner on public.gestor_notes for select to authenticated
  using (owner_id = (select auth.uid()));

create policy gestor_notes_select_gestor on public.gestor_notes for select to authenticated
  using (private.gestor_has_access(owner_id) and gestor_id = (select auth.uid()));

grant select on public.gestor_notes to authenticated;

-- Solo de añadir para todos, también para el dueño de la tabla.
create function private.gestor_notes_is_append_only() returns trigger
language plpgsql set search_path = ''
as $$
begin
  raise exception 'gestor_notes_is_append_only' using errcode = 'P0001';
end
$$;

create trigger gestor_notes_no_update_delete before update or delete on public.gestor_notes
  for each row execute function private.gestor_notes_is_append_only();
create trigger gestor_notes_no_truncate before truncate on public.gestor_notes
  for each statement execute function private.gestor_notes_is_append_only();

revoke all on all functions in schema private from public;
