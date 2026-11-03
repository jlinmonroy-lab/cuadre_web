"""Rutas y utilidades comunes de las guardas de reglas del proyecto."""

import ast
from collections.abc import Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "backend" / "src" / "cuadre"
MIGRATIONS = REPO / "supabase" / "migrations"


def python_files(*roots: Path) -> Iterator[Path]:
    for root in roots:
        if root.exists():
            yield from (p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts)


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()
