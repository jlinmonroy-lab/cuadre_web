"""Valida que contracts/ es coherente consigo mismo.

Uso (con el .venv de la raíz activado):
    python contracts/tools/validate_examples.py

Comprueba:
  1. Cada ejemplo cumple su esquema JSON (lo que verá cuadre-agents) y su modelo Pydantic (lo que verá la web).
  2. Los flujos SSE tienen un final válido y las abstenciones por criterio profesional derivan a alguien.
  3. Cada salida de ejemplo cuadra al céntimo consigo misma (totales, ámbitos, casillas del 303 y del 130).
  4. Cada herramienta MCP tiene su ejemplo y viceversa.
  5. openapi.yaml: versión, operationId únicos y referencias que resuelven.
"""

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError

CONTRACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTRACTS / "python"))

from cuadre_contracts.chat import ChatRequest, ChatStreamFrame  # noqa: E402
from cuadre_contracts.extract import AgentError, ExtractRequest, ExtractResponse  # noqa: E402
from cuadre_contracts.mcp_tools import TOOLS  # noqa: E402

SCHEMAS_DIR = CONTRACTS / "agents-api" / "v1" / "schemas"
EXAMPLES = CONTRACTS / "examples"

problems: list[str] = []
checked = 0


def fail(message: str) -> None:
    problems.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_schema(schema: dict, instance: object, label: str) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in validator.iter_errors(instance):
        where = "/".join(str(p) for p in error.absolute_path) or "$"
        fail(f"{label}: esquema JSON · {where}: {error.message}")


def check_model(model: type[BaseModel], instance: object, label: str) -> None:
    try:
        model.model_validate(instance)
    except ValidationError as exc:
        fail(f"{label}: modelo Pydantic · {exc.errors()[0]['loc']}: {exc.errors()[0]['msg']}")


def check_both(schema_file: str, model: type[BaseModel], instance: object, label: str) -> None:
    global checked
    checked += 1
    check_schema(load_json(SCHEMAS_DIR / schema_file), instance, label)
    check_model(model, instance, label)


def parse_sse(text: str) -> list[dict]:
    frames = []
    for block in text.strip().split("\n\n"):
        event = None
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data_lines.append(line[len("data: ") :])
        frames.append({"event": event, "data": json.loads("\n".join(data_lines))})
    return frames


def check_extract() -> None:
    for path in sorted((EXAMPLES / "extract").iterdir()):
        label = f"examples/extract/{path.name}"
        data = load_json(path)
        if path.name.endswith(".request.json"):
            check_both("extract_request.schema.json", ExtractRequest, data, label)
        elif path.name.endswith(".response.json"):
            check_both("extract_response.schema.json", ExtractResponse, data, label)
        elif path.name.endswith(".error.json"):
            check_both("agent_error.schema.json", AgentError, data, label)
        else:
            fail(f"{label}: nombre sin sufijo .request/.response/.error")


def check_chat() -> None:
    for path in sorted((EXAMPLES / "chat").iterdir()):
        label = f"examples/chat/{path.name}"
        if path.name.endswith(".request.json"):
            check_both("chat_request.schema.json", ChatRequest, load_json(path), label)
        elif path.suffix == ".sse":
            frames = parse_sse(path.read_text(encoding="utf-8"))
            for index, frame in enumerate(frames):
                check_both("chat_stream_frame.schema.json", ChatStreamFrame, frame, f"{label}[{index}]")
            names = [f["event"] for f in frames]
            if names[-1] not in ("done", "error") or any(n in ("done", "error") for n in names[:-1]):
                fail(f"{label}: el flujo debe terminar exactamente con un frame done o error")
            for frame in frames:
                if frame["event"] == "abstention":
                    data = frame["data"]
                    if data["reason"] == "professional_judgment" and not data["referral"]:
                        fail(f"{label}: professional_judgment exige referral")
        else:
            fail(f"{label}: extensión no reconocida")

    # 1.1.0 (SPEC-W-004, P-01): sin herramientas de datos no hay `X-User-Token`. Tiene que existir una petición de ejemplo así y el OpenAPI no
    # puede exigir la cabecera siempre.
    requests = [load_json(p) for p in sorted((EXAMPLES / "chat").glob("*.request.json"))]
    if not any(r.get("mcp_url") is None for r in requests):
        fail("examples/chat: falta una petición con `mcp_url: null` (sin herramientas de datos)")
    doc = yaml.safe_load((CONTRACTS / "agents-api" / "v1" / "openapi.yaml").read_text(encoding="utf-8"))
    parameters = doc["paths"]["/v1/chat"]["post"]["parameters"]
    token = [p for p in parameters if p.get("name") == "X-User-Token"]
    if len(token) != 1 or token[0].get("required") is not False:
        fail("openapi.yaml: `X-User-Token` debe existir y no ser obligatorio siempre (solo con `mcp_url`)")


def sum_items(items: list[dict], key: str) -> int:
    return sum(item[key] for item in items)


def check_resumen(output: dict, label: str, annual: bool) -> None:
    ing = output["ingresos"]
    if ing["total_cents"] != ing["nacional_cents"] + ing["ue_cents"] + ing["fuera_ue_cents"]:
        fail(f"{label}: ingresos.total_cents no suma los tres ámbitos")
    if output["rendimiento_cents"] != ing["total_cents"] - output["gastos_cents"]:
        fail(f"{label}: rendimiento_cents != ingresos - gastos")
    if sum_items(output["por_cliente"], "base_cents") != ing["total_cents"]:
        fail(f"{label}: por_cliente no suma ingresos.total_cents")
    for ambito, key in (("nacional", "nacional_cents"), ("ue", "ue_cents"), ("fuera_ue", "fuera_ue_cents")):
        part = sum(c["base_cents"] for c in output["por_cliente"] if c["ambito"] == ambito)
        if part != ing[key]:
            fail(f"{label}: por_cliente del ámbito {ambito} no suma ingresos.{key}")
    if annual and output["acumulado_anio_cents"] != ing["total_cents"]:
        fail(f"{label}: en el resumen anual el acumulado debe igualar los ingresos")
    if not annual and output["acumulado_anio_cents"] < ing["total_cents"]:
        fail(f"{label}: el acumulado del año no puede ser menor que el mes")


def check_buscar(output: dict, label: str) -> None:
    items = output["items"]
    for item in items:
        expected = item["base_cents"] + item["iva_cents"] - item["retencion_cents"]
        if item["total_cents"] != expected:
            fail(f"{label}: total_cents de {item['numero']} != base + iva - retención")
    if output["truncado"]:
        return
    for tipo, key in (("emitida", "totales_emitidas"), ("gasto", "totales_gastos")):
        rows = [i for i in items if i["tipo"] == tipo]
        totals = output[key]
        if not rows:
            if totals is not None:
                fail(f"{label}: {key} debe ser null si no hay filas de tipo {tipo}")
            continue
        if totals is None or totals["n"] != len(rows):
            fail(f"{label}: {key}.n no coincide con las filas")
            continue
        for field in ("base_cents", "iva_cents", "retencion_cents", "total_cents"):
            if totals[field] != sum_items(rows, field):
                fail(f"{label}: {key}.{field} no suma las filas")


def casillas(output: dict, modelo: str) -> dict[str, int]:
    model = next(m for m in output["modelos"] if m["modelo"] == modelo)
    return {c["casilla"]: c["importe_cents"] for c in model["casillas"]}


def check_borrador(output: dict, label: str) -> None:
    c = casillas(output, "303")
    if c["27"] != sum(c.get(k, 0) for k in ("03", "06", "09")):
        fail(f"{label}: 303 casilla 27 no suma las cuotas devengadas")
    if c["46"] != c["27"] - c["45"]:
        fail(f"{label}: 303 casilla 46 != 27 - 45")
    m303 = next(m for m in output["modelos"] if m["modelo"] == "303")
    if m303["resultado_cents"] != abs(c["46"]) or (m303["resultado_tipo"] == "a_ingresar") != (c["46"] > 0):
        fail(f"{label}: 303 resultado inconsistente con la casilla 46")

    h = casillas(output, "130")
    if h["03"] != h["01"] - h["02"]:
        fail(f"{label}: 130 casilla 03 != 01 - 02")
    if h["04"] != (h["03"] * 20 + 50) // 100:
        fail(f"{label}: 130 casilla 04 != 20 % de la 03 (redondeo medio-arriba)")
    if h["07"] != h["04"] - h["05"] - h["06"]:
        fail(f"{label}: 130 casilla 07 != 04 - 05 - 06")
    m130 = next(m for m in output["modelos"] if m["modelo"] == "130")
    if m130["resultado_cents"] != max(0, h["07"]):
        fail(f"{label}: 130 resultado inconsistente con la casilla 07")


def check_gastos(output: dict, label: str) -> None:
    cats = output["categorias"]
    for cat in cats:
        if cat["total_cents"] != cat["base_cents"] + cat["iva_cents"]:
            fail(f"{label}: {cat['categoria']} total != base + iva")
    total = output["total"]
    if total["n"] != sum_items(cats, "n"):
        fail(f"{label}: total.n no suma las categorías")
    for field in ("base_cents", "iva_cents", "total_cents"):
        if total[field] != sum_items(cats, field):
            fail(f"{label}: total.{field} no suma las categorías")


ARITHMETIC = {
    "buscar_facturas": check_buscar,
    "resumen_mes": lambda o, label: check_resumen(o, label, annual=False),
    "resumen_anio": lambda o, label: check_resumen(o, label, annual=True),
    "borrador_trimestre": check_borrador,
    "gastos_por_categoria": check_gastos,
}


def check_mcp() -> None:
    global checked
    tools_json = load_json(CONTRACTS / "mcp" / "v1" / "tools.json")
    by_name = {t["name"]: t for t in tools_json["tools"]}
    models = {t.name: t for t in TOOLS}
    if set(by_name) != set(models):
        fail("mcp/v1/tools.json no coincide con TOOLS (ejecuta export_schemas.py)")
    files = {p.name.removesuffix(".example.json"): p for p in (EXAMPLES / "mcp").glob("*.example.json")}
    for name in sorted(set(by_name) | set(files)):
        if name not in files:
            fail(f"mcp: la herramienta {name} no tiene ejemplo en examples/mcp/")
            continue
        if name not in by_name:
            fail(f"mcp: examples/mcp/{name}.example.json no corresponde a ninguna herramienta")
            continue
        label = f"examples/mcp/{files[name].name}"
        data = load_json(files[name])
        checked += 1
        if data["tool"] != name:
            fail(f"{label}: el campo tool no coincide con el nombre del archivo")
        check_schema(by_name[name]["inputSchema"], data["input"], f"{label} (input)")
        check_schema(by_name[name]["outputSchema"], data["output"], f"{label} (output)")
        check_model(models[name].input_model, data["input"], f"{label} (input)")
        check_model(models[name].output_model, data["output"], f"{label} (output)")
        ARITHMETIC[name](data["output"], label)


def collect_refs(node: object) -> list[str]:
    refs: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                refs.append(value)
            else:
                refs += collect_refs(value)
    elif isinstance(node, list):
        for value in node:
            refs += collect_refs(value)
    return refs


def check_openapi() -> None:
    path = CONTRACTS / "agents-api" / "v1" / "openapi.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    version = (CONTRACTS / "VERSION").read_text(encoding="utf-8").strip()
    if doc["info"]["version"] != version:
        fail(f"openapi.yaml: info.version {doc['info']['version']} != contracts/VERSION {version}")
    operation_ids = [
        op["operationId"]
        for item in doc["paths"].values()
        for method, op in item.items()
        if method in ("get", "post", "put", "patch", "delete")
    ]
    if len(operation_ids) != len(set(operation_ids)):
        fail("openapi.yaml: operationId repetidos")
    for ref in collect_refs(doc):
        if ref.startswith("#/"):
            node = doc
            for part in ref[2:].split("/"):
                if not isinstance(node, dict) or part not in node:
                    fail(f"openapi.yaml: referencia interna sin resolver {ref}")
                    break
                node = node[part]
        elif not (path.parent / ref.split("#")[0]).exists():
            fail(f"openapi.yaml: referencia a archivo inexistente {ref}")

    changelog = (CONTRACTS / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        fail(f"CHANGELOG.md: falta la entrada ## [{version}]")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    check_extract()
    check_chat()
    check_mcp()
    check_openapi()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print(f"\n{len(problems)} problema(s)", file=sys.stderr)
        return 1
    print(f"OK: {checked} documentos validados contra esquema JSON y modelo Pydantic; aritmética y OpenAPI coherentes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
