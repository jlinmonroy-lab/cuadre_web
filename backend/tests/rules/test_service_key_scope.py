"""T-04 · La clave de servicio de Supabase y `DATABASE_SERVICE_URL` solo se usan en `cuadre.jobs` y `cuadre.cli`.

Nunca en rutas que actúan en nombre de un usuario ni en el frontend. `cuadre.config` únicamente los DECLARA como ajustes y
`cuadre.db` define `service_transaction` (que no lee ningún ajuste).
"""

import ast

from tests.rules.paths import REPO, SRC, python_files, rel

SETTINGS = {"supabase_service_role_key", "database_service_url", "admin_password"}
SETTING_STRINGS = ("SUPABASE_SERVICE_ROLE_KEY", "DATABASE_SERVICE_URL", "ADMIN_PASSWORD")
SERVICE_API = {"service_transaction"}

# módulo (ruta relativa a cuadre/) -> qué puede usar
ALLOWED_EVERYTHING = ("config.py", "cli.py", "jobs/")
ALLOWED_SERVICE_API = ("db/",)

# Los scripts que comprueban el build buscan precisamente estas cadenas: es su trabajo nombrarlas.
SCANNER_FILES = {"scripts/bundle-scan.mjs", "scripts/bundle-scan.test.mjs", "scripts/check-bundle.mjs"}


def violations(source: str, path_in_package: str) -> list[str]:
    if path_in_package.startswith(ALLOWED_EVERYTHING):
        return []
    allow_service_api = path_in_package.startswith(ALLOWED_SERVICE_API)
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }  # documentar una variable no es usarla
    found = []
    for node in ast.walk(tree):
        names = set()
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and any(s in node.value for s in SETTING_STRINGS)
        ):
            found.append(f"línea {node.lineno}: cadena que nombra una credencial de servicio")
        for name in names:
            if name in SETTINGS or (name in SERVICE_API and not allow_service_api):
                found.append(f"línea {getattr(node, 'lineno', '?')}: usa `{name}`")
    return found


def test_the_detector_flags_forbidden_use_and_allows_the_exceptions() -> None:
    assert violations("settings.supabase_service_role_key", "api/routes_me.py")
    assert violations("from cuadre.db import service_transaction", "api/routes_me.py")
    assert violations("os.environ['DATABASE_SERVICE_URL']", "core/auth.py")
    assert violations("settings.supabase_service_role_key", "cli.py") == []
    assert violations("settings.database_service_url", "jobs/close_month.py") == []
    assert violations("def service_transaction(): ...", "db/session.py") == []
    assert violations("settings.database_service_url", "db/session.py"), (
        "db define service_transaction pero no lee ajustes"
    )
    assert violations('def f():\n    """Se abre con `DATABASE_SERVICE_URL`."""', "db/session.py") == [], (
        "un docstring no es un uso"
    )
    assert violations('x = "DATABASE_SERVICE_URL"', "db/session.py"), "pero una cadena en código sí"


def test_only_config_cli_and_jobs_touch_the_service_credentials() -> None:
    offenders = {}
    for path in python_files(SRC):
        in_package = path.relative_to(SRC).as_posix()
        if hits := violations(path.read_text(encoding="utf-8"), in_package):
            offenders[rel(path)] = hits
    assert offenders == {}


def test_the_frontend_never_mentions_the_service_credentials() -> None:
    frontend = REPO / "frontend"
    if not frontend.exists():
        return
    needles = ("SERVICE_ROLE", "service_role", "DATABASE_SERVICE_URL", "SUPABASE_SECRET", "sb_secret_")
    offenders = []
    for path in sorted(frontend.rglob("*")):
        if not path.is_file() or any(
            p in path.parts for p in ("node_modules", ".next", "playwright-report", "test-results")
        ):
            continue
        if path.suffix not in {
            ".ts",
            ".tsx",
            ".js",
            ".mjs",
            ".json",
            ".css",
            ".md",
            ".env",
            ".local",
        } and not path.name.startswith(".env"):
            continue
        if path.name == "package-lock.json" or path.relative_to(frontend).as_posix() in SCANNER_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        offenders += [f"{rel(path)}: {n}" for n in needles if n in text]
    assert offenders == []
