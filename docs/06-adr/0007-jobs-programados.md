# ADR-0007 · Jobs programados en código Python, no en n8n

- **Estado:** Aceptado. Parcialmente sustituido por [ADR-0016](0016-backend-en-vercel.md): solo cómo se invoca el cron (GET
  protegido con `CRON_SECRET`, programado en UTC); el resto de esta decisión sigue vigente.
- **Fecha:** 2026-11-03

## Contexto

Hay dos tareas programadas: el cierre mensual automático el día 1 (RF-012) y los recordatorios por correo antes de cada
plazo trimestral (RF-015), más el resumen de cartera del gestor. NFR-09 exige que el cierre sea idempotente y que el
100 % de los recordatorios salga en su fecha, verificado con fechas simuladas. El enunciado deja elegir entre n8n o un
job programado.

## Decisión

- **Cada tarea es una función Python en `cuadre.jobs`** que recibe el reloj como parámetro (`now`) y es idempotente:
  el cierre usa `INSERT … ON CONFLICT (owner_id, year, month)`, y el recordatorio registra `(owner_id, periodo, tipo)`
  único en `reminder_log` antes de enviar.
- **Se invoca de dos formas:** por CLI (`python -m cuadre.cli close-month --month 2026-10`) para operaciones manuales,
  y por una ruta interna `POST /internal/jobs/{name}` protegida con `INTERNAL_JOBS_SECRET` y no documentada en el cliente.
- **Lo dispara el planificador de la plataforma de despliegue** (cron); su elección va con ADR-0014. Los jobs se ejecutan
  en la zona horaria `Europe/Madrid`.
- Los jobs son el único sitio, junto con la CLI, donde se admite la service key, y siempre con el `owner_id` explícito
  en cada consulta.
- Si un job falla a medias, repetirlo es seguro.

## Alternativas descartadas

- **n8n.** Útil para integraciones, pero la lógica de idempotencia y de fechas tendría que probarse fuera del conjunto de
  tests de Python, añade un servicio más que alojar en la UE con su propio contrato de encargado, y las credenciales
  quedarían repartidas.
- **`pg_cron` + `pg_net`.** Mantiene la lógica cerca de los datos, pero llamar a servicios externos (correo) desde la base
  de datos complica los reintentos y las pruebas.
- **Cron dentro del proceso de FastAPI.** Se duplicaría con cada réplica del backend.

## Consecuencias

- Los tests de `backend/tests/jobs/` pasan fechas simuladas (1 de octubre, 20 de enero…) sin tocar el reloj del sistema.
- n8n puede entrar más adelante para flujos que no sean críticos, sin cambiar este diseño.
