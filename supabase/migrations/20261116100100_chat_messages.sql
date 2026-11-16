-- SPEC-W-004 §5.2 · Mensajes del chatbot (RF-016, RF-017, NFR-08).
--
-- `chat_messages`: cada mensaje de la persona y cada respuesta del asistente. INMUTABLE (D-07): el de la persona se inserta antes de llamar al agente y el del
-- asistente una sola vez, al final del flujo, con el estado en que terminó (`complete`, `abstained`, `error` o `interrupted`). No se actualiza ni se borra
-- suelto; solo desaparece con su conversación (borrado de la conversación o de la cuenta).
--
-- El contenido del agente es dato no confiable (ADR-0012): aquí se guarda tal cual, acotado, y la interfaz lo pinta como texto. `has_source` es la aserción
-- por código de NFR-08 (D-08): nulo si no se evalúa, `false` si una respuesta terminó sin ninguna cita ni herramienta.
-- Las longitudes de base de datos son las del contrato C2 (8.000); el tope de 2.000 del mensaje de la persona lo aplica el servicio.

create table public.chat_messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  owner_id        uuid not null references public.profiles (id) on delete cascade,
  role            text not null,
  content         text not null,
  status          text not null default 'complete',
  finish_reason   text,
  trace_id        text,
  has_source      boolean,
  citations       jsonb not null default '[]',
  abstention      jsonb,
  created_at      timestamptz not null default now(),
  constraint chat_messages_id_owner_key unique (id, owner_id),
  constraint chat_messages_conversation_fk foreign key (conversation_id, owner_id)
    references public.chat_conversations (id, owner_id) on delete cascade,
  constraint chat_messages_role_known check (role in ('user', 'assistant')),
  constraint chat_messages_status_known check (status in ('complete', 'abstained', 'error', 'interrupted')),
  constraint chat_messages_finish_reason_known check (finish_reason is null or finish_reason in ('stop', 'abstained', 'length', 'error')),
  constraint chat_messages_content_length check (char_length(content) <= 8000),
  constraint chat_messages_trace_id_length check (trace_id is null or char_length(trace_id) <= 200),
  constraint chat_messages_citations_array check (jsonb_typeof(citations) = 'array'),
  constraint chat_messages_abstention_object check (abstention is null or jsonb_typeof(abstention) = 'object'),
  -- El mensaje de la persona: no vacío y sin ningún dato del agente.
  constraint chat_messages_user_shape check (
    role <> 'user' or (
      content ~ '[^[:space:]]' and status = 'complete' and finish_reason is null and trace_id is null
      and has_source is null and citations = '[]'::jsonb and abstention is null
    )
  ),
  -- El estado y la razón de fin cuentan lo mismo (el asistente). Ojo con los nulos: sin `is not null`, `complete` sin razón de fin pasaría el CHECK.
  constraint chat_messages_status_matches_finish check (
    role <> 'assistant' or (
      (status = 'complete' and finish_reason is not null and finish_reason in ('stop', 'length'))
      or (status = 'abstained' and finish_reason is not distinct from 'abstained')
      or (status = 'error' and (finish_reason is null or finish_reason = 'error'))
      or (status = 'interrupted' and finish_reason is null)
    )
  ),
  constraint chat_messages_source_only_when_complete check (has_source is null or status = 'complete')
);

-- El hilo de una conversación en orden, y el tope por hora: solo cuenta los mensajes de la persona.
create index chat_messages_thread on public.chat_messages (conversation_id, created_at, id);
create index chat_messages_user_recent on public.chat_messages (owner_id, created_at) where role = 'user';

alter table public.chat_messages enable row level security;
alter table public.chat_messages force row level security;
revoke all on public.chat_messages from public, anon, authenticated, service_role;

create policy chat_messages_select_owner on public.chat_messages for select to authenticated
  using (owner_id = (select auth.uid()));

grant select on public.chat_messages to authenticated;

-- Inmutable para todos, también para el dueño de la tabla. El único borrado posible es el que arrastra la conversación: cuando se ejecuta la cascada, la
-- conversación padre ya no existe; un borrado suelto la encuentra y falla. Si se cambia el tratamiento del padre, hay que cambiar esta función.
create function private.chat_messages_is_immutable() returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  if tg_op = 'DELETE' and not exists (select 1 from public.chat_conversations c where c.id = old.conversation_id) then
    return old;
  end if;
  raise exception 'chat_message_immutable' using errcode = 'P0001';
end
$$;

create function private.chat_messages_no_truncate() returns trigger
language plpgsql set search_path = ''
as $$
begin
  raise exception 'chat_message_immutable' using errcode = 'P0001';
end
$$;

create trigger chat_messages_no_update_delete before update or delete on public.chat_messages
  for each row execute function private.chat_messages_is_immutable();
create trigger chat_messages_no_truncate before truncate on public.chat_messages
  for each statement execute function private.chat_messages_no_truncate();

revoke all on all functions in schema private from public;
