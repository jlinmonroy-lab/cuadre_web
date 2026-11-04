"""T-04, T-15 · El frontend solo conoce variables públicas y solo habla con la API de cuadre-web.

Nunca ve la clave de servicio ni una URL de base de datos, y no usa los datos de Supabase directamente (la Data API está desactivada y
las reglas viven en la API): `@supabase/ssr` sirve únicamente para la sesión. La comprobación del resultado del build está en
`frontend/scripts/check-bundle.mjs` (AC-15).
"""

import re
from collections.abc import Iterator
from pathlib import Path

from tests.rules.paths import REPO, rel

FRONTEND = REPO / "frontend"
SOURCE_SUFFIXES = {".ts", ".tsx", ".mjs", ".js", ".css"}
# Estos scripts buscan precisamente esas cadenas en el build; es su trabajo nombrarlas.
SCANNER_FILES = {"scripts/bundle-scan.mjs", "scripts/bundle-scan.test.mjs", "scripts/check-bundle.mjs"}
SKIPPED_DIRECTORIES = {"node_modules", ".next", "out", "build", "coverage", "playwright-report", "test-results"}

FORBIDDEN = re.compile(
    r"SERVICE_ROLE|service_role|SUPABASE_SERVICE|DATABASE_URL|DATABASE_SERVICE_URL|sb_secret_|postgres(?:ql)?://|\bpsycopg\b"
)
ENV_READ = re.compile(r"process\.env(?:\.([A-Za-z0-9_]+)|\s*\[)")
ALLOWED_ENV = re.compile(r"NEXT_PUBLIC_[A-Z0-9_]+|NODE_ENV")
# Acceso a datos de Supabase desde el frontend: `supabase.from('…')`, `.rpc(`, `.storage`.
DATA_ACCESS = re.compile(r"supabase\w*\s*\.\s*(?:from|rpc|storage|functions|channel|realtime)\b", re.IGNORECASE)


def frontend_sources() -> Iterator[Path]:
    for path in sorted(FRONTEND.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(FRONTEND)
        if SKIPPED_DIRECTORIES & set(relative.parts) or relative.as_posix() in SCANNER_FILES:
            continue
        yield path


def forbidden_names(text: str) -> list[str]:
    return sorted({m.group(0) for m in FORBIDDEN.finditer(text)})


def env_violations(text: str) -> list[str]:
    bad = []
    for m in ENV_READ.finditer(text):
        name = m.group(1)
        if name is None:
            bad.append("process.env[...] (acceso dinámico)")
        elif not ALLOWED_ENV.fullmatch(name):
            bad.append(f"process.env.{name}")
    return bad


def test_the_detectors() -> None:
    assert forbidden_names("const k = process.env.SUPABASE_SERVICE_ROLE_KEY") == ["SUPABASE_SERVICE"]
    assert forbidden_names("const role = 'service_role'") == ["service_role"]
    assert forbidden_names('import pg from "postgresql://u:p@h/db"') == ["postgresql://"]
    assert forbidden_names("const url = process.env.NEXT_PUBLIC_SUPABASE_URL") == []
    assert env_violations("process.env.NEXT_PUBLIC_API_BASE_URL + process.env.NODE_ENV") == []
    assert env_violations("process.env.DATABASE_URL") == ["process.env.DATABASE_URL"]
    assert env_violations("process.env.SECRET_THING") == ["process.env.SECRET_THING"]
    assert env_violations("process.env[name]") == ["process.env[...] (acceso dinámico)"]
    assert DATA_ACCESS.search("const { data } = await supabase.from('invoices').select()")
    assert DATA_ACCESS.search("supabaseClient.rpc('x')")
    assert DATA_ACCESS.search("supabase.auth.getClaims()") is None
    assert DATA_ACCESS.search("Array.from(items)") is None


def test_the_frontend_has_sources_to_check() -> None:
    assert len(list(frontend_sources())) >= 20, "la guarda no está viendo el código del frontend"


def test_no_frontend_file_names_the_service_key_or_a_database_url() -> None:
    offenders = {}
    for path in frontend_sources():
        if names := forbidden_names(path.read_text(encoding="utf-8")):
            offenders[rel(path)] = names
    assert offenders == {}


def test_the_frontend_only_reads_public_environment_variables() -> None:
    offenders = {}
    for path in frontend_sources():
        if bad := env_violations(path.read_text(encoding="utf-8")):
            offenders[rel(path)] = bad
    assert offenders == {}


def test_the_frontend_does_not_touch_supabase_data() -> None:
    offenders = [rel(p) for p in frontend_sources() if DATA_ACCESS.search(p.read_text(encoding="utf-8"))]
    assert offenders == [], "los datos van por la API (cliente generado), no por supabase-js"


def test_the_frontend_env_template_only_has_public_placeholders() -> None:
    bad = []
    for line in (FRONTEND / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.split("  #")[0].strip()
        if not name.startswith("NEXT_PUBLIC_"):
            bad.append(f"{name}: no es pública")
        elif re.search(r"KEY|SECRET|TOKEN|PASSWORD", name) and not (value.startswith("<") and value.endswith(">")):
            bad.append(f"{name}: valor real en la plantilla")
    assert bad == []
