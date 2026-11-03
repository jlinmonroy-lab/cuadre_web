"""Genera `backend/openapi.json` (estable y ordenado) o comprueba que sigue al día.

Uso (con el entorno virtual activado):
    python backend/scripts/export_openapi.py            # escribe backend/openapi.json
    python backend/scripts/export_openapi.py --check    # CI: falla si el archivo versionado difiere de las rutas

De `openapi.json` sale el cliente TypeScript del frontend (`npm run gen:api`, ADR-0011). No se edita a mano.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Exportar no abre conexiones: valores de relleno para poder construir la aplicación en cualquier entorno (también en CI).
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:54321")
os.environ.setdefault("DATABASE_URL", "postgresql://cuadre_app@127.0.0.1:54322/postgres")

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def render() -> str:
    from cuadre.config import Settings
    from cuadre.main import create_app

    schema = create_app(Settings()).openapi()  # type: ignore[call-arg]
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="no escribe: falla si backend/openapi.json difiere")
    args = parser.parse_args()

    text = render()
    if args.check:
        current = OPENAPI_PATH.read_text(encoding="utf-8").replace("\r\n", "\n") if OPENAPI_PATH.exists() else None
        if current != text:
            print(
                "backend/openapi.json no coincide con las rutas. Ejecuta `python backend/scripts/export_openapi.py` y revisa el cambio.",
                file=sys.stderr,
            )
            return 1
        print("OK: backend/openapi.json coincide con las rutas")
        return 0
    OPENAPI_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"escrito {OPENAPI_PATH.relative_to(OPENAPI_PATH.parents[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
