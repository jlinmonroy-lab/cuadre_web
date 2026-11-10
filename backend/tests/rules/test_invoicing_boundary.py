"""T7-01, T7-04, AC-24 · El dominio de facturación (`cuadre.tax` y `cuadre.invoicing`) es Python puro y estructuralmente no puede salirse de ahí.

Sus módulos puros no importan la base de datos, la red, FastAPI, Pydantic ni la configuración, no leen ningún reloj (la fecha de hoy es un argumento)
y no importan `python-stdnum`. `cuadre.tax` no depende de `cuadre.invoicing` (el reparto es en un solo sentido). De `cuadre.validators` solo se
usan el IVA (`vat`) y la fecha mínima (`limits`). El float lo vigila `test_no_float.py` en todo `src/cuadre`.

Cada módulo de cada paquete tiene que estar declarado aquí, como puro o como no puro. El hito 3 añadirá `service`, `repository`, `models`, `errors`,
`pdf` y `storage` a `IMPURE` a propósito: sin esa decisión explícita, un módulo nuevo hace fallar esta prueba en vez de colarse sin vigilancia.
"""

from tests.rules.paths import SRC, python_files, rel
from tests.rules.test_clients_boundary import network_imports
from tests.rules.test_validators_boundary import clock_calls, forbidden_imports, imported_modules, stdnum_imports

TAX = SRC / "tax"
INVOICING = SRC / "invoicing"
PURE_TAX = {"__init__.py", "amounts.py", "invoice_terms.py", "limits.py", "types.py"}
PURE_INVOICING = {
    "__init__.py",
    "limits.py",
    "logo.py",
    "numbering.py",
    "qr.py",
    "rectification.py",
    "rules.py",
    "storage_path.py",
    "texts.py",
    "types.py",
}
IMPURE_TAX: set[str] = set()
IMPURE_INVOICING = {
    "errors.py",
    "models.py",
    "pdf.py",
    "repository.py",
    "service.py",
    "storage.py",
}  # SPEC-W-007 hito 3: API y base de datos; hito 4: el PDF (reportlab y Pillow) y Storage

PACKAGES = ((TAX, PURE_TAX, IMPURE_TAX), (INVOICING, PURE_INVOICING, IMPURE_INVOICING))


def pure_files() -> list:
    return [p for root, pure, _ in PACKAGES for p in python_files(root) if p.name in pure]


def test_the_detectors_detect() -> None:
    assert forbidden_imports("from cuadre.db import user_transaction")
    assert forbidden_imports("from pydantic import BaseModel")
    assert forbidden_imports("import fastapi")
    assert forbidden_imports("from cuadre.validators.vat import percentage_of") == []
    assert clock_calls("from datetime import date\nx = date.today()")
    assert clock_calls("from datetime import datetime\nx = datetime.now()")
    assert clock_calls("x = 1") == []
    assert stdnum_imports("from stdnum.eu import vat")
    assert network_imports("import socket")
    assert network_imports("import re") == []


def test_every_module_of_each_package_is_declared_as_pure_or_not() -> None:
    for root, pure, impure in PACKAGES:
        found = {p.name for p in python_files(root)}
        assert found == pure | impure, (
            f"{root.name}: módulos sin declarar: {sorted(found - pure - impure)}; "
            f"declarados y ausentes: {sorted((pure | impure) - found)}"
        )
        assert not (pure & impure)


def test_the_packages_exist_and_have_code() -> None:
    assert len(pure_files()) >= 15


def test_the_pure_modules_import_nothing_that_reaches_the_database_the_network_or_the_application() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := forbidden_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_no_module_of_the_packages_touches_the_network_not_even_the_ones_with_a_database() -> None:
    offenders = {
        rel(p): hits
        for root, _, _ in PACKAGES
        for p in python_files(root)
        if (hits := network_imports(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_pure_modules_never_read_a_clock() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := clock_calls(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_packages_never_touch_python_stdnum() -> None:
    offenders = {
        rel(p): hits
        for root, _, _ in PACKAGES
        for p in python_files(root)
        if (hits := stdnum_imports(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_tax_package_does_not_depend_on_the_invoicing_package() -> None:
    offenders = {
        rel(p): [m for m in imported_modules(p.read_text(encoding="utf-8")) if m.startswith("cuadre.invoicing")]
        for p in python_files(TAX)
    }
    assert {k: v for k, v in offenders.items() if v} == {}


def test_the_domain_uses_the_validators_only_for_vat_and_the_earliest_date() -> None:
    imported = {
        m
        for p in pure_files()
        for m in imported_modules(p.read_text(encoding="utf-8"))
        if m.startswith("cuadre.validators")
    }
    assert imported <= {
        "cuadre.validators.vat",
        "cuadre.validators.vat.percentage_of",
        "cuadre.validators.vat.parse_rate",
        "cuadre.validators.limits",
        "cuadre.validators.limits.EARLIEST_DATE",
    }
    assert imported  # y de verdad los usa


def test_the_domain_reaches_other_domains_only_through_their_pure_types_and_limits() -> None:
    """De `cuadre.clients` solo los tipos de ámbito y tipo y las categorías de texto; nada del servicio, el repositorio ni la API."""
    allowed_prefixes = (
        "cuadre.tax",
        "cuadre.invoicing",
        "cuadre.validators",
        "cuadre.clients.types",
        "cuadre.clients.limits",
    )
    offenders: dict[str, list[str]] = {}
    for p in pure_files():
        bad = [
            m
            for m in imported_modules(p.read_text(encoding="utf-8"))
            if m.startswith("cuadre.") and not m.startswith(allowed_prefixes)
        ]
        if bad:
            offenders[rel(p)] = bad
    assert offenders == {}
