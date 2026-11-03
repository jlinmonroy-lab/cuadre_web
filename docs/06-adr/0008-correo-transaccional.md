# ADR-0008 · Correo transaccional detrás de una interfaz

- **Estado:** Propuesto (el proveedor se elige al cerrar DEP-05)
- **Fecha:** 2026-11-03

## Contexto

Los recordatorios (RF-015), la invitación al gestor y, como *Could*, el reporte en PDF (RF-022) necesitan correo
transaccional con dominio verificado (DEP-05). Los correos de Auth (confirmación, recuperación) los envía Supabase.
Cada proveedor es un encargado del tratamiento y debe ofrecer región UE y contrato (DEP-06, NFR-11).

## Decisión

- **Interfaz `EmailSender`** en `cuadre.notifications` con tres implementaciones: `ConsoleEmailSender` (desarrollo),
  `MemoryEmailSender` (tests, para aserciones sobre lo enviado) y una real que se activa con `EMAIL_PROVIDER`.
- **En local**, los correos de Auth caen en Mailpit (incluido en la pila de Supabase CLI) y los de la aplicación se
  escriben en consola o en memoria.
- **Contenido:** plantillas en español; el cuerpo de un recordatorio lleva cifras ya calculadas por `cuadre.tax`, nunca
  datos de IBAN. No se registran cuerpos de correo en los logs.
- **Proveedor real:** pendiente. Criterios de elección: región UE, contrato de encargado, dominio propio con SPF/DKIM,
  precio al volumen del piloto. Candidatos a evaluar: Resend (región UE), Brevo, Amazon SES (región UE).

## Alternativas descartadas

- **Acoplarse a un proveedor desde ya.** Se decide con la cuenta y el dominio a mano; hasta entonces la interfaz basta
  para desarrollar y probar W-014.
- **Usar el SMTP de Supabase para todo.** Está pensado para los correos de Auth, con límites de envío bajos.

## Consecuencias

- W-014 se puede implementar y probar entera (fechas simuladas, contenido, idempotencia) sin proveedor real.
- Antes del piloto hay que cerrar proveedor, dominio verificado y contrato de encargado.
