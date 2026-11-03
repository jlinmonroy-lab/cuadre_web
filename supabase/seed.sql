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

-- 4 · Perfil de negocio de ejemplo (datos fiscales inventados y no válidos).
update public.business_profiles set
  legal_name = 'Alicia Demo (sintético)', tax_id = 'TEST-0001', fiscal_address = 'Calle Ficticia 1, 00000 Ciudad de Pruebas',
  activity = 'Diseño gráfico', activity_start_date = date '2025-01-15', irpf_rate = 7, iban = 'ES00 0000 0000 0000 0000 0001'
where owner_id = 'a1000000-0000-4000-8000-000000000001';

update public.business_profiles set
  legal_name = 'Beto Demo (sintético)', tax_id = 'TEST-0002', fiscal_address = 'Avenida Inventada 2, 00000 Ciudad de Pruebas',
  activity = 'Consultoría', activity_start_date = date '2023-06-01', irpf_rate = 15, iban = 'ES00 0000 0000 0000 0000 0002'
where owner_id = 'a1000000-0000-4000-8000-000000000002';
