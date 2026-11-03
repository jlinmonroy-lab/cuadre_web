-- SPEC-W-001 §5.2.4 · Políticas RLS y privilegios (normativos). Lo que no figura aquí está DENEGADO.
-- `anon` no tiene políticas ni privilegios. Todas las políticas son `to authenticated`.
-- Se usa `(select auth.uid())` para que PostgreSQL evalúe la identidad una sola vez por consulta.

-- profiles ---------------------------------------------------------------------------------------------------------------
-- Cualquiera ve su fila (incluso suspendida: la API la necesita para responder 403 account_suspended). El administrador ve las de
-- todos (metadatos) y el gestor, las de sus clientes con vínculo activo. El rol y el estado solo cambian por app.admin_set_*.
create policy profiles_select on public.profiles for select to authenticated
  using (id = (select auth.uid()) or private.is_admin() or private.gestor_has_access(id));

create policy profiles_update_own on public.profiles for update to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- business_profiles ------------------------------------------------------------------------------------------------------
-- Datos financieros: el dueño lee y edita; el gestor SOLO lee, y solo con vínculo activo; el administrador, nada.
create policy business_profiles_select on public.business_profiles for select to authenticated
  using (owner_id = (select auth.uid()) or private.gestor_has_access(owner_id));

create policy business_profiles_update_own on public.business_profiles for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));

-- gestor_access ----------------------------------------------------------------------------------------------------------
create policy gestor_access_select_owner on public.gestor_access for select to authenticated
  using (owner_id = (select auth.uid()));

create policy gestor_access_select_gestor on public.gestor_access for select to authenticated
  using (
    private.app_role() = 'gestor'::public.user_role
    and (gestor_id = (select auth.uid()) or gestor_email = private.app_email())
  );

-- El dueño invita; solo puede fijar owner_id y gestor_email (privilegio de columna). Estado, caducidad y gestor_id salen de los
-- valores por defecto, que esta comprobación exige. No puede invitarse a sí mismo.
create policy gestor_access_insert_owner on public.gestor_access for insert to authenticated
  with check (
    owner_id = (select auth.uid())
    and status = 'pending'
    and gestor_id is null
    and gestor_email <> private.app_email()
  );

-- activity_log -----------------------------------------------------------------------------------------------------------
create policy activity_log_select_owner on public.activity_log for select to authenticated
  using (owner_id = (select auth.uid()));

create policy activity_log_select_actor on public.activity_log for select to authenticated
  using (actor_id = (select auth.uid()));

create policy activity_log_select_admin on public.activity_log for select to authenticated
  using (category = 'account'::public.activity_category and private.is_admin());

-- Privilegios (defensa en profundidad; ver la nota de la primera migración sobre TRUNCATE) ---------------------------------
grant select on public.profiles to authenticated;
grant update (display_name) on public.profiles to authenticated;

grant select on public.business_profiles to authenticated;
grant update (legal_name, tax_id, fiscal_address, activity, iae_epigraph, activity_start_date, vat_regime,
              irpf_rate, logo_path, iban, home_pct)
  on public.business_profiles to authenticated;

grant select on public.gestor_access to authenticated;
grant insert (owner_id, gestor_email) on public.gestor_access to authenticated;

grant select on public.activity_log to authenticated;

-- service_role (cuadre.cli, jobs): lo estrictamente necesario. Se amplía por spec cuando un job lo requiera.
grant select on public.profiles to service_role;
grant update (role, status) on public.profiles to service_role;
