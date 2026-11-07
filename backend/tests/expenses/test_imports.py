"""SPEC-W-003 §5.4 · `cuadre.expenses` y `cuadre.documents` se refieren sin ciclos, en cualquier orden de importación.

`documents.models` importa `expenses.validation_models` y `expenses.*` importa `documents.repository`: si alguien añade la flecha contraria
(`expenses` -> `documents.service`), algún orden de importación se rompe. Cada módulo se importa en un intérprete limpio.
"""

import ast
import subprocess
import sys

import pytest

from tests.rules.paths import SRC, python_files, rel

MODULES = [
    "cuadre.expenses.validation_models",
    "cuadre.expenses.models",
    "cuadre.expenses.errors",
    "cuadre.expenses.cursor",
    "cuadre.expenses.repository",
    "cuadre.expenses.validation",
    "cuadre.expenses.presentation",
    "cuadre.expenses.service",
    "cuadre.documents.models",
    "cuadre.documents.service",
    "cuadre.api.routes_expenses",
    "cuadre.api.routes_documents",
]

# Lo que `cuadre.expenses` nunca debe importar: el servicio de documentos, Storage y el cliente de agentes (el ciclo, y la frontera de IA).
FORBIDDEN = ("cuadre.documents.service", "cuadre.documents.storage", "cuadre.agents.client", "cuadre.agents.http")


@pytest.mark.parametrize("module", MODULES)
def test_each_module_imports_on_its_own_in_a_clean_interpreter(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import {module}"], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr[-600:]


def imported(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
            found += [f"{node.module}.{a.name}" for a in node.names]
    return found


def test_the_detector_detects() -> None:
    assert imported("from cuadre.documents.service import DocumentService")
    assert "cuadre.documents.service" in imported("from cuadre.documents.service import DocumentService")
    assert "cuadre.documents.storage" in imported("from cuadre.documents import storage")
    assert imported("from cuadre.documents import repository") == ["cuadre.documents", "cuadre.documents.repository"]


def test_expenses_does_not_import_the_document_service_storage_or_the_agents_client() -> None:
    offenders = {
        rel(path): [m for m in imported(path.read_text(encoding="utf-8")) if m in FORBIDDEN]
        for path in python_files(SRC / "expenses")
    }
    assert {k: v for k, v in offenders.items() if v} == {}
    assert len(offenders) >= 8
