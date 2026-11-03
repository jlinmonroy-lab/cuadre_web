"""AC-15 (parte backend) · `backend/openapi.json` coincide con las rutas. De él sale el cliente TypeScript (ADR-0011)."""

import importlib.util

from tests.rules.paths import REPO


def load_exporter():
    path = REPO / "backend" / "scripts" / "export_openapi.py"
    spec = importlib.util.spec_from_file_location("export_openapi", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_json_matches_the_routes() -> None:
    exporter = load_exporter()
    committed = exporter.OPENAPI_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == exporter.render(), "ejecuta `python backend/scripts/export_openapi.py` y revisa el cambio"


def test_the_exported_schema_is_stable_between_runs() -> None:
    exporter = load_exporter()
    assert exporter.render() == exporter.render()
