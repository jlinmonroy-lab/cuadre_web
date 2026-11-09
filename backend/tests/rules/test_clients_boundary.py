"""T6-01, AC-18 · El dominio de clientes (`cuadre.clients`) es Python puro y estructuralmente no puede salirse de ahí (SPEC-W-006 §6).

Sus módulos puros no importan la base de datos, la red, FastAPI, Pydantic ni la configuración, no leen ningún reloj y **no importan
`python-stdnum`**: el NIF y el NIF-IVA los normaliza `cuadre.validators`, la única puerta a esa librería. VIES es un puerto
(`ViesChecker`) con un simulado que no sale de la aplicación (RES-04).

Cada módulo del paquete tiene que estar declarado aquí, como puro o como no puro. El hito 3 añade `service`, `repository`, `models`… a
`IMPURE` a propósito: sin esa decisión explícita, un módulo nuevo hace fallar esta prueba en vez de colarse sin vigilancia.
"""

from tests.rules.paths import SRC, python_files, rel
from tests.rules.test_validators_boundary import clock_calls, forbidden_imports, imported_modules, stdnum_imports

CLIENTS = SRC / "clients"
PURE = {"__init__.py", "countries.py", "limits.py", "rules.py", "scope.py", "types.py", "vies.py"}
IMPURE: set[str] = set()  # SPEC-W-006 hito 3: service, repository, models, errors…

NETWORK = ("httpx", "httpx2", "requests", "urllib", "urllib3", "socket", "aiohttp", "zeep", "http")


def network_imports(source: str) -> list[str]:
    return [m for m in imported_modules(source) if any(m == n or m.startswith(n + ".") for n in NETWORK)]


def pure_files() -> list:
    return [p for p in python_files(CLIENTS) if p.name in PURE]


def test_the_detectors_detect() -> None:
    assert forbidden_imports("from cuadre.db import user_transaction")
    assert forbidden_imports("from pydantic import BaseModel")
    assert forbidden_imports("import fastapi")
    assert forbidden_imports("from cuadre.validators import normalize_tax_id") == []
    assert forbidden_imports("import re\nfrom typing import Literal") == []
    assert clock_calls("from datetime import date\nx = date.today()")
    assert clock_calls("x = 1") == []
    assert stdnum_imports("from stdnum.eu import vat")
    assert stdnum_imports("from cuadre.validators import normalize_tax_id") == []
    assert network_imports("import socket")
    assert network_imports("from urllib.request import urlopen")
    assert network_imports("import httpx2 as httpx")
    assert network_imports("import re") == []
    assert "cuadre.validators.normalize_tax_id" in imported_modules("from cuadre.validators import normalize_tax_id")


def test_every_module_of_the_package_is_declared_as_pure_or_not() -> None:
    found = {p.name for p in python_files(CLIENTS)}
    assert found == PURE | IMPURE, (
        f"módulos sin declarar: {sorted(found - PURE - IMPURE)}; declarados y ausentes: {sorted((PURE | IMPURE) - found)}"
    )
    assert not (PURE & IMPURE)


def test_the_package_exists_and_has_code() -> None:
    assert len(pure_files()) >= 7


def test_the_pure_modules_import_nothing_that_reaches_the_database_the_network_or_the_application() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := forbidden_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_pure_modules_never_touch_the_network() -> None:
    """VIES se simula: ni el puerto ni el simulado abren una conexión (RES-04)."""
    offenders = {rel(p): hits for p in pure_files() if (hits := network_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_pure_modules_never_read_a_clock() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := clock_calls(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_clients_package_never_touches_python_stdnum() -> None:
    """El NIF y el NIF-IVA pasan por `cuadre.validators`: allí están el prefiltro y las defensas de SPEC-W-003 B.1."""
    offenders = {rel(p): hits for p in python_files(CLIENTS) if (hits := stdnum_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_domain_imports_the_validators_only_through_their_public_names() -> None:
    """`cuadre.clients` usa `normalize_tax_id` y las constantes de prefijos; nada de los módulos internos de `stdnum`."""
    imported = {
        m
        for p in pure_files()
        for m in imported_modules(p.read_text(encoding="utf-8"))
        if m.startswith("cuadre.validators")
    }
    assert imported <= {
        "cuadre.validators",
        "cuadre.validators.normalize_tax_id",
        "cuadre.validators.limits",
        "cuadre.validators.limits.PREFIX_ALIASES",
    }
