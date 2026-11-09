"""T5-02, AC-21 · El dominio del perfil (`cuadre.profile`) es Python puro y estructuralmente no puede salirse de ahí (SPEC-W-005 §6).

Sus módulos puros no importan la base de datos, la red, FastAPI, Pydantic ni la configuración, no leen ningún reloj (`today` entra como
parámetro) y **no importan `python-stdnum`**: el NIF y el IBAN los normaliza `cuadre.validators`, la única puerta a esa librería.

Cada módulo del paquete tiene que estar declarado aquí, como puro o como no puro. El hito 3 añade `service`, `repository`, `models`… a
`IMPURE` a propósito: sin esa decisión explícita, un módulo nuevo hace fallar esta prueba en vez de colarse sin vigilancia.
"""

from tests.rules.paths import SRC, python_files, rel
from tests.rules.test_validators_boundary import clock_calls, forbidden_imports, imported_modules, stdnum_imports

PROFILE = SRC / "profile"
PURE = {"__init__.py", "limits.py", "logo.py", "rules.py", "series.py", "types.py"}
IMPURE = {"errors.py", "models.py", "repository.py", "service.py"}  # SPEC-W-005 hito 3: API, base de datos y Storage


def pure_files() -> list:
    return [p for p in python_files(PROFILE) if p.name in PURE]


def test_the_detectors_detect() -> None:
    assert forbidden_imports("from cuadre.db import user_transaction")
    assert forbidden_imports("from pydantic import BaseModel")
    assert forbidden_imports("import fastapi")
    assert forbidden_imports("from cuadre.validators import normalize_iban") == []
    assert forbidden_imports("import re\nfrom datetime import date\nfrom decimal import Decimal") == []
    assert clock_calls("from datetime import date\nx = date.today()")
    assert clock_calls("x = date(2026, 1, 1)") == []
    assert stdnum_imports("import stdnum.iban as i")
    assert stdnum_imports("from stdnum.es import nif")
    assert stdnum_imports("from cuadre.validators import normalize_iban") == []
    assert "cuadre.validators.normalize_iban" in imported_modules("from cuadre.validators import normalize_iban")


def test_every_module_of_the_package_is_declared_as_pure_or_not() -> None:
    found = {p.name for p in python_files(PROFILE)}
    assert found == PURE | IMPURE, (
        f"módulos sin declarar: {sorted(found - PURE - IMPURE)}; declarados y ausentes: {sorted((PURE | IMPURE) - found)}"
    )
    assert not (PURE & IMPURE)


def test_the_package_exists_and_has_code() -> None:
    assert len(pure_files()) >= 6


def test_the_pure_modules_import_nothing_that_reaches_the_database_the_network_or_the_application() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := forbidden_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_pure_modules_never_read_a_clock() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := clock_calls(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_profile_package_never_touches_python_stdnum() -> None:
    """El IBAN y el NIF pasan por `cuadre.validators`: allí están el prefiltro y las defensas de B.1."""
    offenders = {rel(p): hits for p in python_files(PROFILE) if (hits := stdnum_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}
