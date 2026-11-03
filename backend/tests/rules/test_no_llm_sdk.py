"""T-09, T-17, ADR-0012 · Este repositorio no llama a ninguna API de modelos de lenguaje: ni SDKs ni claves.

Todo lo que necesite IA pasa por `AgentsClient` hacia el servicio de agentes (otro repositorio).
"""

import ast
import json
import re
import tomllib

from tests.rules.paths import REPO, python_files, rel

BANNED = (
    "anthropic",
    "openai",
    "langchain",
    "langgraph",
    "llama-index",
    "llama_index",
    "google-generativeai",
    "google.generativeai",
    "google-genai",
    "mistralai",
    "cohere",
    "ollama",
    "litellm",
    "groq",
    "vertexai",
    "transformers",
    "huggingface-hub",
    "huggingface_hub",
)
SECRET_VARIABLES = re.compile(r"(ANTHROPIC|OPENAI|MISTRAL|COHERE|GROQ|GEMINI|GOOGLE_API)_?[A-Z_]*KEY", re.IGNORECASE)


def is_banned(name: str) -> bool:
    base = re.split(r"[\[<>=!~ ;@]", name.strip(), maxsplit=1)[0].lower().replace("_", "-")
    return any(base == b.replace("_", "-") or base.startswith(b.replace("_", "-") + "-") for b in BANNED)


def test_the_detector() -> None:
    assert is_banned("anthropic>=0.30")
    assert is_banned("openai")
    assert is_banned("langchain-core==1.0")
    assert is_banned("google_generativeai")
    assert not is_banned("pydantic==2.14.2")
    assert not is_banned("PyJWT[crypto]==2.15.1")


def test_python_dependencies_have_no_llm_sdk() -> None:
    declared = []
    for pyproject in (REPO / "backend" / "pyproject.toml", REPO / "contracts" / "python" / "pyproject.toml"):
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
        declared += data.get("dependencies", [])
        for extra in data.get("optional-dependencies", {}).values():
            declared += extra
    declared += [
        line
        for line in (REPO / "contracts" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [d for d in declared if is_banned(d)] == []


def test_node_dependencies_have_no_llm_sdk() -> None:
    offenders = []
    for manifest in (REPO / "package.json", REPO / "frontend" / "package.json"):
        if not manifest.exists():
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            offenders += [f"{rel(manifest)}: {name}" for name in data.get(section, {}) if is_banned(name)]
    assert offenders == []


def test_no_python_module_imports_an_llm_sdk() -> None:
    offenders = []
    for path in python_files(REPO / "backend" / "src", REPO / "contracts" / "python", REPO / "contracts" / "tools"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            offenders += [f"{rel(path)}: import {m}" for m in modules if is_banned(m.split(".")[0]) or is_banned(m)]
    assert offenders == []


def test_the_env_template_has_no_model_api_keys() -> None:
    template = (REPO / ".env.example").read_text(encoding="utf-8")
    assert SECRET_VARIABLES.search(template) is None
