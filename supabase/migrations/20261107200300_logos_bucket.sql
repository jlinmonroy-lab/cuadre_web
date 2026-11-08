-- SPEC-W-005 hito 2 · Bucket privado `logos` (D-01, ADR-0004).
--
-- Solo el bucket y sus límites; las políticas y las funciones `private.logo_*` llegan en la migración siguiente. Mientras tanto
-- `storage.objects` no tiene ninguna política para este bucket: nadie lee ni escribe en él.
-- 1 MiB (1048576 bytes) y tres tipos de imagen; SVG no (puede llevar scripts, T5-06). Storage no mira el contenido (Anexo B.1): la firma del
-- archivo la comprueba la API con los 12 primeros bytes.
-- Idempotente: volver a aplicarla restablece los límites y deja el bucket privado.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'logos',
  'logos',
  false,
  1048576,
  array['image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;
