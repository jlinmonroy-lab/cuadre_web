# cuadre-web

Aplicación web 100 % online de facturación, contabilidad y borradores de los modelos 303 y 130 para autónomos en España.
Este repositorio contiene la web (interfaz, API, base de datos, roles, lógica fiscal, cierre mensual, recordatorios e
interfaz del chatbot). El agente de lectura de facturas y el del chatbot viven en **cuadre-agents** y se consumen a través
de los contratos de [`contracts/`](contracts/README.md).

> Proyecto en fase de especificación: todavía no hay código de aplicación. El trabajo sigue desarrollo guiado por specs
> (spec-anchored). El punto de partida es [`SPEC-W-001`](docs/04-specs/SPEC-W-001-base-auth-roles-rls.md).

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

# Comprobar los contratos
python contracts/tools/export_schemas.py --check
python contracts/tools/validate_examples.py
```

Cuando se implemente SPEC-W-001 se añadirán `pip install -e "backend[dev]"`, `npm ci`, `npx supabase start` y los comandos de
arranque de la API y el frontend (consulta la spec, apartado 5.5). Copia `.env.example` a `.env` y a
`frontend/.env.local`; **nunca** subas valores reales.

## Reglas que no se negocian

Importes sin `float` · una factura emitida no se edita ni se borra · nada se envía a la AEAT · solo datos sintéticos · este
repositorio no llama a APIs de modelos · la service key de Supabase no sale de los jobs y la CLI. La lista completa y su
justificación están en [`CLAUDE.md`](CLAUDE.md).
