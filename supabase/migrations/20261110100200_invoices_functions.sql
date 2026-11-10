-- SPEC-W-007 §5.2 · Emisión de facturas. Son la ÚNICA vía de escritura en `invoices` y `invoice_files`.
--
-- Mismo patrón que SPEC-W-005 y SPEC-W-006: SECURITY DEFINER con `search_path = ''`, comprueban quién llama con auth.uid() y
-- private.app_role() (solo `usuario`: un gestor, un administrador o una cuenta suspendida reciben 42501), errores P0001 con un código estable
-- en el mensaje y, si procede, el campo o el dato en el DETAIL. Una factura, serie o cliente ajenos responden igual que los inexistentes.
--
-- CERROJOS (B.1-D, obligatorios). TODAS empiezan por `private.series_enter()`: el cerrojo asesor de la persona, que serializa cuanto emite,
-- numera o cobra. Además, la emisión bloquea la FILA de la serie (`FOR UPDATE`) y la de la original en una rectificativa (`FOR UPDATE`, antes
-- de calcular lo vigente), y el cliente con `FOR SHARE` (no se edita ni se archiva mientras se factura). Orden fijo, el mismo siempre, para no
-- abrir interbloqueos: persona → serie → cliente → original. La fecha se compara DENTRO del cerrojo. Medido sin ellos: 20 hilos × 5
-- emisiones daban 18 de 100 y cinco anulaciones simultáneas de una factura admitían dos.
--
-- LO QUE LA BASE REPITE Y LO QUE NO (D-10 de SPEC-W-006). Las condiciones fiscales (`p_terms`) las calcula `cuadre.tax`; aquí se comprueba
-- que son COHERENTES: el tratamiento es el del cliente, los tipos son los permitidos, el perfil manda en la retención, el total es base + IVA
-- − retención. No se recalcula un porcentaje. En cambio, lo que protege el libro SÍ se recalcula bajo el cerrojo: en una rectificativa, la
-- base vigente (la de la original más sus rectificativas) y que lo devuelto nunca deje la base, el IVA o la retención vigentes por debajo
-- de cero: nadie devuelve dos veces una factura aunque llame a la función a mano.
--
-- ORDEN DE LAS COMPROBACIONES (emitir): rol → serie → cliente (no existe, archivado, sin domicilio) → perfil → forma de los campos (fecha no
-- futura, concepto, base, condiciones) → retención sin elegir → fecha anterior a la última de la serie → serie agotada → coherencia de las
-- condiciones. En una rectificativa: rol → fecha → serie del año → original (no existe, ya es rectificativa) → perfil → motivo, base corregida
-- y condiciones → nada que rectificar → la base sube → fechas (la de la original, la de la serie) → serie agotada → coherencia.

-- Tratamiento que corresponde a un cliente (§5.1.2). Es la única tabla de la base que mira el ámbito; la regla vive en `cuadre.tax`.
create function private.invoice_expected_treatment(p_scope public.client_scope, p_kind public.client_kind)
returns public.invoice_tax_treatment
language sql immutable set search_path = ''
as $$
  select case
    when p_scope = 'national' then 'national_vat'::public.invoice_tax_treatment
    when p_scope = 'eu' and p_kind = 'business' then 'eu_reverse_charge'::public.invoice_tax_treatment
    when p_scope = 'eu' then 'eu_consumer_vat'::public.invoice_tax_treatment
    when p_kind = 'business' then 'non_eu_not_subject'::public.invoice_tax_treatment
    else 'non_eu_consumer_vat'::public.invoice_tax_treatment
  end
$$;

-- Primer campo de `p_terms` que no tiene la forma esperada, o NULL si todo está bien. `terms` si el objeto en sí no vale (no es un objeto,
-- le faltan o le sobran claves). En una factura ordinaria lleva las siete condiciones; en una rectificativa solo los tres importes (lo demás
-- lo hereda de la original). Cada importe es un entero JSON de hasta 15 cifras (RES-02): 12.5, 12.0 y "12" no valen; en la rectificativa
-- pueden ser negativos. Los tipos son números JSON: 21, 21.0 y 21.00 valen.
create function private.invoice_terms_problem(p jsonb, p_rectifying boolean) returns text
language plpgsql immutable set search_path = ''
as $$
declare
  v_known text[] := case when p_rectifying then array['vat_cents', 'irpf_cents', 'total_cents']
    else array['tax_treatment', 'vat_rate', 'vat_cents', 'irpf_rate', 'irpf_cents', 'total_cents', 'legal_note'] end;
  v_cents_pattern text := case when p_rectifying then '^-?[0-9]{1,15}$' else '^[0-9]{1,15}$' end;
  v_key text;
begin
  if p is null or jsonb_typeof(p) <> 'object' then
    return 'terms';
  end if;
  for v_key in select jsonb_object_keys(p) loop
    if not (v_key = any (v_known)) then
      return 'terms';
    end if;
  end loop;
  foreach v_key in array v_known loop
    if not (p ? v_key) then
      return v_key;
    end if;
  end loop;

  if not p_rectifying then
    if jsonb_typeof(p -> 'tax_treatment') <> 'string'
       or (p ->> 'tax_treatment') not in ('national_vat', 'eu_reverse_charge', 'eu_consumer_vat', 'non_eu_consumer_vat', 'non_eu_not_subject') then
      return 'tax_treatment';
    end if;
    foreach v_key in array array['vat_rate', 'irpf_rate'] loop
      if jsonb_typeof(p -> v_key) <> 'number' or (p ->> v_key) !~ '^[0-9]{1,2}(\.0{1,2})?$' then
        return v_key;
      end if;
    end loop;
    if jsonb_typeof(p -> 'legal_note') not in ('string', 'null') or char_length(p ->> 'legal_note') > 300 then
      return 'legal_note';
    end if;
  end if;
  foreach v_key in array array['vat_cents', 'irpf_cents', 'total_cents'] loop
    if jsonb_typeof(p -> v_key) <> 'number' or (p ->> v_key) !~ v_cents_pattern then
      return v_key;
    end if;
  end loop;
  return null;
end
$$;

-- Último día en que se emitió algo en la serie, o NULL. Se lee DENTRO del cerrojo de la serie.
create function private.series_last_issue_date(p_owner uuid, p_series uuid) returns date
language sql stable security definer set search_path = ''
as $$
  select max(i.issue_date) from public.invoices i where i.owner_id = p_owner and i.series_id = p_series
$$;

-- La fecha de expedición no es de antes del 2000 ni futura (día de Madrid). Devuelve NULL si vale o `issue_date` si no.
create function private.invoice_date_problem(p_issue_date date) returns text
language sql stable set search_path = ''
as $$
  select case when p_issue_date is null or p_issue_date < date '2000-01-01' or p_issue_date > private.today_madrid()
              then 'issue_date' end
$$;

-- Asigna el número de la serie, lo avanza, guarda la factura y deja constancia. La llaman las dos funciones de emisión con la serie ya
-- bloqueada y la fila lista salvo el número y la copia del código. Si algo falla aquí, todo se deshace: el número no se consume.
create function private.invoice_insert(p_invoice public.invoices, p_series public.invoice_series) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_invoice public.invoices := p_invoice;
begin
  if p_series.next_number > 999999 then
    raise exception 'series_exhausted' using errcode = 'P0001';
  end if;
  v_invoice.series_id := p_series.id;
  v_invoice.series_code := p_series.code;
  v_invoice.number := p_series.next_number;

  update public.invoice_series set next_number = next_number + 1 where id = p_series.id;
  insert into public.invoices values (v_invoice.*);

  perform private.log_activity(
    'data', v_invoice.owner_id, 'usuario', v_invoice.owner_id,
    case when v_invoice.kind = 'rectifying' then 'invoice.rectified' else 'invoice.issued' end,
    'invoice', v_invoice.id::text,
    jsonb_strip_nulls(jsonb_build_object(
      'invoice_id', v_invoice.id, 'series', v_invoice.series_code, 'number', v_invoice.number,
      'treatment', v_invoice.tax_treatment, 'rectifies_id', v_invoice.rectifies_id)));
  return v_invoice.id;
end
$$;

-- Emite una factura ordinaria. Devuelve su id. `p_terms` lleva las siete condiciones ya calculadas (ver arriba).
create function app.issue_invoice(
  p_client_id uuid, p_series_id uuid, p_issue_date date, p_concept text, p_base_cents bigint, p_terms jsonb
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_series public.invoice_series := private.series_lock_for_issue(p_series_id, 'standard');
  v_client public.clients;
  v_profile public.business_profiles;
  v_missing text;
  v_problem text;
  v_treatment public.invoice_tax_treatment;
  v_vat_rate numeric;
  v_irpf_rate numeric;
  v_vat bigint;
  v_irpf bigint;
  v_total bigint;
  v_last date;
  v_invoice public.invoices;
begin
  select * into v_client from public.clients c where c.id = p_client_id and c.owner_id = v_owner for share;
  if not found then
    raise exception 'client_not_found' using errcode = 'P0001';
  end if;
  if v_client.archived_at is not null then
    raise exception 'client_not_billable' using errcode = 'P0001', detail = 'archived';
  end if;
  if btrim(coalesce(v_client.address, '')) = '' then
    raise exception 'client_not_billable' using errcode = 'P0001', detail = 'address';
  end if;

  select * into v_profile from public.business_profiles b where b.owner_id = v_owner;
  select string_agg(f.field, ',' order by f.ord) into v_missing
    from (values (1, 'legal_name', v_profile.legal_name), (2, 'tax_id', v_profile.tax_id), (3, 'fiscal_address', v_profile.fiscal_address))
         as f(ord, field, value)
   where btrim(coalesce(f.value, '')) = '';
  if v_missing is not null then
    raise exception 'profile_incomplete' using errcode = 'P0001', detail = v_missing;
  end if;

  v_problem := coalesce(
    private.invoice_date_problem(p_issue_date),
    case when p_concept is null or char_length(p_concept) not between 2 and 300 then 'concept' end,
    case when p_base_cents is null or p_base_cents not between 1 and 9999999999 then 'base_cents' end,
    private.invoice_terms_problem(p_terms, false));
  -- La fecha futura es un campo; la anterior a la última de la serie es otro error (más abajo, ya con el número en la mano).
  if v_problem is not null then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = v_problem;
  end if;

  v_treatment := private.invoice_expected_treatment(v_client.scope, v_client.kind);
  if v_treatment = 'national_vat' and v_client.kind = 'business' and v_profile.irpf_rate is null then
    raise exception 'irpf_rate_missing' using errcode = 'P0001';
  end if;

  v_last := private.series_last_issue_date(v_owner, v_series.id);
  if v_last is not null and p_issue_date < v_last then
    raise exception 'invoice_date_out_of_order' using errcode = 'P0001', detail = v_last::text;
  end if;
  if v_series.next_number > 999999 then
    raise exception 'series_exhausted' using errcode = 'P0001';
  end if;

  -- Coherencia de las condiciones con el cliente y el perfil (no se recalcula ningún porcentaje).
  v_vat_rate := (p_terms ->> 'vat_rate')::numeric;
  v_irpf_rate := (p_terms ->> 'irpf_rate')::numeric;
  v_vat := (p_terms ->> 'vat_cents')::bigint;
  v_irpf := (p_terms ->> 'irpf_cents')::bigint;
  v_total := (p_terms ->> 'total_cents')::bigint;

  if (p_terms ->> 'tax_treatment')::public.invoice_tax_treatment is distinct from v_treatment then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'tax_treatment';
  end if;
  if v_treatment in ('eu_reverse_charge', 'non_eu_not_subject') then
    if v_vat_rate <> 0 then
      raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'vat_rate';
    end if;
    if v_vat <> 0 then
      raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'vat_cents';
    end if;
  elsif v_vat_rate not in (4, 10, 21) then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'vat_rate';
  end if;
  if v_treatment = 'national_vat' and v_client.kind = 'business' then
    if v_irpf_rate <> v_profile.irpf_rate then
      raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'irpf_rate';
    end if;
  elsif v_irpf_rate <> 0 then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'irpf_rate';
  end if;
  if v_irpf_rate = 0 and v_irpf <> 0 then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'irpf_cents';
  end if;
  if v_total <> p_base_cents + v_vat - v_irpf then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'total_cents';
  end if;
  if (v_treatment in ('eu_reverse_charge', 'non_eu_not_subject')) <> (jsonb_typeof(p_terms -> 'legal_note') = 'string') then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'legal_note';
  end if;

  v_invoice.id := gen_random_uuid();
  v_invoice.owner_id := v_owner;
  v_invoice.kind := 'standard';
  v_invoice.issue_date := p_issue_date;
  v_invoice.client_id := v_client.id;
  v_invoice.client_name := v_client.name;
  v_invoice.client_kind := v_client.kind;
  v_invoice.client_country := v_client.country;
  v_invoice.client_scope := v_client.scope;
  v_invoice.client_tax_id := v_client.tax_id;
  v_invoice.client_address := btrim(v_client.address);
  v_invoice.issuer_name := v_profile.legal_name;
  v_invoice.issuer_tax_id := v_profile.tax_id;
  v_invoice.issuer_address := v_profile.fiscal_address;
  v_invoice.issuer_iban := v_profile.iban;
  v_invoice.concept := p_concept;
  v_invoice.tax_treatment := v_treatment;
  v_invoice.base_cents := p_base_cents;
  v_invoice.vat_rate := v_vat_rate;
  v_invoice.vat_cents := v_vat;
  v_invoice.irpf_rate := v_irpf_rate;
  v_invoice.irpf_cents := v_irpf;
  v_invoice.total_cents := v_total;
  v_invoice.legal_note := p_terms ->> 'legal_note';
  v_invoice.created_at := now();
  return private.invoice_insert(v_invoice, v_series);
end
$$;

-- Emite una rectificativa de `p_original_id` (D-12). `p_corrected_base_cents` es la base DESPUÉS de rectificar (0 = anulación completa);
-- la base de la rectificativa es esa menos la vigente, y el IVA y la retención que lleva `p_terms` (con `total_cents`) son las diferencias
-- de valores. Hereda de la original el cliente, el tratamiento, los tipos y la mención; el emisor es el perfil actual.
create function app.issue_rectifying_invoice(
  p_original_id uuid, p_reason text, p_corrected_base_cents bigint, p_issue_date date, p_terms jsonb
) returns uuid
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_problem text := private.invoice_date_problem(p_issue_date);
  v_series public.invoice_series;
  v_original public.invoices;
  v_profile public.business_profiles;
  v_missing text;
  v_base bigint;
  v_vat bigint;
  v_irpf bigint;
  v_standing_base bigint;
  v_standing_vat bigint;
  v_standing_irpf bigint;
  v_last date;
  v_invoice public.invoices;
begin
  if v_problem is not null then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = v_problem;
  end if;

  -- Serie rectificativa del año de la fecha (la crea si falta), bloqueada; después, la original, bloqueada, y solo entonces lo vigente.
  v_series := private.series_lock_for_issue(app.ensure_rectifying_series(extract(year from p_issue_date)::integer), 'rectifying');
  select * into v_original from public.invoices i where i.id = p_original_id and i.owner_id = v_owner for update;
  if not found then
    raise exception 'invoice_not_found' using errcode = 'P0001';
  end if;
  if v_original.kind = 'rectifying' then
    raise exception 'invoice_not_rectifiable' using errcode = 'P0001';
  end if;

  select * into v_profile from public.business_profiles b where b.owner_id = v_owner;
  select string_agg(f.field, ',' order by f.ord) into v_missing
    from (values (1, 'legal_name', v_profile.legal_name), (2, 'tax_id', v_profile.tax_id), (3, 'fiscal_address', v_profile.fiscal_address))
         as f(ord, field, value)
   where btrim(coalesce(f.value, '')) = '';
  if v_missing is not null then
    raise exception 'profile_incomplete' using errcode = 'P0001', detail = v_missing;
  end if;

  v_problem := coalesce(
    case when p_reason is null or char_length(p_reason) not between 2 and 300 then 'reason' end,
    case when p_corrected_base_cents is null or p_corrected_base_cents < 0 then 'corrected_base_cents' end,
    private.invoice_terms_problem(p_terms, true));
  if v_problem is not null then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = v_problem;
  end if;

  -- Lo vigente: la original más las diferencias de sus rectificativas anteriores.
  select v_original.base_cents + coalesce(sum(r.base_cents), 0),
         v_original.vat_cents + coalesce(sum(r.vat_cents), 0),
         v_original.irpf_cents + coalesce(sum(r.irpf_cents), 0)
    into v_standing_base, v_standing_vat, v_standing_irpf
    from public.invoices r where r.owner_id = v_owner and r.rectifies_id = v_original.id;

  if p_corrected_base_cents = v_standing_base then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'corrected_base_cents';
  end if;
  if p_corrected_base_cents > v_standing_base then
    raise exception 'rectification_exceeds' using errcode = 'P0001';
  end if;

  if p_issue_date < v_original.issue_date then
    raise exception 'invoice_date_out_of_order' using errcode = 'P0001', detail = v_original.issue_date::text;
  end if;
  v_last := private.series_last_issue_date(v_owner, v_series.id);
  if v_last is not null and p_issue_date < v_last then
    raise exception 'invoice_date_out_of_order' using errcode = 'P0001', detail = v_last::text;
  end if;
  if v_series.next_number > 999999 then
    raise exception 'series_exhausted' using errcode = 'P0001';
  end if;

  v_base := p_corrected_base_cents - v_standing_base;
  v_vat := (p_terms ->> 'vat_cents')::bigint;
  v_irpf := (p_terms ->> 'irpf_cents')::bigint;
  -- El IVA y la retención restan (o son cero), no dejan lo vigente por debajo de cero y, en una anulación completa, lo devuelven todo. Si la original
  -- no llevaba IVA o retención, lo vigente es 0 y las dos primeras condiciones ya fuerzan 0.
  if v_vat > 0 or v_standing_vat + v_vat < 0 or (p_corrected_base_cents = 0 and v_standing_vat + v_vat <> 0) then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'vat_cents';
  end if;
  if v_irpf > 0 or v_standing_irpf + v_irpf < 0 or (p_corrected_base_cents = 0 and v_standing_irpf + v_irpf <> 0) then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'irpf_cents';
  end if;
  if (p_terms ->> 'total_cents')::bigint <> v_base + v_vat - v_irpf then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'total_cents';
  end if;

  v_invoice.id := gen_random_uuid();
  v_invoice.owner_id := v_owner;
  v_invoice.kind := 'rectifying';
  v_invoice.issue_date := p_issue_date;
  v_invoice.client_id := v_original.client_id;
  v_invoice.client_name := v_original.client_name;
  v_invoice.client_kind := v_original.client_kind;
  v_invoice.client_country := v_original.client_country;
  v_invoice.client_scope := v_original.client_scope;
  v_invoice.client_tax_id := v_original.client_tax_id;
  v_invoice.client_address := v_original.client_address;
  v_invoice.issuer_name := v_profile.legal_name;
  v_invoice.issuer_tax_id := v_profile.tax_id;
  v_invoice.issuer_address := v_profile.fiscal_address;
  v_invoice.issuer_iban := v_profile.iban;
  v_invoice.concept := v_original.concept;
  v_invoice.tax_treatment := v_original.tax_treatment;
  v_invoice.base_cents := v_base;
  v_invoice.vat_rate := v_original.vat_rate;
  v_invoice.vat_cents := v_vat;
  v_invoice.irpf_rate := v_original.irpf_rate;
  v_invoice.irpf_cents := v_irpf;
  v_invoice.total_cents := (p_terms ->> 'total_cents')::bigint;
  v_invoice.legal_note := v_original.legal_note;
  v_invoice.rectifies_id := v_original.id;
  v_invoice.rectification_reason := p_reason;
  v_invoice.created_at := now();
  return private.invoice_insert(v_invoice, v_series);
end
$$;

-- Marca o desmarca como cobrada una factura ordinaria (`paid_at` es lo único que cambia en una factura). Marcar una ya cobrada conserva la
-- primera fecha. Solo se registra el cambio real.
create function app.set_invoice_paid(p_id uuid, p_paid boolean) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
  v_invoice public.invoices;
  v_paid_at timestamptz;
begin
  select * into v_invoice from public.invoices i where i.id = p_id and i.owner_id = v_owner for update;
  if not found then
    raise exception 'invoice_not_found' using errcode = 'P0001';
  end if;
  if v_invoice.kind = 'rectifying' then
    raise exception 'invoice_not_payable' using errcode = 'P0001';
  end if;
  if p_paid is null then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'paid';
  end if;

  v_paid_at := case when p_paid then coalesce(v_invoice.paid_at, now()) end;
  if v_paid_at is distinct from v_invoice.paid_at then
    update public.invoices set paid_at = v_paid_at where id = p_id;
    perform private.log_activity(
      'data', v_owner, 'usuario', v_owner, 'invoice.payment_changed', 'invoice', p_id::text,
      jsonb_build_object('invoice_id', p_id, 'series', v_invoice.series_code, 'number', v_invoice.number, 'paid', p_paid));
  end if;
end
$$;

-- Registra, UNA sola vez, el PDF de una factura propia. La ruta y la huella han de ser coherentes (`{owner}/{factura}-{sha256[:16]}.pdf`).
create function app.attach_invoice_pdf(p_invoice_id uuid, p_path text, p_sha256 text, p_size integer) returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_owner uuid := private.series_enter();
begin
  perform 1 from public.invoices i where i.id = p_invoice_id and i.owner_id = v_owner for update;
  if not found then
    raise exception 'invoice_not_found' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.invoice_files f where f.invoice_id = p_invoice_id) then
    raise exception 'invoice_pdf_exists' using errcode = 'P0001';
  end if;
  if p_sha256 is null or p_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'sha256';
  end if;
  if p_size is null or p_size not between 1 and 1048576 then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'size_bytes';
  end if;
  if p_path is distinct from v_owner::text || '/' || p_invoice_id::text || '-' || substr(p_sha256, 1, 16) || '.pdf' then
    raise exception 'invalid_invoice' using errcode = 'P0001', detail = 'storage_path';
  end if;
  insert into public.invoice_files (invoice_id, owner_id, storage_path, sha256, size_bytes)
  values (p_invoice_id, v_owner, p_path, p_sha256, p_size);
end
$$;

-- Las funciones nuevas nacen con EXECUTE para PUBLIC: se retira. Solo las de `app.*` llegan a `authenticated`.
revoke all on all functions in schema private from public;
revoke all on all functions in schema app from public;
grant execute on function
  app.issue_invoice(uuid, uuid, date, text, bigint, jsonb),
  app.issue_rectifying_invoice(uuid, text, bigint, date, jsonb),
  app.set_invoice_paid(uuid, boolean),
  app.attach_invoice_pdf(uuid, text, text, integer)
  to authenticated;
