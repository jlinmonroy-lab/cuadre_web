"""SPEC-W-001 §8.4 · En el CI un test omitido hace fallar la sesión (si no, la puerta NFR-06 puede dar un falso verde)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.rules.paths import REPO

SAMPLE = """
import pytest

def test_ok():
    pass

def test_skipped_for_a_missing_key():
    pytest.skip("Falta TEST_SUPABASE_ANON_KEY")
"""


def run_sample(tmp_path: Path, body: str, ci: str | None) -> subprocess.CompletedProcess[str]:
    """Ejecuta pytest en un proceso aparte, sobre un archivo de muestra, con el plugin del CI y la variable `CI` indicada."""
    (tmp_path / "test_sample.py").write_text(body, encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "CI"}
    env["PYTHONPATH"] = str(REPO / "backend")
    if ci is not None:
        env["CI"] = ci
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "tests.ci_gate", "-p", "no:cacheprovider", "-q"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_a_skipped_test_fails_the_session_in_ci(tmp_path: Path) -> None:
    result = run_sample(tmp_path, SAMPLE, ci="true")
    assert result.returncode == 1, result.stdout
    assert "no se permite omitir" in result.stdout
    assert "test_skipped_for_a_missing_key" in result.stdout
    assert "Falta TEST_SUPABASE_ANON_KEY" in result.stdout, "dice por qué se omitió"


@pytest.mark.parametrize("ci", [None, "", "0", "false"])
def test_locally_a_skip_is_still_just_a_skip(tmp_path: Path, ci: str | None) -> None:
    result = run_sample(tmp_path, SAMPLE, ci=ci)
    assert result.returncode == 0, result.stdout


def test_without_skips_the_ci_session_passes(tmp_path: Path) -> None:
    result = run_sample(tmp_path, "def test_ok():\n    pass\n", ci="true")
    assert result.returncode == 0, result.stdout


def test_real_failures_still_fail_in_ci(tmp_path: Path) -> None:
    result = run_sample(tmp_path, "def test_bad():\n    assert 1 == 2\n", ci="true")
    assert result.returncode == 1
