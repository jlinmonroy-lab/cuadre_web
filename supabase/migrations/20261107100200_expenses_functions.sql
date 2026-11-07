-- SPEC-W-003 §5.2 · Funciones `app.*` de gastos. Son la ÚNICA vía de escritura en `expenses` (y la única que lleva un documento
-- a `registered` y lo devuelve a revisión).
--
-- Mismo patrón que SPEC-W-002: SECURITY DEFINER con `search_path = ''`, comprueban quién llama con auth.uid() y private.app_role(),
-- cambian el estado y lo registran en activity_log EN LA MISMA TRANSACCIÓN. Errores: 42501 si el rol no basta; P0001 con un código
-- estable en el mensaje (`document_not_found`, `document_wrong_state`, `suspicion_not_acknowledged`, `invalid_expense`,
-- `expense_not_found`, `expense_wrong_state`); `invalid_expense` lleva en `detail` el campo que falla (§5.3). Un documento o un
-- gasto ajeno responde igual que uno inexistente. El registro de actividad lleva identificadores, categoría y marcas;
-- NUNCA nombres, NIF, números de factura ni importes (T3-08).
--
-- Lo que estas funciones NO garantizan (de eso se ocupa `cuadre.validators`, D-01): que el NIF sea válido, que la cuota cuadre con
-- el tipo o que no haya un duplicado que no sea exacto. Comprueban lo barato; el resto lo defienden las CHECK y los índices de
-- `expenses`. Orden de cerrojos: primero el documento y después el gasto, en todas.

-- «Hoy» en Europe/Madrid: a las 23:30 UTC de un 31 de diciembre ya es 1 de enero.
create function private.today_madrid() returns date
language sql stable set search_path = ''
as $$ select (now() at time zone 'Europe/Madrid')::date $$;

-- Bloquea y devuelve el gasto de quien llama. Mismo error si no existe o es de otra persona.
create function private.expense_lock_own(p_id uuid) returns public.expenses
language plpgsql security definer set search_path = ''
as $$
declare
  v_expense public.expenses%rowtype;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  select * into v_expense from public.expenses e where e.id = p_id and e.owner_id = (select auth.uid()) for update;
  if not found then
    raise exception 'expense_not_found' using errcode = 'P0001';
  end if;
  return v_expense;
end
$$;

-- Primer campo de `p_values` que no tiene la forma esperada, o NULL si todo está bien. `values` si el objeto en sí no vale (no es un
-- objeto, tiene claves de más). Cada importe ha de ser un entero JSON de 0 a 15 cifras (RES-02): 12.5, 12.0 y "12" no valen.
create function private.expense_values_problem(p jsonb) returns text
language plpgsql immutable set search_path = ''
as $$
declare
  v_known constant text[] := array['expense_date', 'supplier_name', 'supplier_tax_id', 'supplier_scope', 'invoice_number',
                                   'doc_type', 'base_cents', 'vat_cents', 'withholding_cents', 'total_cents',
                                   'tax_breakdown', 'deductible_vat'];
  v_key text;
begin
  if p is null or jsonb_typeof(p) <> 'object' then
    return 'values';
  end if;
  for v_key in select jsonb_object_keys(p) loop
    if not (v_key = any (v_known)) then
      return 'values';
    end if;
  end loop;
  foreach v_key in array v_known loop
    if not (p ? v_key) then
      return v_key;
    end if;
  end loop;

  foreach v_key in array array['expense_date', 'supplier_name', 'supplier_tax_id', 'supplier_scope', 'doc_type'] loop
    if jsonb_typeof(p -> v_key) <> 'string' then
      return v_key;
    end if;
  end loop;
  if jsonb_typeof(p -> 'invoice_number') not in ('string', 'null') then
    return 'invoice_number';
  end if;
  if (p ->> 'expense_date') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then
    return 'expense_date';
  end if;
  if (p ->> 'supplier_scope') not in ('national', 'eu') then
    return 'supplier_scope';
  end if;
  foreach v_key in array array['base_cents', 'vat_cents', 'withholding_cents', 'total_cents'] loop
    if jsonb_typeof(p -> v_key) <> 'number' or (p ->> v_key) !~ '^[0-9]{1,15}$' then
      return v_key;
    end if;
  end loop;
  if jsonb_typeof(p -> 'tax_breakdown') <> 'array' then
    return 'tax_breakdown';
  end if;
  if jsonb_typeof(p -> 'deductible_vat') <> 'boolean' then
    return 'deductible_vat';
  end if;
  return null;
end
$$;

-- Devuelve el documento de quien llama, BLOQUEADO (`FOR UPDATE`) hasta el fin de la transacción: permite validar y registrar sin que
-- nadie lo cambie entre medias. Mismo error si no existe, es ajeno o está descartado.
create function app.lock_document(p_id uuid) returns public.documents
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_id);
begin
  if v_doc.status = 'discarded' then
    raise exception 'document_not_found' using errcode = 'P0001';
  end if;
  return v_doc;
end
$$;

-- review | extraction_failed -> registered, con un gasto nuevo. `p_values` son los valores YA normalizados que devuelve
-- `cuadre.validators` (claves en `private.expense_values_problem`; `invoice_number_key` no se envía: la base la genera).
create function app.register_expense_from_document(
  p_document_id uuid, p_category public.expense_category, p_values jsonb, p_acknowledged boolean
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_doc public.documents := private.document_lock_own(p_document_id);
  v_id uuid := gen_random_uuid();
  v_date date;
  v_problem text;
  v_acknowledged boolean;
begin
  if v_doc.status not in ('review', 'extraction_failed') then
    raise exception 'document_wrong_state' using errcode = 'P0001';
  end if;
  -- NFR-07: una sospecha de instrucciones ocultas se reconoce para registrar, también aquí y no solo en la API.
  if v_doc.injection_suspected and not coalesce(p_acknowledged, false) then
    raise exception 'suspicion_not_acknowledged' using errcode = 'P0001';
  end if;
  v_acknowledged := v_doc.injection_suspected and coalesce(p_acknowledged, false);

  if p_category is null then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'category';
  end if;
  v_problem := private.expense_values_problem(p_values);
  if v_problem is not null then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = v_problem;
  end if;

  begin
    v_date := (p_values ->> 'expense_date')::date;
  exception when others then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'expense_date';
  end;
  if v_date < private.expense_earliest_date() or v_date > private.today_madrid() then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'expense_date';
  end if;
  if not private.expense_breakdown_matches(
       p_values -> 'tax_breakdown', (p_values ->> 'base_cents')::bigint, (p_values ->> 'vat_cents')::bigint) then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'tax_breakdown';
  end if;

  insert into public.expenses (
    id, owner_id, origin, document_id, expense_date, supplier_name, supplier_tax_id, invoice_number, doc_type, supplier_scope,
    category, base_cents, vat_cents, withholding_cents, total_cents, tax_breakdown, deductible_vat, suspicion_acknowledged)
  values (
    v_id, v_doc.owner_id, 'document', p_document_id, v_date, p_values ->> 'supplier_name', p_values ->> 'supplier_tax_id',
    p_values ->> 'invoice_number', p_values ->> 'doc_type', (p_values ->> 'supplier_scope')::public.supplier_scope,
    p_category, (p_values ->> 'base_cents')::bigint, (p_values ->> 'vat_cents')::bigint,
    (p_values ->> 'withholding_cents')::bigint, (p_values ->> 'total_cents')::bigint, p_values -> 'tax_breakdown',
    (p_values ->> 'deductible_vat')::boolean, v_acknowledged);

  update public.documents set status = 'registered' where id = p_document_id;

  perform private.log_activity('data', v_doc.owner_id, 'usuario', v_doc.owner_id, 'expense.registered', 'expense', v_id::text,
                               jsonb_build_object('expense_id', v_id, 'document_id', p_document_id, 'origin', 'document',
                                                  'category', p_category, 'acknowledged_suspicion', v_acknowledged));
  return v_id;
end
$$;

-- Gasto sin factura (RF-011, D-09): puntual, sin IVA y no deducible. El concepto se guarda recortado.
create function app.create_manual_expense(p_date date, p_concept text, p_category public.expense_category, p_amount_cents bigint)
returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_id uuid := gen_random_uuid();
  v_concept text := btrim(p_concept);
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  if p_date is null or p_date < private.expense_earliest_date() or p_date > private.today_madrid() then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'expense_date';
  end if;
  if v_concept is null or char_length(v_concept) not between 1 and 200 then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'concept';
  end if;
  if p_category is null then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'category';
  end if;
  if p_amount_cents is null or p_amount_cents not between 1 and 999999999999999 then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'amount_cents';
  end if;

  insert into public.expenses (
    id, owner_id, origin, expense_date, supplier_name, category, base_cents, vat_cents, withholding_cents, total_cents,
    tax_breakdown, deductible_vat)
  values (v_id, v_uid, 'manual', p_date, v_concept, p_category, p_amount_cents, 0, 0, p_amount_cents, '[]', false);

  perform private.log_activity('data', v_uid, 'usuario', v_uid, 'expense.registered', 'expense', v_id::text,
                               jsonb_build_object('expense_id', v_id, 'document_id', null, 'origin', 'manual',
                                                  'category', p_category, 'acknowledged_suspicion', false));
  return v_id;
end
$$;

-- Cambia la categoría de un gasto vivo. Si es la misma, no hace nada ni registra.
create function app.set_expense_category(p_id uuid, p_category public.expense_category) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_expense public.expenses := private.expense_lock_own(p_id);
begin
  if v_expense.voided_at is not null then
    raise exception 'expense_wrong_state' using errcode = 'P0001';
  end if;
  if p_category is null then
    raise exception 'invalid_expense' using errcode = 'P0001', detail = 'category';
  end if;
  if p_category = v_expense.category then
    return;
  end if;

  update public.expenses set category = p_category where id = p_id;

  perform private.log_activity('data', v_expense.owner_id, 'usuario', v_expense.owner_id, 'expense.category_changed', 'expense',
                               p_id::text, jsonb_build_object('expense_id', p_id, 'from_category', v_expense.category,
                                                              'to_category', p_category));
end
$$;

-- Anula un gasto: deja de contar y, si venía de un documento, el documento vuelve a revisión (D-10): a `review` si tiene lectura,
-- a `extraction_failed` si nunca la hubo (su `review` y su motivo de fallo se conservan). Devuelve el estado del documento, o NULL.
create function app.void_expense(p_id uuid) returns public.document_status
language plpgsql security definer set search_path = ''
as $$
declare
  v_document_id uuid;
  v_doc public.documents;
  v_expense public.expenses;
  v_next public.document_status;
begin
  if private.app_role() is distinct from 'usuario'::public.user_role then
    raise exception 'insufficient_privilege' using errcode = '42501';
  end if;

  -- Primero el documento y después el gasto (el mismo orden que al registrar): el gasto se localiza sin bloquearlo.
  select e.document_id into v_document_id from public.expenses e where e.id = p_id and e.owner_id = (select auth.uid());
  if not found then
    raise exception 'expense_not_found' using errcode = 'P0001';
  end if;
  if v_document_id is not null then
    v_doc := private.document_lock_own(v_document_id);
  end if;
  v_expense := private.expense_lock_own(p_id);
  if v_expense.voided_at is not null then
    raise exception 'expense_wrong_state' using errcode = 'P0001';
  end if;

  update public.expenses set voided_at = now() where id = p_id;

  if v_document_id is not null then
    v_next := case when v_doc.extraction is not null then 'review' else 'extraction_failed' end;
    update public.documents set status = v_next where id = v_document_id;
  end if;

  perform private.log_activity('data', v_expense.owner_id, 'usuario', v_expense.owner_id, 'expense.voided', 'expense', p_id::text,
                               jsonb_build_object('expense_id', p_id, 'origin', v_expense.origin));
  return v_next;
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`; los ayudantes de
-- `private` los invocan estas funciones (mismo dueño) y no se conceden a nadie.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function
  app.lock_document(uuid),
  app.register_expense_from_document(uuid, public.expense_category, jsonb, boolean),
  app.create_manual_expense(date, text, public.expense_category, bigint),
  app.set_expense_category(uuid, public.expense_category),
  app.void_expense(uuid)
  to authenticated;
