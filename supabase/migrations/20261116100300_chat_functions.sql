-- SPEC-W-004 §5.2 · Escrituras del chat. `SECURITY DEFINER` con `search_path = ''`; errores `P0001` con código estable; `42501` si no es `usuario` activo.
--
-- Códigos: `chat_rate_limited` (tope por hora alcanzado), `conversation_not_found` (no existe o es de otra persona: no se distingue), `message_not_found`,
-- `invalid_hourly_limit`. Los CHECK de las tablas dan el resto (contenido vacío o demasiado largo, estado incoherente, motivo de valoración).
--
-- El reloj es el de la base de datos (`now()`): no hay un `now` que pasar desde fuera y nadie puede falsearlo. El límite por hora y el título llegan como
-- parámetros: la constante vive en `cuadre.chat.limits` y la regla del título (recorte por palabra) es Python puro.

-- El mensaje de la persona. Con `p_conversation_id` nulo crea la conversación (D-03); con uno, la bloquea y añade. El cerrojo asesor por persona hace que
-- dos envíos a la vez no superen el tope (AC-16). Cuenta solo los mensajes de la persona de la última hora: los del asistente y los antiguos no.
create function app.append_chat_user_message(p_conversation_id uuid, p_content text, p_title text, p_hourly_limit integer)
returns table (conversation_id uuid, message_id uuid)
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
  v_conversation uuid;
  v_message uuid;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  if p_hourly_limit is null or p_hourly_limit not between 1 and 1000 then
    raise exception 'invalid_hourly_limit' using errcode = 'P0001';
  end if;

  perform pg_advisory_xact_lock(hashtextextended('chat:' || v_owner::text, 0));

  if p_conversation_id is not null then
    select c.id into v_conversation from public.chat_conversations c
     where c.id = p_conversation_id and c.owner_id = v_owner for update;
    if v_conversation is null then
      raise exception 'conversation_not_found' using errcode = 'P0001';
    end if;
  end if;

  if (select count(*) from public.chat_messages m
       where m.owner_id = v_owner and m.role = 'user' and m.created_at > now() - interval '1 hour') >= p_hourly_limit then
    raise exception 'chat_rate_limited' using errcode = 'P0001';
  end if;

  if v_conversation is null then
    insert into public.chat_conversations (owner_id, title) values (v_owner, p_title) returning id into v_conversation;
  end if;

  insert into public.chat_messages (conversation_id, owner_id, role, content)
  values (v_conversation, v_owner, 'user', p_content)
  returning id into v_message;

  update public.chat_conversations set last_message_at = now() where id = v_conversation;

  return query select v_conversation, v_message;
end
$$;

-- La respuesta del asistente, una sola vez y al final (D-07). El id lo asigna la web (D-06): un id repetido falla por la clave. `for share` impide que
-- se borre la conversación mientras se inserta.
create function app.append_chat_assistant_message(
  p_conversation_id uuid, p_message_id uuid, p_content text, p_status text, p_finish_reason text, p_trace_id text,
  p_has_source boolean, p_citations jsonb, p_abstention jsonb
) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
  v_conversation uuid;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select c.id into v_conversation from public.chat_conversations c
   where c.id = p_conversation_id and c.owner_id = v_owner for share;
  if v_conversation is null then
    raise exception 'conversation_not_found' using errcode = 'P0001';
  end if;

  insert into public.chat_messages (id, conversation_id, owner_id, role, content, status, finish_reason, trace_id, has_source, citations, abstention)
  values (p_message_id, v_conversation, v_owner, 'assistant', p_content, p_status, p_finish_reason, p_trace_id, p_has_source,
          coalesce(p_citations, '[]'::jsonb), p_abstention);

  update public.chat_conversations set last_message_at = now() where id = v_conversation;
end
$$;

-- Borra la conversación de la persona con todo lo suyo: mensajes y valoraciones se van por la cascada.
create function app.delete_chat_conversation(p_conversation_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
  v_deleted uuid;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  delete from public.chat_conversations c where c.id = p_conversation_id and c.owner_id = v_owner returning c.id into v_deleted;
  if v_deleted is null then
    raise exception 'conversation_not_found' using errcode = 'P0001';
  end if;
end
$$;

-- Valora (o cambia la valoración de) una respuesta del asistente de la propia persona. Un mensaje de la persona, ajeno o inexistente no se distingue.
create function app.rate_chat_message(p_message_id uuid, p_rating text, p_reason text) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := (select auth.uid());
  v_message uuid;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select m.id into v_message from public.chat_messages m
   where m.id = p_message_id and m.owner_id = v_owner and m.role = 'assistant';
  if v_message is null then
    raise exception 'message_not_found' using errcode = 'P0001';
  end if;

  insert into public.chat_feedback (message_id, owner_id, rating, reason)
  values (v_message, v_owner, p_rating, p_reason)
  on conflict (message_id) do update set rating = excluded.rating, reason = excluded.reason, updated_at = now();
end
$$;

revoke all on function app.append_chat_user_message(uuid, text, text, integer) from public;
revoke all on function app.append_chat_assistant_message(uuid, uuid, text, text, text, text, boolean, jsonb, jsonb) from public;
revoke all on function app.delete_chat_conversation(uuid) from public;
revoke all on function app.rate_chat_message(uuid, text, text) from public;
grant execute on function app.append_chat_user_message(uuid, text, text, integer) to authenticated;
grant execute on function app.append_chat_assistant_message(uuid, uuid, text, text, text, text, boolean, jsonb, jsonb) to authenticated;
grant execute on function app.delete_chat_conversation(uuid) to authenticated;
grant execute on function app.rate_chat_message(uuid, text, text) to authenticated;
