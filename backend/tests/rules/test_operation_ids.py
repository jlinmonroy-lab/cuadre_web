"""T-11, ADR-0011 · Cada ruta declara `operation_id` explícito, único y con forma `verbo_objeto`.

El cliente TypeScript se genera desde `openapi.json`: sus funciones se llaman como el `operation_id`.
"""

import ast
import re

import pytest

from cuadre.config import Settings
from cuadre.core.routing import new_router
from cuadre.main import create_app
from tests.rules.paths import SRC, python_files, rel

PATTERN = re.compile(r"^[a-z]+(_[a-z0-9]+)+$")
VERBS = {
    "get",
    "list",
    "create",
    "update",
    "delete",
    "set",
    "issue",
    "upload",
    "confirm",
    "validate",
    "accept",
    "decline",
    "revoke",
    # SPEC-W-010 §5.3: invitar a un gestor.
    "invite",
    "send",
    # SPEC-W-002 §5.1 fija estos operation_id (el prototipo y la spec los nombran así).
    "complete",
    "retry",
    "save",
    "discard",
    # SPEC-W-003 §5.4: anular un gasto.
    "void",
    # SPEC-W-007 §5.3: la vista previa de una factura.
    "preview",
}


def test_every_operation_id_is_snake_case_verb_object_and_unique() -> None:
    schema = create_app(Settings()).openapi()  # type: ignore[call-arg]
    ids = [op["operationId"] for path in schema["paths"].values() for op in path.values()]
    assert len(ids) >= 2
    assert len(ids) == len(set(ids)), f"operation_id repetidos: {sorted(i for i in ids if ids.count(i) > 1)}"
    for operation_id in ids:
        assert PATTERN.match(operation_id), f"{operation_id!r} no es verbo_objeto en snake_case"
        assert operation_id.split("_")[0] in VERBS, f"{operation_id!r} no empieza por un verbo conocido {sorted(VERBS)}"


def test_a_route_without_operation_id_fails_when_it_is_defined() -> None:
    router = new_router(tags=["prueba"])
    with pytest.raises(RuntimeError, match="no declara operation_id"):

        @router.get("/sin-id")
        def handler() -> None: ...


def test_routers_are_only_created_through_the_factory() -> None:
    """Un `APIRouter(...)` suelto usaría el generador por defecto de FastAPI y se saltaría la exigencia de operation_id."""
    offenders = []
    for path in python_files(SRC):
        if path.name == "routing.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                if name == "APIRouter":
                    offenders.append(f"{rel(path)}:{node.lineno}")
    assert offenders == []


def test_the_application_itself_requires_operation_ids() -> None:
    source = (SRC / "main.py").read_text(encoding="utf-8")
    assert "generate_unique_id_function=require_operation_id" in source
