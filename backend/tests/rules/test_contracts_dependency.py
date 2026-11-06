"""SPEC-W-002 §8.4 · El backend depende de `cuadre-contracts` y todos los sitios que instalan el entorno lo hacen en el orden correcto.

`cuadre-contracts` no está en PyPI: vive en `contracts/python` y debe instalarse ANTES que el backend. Con él ya instalado, pip no
consulta el índice por ese nombre (si no, instalaría un paquete ajeno con el mismo nombre).
"""

import re
import tomllib

from tests.rules.paths import REPO

INSTALL_CONTRACTS = "pip install -e contracts/python"
INSTALL_BACKEND = 'pip install -e "backend[dev]"'


def installs_contracts_before_backend(text: str) -> bool:
    contracts, backend = text.find(INSTALL_CONTRACTS), text.find(INSTALL_BACKEND)
    return 0 <= contracts < backend


def test_the_order_detector() -> None:
    assert installs_contracts_before_backend(f"{INSTALL_CONTRACTS}\n{INSTALL_BACKEND}")
    assert not installs_contracts_before_backend(f"{INSTALL_BACKEND}\n{INSTALL_CONTRACTS}")
    assert not installs_contracts_before_backend(INSTALL_BACKEND)
    assert not installs_contracts_before_backend(INSTALL_CONTRACTS)


def test_the_backend_pins_exactly_the_version_of_the_contracts() -> None:
    backend = tomllib.loads((REPO / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pins = [d for d in backend["dependencies"] if re.split(r"[=<>!~ \[]", d, maxsplit=1)[0] == "cuadre-contracts"]
    assert len(pins) == 1, "el backend debe declarar cuadre-contracts una vez"
    (pin,) = pins
    assert pin.startswith("cuadre-contracts=="), "fijada con ==, como el resto de dependencias"

    contracts = tomllib.loads((REPO / "contracts" / "python" / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert contracts["name"] == "cuadre-contracts"
    version_file = (REPO / "contracts" / "VERSION").read_text(encoding="utf-8").strip()
    assert pin.removeprefix("cuadre-contracts==") == contracts["version"] == version_file


def test_the_ci_action_installs_the_contracts_before_the_backend() -> None:
    action = (REPO / ".github" / "actions" / "python-env" / "action.yml").read_text(encoding="utf-8")
    assert installs_contracts_before_backend(action)
    assert "contracts/python/pyproject.toml" in action, "la caché de pip debe depender también de los contratos"


def test_the_readme_installs_the_contracts_before_the_backend() -> None:
    assert installs_contracts_before_backend((REPO / "README.md").read_text(encoding="utf-8"))


def test_spec_w001_installs_the_contracts_before_the_backend() -> None:
    spec = (REPO / "docs" / "04-specs" / "SPEC-W-001-base-auth-roles-rls.md").read_text(encoding="utf-8")
    sequence = spec[spec.index("### 8.2 Secuencia") :]
    assert installs_contracts_before_backend(sequence)
