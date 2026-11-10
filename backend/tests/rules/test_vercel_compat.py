"""T2-13, T2-14, ADR-0016 · La API es compatible con una función de Vercel: sin trabajo posterior a la respuesta y sin archivos por la API.

* **Sin trabajo posterior a la respuesta.** Una función serverless puede congelarse al responder: nada de `BackgroundTasks`, hilos,
  procesos ni tareas que sobrevivan a la petición. La lectura de una factura ocurre DENTRO de `complete` y `retry` (D-02).
* **Ningún archivo pasa por la API.** Vercel limita el cuerpo de una petición a 4,5 MB y aquí el límite es de 15 MiB: el navegador sube
  a Storage con una URL firmada y el agente lee con otra.
"""

import ast
import json
from typing import Any

from cuadre.config import Settings
from cuadre.main import create_app
from tests.rules.paths import SRC, python_files, rel

# Nombres que delatan trabajo que sobrevive a la respuesta.
BACKGROUND_NAMES = {
    "BackgroundTasks",
    "BackgroundTask",
    "Thread",
    "Timer",
    "Process",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "create_task",
    "ensure_future",
    "run_in_executor",
    "call_later",
    "call_soon",
}
BACKGROUND_MODULES = {"threading", "multiprocessing", "sched", "concurrent.futures"}
UPLOAD_NAMES = {"UploadFile", "File", "Form"}
FORBIDDEN_MEDIA_TYPES = ("multipart/form-data", "application/octet-stream")
# La única respuesta que no es JSON: el PDF de una factura (SPEC-W-007 §5.3). Pesa de 8 a 18 KB y el bucket lo limita a 1 MiB, muy por debajo de los
# 4,5 MB de Vercel; la web no ve nunca la URL de Storage (§5.5). ADR-0016 (punto 5) habla de subidas y de archivos grandes: ninguna ruta los admite.
ALLOWED_BINARY_RESPONSES = ["GET /api/invoices/{invoice_id}/pdf: application/pdf"]


def background_work(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [f"línea {node.lineno}: import {a.name}" for a in node.names if a.name in BACKGROUND_MODULES]
        elif isinstance(node, ast.ImportFrom) and node.module in BACKGROUND_MODULES:
            found.append(f"línea {node.lineno}: from {node.module}")
        elif isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name in BACKGROUND_NAMES:
                found.append(f"línea {node.lineno}: {name}")
        elif isinstance(node, ast.alias) and node.name in BACKGROUND_NAMES:
            found.append(f"línea {getattr(node, 'lineno', '?')}: import {node.name}")
    return found


def file_upload_in_routes(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.alias):
            name = node.name
        if name in UPLOAD_NAMES:
            found.append(f"línea {getattr(node, 'lineno', '?')}: {name}")
    return found


def media_types(schema: Any) -> list[str]:
    """Todos los tipos de contenido que el OpenAPI declara en cuerpos de petición y de respuesta."""
    found: list[str] = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            bodies = [operation.get("requestBody", {}).get("content", {})]
            bodies += [r.get("content", {}) for r in operation.get("responses", {}).values()]
            found += [f"{method.upper()} {path}: {m}" for body in bodies for m in body]
    return found


# --- Los detectores detectan ------------------------------------------------------------------------------------------------


def test_the_background_detector() -> None:
    assert background_work("from fastapi import BackgroundTasks")
    assert background_work("def f(bg: BackgroundTasks): bg.add_task(g)")
    assert background_work("import threading")
    assert background_work("import threading as t\nt.Thread(target=f).start()")
    assert background_work("from concurrent.futures import ThreadPoolExecutor")
    assert background_work("asyncio.create_task(f())")
    assert background_work("loop.run_in_executor(None, f)")
    assert background_work("from multiprocessing import Process")
    assert background_work("import itertools\nn = next(itertools.count())") == []
    assert background_work("from fastapi.concurrency import run_in_threadpool\nawait run_in_threadpool(f)") == []


def test_the_upload_detector() -> None:
    assert file_upload_in_routes("from fastapi import UploadFile")
    assert file_upload_in_routes("def f(file: UploadFile = File(...)): ...")
    assert file_upload_in_routes("def f(x: str = Form(...)): ...")
    assert file_upload_in_routes("def f(body: UploadRequest): ...") == []


def test_the_media_type_detector() -> None:
    schema = {
        "paths": {
            "/x": {
                "post": {
                    "requestBody": {"content": {"multipart/form-data": {}}},
                    "responses": {"200": {"content": {"application/json": {}}}},
                }
            }
        }
    }
    assert media_types(schema) == ["POST /x: multipart/form-data", "POST /x: application/json"]


# --- Aplicación a este repositorio ----------------------------------------------------------------------------------------------


def test_t213_the_application_has_no_work_that_outlives_the_response() -> None:
    offenders = {
        rel(path): hits for path in python_files(SRC) if (hits := background_work(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_t214_no_route_takes_or_serves_files() -> None:
    offenders = {
        rel(path): hits
        for path in python_files(SRC / "api")
        if (hits := file_upload_in_routes(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_t214_the_openapi_declares_neither_multipart_nor_binary_bodies() -> None:
    schema = create_app(
        Settings(
            _env_file=None,
            supabase_url="http://127.0.0.1:54321",
            database_url="postgresql://x@127.0.0.1:5/x",
            agents_base_url=None,
        )
    ).openapi()  # type: ignore[call-arg]
    declared = media_types(schema)
    assert declared, "el esquema debería declarar tipos de contenido"
    assert [d for d in declared if any(m in d for m in FORBIDDEN_MEDIA_TYPES)] == []
    # Y lo que la API sí acepta como cuerpo es JSON; la única respuesta binaria es el PDF de una factura.
    assert [d for d in declared if "application/pdf" in d] == ALLOWED_BINARY_RESPONSES
    assert {d.split(": ")[1] for d in declared} <= {"application/json", "application/problem+json", "application/pdf"}
    requests = [
        m
        for operations in schema["paths"].values()
        for operation in operations.values()
        for m in operation.get("requestBody", {}).get("content", {})
    ]
    assert set(requests) == {"application/json"}  # ninguna ruta recibe un archivo


def test_the_committed_openapi_has_the_same_property() -> None:
    committed = json.loads((SRC.parents[1] / "openapi.json").read_text(encoding="utf-8"))
    assert [d for d in media_types(committed) if any(m in d for m in FORBIDDEN_MEDIA_TYPES)] == []
