"""SPEC-W-003 §5.4, T3-03 · `python-stdnum` y `tzdata` fijados, sin el extra SOAP (nada sale a la red).

El corpus de los validadores se midió con la versión 2.2 (Anexo B.1 de la spec): subirla exige repetir esa batería, y este test lo obliga a pasar
por aquí.
"""

import importlib.metadata
import importlib.util
import re
import tomllib

from tests.rules.paths import REPO

MEASURED_WITH = "2.2"


def dependency_name(requirement: str) -> str:
    return re.split(r"[=<>!~ \[;]", requirement, maxsplit=1)[0].lower().replace("_", "-")


def declared(name: str) -> list[str]:
    backend = tomllib.loads((REPO / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return [d for d in backend["dependencies"] if dependency_name(d) == name]


def test_the_name_detector() -> None:
    assert dependency_name("python-stdnum==2.2") == "python-stdnum"
    assert dependency_name("python_stdnum[soap]>=2") == "python-stdnum"
    assert dependency_name("tzdata==2026.6") == "tzdata"
    assert dependency_name("psycopg[binary]==3.3.7") == "psycopg"


def test_python_stdnum_is_pinned_exactly_without_extras() -> None:
    (pin,) = declared("python-stdnum")
    assert pin == f"python-stdnum=={MEASURED_WITH}", (
        "subir la versión exige repetir la batería del Anexo B.1 y actualizar este test"
    )
    assert "[" not in pin, "sin extras: `zeep`, que usa la consulta a VIES, no debe entrar"


def test_tzdata_is_pinned_exactly() -> None:
    (pin,) = declared("tzdata")
    assert re.fullmatch(r"tzdata==[0-9]{4}\.[0-9]+", pin), pin


def test_the_installed_versions_are_the_pinned_ones() -> None:
    for name in ("python-stdnum", "tzdata"):
        (pin,) = declared(name)
        assert importlib.metadata.version(name) == pin.split("==", 1)[1]


def test_the_soap_client_is_neither_declared_nor_installed() -> None:
    project = tomllib.loads((REPO / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = [
        *project["dependencies"],
        *(r for group in project.get("optional-dependencies", {}).values() for r in group),
    ]
    assert [r for r in requirements if dependency_name(r) == "zeep"] == []
    assert [r for r in requirements if "[soap]" in r.lower()] == []
    assert importlib.util.find_spec("zeep") is None
