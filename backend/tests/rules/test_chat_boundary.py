"""AC-20 · Las reglas del chat (`cuadre.chat.rules` y sus tipos) son Python puro (SPEC-W-004 §6, T-01, T-05).

Sus módulos puros no importan la base de datos, la red, FastAPI, Pydantic ni la configuración y no leen ningún reloj (`today` entra como parámetro). Lo
único que traen de fuera son los modelos del contrato (`cuadre_contracts`): datos del contrato sin entrada ni salida. Cada módulo del paquete tiene que
estar declarado aquí, como puro o como no puro: un módulo nuevo sin esa decisión explícita hace fallar esta prueba en vez de colarse sin vigilancia.
"""

from tests.rules.paths import SRC, python_files, rel
from tests.rules.test_validators_boundary import clock_calls, forbidden_imports

CHAT = SRC / "chat"
PURE = {"__init__.py", "events.py", "limits.py", "rules.py", "types.py"}
IMPURE = {
    "errors.py",
    "models.py",
    "repository.py",
    "service.py",
}  # ProblemError, Pydantic de la API, SQL y el servicio con el agente


def pure_files() -> list:
    return [p for p in python_files(CHAT) if p.name in PURE]


def test_every_module_of_the_package_is_declared_as_pure_or_not() -> None:
    found = {p.name for p in python_files(CHAT)}
    assert found == PURE | IMPURE, (
        f"módulos sin declarar: {sorted(found - PURE - IMPURE)}; declarados y ausentes: {sorted((PURE | IMPURE) - found)}"
    )
    assert not (PURE & IMPURE)


def test_the_package_exists_and_has_code() -> None:
    assert len(pure_files()) == len(PURE)


def test_the_pure_modules_import_nothing_that_reaches_the_database_the_network_or_the_application() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := forbidden_imports(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_pure_modules_never_read_a_clock() -> None:
    offenders = {rel(p): hits for p in pure_files() if (hits := clock_calls(p.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_pure_modules_do_not_depend_on_the_agents_package() -> None:
    """El código de un fallo del agente llega como texto: las reglas no se acoplan al cliente HTTP ni a sus excepciones."""
    for path in pure_files():
        imports = [
            line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(("import ", "from "))
        ]
        assert not [line for line in imports if "cuadre.agents" in line], rel(path)


def test_only_the_service_talks_to_the_agent_and_only_the_repository_to_the_database() -> None:
    for path in python_files(CHAT):
        imports = [
            line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(("import ", "from "))
        ]
        if path.name != "service.py":
            assert not [line for line in imports if "cuadre.agents" in line], rel(path)
        if path.name not in {"service.py", "repository.py"}:
            assert not [line for line in imports if "psycopg" in line or "cuadre.db" in line], rel(path)
