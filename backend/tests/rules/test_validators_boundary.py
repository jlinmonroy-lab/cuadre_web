"""T3-03, AC-19 · `cuadre.validators` es Python puro y estructuralmente no puede salirse de ahí (SPEC-W-003 §6).

No importa la base de datos, la red, FastAPI ni la configuración; no lee ningún reloj (`today` entra como parámetro); solo `tax_id.py` toca
`python-stdnum`, y nunca la consulta a VIES ni su cliente SOAP. Así «sin red» y «sin reloj» no dependen de que alguien se acuerde.
"""

import ast

from tests.rules.paths import SRC, python_files, rel

VALIDATORS = SRC / "validators"
TAX_ID = VALIDATORS / "tax_id.py"

FORBIDDEN_IMPORTS = (
    "cuadre.db",
    "cuadre.core",
    "cuadre.api",
    "cuadre.config",
    "cuadre.documents",
    "cuadre.agents",
    "psycopg",
    "psycopg_pool",
    "httpx",
    "httpx2",
    "fastapi",
    "starlette",
    "pydantic",
    "jwt",
    "requests",
    "urllib",
    "socket",
    "ssl",
    "time",
    "os",
    "subprocess",
    "asyncio",
    "threading",
    "zeep",
)
CLOCK_CALLS = {
    "now",
    "today",
    "utcnow",
    "fromtimestamp",
    "utcfromtimestamp",
    "time",
    "monotonic",
    "perf_counter",
    "sleep",
}
STDNUM_ALLOWED = ("stdnum.es", "stdnum.eu")
VIES_NAMES = {"check_vies", "check_vies_approx", "get_soap_client"}


def imported_modules(source: str) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
            modules += [f"{node.module}.{a.name}" for a in node.names]
    return modules


def forbidden_imports(source: str) -> list[str]:
    return [m for m in imported_modules(source) if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS)]


def clock_calls(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in CLOCK_CALLS:
            found.append(f"línea {node.lineno}: .{func.attr}()")
        elif isinstance(func, ast.Name) and func.id in CLOCK_CALLS:
            found.append(f"línea {node.lineno}: {func.id}()")
    return found


def stdnum_imports(source: str) -> list[str]:
    return [m for m in imported_modules(source) if m == "stdnum" or m.startswith("stdnum.")]


def disallowed_stdnum_imports(source: str) -> list[str]:
    return [m for m in stdnum_imports(source) if not any(m == a or m.startswith(a + ".") for a in STDNUM_ALLOWED)]


def vies_uses(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id in VIES_NAMES:
            found.append(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in VIES_NAMES:
            found.append(node.attr)
        elif isinstance(node, ast.alias) and node.name in VIES_NAMES:
            found.append(node.name)
    found += [m for m in imported_modules(source) if "vies" in m.lower()]
    return found


def test_the_detectors_detect() -> None:
    assert forbidden_imports("from cuadre.db import user_transaction")
    assert forbidden_imports("import psycopg")
    assert forbidden_imports("import time")
    assert forbidden_imports("from datetime import date\nimport httpx2")
    assert forbidden_imports("from cuadre.validators.limits import X\nfrom datetime import date\nimport re") == []
    assert clock_calls("from datetime import date\nx = date.today()")
    assert clock_calls("import datetime\nx = datetime.datetime.now()")
    assert clock_calls("x = utcnow()")
    assert clock_calls("x = time.monotonic()")
    assert clock_calls("x = date(2026, 1, 1)\ny = date.fromisoformat('2026-01-01')") == []
    assert stdnum_imports("from stdnum.es import nif")
    assert stdnum_imports("import stdnum")
    assert stdnum_imports("import re") == []
    assert disallowed_stdnum_imports("from stdnum.util import get_soap_client")
    assert disallowed_stdnum_imports("from stdnum.es import nif\nfrom stdnum.eu import vat") == []
    assert vies_uses("from stdnum.eu import vat\nvat.check_vies('DE1')")
    assert vies_uses("from stdnum.util import get_soap_client")
    assert vies_uses("import stdnum.eu.vies")
    assert vies_uses("from stdnum.eu import vat\nvat.validate('DE1')") == []


def test_the_validators_package_exists_and_has_code() -> None:
    assert len(list(python_files(VALIDATORS))) >= 10
    assert TAX_ID.exists()


def test_the_validators_import_nothing_that_reaches_the_database_the_network_or_the_application() -> None:
    offenders = {
        rel(p): hits for p in python_files(VALIDATORS) if (hits := forbidden_imports(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_validators_never_read_a_clock() -> None:
    offenders = {rel(p): hits for p in python_files(VALIDATORS) if (hits := clock_calls(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_only_tax_id_touches_python_stdnum_and_only_its_spanish_and_eu_modules() -> None:
    importers = [p for p in python_files(VALIDATORS) if stdnum_imports(p.read_text(encoding="utf-8"))]
    assert importers == [TAX_ID]
    assert disallowed_stdnum_imports(TAX_ID.read_text(encoding="utf-8")) == []


def test_nothing_in_the_package_can_reach_vies_or_the_soap_client() -> None:
    offenders = {rel(p): hits for p in python_files(VALIDATORS) if (hits := vies_uses(p.read_text(encoding="utf-8")))}
    assert offenders == {}
