-- SPEC-W-005 §5.2 · CHECK con nombre en `business_profiles` y `logo_path` fuera de las columnas editables.
--
-- La base defiende solo lo barato (D-14): longitudes, el 7 y el 15, el régimen y la forma de la ruta del logo. NO valida el NIF ni el IBAN,
-- que son de Python (`cuadre.validators`, una sola fuente: T5-03); `cuadre.profile.limits` repite estos números y `test_limits_parity.py` los
-- compara. Todos admiten NULL (un perfil se guarda incompleto). El spike del hito 0 (Anexo B.1) los aplicó en seco sobre 6.236 filas.
--
-- `logo_path` deja de ser editable por escritura directa (D-13): solo lo cambian `app.set_business_logo` y `app.clear_business_logo`, que
-- comprueban la ruta. La CHECK la repite por si alguien llega por otro camino. El `$` de PostgreSQL no admite un salto de línea final.

alter table public.business_profiles
  add constraint business_profiles_irpf_rate_allowed check (irpf_rate in (7, 15)),
  add constraint business_profiles_vat_regime_general check (vat_regime = 'general'),
  add constraint business_profiles_legal_name_length check (char_length(legal_name) between 2 and 200),
  add constraint business_profiles_fiscal_address_length check (char_length(fiscal_address) between 5 and 300),
  add constraint business_profiles_activity_length check (char_length(activity) <= 200),
  add constraint business_profiles_iae_epigraph_format
    check (char_length(iae_epigraph) <= 20 and iae_epigraph ~ '^[0-9A-Za-z. -]+$'),
  add constraint business_profiles_logo_path_format
    check (logo_path ~ ('^' || owner_id::text || '/[0-9a-f-]{36}\.(png|jpg|webp)$'));

revoke update (logo_path) on public.business_profiles from authenticated;
