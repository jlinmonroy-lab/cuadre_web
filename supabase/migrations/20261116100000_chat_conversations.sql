-- SPEC-W-004 §5.2 · Conversaciones del chatbot (RF-016, RF-018, NFR-06).
--
-- `chat_conversations`: una fila por conversación de una persona. Nace con su primer mensaje (D-03) y se borra entera con `app.delete_chat_conversation`.
-- El título lo calcula el servicio (regla pura) y llega como parámetro. `last_message_at` lo mantienen las funciones de la migración de funciones.
--
-- No se escribe directamente, ni el dueño ni `service_role` (que además no tiene DELETE en ninguna tabla): toda escritura pasa por las funciones `app.*`.
-- Gestor y administrador no tienen ninguna política (D-15, D3): el chat de una persona no lo ve nadie más.

create table public.chat_conversations (
  id              uuid primary key default gen_random_uuid(),
  owner_id        uuid not null references public.profiles (id) on delete cascade,
  title           text not null,
  created_at      timestamptz not null default now(),
  last_message_at timestamptz not null default now(),
  -- La clave compuesta permite que los mensajes enlacen con la conversación Y con su dueño: un mensaje no puede colgar de una conversación ajena.
  constraint chat_conversations_id_owner_key unique (id, owner_id),
  constraint chat_conversations_title_length check (char_length(title) between 1 and 80)
);

create index chat_conversations_owner_recent on public.chat_conversations (owner_id, last_message_at desc, id);

alter table public.chat_conversations enable row level security;
alter table public.chat_conversations force row level security;
revoke all on public.chat_conversations from public, anon, authenticated, service_role;

-- Dueño: lo suyo. Gestor y administrador: nada.
create policy chat_conversations_select_owner on public.chat_conversations for select to authenticated
  using (owner_id = (select auth.uid()));

grant select on public.chat_conversations to authenticated;
