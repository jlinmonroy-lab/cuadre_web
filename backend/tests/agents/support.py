"""Ayudas comunes de las pruebas del cliente de agentes: ejemplos del contrato y registros capturados."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cuadre.config import Settings
from cuadre_contracts import ExtractRequest, ExtractResponse
from tests.rules.paths import REPO

EXAMPLES = REPO / "contracts" / "examples" / "extract"
SCHEMAS = REPO / "contracts" / "agents-api" / "v1" / "schemas"

RESPONSE_NAMES = sorted(p.name.removesuffix(".response.json") for p in EXAMPLES.glob("*.response.json"))
API_KEY = "test-agents-key-0123456789"


def example_path(name: str) -> Path:
    return EXAMPLES / name


def example_json(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(example_path(name).read_text(encoding="utf-8"))
    return data


def response_json(name: str) -> dict[str, Any]:
    return example_json(f"{name}.response.json")


def example_request() -> ExtractRequest:
    return ExtractRequest.model_validate_json(example_path("extract.request.json").read_bytes())


def example_response(name: str) -> ExtractResponse:
    return ExtractResponse.model_validate_json(example_path(f"{name}.response.json").read_bytes())


def with_extraction(name: str, **changes: Any) -> dict[str, Any]:
    """El ejemplo `name` con campos de `extraction` sustituidos (para fabricar respuestas malformadas)."""
    data = response_json(name)
    data["extraction"].update(changes)
    return data


@contextmanager
def captured_logs(*names: str) -> Iterator[list[logging.LogRecord]]:
    """Registros de los loggers indicados. `configure_logging` desactiva la propagación de `cuadre`, así que `caplog` no los vería."""
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Collect(level=logging.DEBUG)
    loggers = [logging.getLogger(n) for n in names]
    previous = [lg.level for lg in loggers]
    for lg in loggers:
        lg.addHandler(handler)
        lg.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        for lg, level in zip(loggers, previous, strict=True):
            lg.removeHandler(handler)
            lg.setLevel(level)


def rendered(records: list[logging.LogRecord]) -> str:
    """Todo lo que dicen los registros (mensaje y campos extra), como un solo texto."""
    return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in records)


def make_settings(**overrides: Any) -> Settings:
    """`Settings` aislados del `.env` y del entorno del equipo: todo lo relevante se fija aquí o se pasa."""
    values: dict[str, Any] = {
        "app_env": "local",
        "supabase_url": "http://127.0.0.1:54321",
        "database_url": "postgresql://cuadre_app@127.0.0.1:5/postgres",
        "agents_base_url": None,
        "agents_api_key": None,
        "agents_timeout_seconds": 45,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]
