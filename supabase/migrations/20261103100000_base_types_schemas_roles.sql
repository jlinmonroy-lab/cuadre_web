-- SPEC-W-001 §5.2.1 y §5.2.6 · Tipos, esquemas y roles de login.
--
-- Decisiones (ver ADR-0003, ADR-0004, ADR-0005):
--   * `private` guarda las funciones auxiliares de las políticas; `app`, las que invoca el backend. Ninguna es accesible por PUBLIC.
--   * Los correos son `text` en minúsculas con CHECK, NO `citext`: las funciones SECURITY DEFINER fijan `search_path = ''` y, sin
--     él, el operador `=` de citext no se resuelve y PostgreSQL cae en silencio a `text = text` (sensible a mayúsculas).

create type public.user_role as enum ('usuario', 'gestor', 'admin');
create type public.account_status as enum ('active', 'suspended');
create type public.gestor_access_status as enum ('pending', 'active', 'revoked', 'declined');
create type public.activity_category as enum ('access', 'account', 'data');

create schema private;
create schema app;
revoke all on schema private from public;
revoke all on schema app from public;
grant usage on schema private to authenticated, service_role;
grant usage on schema app to authenticated;

-- Privilegios por defecto. Aunque supabase/config.toml fija `auto_expose_new_tables = false` (que retira SELECT/INSERT/UPDATE/DELETE),
-- Supabase sigue concediendo TRUNCATE, REFERENCES, TRIGGER y MAINTAIN a anon, authenticated y service_role sobre las tablas nuevas
-- de `public`, y TRUNCATE no está sujeto a la RLS. Aquí se revoca todo y cada migración concede explícitamente lo que necesita.
alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated, service_role;
alter default privileges for role postgres in schema public revoke all on functions from anon, authenticated, service_role;

-- Roles de login del backend. Ninguno tiene privilegios propios: una consulta que olvide cambiar de rol falla con «permission denied»
-- en vez de saltarse la RLS en silencio. Sus contraseñas no están aquí: en local las fija supabase/seed.sql; en otros entornos, la plataforma.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'cuadre_app') then
    create role cuadre_app login nobypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'cuadre_jobs') then
    create role cuadre_jobs login nobypassrls;
  end if;
end
$$;

-- PostgreSQL 16+: la pertenencia permite SET ROLE pero no hereda privilegios.
grant authenticated to cuadre_app with inherit false, set true;
grant anon to cuadre_app with inherit false, set true;
grant service_role to cuadre_jobs with inherit false, set true;
