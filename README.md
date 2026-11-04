# cuadre-web

Aplicación web 100 % online de facturación, contabilidad y borradores de los modelos 303 y 130 para autónomos en España.
Este repositorio contiene la web (interfaz, API, base de datos, roles, lógica fiscal, cierre mensual, recordatorios e
interfaz del chatbot). El agente de lectura de facturas y el del chatbot viven en **cuadre-agents** y se consumen a través
de los contratos de [`contracts/`](contracts/README.md).

> Desarrollo guiado por specs (spec-anchored). Se está implementando
> [`SPEC-W-001`](docs/04-specs/SPEC-W-001-base-auth-roles-rls.md) por hitos: cimientos, base de datos con RLS, API y frontend
> y pruebas de extremo a extremo están hechos; falta el CI (el estado de cada spec está en `docs/04-specs/tasks.json`).

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
pip install -e "backend[dev]"

# Supabase local (Docker Desktop en marcha)
npm ci
npm run gen:signing-key                            # una vez: clave ES256 de desarrollo (gitignorada)
npx supabase start                                 # y `npx supabase db reset` para recrear migraciones + seed

# Variables de entorno (nunca se suben valores reales)
copy .env.example .env                             # backend y tests; rellena con `npx supabase status`
copy frontend\.env.example frontend\.env.local     # solo NEXT_PUBLIC_*

# Arranque
uvicorn cuadre.main:app --reload --port 8000 --app-dir backend/src
npm --prefix frontend ci
npm --prefix frontend run dev                      # http://localhost:3000
```

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
npm --prefix frontend run lint ; npm --prefix frontend run typecheck ; npm --prefix frontend run test:unit
npm --prefix frontend run gen:api -- --check
npm --prefix frontend run build ; npm --prefix frontend run check:bundle
npm --prefix frontend run e2e:install              # una vez: Chromium, Firefox y WebKit de Playwright
npm --prefix frontend run test:e2e                 # contra `next start` (lo construye); pila de Supabase en marcha y puertos 3000 y 8000 libres
```

Las pruebas E2E arrancan solas la API y la web (producción); no reutilizan un servidor ya levantado, para no probar sin querer el de
desarrollo (`E2E_REUSE_SERVER=1` lo permite). Dejan cuentas `e2e-…@example.test` en la base local: `npm run db:reset` la limpia.

## Reglas que no se negocian

Importes sin `float` · una factura emitida no se edita ni se borra · nada se envía a la AEAT · solo datos sintéticos · este
repositorio no llama a APIs de modelos · la service key de Supabase no sale de los jobs y la CLI. La lista completa y su
justificación están en [`CLAUDE.md`](CLAUDE.md).
