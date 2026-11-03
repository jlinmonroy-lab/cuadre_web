"""RES-02 · Nunca `float` para importes (SPEC-W-001 T-02, ADR-0006).

Se aplica a todo el código de dominio (`backend/src/cuadre`, `contracts/python`) y a las migraciones. Es deliberadamente estricto:
ni anotaciones, ni llamadas, ni literales con decimales. Para duraciones se usan enteros (milisegundos, nanosegundos).
"""

import ast
import re

from tests.rules.paths import MIGRATIONS, REPO, SRC, parse, python_files, rel

SQL_FLOAT = re.compile(r"\b(real|double\s+precision|float[48]?)\b", re.IGNORECASE)


def float_uses(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id == "float":
            found.append(f"línea {node.lineno}: uso de `float`")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"línea {node.lineno}: literal decimal {node.value!r}")
    return found


def sql_float_uses(sql: str) -> list[str]:
    without_comments = re.sub(r"/\*.*?\*/", "", re.sub(r"--[^\n]*", "", sql), flags=re.DOTALL)
    return [m.group(0) for m in SQL_FLOAT.finditer(without_comments)]


# --- Los detectores detectan ------------------------------------------------------------------------------------------------


def test_the_python_detector_flags_annotations_calls_and_literals() -> None:
    assert float_uses("def f(x: float) -> None: ...")
    assert float_uses("y = float('1.5')")
    assert float_uses("z = 0.5")
    assert float_uses("timeout: int = 5\nd = {'a': 1}") == []


def test_the_sql_detector_flags_float_types_but_not_comments() -> None:
    assert sql_float_uses("create table t (amount double precision);")
    assert sql_float_uses("create table t (a real, b float8, c FLOAT);")
    assert sql_float_uses("-- no usar real ni float\ncreate table t (cents bigint); /* double precision */") == []


# --- Aplicación a este repositorio --------------------------------------------------------------------------------------------


def test_no_float_in_the_application_and_contract_code() -> None:
    offenders = {
        rel(path): hits
        for path in python_files(SRC, REPO / "contracts" / "python")
        if (hits := float_uses(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_no_float_columns_in_the_migrations() -> None:
    files = sorted(MIGRATIONS.glob("*.sql"))
    assert files, "no hay migraciones"
    offenders = {rel(f): hits for f in files if (hits := sql_float_uses(f.read_text(encoding="utf-8")))}
    assert offenders == {}


def test_the_source_files_parse() -> None:
    for path in python_files(SRC):
        parse(path)
