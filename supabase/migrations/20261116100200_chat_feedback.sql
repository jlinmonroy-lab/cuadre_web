-- SPEC-W-004 §5.2 · Valoración de las respuestas del chatbot (RF-018, D-04).
--
-- `chat_feedback`: una valoración por mensaje del asistente, editable. Pulgar arriba o abajo; abajo exige un motivo de la lista cerrada y arriba no lleva
-- ninguno. Sin texto libre (podría ser dato personal). Es local: no se envía al agente.
--
-- Ojo con los nulos: sin `reason is not null`, un pulgar abajo sin motivo pasaría el CHECK (`null in (...)` no es falso).
-- No se escribe directamente: pasa por `app.rate_chat_message`, que comprueba que el mensaje es del asistente y de la persona. Se borra con el mensaje.

create table public.chat_feedback (
  message_id uuid primary key,
  owner_id   uuid not null references public.profiles (id) on delete cascade,
  rating     text not null,
  reason     text,
  updated_at timestamptz not null default now(),
  constraint chat_feedback_message_fk foreign key (message_id, owner_id)
    references public.chat_messages (id, owner_id) on delete cascade,
  constraint chat_feedback_rating_known check (rating in ('up', 'down')),
  constraint chat_feedback_reason_matches_rating check (
    (rating = 'up' and reason is null)
    or (rating = 'down' and reason is not null and reason in ('incorrect', 'no_source', 'not_helpful', 'other'))
  )
);

create trigger chat_feedback_touch_updated_at before update on public.chat_feedback
  for each row execute function private.touch_updated_at();

alter table public.chat_feedback enable row level security;
alter table public.chat_feedback force row level security;
revoke all on public.chat_feedback from public, anon, authenticated, service_role;

create policy chat_feedback_select_owner on public.chat_feedback for select to authenticated
  using (owner_id = (select auth.uid()));

grant select on public.chat_feedback to authenticated;
