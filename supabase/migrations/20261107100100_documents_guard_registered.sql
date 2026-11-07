-- SPEC-W-003 §5.2 · `documents_guard` ampliado: `registered` deja de ser terminal.
--
-- Sustituye con CREATE OR REPLACE al trigger de la migración 20261105100100 (las aplicadas no se editan, T3-12). El trigger de la
-- tabla sigue siendo el mismo; solo cambia la función. Reglas nuevas:
--   * `review > registered` y `extraction_failed > registered`: solo si el documento tiene un gasto VIVO (D-11);
--   * `registered > review` y `registered > extraction_failed`: solo si el gasto del documento se ha anulado EN ESTA MISMA
--     TRANSACCIÓN (`voided_at = now()`, que en PostgreSQL es la hora de la transacción) y ya no queda ninguno vivo (D-10);
--   * cualquier otra actualización de un `registered` (también una que no cambie el estado) es una transición ilegal;
--   * `discarded` sigue siendo terminal.

create or replace function private.documents_guard() returns trigger
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

  if old.status = 'discarded' then
    raise exception 'document_invalid_transition' using errcode = 'P0001';
  end if;

  if old.status = 'registered' then
    -- Solo se sale de `registered` al anular su gasto, y con la anulación hecha en esta misma transacción.
    if new.status not in ('review', 'extraction_failed')
       or not exists (select 1 from public.expenses e where e.document_id = old.id and e.voided_at = now())
       or exists (select 1 from public.expenses e where e.document_id = old.id and e.voided_at is null) then
      raise exception 'document_invalid_transition' using errcode = 'P0001';
    end if;
  elsif new.status is distinct from old.status then
    if not (v_move = any (array[
         'uploading>processing', 'uploading>discarded',
         'processing>review', 'processing>extraction_failed', 'processing>discarded',
         'review>discarded', 'review>registered',
         'extraction_failed>processing', 'extraction_failed>discarded', 'extraction_failed>registered'
       ])) then
      raise exception 'document_invalid_transition' using errcode = 'P0001';
    end if;
    -- Registrar exige un gasto vivo del documento (la función lo inserta antes de cambiar el estado).
    if new.status = 'registered'
       and not exists (select 1 from public.expenses e where e.document_id = old.id and e.voided_at is null) then
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

revoke all on all functions in schema private from public;
