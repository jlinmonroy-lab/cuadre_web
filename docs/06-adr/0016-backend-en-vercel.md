# ADR-0016 · Backend FastAPI desplegado en Vercel Functions (región UE)

- **Estado:** Aceptado como decisión de plataforma; la comprobación en un despliegue real queda para su spec (ver «Sin verificar»)
- **Fecha:** 2026-11-04
- **Sustituye en parte a:** ADR-0007 (solo **cómo se invoca** el cron; la lógica de los jobs sigue igual).
- **Concreta:** ADR-0014 (propuesto) en lo que toca al backend.

## Contexto

Se quiere un backend compatible con Vercel. ADR-0014 dejaba abierto el alojamiento y, en su restricción 3, pedía «un proceso de larga
duración» para el backend. Vercel no ofrece un proceso persistente: ejecuta el backend como **Vercel Functions** (con Fluid compute), que se
escalan con el tráfico.

Revisada la documentación de Vercel (páginas de FastAPI, runtime de Python, Cron Jobs y límites de las funciones, actualizadas entre agosto y
septiembre de 2026), el backend actual **sí** puede ejecutarse allí sin reescribirlo:

| Tema | Lo que dice Vercel | Efecto en cuadre-web |
|---|---|---|
| FastAPI | Ejecución nativa. Busca una instancia `app` en `app.py`, `main.py`… (también dentro de `src/`) o en `tool.vercel.entrypoint` de `pyproject.toml`. Admite lifespan, streaming y `maxDuration`. | Compatible. La nuestra es `cuadre.main:app` en `backend/src/`. |
| Python | 3.12 (por defecto), 3.13 y 3.14; dependencias por `pyproject.toml` o `requirements.txt`; bundle de hasta 500 MB sin comprimir. | Encaja con `requires-python = ">=3.12,<3.13"`. |
| Duración | 300 s por defecto y máximo en Hobby; 800 s máximo en Pro (1.800 s en beta); el streaming cuenta dentro de ese tiempo. | Cumple los 45 s de la lectura de facturas y el SSE del chat. |
| Cuerpo | Petición y respuesta de **hasta 4,5 MB** (si no, 413). | Una factura de hasta 15 MiB **no puede pasar por la API**. |
| Segundo plano | Para trabajo independiente de la respuesta recomienda Vercel Queues o Workflows. El cierre del lifespan dura como máximo 500 ms. | No se puede contar con trabajo que siga **después** de responder. |
| Cron | Hace un **GET** a una ruta, **siempre en UTC**, en todos los planes (hasta 100 por proyecto). | ADR-0007 fijaba `POST` y la zona `Europe/Madrid`. |
| Región | Una región por defecto, **`iad1` (EE. UU.)**, que se puede cambiar. | Hay que fijarla a la UE (NFR-11, ADR-0014). |
| Descriptores | 1.024 compartidos entre ejecuciones concurrentes, conexiones a la base incluidas. | El pool de psycopg (hoy `max_size=10` por instancia) hay que reducirlo. |

## Decisión

1. **El backend FastAPI se despliega como Vercel Function**, con la región fijada a la UE (por ejemplo `fra1`, en `vercel.json` o en los
   ajustes del proyecto, junto a Supabase en Fráncfort o París). No se reescribe nada: la entrada se declara con `tool.vercel.entrypoint`
   en `backend/pyproject.toml`. El desarrollo local sigue con `uvicorn`.
2. **Los jobs los dispara Vercel Cron por GET** a una ruta interna (`GET /internal/jobs/{name}`), protegida con `CRON_SECRET` y no
   publicada en `openapi.json`. Sustituye al `POST` y a `INTERNAL_JOBS_SECRET` de ADR-0007; la CLI sigue disponible para operaciones
   manuales. **Un GET con efectos secundarios solo se admite aquí**, porque el planificador no ofrece otro método, y se compensa con el
   secreto y con la idempotencia de cada job.
3. **El planificador va en UTC; el job decide con el reloj de Madrid.** Cada job sigue recibiendo `now` y calculando la fecha en
   `Europe/Madrid` (ADR-0007). La hora UTC de cada cron se elige de modo que caiga en el mismo día de Madrid en verano y en invierno; se
   concreta en las specs de cierre mensual y recordatorios. Como los jobs son idempotentes, repetir o adelantar una ejecución es seguro.
4. **Nada de trabajo después de responder.** Las rutas no usan `BackgroundTasks` ni hilos que sobrevivan a la respuesta. Lo que dura
   (la lectura de una factura, hasta 45 s) ocurre **dentro de la petición**, con el estado guardado en la base de datos, y una lectura
   interrumpida se detecta por su antigüedad (SPEC-W-002, AC-11). Si algún día el trabajo no cupiera en una petición, se evalúa Vercel
   Queues; hoy no hace falta.
5. **Los archivos no pasan por la API.** Del navegador a Storage con URL firmada (ADR-0004) y de Storage al agente con otra URL firmada
   (ADR-0012). Ninguna ruta admite `multipart/form-data` ni cuerpos binarios (límite de 4,5 MB).
6. **Base de datos solo por el pooler de Supabase en modo transacción.** Se mantiene `prepare_threshold=None` (ya está, ADR-0003); se
   reduce el tamaño del pool y se añaden `max_lifetime` y comprobación de la conexión, porque una instancia detenida y reanudada puede
   encontrarse con conexiones que el pooler ya cerró. Los valores concretos se fijan midiendo, en la spec de despliegue.
7. **Un solo dominio hacia el navegador, o una lista de orígenes.** `FRONTEND_ORIGIN` admite un origen y las vistas previas de Vercel cambian
   de dominio. La spec de despliegue elegirá entre servir la API bajo el dominio del frontend (reescritura de `/api` o Vercel Services) y
   ampliar la configuración de CORS.
8. **El servidor MCP (ADR-0013) y el streaming del chat se diseñan sin estado**, acotados por la duración máxima de la función.

**Lo que no cambia:** psycopg síncrono (ADR-0015), el rol `cuadre_app` y la RLS, `SET LOCAL ROLE`, el CI de GitHub Actions, los tests y la
estructura de `backend/src/cuadre/`.

## Alternativas descartadas

- **Reescribir el backend en TypeScript dentro de Next.js.** Un solo proyecto y lenguaje, pero se perderían FastAPI, Pydantic,
  `cuadre-contracts` (Python), los validadores y todo el backend de SPEC-W-001, y se reabrirían ADR-0003, ADR-0015 y el contrato con
  cuadre-agents. Ningún límite de Vercel lo exige.
- **Vercel Queues desde el principio.** Fiable, pero añade un servicio que hoy no se necesita: la carga es una persona por sesión y cinco
  lecturas simultáneas como máximo (SPEC-W-002, D-03).
- **Contenedores en otro proveedor europeo.** Siguen siendo una salida si alguna de las comprobaciones de abajo fallara; ADR-0014 la mantiene
  abierta.

## Consecuencias

- ADR-0014 se actualiza (sigue propuesto): ya no exige un proceso persistente, sino streaming y una duración máxima de al menos 45 s.
- SPEC-W-002 cambia: D-02 (lectura dentro de la petición, no en segundo plano) y D-01 (sin plan B por la API).
- Hay que añadir `vercel.json` y la entrada en `pyproject.toml`, cambiar la ruta de jobs y ajustar el pool. Va en una spec de despliegue, con un
  primer hito de comprobación, y necesita un repositorio remoto y una cuenta de Vercel que hoy no existen.
- Cada decisión de región y de proveedor sigue sujeta a los contratos de encargado (DEP-06).

## Sin verificar

Lo anterior se apoya en la documentación de Vercel y no se ha probado en un despliegue. Queda para el primer hito de la spec de despliegue:

- Que `tool.vercel.entrypoint = "cuadre.main:app"` funcione con `backend/src/` y con la carpeta raíz del proyecto en `backend`.
- Que Vercel instale `contracts/python` (`cuadre-contracts`), que queda fuera de `backend/`, cuando llegue SPEC-W-002.
- Qué ocurre con la petición que lee una factura si el navegador cierra la conexión antes de que termine.
- Que el pooler de Supabase en modo transacción sirva por IPv4 a las funciones de Vercel.
- El formato exacto con que Vercel envía `CRON_SECRET`, la frecuencia mínima del cron en cada plan y qué cubre el plan Hobby para un uso comercial
  (a falta de comprobarlo, se supone que Hobby es solo para uso no comercial).

## Fuentes

Documentación de Vercel consultada el 2026-11-04: [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi),
[runtime de Python](https://vercel.com/docs/functions/runtimes/python), [Cron Jobs](https://vercel.com/docs/cron-jobs) y
[límites de las funciones](https://vercel.com/docs/functions/limitations).
