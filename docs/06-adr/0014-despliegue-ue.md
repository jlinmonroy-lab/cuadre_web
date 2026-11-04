# ADR-0014 · Despliegue 100 % en la UE

- **Estado:** Propuesto (pendiente de cuentas y de los contratos de encargado, DEP-06)
- **Fecha:** 2026-11-03 (actualizado el 2026-11-04: el backend, concretado por [ADR-0016](0016-backend-en-vercel.md))

## Contexto

La aplicación es online y sin instalación (RES-08), con datos en la UE y contrato de encargado con cada proveedor
(NFR-11). Hay tres piezas que alojar: el frontend Next.js, el backend FastAPI (con sus jobs y el MCP) y Supabase.
Aún no existen cuentas ni dominio, y no hay plazo cerrado.

## Decisión (provisional)

Se fijan las **restricciones**, no el proveedor:

1. Frontend, backend y base de datos en regiones de la UE; ningún subencargado fuera de la UE sin garantías adecuadas.
2. Tres entornos: local, *staging* y producción, cada uno con sus propios secretos y proyecto de Supabase. Los datos de
   *staging* son siempre sintéticos (RES-07).
3. El backend necesita streaming SSE, servidor MCP, conexiones a Postgres y un planificador de cron para ADR-0007. Sirve
   un proceso de larga duración o funciones sin servidor con streaming y una duración máxima de al menos 45 s, sin
   contar con trabajo posterior a la respuesta (ADR-0016). Quedan descartadas las plataformas que limiten el streaming
   o el tiempo de ejecución por debajo de los 45 s de la lectura de facturas.
4. Los secretos viven en la plataforma, no en el repositorio. Solo `NEXT_PUBLIC_*` llega al navegador.
5. Monitorización externa de disponibilidad (NFR-09, ≥ 99 % en el piloto, propuesto).

Opciones a evaluar cuando haya cuentas: frontend y backend en Vercel con la región fijada a la UE (el backend, según
ADR-0016); o frontend en Vercel o en un host de contenedores europeo y backend en un servicio de contenedores con región
UE; Supabase en Fráncfort o París.

## Consecuencias

- Hasta aceptar este ADR, nada del código depende de un proveedor concreto: todo se configura por variables de entorno.
- Antes del piloto hay que cerrar proveedor de alojamiento, región de Supabase, dominio y contratos de encargado.
