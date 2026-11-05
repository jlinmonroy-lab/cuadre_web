-- SPEC-W-002 hito 0 · Bucket privado `documents` (ADR-0004).
--
-- Solo el bucket y sus límites. Las políticas sobre `storage.objects` y las funciones `private.document_*` dependen de la tabla
-- `documents` y llegan con ella. Mientras tanto `storage.objects` tiene RLS activada y ninguna política: nadie lee ni escribe.
-- Los 15 MiB (15728640 bytes) y los cinco tipos coinciden con la CHECK de `documents` y con la API (SPEC-W-002 §5.2).
-- Idempotente: volver a aplicarla restablece los límites y deja el bucket privado.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documents',
  'documents',
  false,
  15728640,
  array['application/pdf', 'image/jpeg', 'image/png', 'image/heic', 'image/webp']
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;
