-- Datos de desarrollo SINTÉTICOS (RES-07). Se ejecuta en `supabase start` (primera vez) y en `supabase db reset`.
-- Nada de aquí sirve en producción: ni las contraseñas, ni los usuarios, ni los datos fiscales (inventados y no válidos).

-- 1 · Contraseñas de DESARROLLO de los roles de login del backend (las migraciones no llevan contraseñas).
alter role cuadre_app  password 'cuadre-dev-only';
alter role cuadre_jobs password 'cuadre-dev-only';

-- 2 · Cinco usuarios que pueden iniciar sesión (correo confirmado), contraseña de desarrollo «cuadre-demo-2026».
--     Las columnas de token de auth.users van a '' y no a NULL: GoTrue falla al leer NULL en ellas.
insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
  confirmation_token, recovery_token, email_change_token_new, email_change, phone_change, phone_change_token,
  email_change_token_current, reauthentication_token
)
select
  v.id, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', v.email,
  extensions.crypt('cuadre-demo-2026', extensions.gen_salt('bf')), now(),
  '{"provider":"email","providers":["email"]}'::jsonb, jsonb_build_object('display_name', v.name), now(), now(),
  '', '', '', '', '', '', '', ''
from (values
  ('a1000000-0000-4000-8000-000000000001'::uuid, 'alicia@example.test', 'Alicia'),
  ('a1000000-0000-4000-8000-000000000002'::uuid, 'beto@example.test',   'Beto'),
  ('a1000000-0000-4000-8000-000000000003'::uuid, 'gina@example.test',   'Gina'),
  ('a1000000-0000-4000-8000-000000000004'::uuid, 'gus@example.test',    'Gus'),
  ('a1000000-0000-4000-8000-000000000005'::uuid, 'adan@example.test',   'Adán')
) as v(id, email, name);

insert into auth.identities (id, user_id, identity_data, provider, provider_id, last_sign_in_at, created_at, updated_at)
select
  gen_random_uuid(), u.id,
  jsonb_build_object('sub', u.id::text, 'email', u.email, 'email_verified', true, 'phone_verified', false),
  'email', u.id::text, now(), now(), now()
from auth.users u
where u.email like '%@example.test';

-- 3 · Roles. El trigger de alta crea a todos como `usuario`; aquí se asignan los de prueba (el seed actúa como administrador de la base).
update public.profiles set role = 'gestor' where email in ('gina@example.test', 'gus@example.test');
update public.profiles set role = 'admin'  where email = 'adan@example.test';

-- 4 · Perfil de negocio de ejemplo. Datos sintéticos (RES-07) pero VÁLIDOS (SPEC-W-005 Anexo B.1): el NIF lleva su letra de control y
-- el IBAN, entidad y oficina 0000 (no existen) con el módulo 97 y los dígitos de control de la cuenta bien. Se guardan compactos, como los
-- guardará la API. Con ellos Alicia y Beto pueden emitir; y el NIF de Alicia es el destinatario de los ejemplos de `contracts/`.
update public.business_profiles set
  legal_name = 'Alicia Demo (sintético)', tax_id = '12345678Z', fiscal_address = 'Calle Ficticia 1, 00000 Ciudad de Pruebas',
  activity = 'Diseño gráfico', activity_start_date = date '2025-01-15', irpf_rate = 7, iban = 'ES3600000000050000000001'
where owner_id = 'a1000000-0000-4000-8000-000000000001';

update public.business_profiles set
  legal_name = 'Beto Demo (sintético)', tax_id = '01230956L', fiscal_address = 'Avenida Inventada 2, 00000 Ciudad de Pruebas',
  activity = 'Consultoría', activity_start_date = date '2023-06-01', irpf_rate = 15, iban = 'ES6300000000010000000002'
where owner_id = 'a1000000-0000-4000-8000-000000000002';

-- 5 · Una serie de facturación por persona (SPEC-W-005 D-03): la del año, predeterminada.
insert into public.invoice_series (owner_id, code, description, is_default) values
  ('a1000000-0000-4000-8000-000000000001', '2026', 'Serie del año', true),
  ('a1000000-0000-4000-8000-000000000002', '2026', 'Serie del año', true);

-- 6 · Clientes de ejemplo (SPEC-W-006): uno de cada ámbito por persona. Sintéticos y ya NORMALIZADOS, como los guardará la API: los CIF de
-- la familia B000000NN pasan el control; los NIF-IVA alemán y francés son números fabricados con dígito de control válido (Anexo B.1-A);
-- el de México es texto libre. El VIES simulado marca solo a las empresas de la UE.
insert into public.clients (owner_id, name, kind, country, scope, tax_id, address, vies_status) values
  ('a1000000-0000-4000-8000-000000000001', 'Estudio Norte S.L.', 'business', 'ES', 'national', 'B00000018', 'Avenida Inventada 4, 28000 Madrid', 'not_applicable'),
  ('a1000000-0000-4000-8000-000000000001', 'Kreativ GmbH', 'business', 'DE', 'eu', 'DE446120774', 'Beispielstrasse 7, 10115 Berlin', 'valid_simulated'),
  ('a1000000-0000-4000-8000-000000000001', 'Taller Zócalo', 'business', 'MX', 'non_eu', 'MXTEST0001', 'Calle Ficticia 12, Ciudad de México', 'not_applicable'),
  ('a1000000-0000-4000-8000-000000000002', 'Café Liebre S.L.', 'business', 'ES', 'national', 'B00000026', 'Plaza Ejemplo 1, 46000 Valencia', 'not_applicable'),
  ('a1000000-0000-4000-8000-000000000002', 'Atelier Lune SARL', 'business', 'FR', 'eu', 'FRZM842411902', '12 rue Imaginaire, 75001 Paris', 'valid_simulated'),
  ('a1000000-0000-4000-8000-000000000002', 'Sam Rivers', 'individual', 'US', 'non_eu', null, '1 Main Street, Springfield', 'not_applicable');

-- 7 · Facturas de ejemplo de Alicia (SPEC-W-007, RES-07): una de cada uno de los cinco tratamientos fiscales, una cobrada y una
-- rectificativa. Se emiten POR LAS PROPIAS FUNCIONES (`app.issue_invoice`…), con las claims de Alicia puestas para la transacción (Anexo
-- B.1-E): así la numeración, las copias del emisor y del cliente y el registro de actividad son los de verdad, y el seed no puede dejar una
-- factura que la aplicación no habría emitido. Los importes son los de la tabla de §5.1.3 (con la retención del 7 % de Alicia). Las fechas
-- son relativas a hoy (Madrid) y crecientes dentro de la serie: una factura no puede ser futura. Para cubrir los cinco tratamientos, Alicia
-- gana dos clientes PARTICULARES, con domicilio: uno de la UE y otro de fuera de la UE. Las facturas quedan sin PDF (`pdf_status: pending`).
insert into public.clients (owner_id, name, kind, country, scope, tax_id, address, vies_status) values
  ('a1000000-0000-4000-8000-000000000001', 'Lena Müller', 'individual', 'DE', 'eu', null, 'Musterweg 3, 80331 München', 'not_applicable'),
  ('a1000000-0000-4000-8000-000000000001', 'Mia Carter', 'individual', 'CA', 'non_eu', null, '25 Maple Avenue, Toronto', 'not_applicable');

do $seed$
declare
  v_alicia constant uuid := 'a1000000-0000-4000-8000-000000000001';
  v_today constant date := private.today_madrid();
  v_series uuid;
  v_first uuid;
begin
  perform set_config('request.jwt.claims', json_build_object('sub', v_alicia, 'role', 'authenticated')::text, true);
  select id into v_series from public.invoice_series where owner_id = v_alicia and code = '2026';

  -- Nacional, empresa: 21 % y retención del 7 % → base 120.000, IVA 25.200, retención 8.400, total 136.800.
  v_first := app.issue_invoice(
    (select id from public.clients where owner_id = v_alicia and name = 'Estudio Norte S.L.'), v_series, v_today - 30,
    'Diseño de identidad visual', 120000,
    '{"tax_treatment": "national_vat", "vat_rate": 21, "vat_cents": 25200, "irpf_rate": 7, "irpf_cents": 8400, "total_cents": 136800, "legal_note": null}');
  -- UE, empresa: inversión del sujeto pasivo.
  perform app.issue_invoice(
    (select id from public.clients where owner_id = v_alicia and name = 'Kreativ GmbH'), v_series, v_today - 25,
    'Desarrollo de la web corporativa', 150000,
    '{"tax_treatment": "eu_reverse_charge", "vat_rate": 0, "vat_cents": 0, "irpf_rate": 0, "irpf_cents": 0, "total_cents": 150000, "legal_note": "Inversión del sujeto pasivo."}');
  -- UE, particular: IVA español.
  perform app.issue_invoice(
    (select id from public.clients where owner_id = v_alicia and name = 'Lena Müller'), v_series, v_today - 20,
    'Ilustraciones para un libro', 100000,
    '{"tax_treatment": "eu_consumer_vat", "vat_rate": 21, "vat_cents": 21000, "irpf_rate": 0, "irpf_cents": 0, "total_cents": 121000, "legal_note": null}');
  -- Fuera de la UE, empresa: no sujeta.
  perform app.issue_invoice(
    (select id from public.clients where owner_id = v_alicia and name = 'Taller Zócalo'), v_series, v_today - 15,
    'Rotulación de un local', 50000,
    '{"tax_treatment": "non_eu_not_subject", "vat_rate": 0, "vat_cents": 0, "irpf_rate": 0, "irpf_cents": 0, "total_cents": 50000, "legal_note": "Operación no sujeta a IVA por reglas de localización (art. 69 de la Ley del IVA)."}');
  -- Fuera de la UE, particular: IVA español.
  perform app.issue_invoice(
    (select id from public.clients where owner_id = v_alicia and name = 'Mia Carter'), v_series, v_today - 10,
    'Retrato por encargo', 100000,
    '{"tax_treatment": "non_eu_consumer_vat", "vat_rate": 21, "vat_cents": 21000, "irpf_rate": 0, "irpf_cents": 0, "total_cents": 121000, "legal_note": null}');

  -- La primera está cobrada y se rectifica a 100.000: base −20.000, IVA −4.200, retención −1.400 (8.400 − 7.000), total −22.800.
  perform app.set_invoice_paid(v_first, true);
  perform app.issue_rectifying_invoice(
    v_first, 'Se facturaron horas de más', 100000, v_today - 5, '{"vat_cents": -4200, "irpf_cents": -1400, "total_cents": -22800}');
end
$seed$;
