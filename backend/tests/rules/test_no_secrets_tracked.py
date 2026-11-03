"""RES-07, T-03 · Ningún secreto, `.env` ni clave privada entra en git. Solo datos sintéticos."""

import re
import shutil
import subprocess

import pytest

from tests.rules.paths import REPO

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está disponible")

FORBIDDEN_FILES = (".env", ".env.local", "frontend/.env.local", "supabase/signing_keys.json")
PATTERNS = {
    "JWT": re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    "clave secreta de Supabase": re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    "clave privada": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "clave de AWS": re.compile(r"AKIA[0-9A-Z]{16}"),
    "clave tipo sk-": re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
}
SENSITIVE_NAME = re.compile(r"(KEY|SECRET|PASSWORD|TOKEN)", re.IGNORECASE)
MAX_BYTES = 1_000_000


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout
    return [name for name in out.decode("utf-8").split("\0") if name]


def scan(text: str) -> list[str]:
    return [label for label, pattern in PATTERNS.items() if pattern.search(text)]


def test_the_scanner_detects_secrets() -> None:
    """Las muestras se construyen en tiempo de ejecución a partir de fragmentos: un literal con forma de secreto en este archivo
    sería detectado por el propio test una vez versionado (y por cualquier escáner externo)."""
    samples = {
        "clave secreta de Supabase": "sb_" + "secret_" + "x" * 30,
        "clave privada": "-----BEGIN " + "EC PRIVATE KEY-----",
        "JWT": ".".join(["ey" + "J" + "a" * 20, "ey" + "J" + "b" * 20, "c" * 20]),
        "clave de AWS": "AK" + "IA" + "A" * 16,
        "clave tipo sk-": "sk" + "-" + "a" * 40,
    }
    assert set(samples) == set(PATTERNS), "cada patrón tiene su muestra"
    for label, sample in samples.items():
        assert label in scan(f"valor={sample}"), f"no se detecta: {label}"
    assert scan("DATABASE_URL=postgresql://cuadre_app:<password>@127.0.0.1/db  # sb_secret_… (elipsis)") == []


def test_no_forbidden_file_is_tracked() -> None:
    tracked = set(tracked_files())
    assert [f for f in FORBIDDEN_FILES if f in tracked] == []


def test_no_tracked_text_file_contains_a_secret() -> None:
    offenders = {}
    for name in tracked_files():
        path = REPO / name
        if not path.is_file() or path.stat().st_size > MAX_BYTES or name.endswith("package-lock.json"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if hits := scan(text):
            offenders[name] = hits
    assert offenders == {}


def test_the_env_template_only_has_placeholders_for_sensitive_values() -> None:
    bad = []
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.split("  #")[0].strip()
        if SENSITIVE_NAME.search(name) and value and not (value.startswith("<") and value.endswith(">")):
            bad.append(name)
    assert bad == [], f"valores reales en .env.example: {bad}"
