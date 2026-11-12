-- SPEC-W-010 §5.2 · ¿De quién es lo que se lee? (D-07). Las lecturas de facturas, gastos, documentos, perfil, clientes y trimestres filtran hasta ahora por
-- `owner_id = auth.uid()`. Para que el gestor lea lo de un autónomo con LAS MISMAS consultas, ese filtro pasa a `owner_id = private.read_owner()`.
--
-- `private.read_owner()` vale `auth.uid()` (lo de siempre) SALVO que la transacción haya fijado `cuadre.read_owner`. Eso solo lo hace la API, con `set_config(..., true)`
-- (local a la transacción: no se filtra a la petición siguiente) y DESPUÉS de que `app.log_gestor_read` haya comprobado el vínculo activo y registrado la lectura.
--
-- No concede nada: el ajuste solo cambia a QUIÉN se mira. Quién puede ver qué sigue decidiéndolo la RLS (`private.gestor_has_access` en cada política): un gestor que
-- fijara el dueño de alguien sin vínculo vería cero filas. Un usuario normal no puede fijarlo: la API no ejecuta SQL arbitrario y la Data API está desactivada.

create function private.read_owner() returns uuid
language sql stable set search_path = ''
as $$
  select coalesce(nullif(current_setting('cuadre.read_owner', true), '')::uuid, auth.uid())
$$;

revoke all on function private.read_owner() from public;
grant execute on function private.read_owner() to authenticated;
