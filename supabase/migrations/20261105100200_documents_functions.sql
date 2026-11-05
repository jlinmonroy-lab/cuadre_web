-- SPEC-W-002 §5.2 · Funciones `app.*` de documentos. Son la ÚNICA vía de escritura en `documents`.
--
-- Mismo patrón que SPEC-W-001: SECURITY DEFINER con `search_path = ''`, comprueban quién llama con auth.uid() y private.app_role(),
-- cambian el estado y lo registran en activity_log EN LA MISMA TRANSACCIÓN. Errores: 42501 si el rol no basta; P0001 con un código
-- estable en el mensaje (`document_not_found`, `document_wrong_state`, `too_many_processing`, `invalid_review`). Un documento ajeno
-- responde igual que uno inexistente: no se revela que existe. El registro de actividad lleva identificadores, tipos y contadores;
-- NUNCA nombres de archivo, NIF ni importes.

-- Constantes de la spec (D-03 y AC-11), en un solo sitio.
create function private.document_max_processing() returns integer
language sql immutable set search_path = ''
as $$ select 5 $$;

create function private.document_processing_timeout() returns interval
language sql immutable set search_path = ''
as $$ select interval '120 seconds' $$;

-- Bloquea y devuelve el documento de quien llama. Mismo error si no existe o es de otra persona.
create function private.document_lock_own(p_id uuid) returns public.documents
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents%rowtype;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select * into v_doc from public.documents d where d.id = p_id and d.owner_id = (select auth.uid()) for update;
  if not found then
    raise exception 'document_not_found' using errcode = 'P0001';
  end if;
  return v_doc;
end
$$;

-- ¿Cabe otra lectura simultánea? No cuentan las que llevan más del tiempo máximo sin cambios (se tratan como fallidas).
-- El cerrojo asesor por persona hace que dos peticiones a la vez no superen el límite.
create function private.document_assert_room_to_read(p_owner uuid, p_except uuid default null) returns void
language plpgsql security definer set search_path = ''
as $$
begin
  perform pg_advisory_xact_lock(hashtextextended('documents.processing:' || p_owner::text, 0));
  if (select count(*) from public.documents d
       where d.owner_id = p_owner and d.status = 'processing'
         and d.updated_at > now() - private.document_processing_timeout()
         and d.id is distinct from p_except) >= private.document_max_processing() then
    raise exception 'too_many_processing' using errcode = 'P0001';
  end if;
end
$$;

-- Reserva el documento y su ruta de Storage. No registra actividad: todavía no hay nada subido.
create function app.create_document(p_filename text, p_mime text, p_size bigint, p_source public.upload_source)
returns table (document_id uuid, object_path text)
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_id uuid := gen_random_uuid();
  v_ext text;
  v_path text;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;
  perform private.document_assert_room_to_read(v_uid);

  v_ext := case p_mime
    when 'application/pdf' then 'pdf' when 'image/jpeg' then 'jpg' when 'image/png' then 'png'
    when 'image/heic' then 'heic' when 'image/webp' then 'webp' else 'bin' end;
  v_path := v_uid::text || '/' || v_id::text || '.' || v_ext;

  insert into public.documents (id, owner_id, source, original_filename, mime_type, size_bytes, storage_path)
  values (v_id, v_uid, p_source, p_filename, p_mime, p_size, v_path);

  return query select v_id, v_path;
end
$$;

-- uploading -> processing. Aquí empieza la lectura, así que aquí se impone el límite de lecturas simultáneas.
create function app.mark_document_uploaded(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if v_doc.status <> 'uploading' then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;
  perform private.document_assert_room_to_read(v_doc.owner_id, v_doc.id);

  update public.documents set status = 'processing', uploaded_at = now() where id = p_id;

  perform private.log_activity('data', v_doc.owner_id, 'usuario', v_doc.owner_id, 'document.uploaded', 'document', p_id::text,
                               jsonb_build_object('document_id', p_id, 'mime_type', v_doc.mime_type,
                                                  'size_bytes', v_doc.size_bytes, 'source', v_doc.source));
end
$$;

-- processing -> review. Guarda la lectura ya normalizada por la API (céntimos enteros; la CHECK de la tabla lo exige).
create function app.record_extraction(p_id uuid, p_extraction jsonb, p_injection boolean, p_trace text, p_cost numeric)
returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if v_doc.status <> 'processing' then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;

  update public.documents
     set status = 'review', extraction = p_extraction, injection_suspected = coalesce(p_injection, false),
         agent_trace_id = p_trace, agent_cost_eur = p_cost, extracted_at = now(), error_code = null
   where id = p_id;

  perform private.log_activity('data', v_doc.owner_id, 'usuario', v_doc.owner_id, 'document.extracted', 'document', p_id::text,
                               jsonb_build_object(
                                 'document_id', p_id,
                                 'injection_suspected', coalesce(p_injection, false),
                                 'doubtful_count', case when jsonb_typeof(p_extraction -> 'doubtful_fields') = 'array'
                                                        then jsonb_array_length(p_extraction -> 'doubtful_fields') else 0 end));
end
$$;

-- processing -> extraction_failed.
create function app.fail_extraction(p_id uuid, p_code text) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if v_doc.status <> 'processing' then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;

  update public.documents set status = 'extraction_failed', error_code = p_code where id = p_id;

  perform private.log_activity('data', v_doc.owner_id, 'usuario', v_doc.owner_id, 'document.extraction_failed', 'document', p_id::text,
                               jsonb_build_object('document_id', p_id, 'error_code', p_code));
end
$$;

-- extraction_failed (o processing caducado) -> processing, con el mismo id: la lectura es idempotente por documento.
create function app.retry_document(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if not (v_doc.status = 'extraction_failed'
          or (v_doc.status = 'processing' and v_doc.updated_at <= now() - private.document_processing_timeout())) then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;
  perform private.document_assert_room_to_read(v_doc.owner_id, v_doc.id);

  update public.documents set status = 'processing', error_code = null where id = p_id;
end
$$;

-- Guarda las correcciones de la persona. La lectura original no cambia (el trigger lo impide).
create function app.save_document_review(p_id uuid, p_review jsonb) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if v_doc.status not in ('review', 'extraction_failed') then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;
  if p_review is null then
    raise exception 'invalid_review' using errcode = 'P0001';
  end if;

  update public.documents set review = p_review where id = p_id;
end
$$;

-- Cualquier estado vivo -> discarded. El archivo lo borra la API con el JWT del usuario.
create function app.discard_document(p_id uuid) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if v_doc.status not in ('uploading', 'processing', 'review', 'extraction_failed') then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;

  update public.documents set status = 'discarded' where id = p_id;

  perform private.log_activity('data', v_doc.owner_id, 'usuario', v_doc.owner_id, 'document.discarded', 'document', p_id::text,
                               jsonb_build_object('document_id', p_id, 'from_status', v_doc.status));
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`; los ayudantes de
-- `private` los invocan estas funciones (mismo dueño) y no se conceden a nadie.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function
  app.create_document(text, text, bigint, public.upload_source),
  app.mark_document_uploaded(uuid),
  app.record_extraction(uuid, jsonb, boolean, text, numeric),
  app.fail_extraction(uuid, text),
  app.retry_document(uuid),
  app.save_document_review(uuid, jsonb),
  app.discard_document(uuid)
  to authenticated;
