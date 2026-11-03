# ADR-0012 · Frontera entre cuadre-web y cuadre-agents

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

El proyecto se divide en dos repositorios que se fusionarán más adelante. cuadre-web lleva la interfaz, la API, la base
de datos, los roles, la lógica fiscal, los validadores, el cierre, el reporte y los recordatorios. cuadre-agents lleva todo
lo que usa modelos de lenguaje: el agente de lectura de facturas y el del chatbot. El charter exige separar la lógica
fiscal del modelo (riesgo de error fiscal) y RES-01 dice que el modelo solo extrae, clasifica y redacta.

## Decisión

1. **Este repositorio no llama a ninguna API de modelos de lenguaje.** Ni SDKs de proveedores en las dependencias, ni
   claves de modelos en las variables de entorno. Un test de CI comprueba las dependencias y las importaciones.
2. **Todo lo que necesita IA pasa por `AgentsClient`**, una interfaz (`typing.Protocol`) en `cuadre.agents` con
   `extract_invoice(...)` y `stream_chat(...)` y dos implementaciones:
   - `FakeAgentsClient`: devuelve los fixtures de `contracts/examples/` (NIF dudoso, suma que no cuadra, instrucciones
     ocultas, abstención…). Se usa cuando no existe `AGENTS_BASE_URL`, y siempre en los tests.
   - `HttpAgentsClient`: habla con `{AGENTS_BASE_URL}/v1/...` con `AGENTS_API_KEY`, tiempos máximos de 45 s (lectura) y
     reintentos acotados, y valida cada respuesta con los modelos de `contracts/`.
3. **Los contratos viven en `contracts/` y están versionados** (semver; v2 ante un cambio incompatible). Son la fuente
   de verdad que copia cuadre-agents.
4. **La web trata toda respuesta del agente como dato no confiable.** Los validadores (NIF, sumas, tipo de IVA,
   duplicados) y el registro del gasto viven aquí. `injection_suspected` fuerza la revisión manual pero nunca es
   condición para validar (NFR-07).
5. **Credenciales separadas.** Web → agentes con `AGENTS_API_KEY`. El agente recibe además un token MCP derivado de corta
   duración, nunca la service key de Supabase (ADR-0013). El agente no tiene acceso directo a la base de datos.
6. **Si el agente no responde:** el documento subido queda en estado `extraction_failed` y la persona puede rellenar el
   gasto a mano; el chat muestra un error claro. Nada se bloquea.
7. **Privacidad (NFR-11).** Las URLs firmadas duran unos 120 s; ni ellas, ni los tokens, ni el contenido de los
   documentos ni los IBAN se escriben en logs ni en trazas de este lado.
8. **Cada repo numera sus specs con su propio prefijo** (`SPEC-W-NNN` aquí, `SPEC-A-NNN` en cuadre-agents). Un cambio de
   contrato se acuerda por `contracts/CHANGELOG.md` antes de fusionar.

## Alternativas descartadas

- **Llamar a un modelo directamente desde la API de la web «mientras tanto».** Rompe la frontera y obliga a deshacer
  después; el cliente simulado da el mismo avance sin acoplamiento.
- **Que el agente escriba directamente en la base de datos.** Quitaría los validadores del único sitio donde pueden
  tener tests deterministas.
- **Un único repositorio desde el principio.** La división en dos repositorios que se fusionarán más adelante es una
  decisión previa del proyecto; este ADR la respeta y fija la frontera para que esa fusión sea mecánica.

## Consecuencias

- Se puede construir y demostrar toda la web con el cliente simulado, y activar el real cambiando una variable.
- Los fixtures simulados y los ejemplos de los contratos son el mismo conjunto de datos, así que no divergen.
- Las pruebas de contrato (qué envía la web, qué acepta) corren en los dos repositorios contra los mismos esquemas.
