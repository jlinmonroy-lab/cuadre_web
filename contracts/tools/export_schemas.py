"""Genera los esquemas JSON de contracts/ a partir de los modelos Pydantic.

Uso (con el .venv de la raíz activado):
    python contracts/tools/export_schemas.py           # escribe los archivos
    python contracts/tools/export_schemas.py --check   # falla si algo versionado difiere (CI)

Los esquemas generados son lo que copia cuadre-agents. Nunca se editan a mano.
"""

import argparse
import json
import re
import sys
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTRACTS / "python"))

from pydantic import BaseModel  # noqa: E402

from cuadre_contracts.chat import ChatRequest, ChatStreamFrame  # noqa: E402
from cuadre_contracts.extract import AgentError, ExtractedInvoice, ExtractRequest, ExtractResponse  # noqa: E402
from cuadre_contracts.mcp_tools import TOOLS, ToolError  # noqa: E402

DIALECT = "https://json-schema.org/draft/2020-12/schema"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# (ruta relativa a contracts/, modelo, modo). Las peticiones se validan tal como las escribe la web;
# las respuestas, tal como las serializa el receptor (todo campo que siempre se emite es obligatorio).
SCHEMAS: tuple[tuple[str, type[BaseModel], str], ...] = (
    ("agents-api/v1/schemas/extract_request.schema.json", ExtractRequest, "validation"),
    ("agents-api/v1/schemas/extracted_invoice.schema.json", ExtractedInvoice, "serialization"),
    ("agents-api/v1/schemas/extract_response.schema.json", ExtractResponse, "serialization"),
    ("agents-api/v1/schemas/agent_error.schema.json", AgentError, "serialization"),
    ("agents-api/v1/schemas/chat_request.schema.json", ChatRequest, "validation"),
    ("agents-api/v1/schemas/chat_stream_frame.schema.json", ChatStreamFrame, "serialization"),
)


def dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def contract_version() -> str:
    version = (CONTRACTS / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.match(version):
        sys.exit(f"contracts/VERSION no es semver: {version!r}")
    return version


def build_schema(model: type[BaseModel], mode: str, version: str) -> dict:
    schema = model.model_json_schema(mode=mode)  # type: ignore[arg-type]
    return {"$schema": DIALECT, "x-contract-version": version, **schema}


def build_tools(version: str) -> dict:
    tools = []
    for tool in TOOLS:
        tools.append(
            {
                "name": tool.name,
                "title": tool.title,
                "description": tool.description,
                "inputSchema": tool.input_model.model_json_schema(mode="validation"),
                "outputSchema": tool.output_model.model_json_schema(mode="serialization"),
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            }
        )
    return {
        "$schema": DIALECT,
        "contract": "cuadre-mcp-tools",
        "x-contract-version": version,
        "transport": {"type": "streamable-http", "path": "/mcp"},
        "auth": {"scheme": "Bearer", "audience": "cuadre-mcp", "scope": "mcp:read", "max_ttl_seconds": 300},
        "errorSchema": ToolError.model_json_schema(mode="serialization"),
        "tools": tools,
    }


def find_floats(node: object, path: str = "$") -> list[str]:
    """RES-02: ningún contrato admite `float`. En JSON Schema, el tipo `number`."""
    found: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "number":
            found.append(path)
        for key, value in node.items():
            found += find_floats(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += find_floats(value, f"{path}[{index}]")
    return found


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="no escribe: falla si lo versionado difiere")
    args = parser.parse_args()

    version = contract_version()
    outputs = {path: build_schema(model, mode, version) for path, model, mode in SCHEMAS}
    outputs["mcp/v1/tools.json"] = build_tools(version)

    problems: list[str] = []
    for path, data in outputs.items():
        for where in find_floats(data):
            problems.append(f"{path}: tipo number (float) en {where} — viola RES-02")
        target = CONTRACTS / path
        text = dump(data)
        if args.check:
            current = target.read_text(encoding="utf-8").replace("\r\n", "\n") if target.exists() else None
            if current != text:
                problems.append(f"{path}: difiere de lo generado (ejecuta export_schemas.py y revisa el cambio)")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
            print(f"escrito {path}")

    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if args.check:
        print(f"OK: {len(outputs)} esquemas coinciden con los modelos (contrato {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
