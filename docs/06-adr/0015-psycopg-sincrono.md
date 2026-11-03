# ADR-0015 · psycopg síncrono con pool de conexiones

- **Estado:** Aceptado
- **Fecha:** 2026-11-03
- **Sustituye en parte a:** ADR-0003 (solo el «asíncrono»; el resto de ADR-0003 sigue vigente).

## Contexto

ADR-0003 eligió psycopg 3 «asíncrono, con pool». Al preparar la implementación de SPEC-W-001 aparece un problema de
plataforma: `psycopg.AsyncConnection` **no funciona con el `ProactorEventLoop`**, que es el bucle por defecto de asyncio
en Windows, y exige `SelectorEventLoop`. El entorno de desarrollo del proyecto es Windows 11 (ADR-0009), y ese bucle lo
crean `pytest-asyncio` y `uvicorn` antes de que el código de la aplicación pueda cambiar la política, de modo que
arreglarlo exigiría parches dependientes del orden de importación y distintos según se use o no `--reload`.

La aplicación tiene una carga pequeña (un autónomo por sesión, un piloto de al menos cinco) y la identidad del usuario
llega a la base de datos con `SET LOCAL ROLE` dentro de una transacción corta por petición (ADR-0003). No hay un
caso de uso en el que la E/S asíncrona de la base de datos aporte algo medible.

## Decisión

- **psycopg 3 síncrono** con `psycopg_pool.ConnectionPool`, `prepare_threshold=None` (compatible con el pooler en modo
  transacción) y un único módulo que abre conexiones, `cuadre.db`.
- **Las rutas que tocan la base de datos son funciones `def`**: FastAPI las ejecuta en su pool de hilos. Las que
  necesiten ser asíncronas (el streaming SSE del chat, el servidor MCP) llaman a la base de datos con
  `run_in_threadpool`.
- **Esperar una conexión más de 5 s falla rápido** (`PoolTimeout` → 503 `database_busy`). Acotar el número de hilos al tamaño
  del pool NO evita los bloqueos, aunque parezca que sí: quien espera una conexión ocupa un hilo, y quien ya la tiene
  necesita otro hilo para terminar su ruta; con la aplicación saturada podrían quedarse todos esperando. Lo que acota el daño es
  el tiempo de espera corto, que convierte la sobrecarga en errores inmediatos en lugar de peticiones colgadas.
- **La transacción de la petición se abre en una dependencia con `scope="function"`**, de modo que se confirma antes de enviar
  la respuesta y un fallo de commit llega al cliente como un 500 (lo fija un test que observa el orden de los eventos).
- **Los tests son síncronos**: no se usa `pytest-asyncio` para la base de datos.

## Comprobación

Verificado el 2026-11-03 en Windows 11 con Python 3.12: `asyncio.run` por defecto crea un `ProactorEventLoop` y
`psycopg.AsyncConnection.connect` falla con «Psycopg cannot use the 'ProactorEventLoop' to run in async mode»; con
`WindowsSelectorEventLoopPolicy` funciona. No se ha probado el comportamiento concreto de `uvicorn` con y sin `--reload`: la
decisión no depende de él.

## Alternativas descartadas

- **Fijar `WindowsSelectorEventLoopPolicy` al importar la aplicación.** Funciona solo si el bucle aún no se ha creado;
  con `uvicorn` sin `--reload` ya existe cuando se importa la aplicación. Frágil y solo en Windows.
- **asyncpg.** Evita el problema del bucle, pero gestiona peor las sentencias preparadas detrás de un pooler en modo
  transacción y obligaría a otra API distinta para `SET LOCAL ROLE`.
- **Desarrollar en WSL2.** Resolvería el bucle, pero cambia el entorno acordado en ADR-0009 por un problema que no existe
  con la opción síncrona.

## Consecuencias

- Se pierde, a cambio de nada que hoy se use, la posibilidad de multiplicar conexiones concurrentes con una sola hebra.
  Si algún día la carga lo exigiera, se reconsidera con medidas.
- El código de la API y de los tests es más simple y se comporta igual en Windows y en Linux.
- ADR-0010 deja de mencionar `pytest-asyncio` para los tests de base de datos.
