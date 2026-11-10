"""T7-09 · Dependencias del PDF: las mínimas, fijadas por versión, confinadas a un módulo y sin red (SPEC-W-007, B.1-A).

`reportlab` dibuja el PDF y su QR, `Pillow` solo mide y lee el logo y `charset-normalizer` lo exige `reportlab`. `pypdf` es solo de pruebas. Ninguna llama
a la red. Y solo `cuadre/invoicing/pdf.py` las importa: el resto de la aplicación no sabe cómo se dibuja un PDF.
"""

import re
import tomllib
from importlib import metadata

import pytest

from tests.rules.paths import SRC, python_files, rel
from tests.rules.test_clients_boundary import network_imports
from tests.rules.test_validators_boundary import forbidden_imports, imported_modules

PYPROJECT = SRC.parents[1] / "pyproject.toml"
RUNTIME = {"reportlab": "5.1.0", "Pillow": "13.0.0", "charset-normalizer": "3.5.2"}
TEST_ONLY = {"pypdf": "7.0.0"}
PDF_MODULE = SRC / "invoicing" / "pdf.py"
PDF_LIBRARIES = ("reportlab", "PIL", "pypdf")


def requirements(section: list[str]) -> dict[str, str]:
    found = {}
    for line in section:
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)(\[[^\]]*\])?==([0-9][^;\s]*)", line.strip())
        if match:
            found[match.group(1)] = match.group(3)
    return found


def project() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]  # type: ignore[no-any-return]


def test_the_runtime_libraries_are_pinned_to_an_exact_version() -> None:
    pinned = requirements(project()["dependencies"])  # type: ignore[arg-type]
    assert {name: pinned.get(name) for name in RUNTIME} == RUNTIME


def test_pypdf_is_a_test_dependency_only() -> None:
    meta = project()
    runtime = requirements(meta["dependencies"])  # type: ignore[arg-type]
    dev = requirements(meta["optional-dependencies"]["dev"])  # type: ignore[index]
    assert "pypdf" not in runtime
    assert {name: dev.get(name) for name in TEST_ONLY} == TEST_ONLY


@pytest.mark.parametrize("name", [*RUNTIME, *TEST_ONLY])
def test_the_installed_version_is_the_pinned_one(name: str) -> None:
    assert metadata.version(name) == {**RUNTIME, **TEST_ONLY}[name]


def test_only_the_pdf_module_imports_the_drawing_libraries() -> None:
    offenders = {}
    for path in python_files(SRC):
        if path == PDF_MODULE:
            continue
        hits = [m for m in imported_modules(path.read_text(encoding="utf-8")) if m.split(".")[0] in PDF_LIBRARIES]
        if hits:
            offenders[rel(path)] = hits
    assert offenders == {}


def test_the_pdf_module_uses_reportlab_and_pillow_and_nothing_that_reaches_the_network_or_the_database() -> None:
    source = PDF_MODULE.read_text(encoding="utf-8")
    modules = imported_modules(source)
    assert any(m.startswith("reportlab") for m in modules) and any(m.startswith("PIL") for m in modules)
    assert network_imports(source) == []
    assert forbidden_imports(source) == []


def test_the_detectors_detect() -> None:
    assert [m for m in imported_modules("from reportlab.pdfgen import canvas") if m.split(".")[0] in PDF_LIBRARIES]
    assert [m for m in imported_modules("import PIL.Image") if m.split(".")[0] in PDF_LIBRARIES]
    assert requirements(["reportlab==5.1.0", "Pillow>=13", 'x==1; python_version<"3.13"'])["reportlab"] == "5.1.0"
    assert "Pillow" not in requirements(["Pillow>=13"])
