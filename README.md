# cuadre-web

Aplicación web 100 % online de facturación, contabilidad y borradores de los modelos 303 y 130 para autónomos en España.
Este repositorio contiene la web (interfaz, API, base de datos, roles, lógica fiscal, cierre mensual, recordatorios e
interfaz del chatbot). El agente de lectura de facturas y el del chatbot viven en **cuadre-agents** y se consumen a través
de los contratos de [`contracts/`](contracts/README.md).

> Desarrollo guiado por specs (spec-anchored). [`SPEC-W-001`](docs/04-specs/SPEC-W-001-base-auth-roles-rls.md) se ha implementado por
> hitos (cimientos, base de datos con RLS, API, frontend, pruebas de extremo a extremo y CI) y está en revisión: el CI está escrito
> y comprobado en un clon limpio, pero aún no se ha ejecutado en GitHub porque no hay repositorio remoto (ver «Integración continua»).
> El estado de cada spec está en `docs/04-specs/tasks.json`.

## Dónde mirar

| Qué | Dónde |
|---|---|
| Alcance y riesgos | [`docs/00-charter.md`](docs/00-charter.md) |
| Requisitos, historias y trazabilidad | [`docs/03-prd.md`](docs/03-prd.md) |
| Prototipo navegable de la interfaz | [`docs/cuadre-interfaz.html`](docs/cuadre-interfaz.html) |
| Specs y su estado | [`docs/04-specs/tasks.json`](docs/04-specs/tasks.json) |
| Decisiones de arquitectura | [`docs/06-adr/`](docs/06-adr/README.md) |
| Contratos con cuadre-agents | [`contracts/`](contracts/README.md) |
| Guía para trabajar con Claude Code | [`CLAUDE.md`](CLAUDE.md) |

## Requisitos

- Python **3.12** (en Windows, `python`; el lanzador `py` puede apuntar a otra versión)
- Node **24** y npm
- Docker Desktop **en marcha** (Supabase local)
- Git

## Puesta en marcha

```powershell
# Entorno virtual de Python (en la raíz del repositorio)
python -m venv .venv
.\.venv\Scripts\Activate.ps1                       # Git Bash: source .venv/Scripts/activate · Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r contracts/requirements.txt
pip install -e contracts/python                    # cuadre-contracts (no está en PyPI): siempre ANTES que el backend, que depende de él
pip install -e "backend[dev]"

# Supabase local (Docker Desktop en marcha)
npm ci
npm run gen:signing-key                            # una vez: clave ES256 de desarrollo (gitignorada)
npx supabase start                                 # y `npx supabase db reset` para recrear migraciones + seed

# Variables de entorno (nunca se suben valores reales)
npm run env:local                                  # con la pila en marcha: genera .env y frontend/.env.local; no pisa los existentes (--force)

# Arranque
uvicorn cuadre.main:app --reload --port 8000 --app-dir backend/src
npm --prefix frontend ci
npm --prefix frontend run dev                      # http://localhost:3000
```

`npm run env:local` escribe `.env` (backend, tests y CLI; nunca llega al frontend) y `frontend/.env.local` (solo `NEXT_PUBLIC_*`) con las claves de la
pila local. `ADMIN_PASSWORD` solo hace falta para `python -m cuadre.cli create-admin`: añádela tú. [`.env.example`](.env.example) documenta cada variable.

Abre **siempre `http://localhost:3000`** (no `127.0.0.1`): las cookies de sesión van por host y la CORS de la API solo admite ese
origen. `npm --prefix frontend run build` descarga las fuentes: necesita red.

Cuentas de desarrollo (datos sintéticos del seed, solo en local): `alicia@example.test` (autónomo), `gina@example.test` (gestor) y
`adan@example.test` (administrador); la contraseña está en `supabase/seed.sql`. El correo que envía Supabase Auth (confirmación y
recuperación) se lee en Mailpit: <http://127.0.0.1:54324>.

## Comprobaciones

```powershell
ruff check backend contracts/tools contracts/python ; ruff format --check backend contracts/tools contracts/python
pytest backend/tests/rls -m rls -q                 # aislamiento por rol (NFR-06, puerta de despliegue)
pytest backend/tests -m "not rls" -q               # API y guardas de reglas
python contracts/tools/export_schemas.py --check ; python contracts/tools/validate_examples.py
python backend/scripts/export_openapi.py --check
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit ; npm run test:scripts
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend run e2e:install              # una vez: Chromium, Firefox y WebKit de Playwright
npm --prefix frontend run test:e2e                 # contra `next start` (lo construye); pila de Supabase en marcha y puertos 3000, 8000 y 8765 libres
```

Las pruebas E2E arrancan solas tres servidores: la API, la web (producción) y un **servidor de agentes de E2E**
(`backend/tests/agents/e2e_server.py`, puerto 8765, o el de `E2E_AGENTS_PORT` si otro proceso lo ocupa; en Windows no se enlaza a un puerto ya
ocupado: falla al arrancar). La API lo usa como `AGENTS_BASE_URL`, así que lee las facturas con `HttpAgentsClient` y
no con el simulado, cuyo orden es global y no sirve con seis proyectos en paralelo: cada prueba elige qué lee el agente con un marcador
dentro del archivo sintético que sube. Ni la API ni la web se reutilizan si ya están levantadas, para no probar sin querer el servidor de
desarrollo ni una API con el simulado (`E2E_REUSE_SERVER=1` lo permite; entonces la API debe arrancarse con la `AGENTS_BASE_URL` y la
`AGENTS_API_KEY` de `frontend/playwright.config.ts`). Con un `next dev` propio en el 3000, `E2E_WEB_PORT=3100 npm --prefix frontend run test:e2e`
levanta la web de E2E en otro puerto. Las pruebas dejan cuentas `e2e-…@example.test` en la base local: `npm run db:reset` la limpia. Las de gastos preparan y limpian los gastos de su
cuenta por la API y necesitan `frontend/.env.local` (lo crea `npm run env:local`; el CI ya lo hace) o `E2E_SUPABASE_URL` y `E2E_SUPABASE_ANON_KEY`.

## Integración continua

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) repite en un runner limpio (Ubuntu) la secuencia de comprobaciones de la spec (§8.2) en cinco
trabajos independientes y en paralelo:

| Trabajo | Qué comprueba | Pila de Supabase |
|---|---|---|
| **RLS (NFR-06)** | `pytest backend/tests/rls -m rls`: 0 accesos indebidos entre usuario, gestor y administrador | sí |
| Python: estilo y deriva | ruff, esquemas de contratos, ejemplos y `openapi.json` | no |
| Backend: API y reglas | `pytest backend/tests -m "not rls"` | sí |
| Frontend: calidad y build | lint, typecheck, pruebas unitarias, cliente generado, build y búsqueda de fugas | no |
| E2E: Playwright | Chromium, Firefox y WebKit a 390 y 1.440 px contra `next start` | sí |

- Sin secretos de repositorio: la pila de Supabase es efímera y sus claves se generan en cada ejecución (`npm run env:local -- --ci` las enmascara en el registro).
- En el CI **un test omitido hace fallar la sesión**: una clave que falte no puede convertir la puerta RLS en un falso verde.
- Las actions de terceros van fijadas por SHA. `backend/tests/rules/test_ci_workflow.py` vigila que la puerta RLS no se pueda saltar, que los permisos sean de solo lectura
  y que el workflow ejecute cada comando de la secuencia de la spec.
- Sin filtros de ruta a propósito: un check obligatorio que no se dispara deja el PR bloqueado.

**Estado:** el workflow está validado con `actionlint` y sus pasos se repitieron, uno a uno, en un clon limpio con `CI=true`, pero **no se ha ejecutado en un runner de
GitHub** porque aún no hay repositorio remoto. Cuando exista:

1. Sube `main` y lanza el workflow a mano (pestaña *Actions* → *CI* → *Run workflow*). Es previsible que la primera ejecución en Linux pida algún ajuste.
2. Protege `main` (*Settings* → *Rules* → *Rulesets*): exige pull request y marca como comprobación obligatoria **`RLS (NFR-06)`** (NFR-06 como puerta de
   despliegue, ADR-0010). Recomendadas: los otros cuatro trabajos.

## Reglas que no se negocian

Importes sin `float` · una factura emitida no se edita ni se borra · nada se envía a la AEAT · solo datos sintéticos · este
repositorio no llama a APIs de modelos · la service key de Supabase no sale de los jobs y la CLI. La lista completa y su
justificación están en [`CLAUDE.md`](CLAUDE.md).
