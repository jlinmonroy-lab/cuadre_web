# ADR-0009 · Entorno de desarrollo: venv en la raíz, npm y Supabase local

- **Estado:** Aceptado
- **Fecha:** 2026-11-03

## Contexto

El equipo es una persona en Windows 11 (PowerShell y Git Bash) con Python 3.12.10, Node 24 y Docker Desktop. El CI
corre en Linux. Los comandos documentados deben valer en ambos sistemas.

## Decisión

- **Python:** entorno virtual `.venv/` en la raíz del repositorio, creado con `python -m venv .venv` usando 3.12
  (en Windows, el lanzador `py` apunta a otra versión: se usa `python` o `py -3.12`). Se activa con
  `.\.venv\Scripts\Activate.ps1` (PowerShell), `source .venv/Scripts/activate` (Git Bash) o `.venv/bin/activate` (Linux).
- **Dependencias de Python:** `pyproject.toml` por paquete con versiones fijadas (`==`) y un extra `dev`;
  `backend/` se instala con `pip install -e "backend[dev]"` y consume `contracts/python` como paquete local. Hasta que
  exista `backend/pyproject.toml` (SPEC-W-001), `contracts/requirements.txt` cubre el tooling de contratos.
- **Node:** `npm` con `package-lock.json` versionado, en `frontend/` y en la raíz.
- **Supabase local:** la CLI de Supabase como dependencia de desarrollo de la raíz (`npx supabase …`), que levanta
  Postgres, Auth, Storage y Mailpit en contenedores. **Requiere Docker Desktop en marcha.**
- **Variables de entorno:** `.env.example` documentado; `.env` y `frontend/.env.local` fuera de git (RES-07).
- **Comandos con el venv activado** y desde la carpeta de cada parte. Los documentos del repositorio escriben así los
  comandos de verificación para que sirvan igual en CI.

## Alternativas descartadas

- **`uv` o Poetry.** Más rápidos o con bloqueo propio, pero el enunciado pide un entorno virtual y `pip` basta para un
  único paquete. Se puede adoptar `uv` más adelante sin cambiar `pyproject.toml`.
- **Un `.venv` dentro de `backend/`.** Los scripts de `contracts/tools/` también lo necesitan; un solo entorno evita
  versiones distintas de Pydantic entre contratos y backend.
- **Make/Just para orquestar.** No existen de forma nativa en Windows; los comandos explícitos son más portables.

## Consecuencias

- Quien clone el repositorio necesita Python 3.12, Node, Docker y la CLI de Supabase (vía `npx`); el README lo lista.
- Un script de arranque (`scripts/setup`) se valorará solo si el onboarding se vuelve repetitivo.
