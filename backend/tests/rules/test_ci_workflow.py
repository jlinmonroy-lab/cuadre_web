"""SPEC-W-001 §8.4 · El CI no puede aflojarse sin que un test lo note.

El CI no se puede ejecutar sin un repositorio remoto, así que lo que se vigila es su forma: que la puerta RLS (NFR-06) exista tal cual la
define la spec y no pueda saltarse, que los permisos sean mínimos, que las actions de terceros estén fijadas por SHA y que el workflow
ejecute cada comando de la secuencia de §8.2 (deriva spec ↔ CI).
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.rules.paths import REPO, rel

GITHUB = REPO / ".github"
WORKFLOW = GITHUB / "workflows" / "ci.yml"
SPEC = REPO / "docs" / "04-specs" / "SPEC-W-001-base-auth-roles-rls.md"
README = REPO / "README.md"

RLS_COMMAND = "pytest backend/tests/rls -m rls -q"
EXPECTED_JOBS = {
    "python": "Python: estilo y deriva",
    "rls": "RLS (NFR-06)",
    "backend": "Backend: API y reglas",
    "frontend": "Frontend: calidad y build",
    "e2e": "E2E: Playwright",
}
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
PINNED_LINE = re.compile(r"uses:\s*\S+@[0-9a-f]{40}\s+#\s*v\d+(\.\d+)*\s*$")

# Líneas de la secuencia de §8.2 que el CI ejecuta de otra forma (el resto debe aparecer tal cual en el workflow o en sus acciones).
EXECUTED_DIFFERENTLY = {
    r".\.venv\Scripts\Activate.ps1": None,  # setup-python deja el intérprete en el PATH
    "npm --prefix frontend exec -- playwright install chromium firefox webkit": (
        "npm --prefix frontend exec -- playwright install --with-deps chromium firefox webkit"  # además, las librerías del sistema
    ),
}


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def action_files() -> list[Path]:
    return sorted((GITHUB / "actions").glob("*/action.yml"))


def workflow_files() -> list[Path]:
    return sorted((GITHUB / "workflows").glob("*.yml"))


def all_steps() -> list[tuple[str, dict[str, Any]]]:
    """Todos los pasos del workflow y de las acciones compuestas, con el nombre de su origen."""
    steps = [
        (f"{WORKFLOW.name}:{job_id}", step) for job_id, job in load(WORKFLOW)["jobs"].items() for step in job["steps"]
    ]
    for action in action_files():
        steps += [(rel(action), step) for step in load(action)["runs"]["steps"]]
    return steps


def run_text() -> str:
    return "\n".join(step["run"] for _, step in all_steps() if "run" in step)


def triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    """PyYAML (YAML 1.1) lee la clave `on` como el booleano True."""
    return workflow.get("on", workflow.get(True))


def spec_sequence() -> list[str]:
    """Comandos del bloque de código de «8.2 Secuencia» de la spec, sin comentarios ni líneas vacías."""
    text = SPEC.read_text(encoding="utf-8")
    section = text.split("### 8.2 ", 1)[1].split("###", 1)[0]
    block = re.search(r"```powershell\n(.*?)```", section, re.DOTALL)
    assert block, "§8.2 ya no tiene su bloque de comandos"
    commands = []
    for line in block.group(1).splitlines():
        command = re.sub(r"\s+#.*$", "", line.strip())
        if command and not command.startswith("#"):
            commands.append(command)
    return commands


# --- La puerta RLS ---------------------------------------------------------------------------------------------------------------


def test_the_workflow_has_exactly_the_expected_jobs() -> None:
    jobs = load(WORKFLOW)["jobs"]
    assert {job_id: job["name"] for job_id, job in jobs.items()} == EXPECTED_JOBS


def test_the_rls_gate_runs_the_nfr06_suite_and_cannot_be_skipped() -> None:
    job = load(WORKFLOW)["jobs"]["rls"]
    assert job["name"] == "RLS (NFR-06)", "es el nombre que se marca como obligatorio en GitHub (README)"
    assert [s["run"] for s in job["steps"] if "run" in s] == [RLS_COMMAND]
    uses = [step.get("uses", "") for step in job["steps"]]
    assert "./.github/actions/local-stack" in uses, "la RLS solo vale contra la pila real de Supabase (ADR-0010)"
    for holder in (job, *job["steps"]):
        assert "if" not in holder, "la puerta RLS corre siempre"
        assert not holder.get("continue-on-error"), "la puerta RLS no se puede tolerar"


def test_nothing_in_the_ci_can_fail_silently() -> None:
    assert not [origin for origin, step in all_steps() if step.get("continue-on-error")]
    for job_id, job in load(WORKFLOW)["jobs"].items():
        assert not job.get("continue-on-error"), job_id
    conditional = [(origin, step["if"]) for origin, step in all_steps() if "if" in step]
    assert conditional == [(f"{WORKFLOW.name}:e2e", "failure()")], (
        "solo se condiciona la subida del informe de Playwright"
    )


def test_the_gate_is_not_filtered_by_paths_or_branches_of_prs() -> None:
    on = triggers(load(WORKFLOW))
    assert {"push", "pull_request"} <= set(on)
    for event in ("push", "pull_request"):
        config = on[event] or {}
        assert "paths" not in config and "paths-ignore" not in config, (
            f"{event}: un check obligatorio no puede tener filtros de ruta"
        )
    assert "branches" not in (on["pull_request"] or {}), "los PR a cualquier rama pasan la puerta"


# --- Permisos, secretos y cadena de suministro -------------------------------------------------------------------------------------


def test_permissions_are_read_only() -> None:
    workflow = load(WORKFLOW)
    assert workflow["permissions"] == {"contents": "read"}
    assert [job_id for job_id, job in workflow["jobs"].items() if "permissions" in job] == [], (
        "ningún trabajo pide más permisos"
    )


def test_the_ci_uses_no_repository_secrets_and_no_privileged_trigger() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in (*workflow_files(), *action_files()))
    assert "secrets." not in text, "todo sale de la pila efímera; un secreto de repositorio no debe hacer falta"
    assert "pull_request_target" not in text and "workflow_run" not in text
    assert "${{" not in run_text(), (
        "ninguna expresión dentro de `run`: evita la inyección de órdenes desde el contexto de GitHub"
    )


def test_third_party_actions_are_pinned_to_a_commit() -> None:
    unpinned = [
        f"{origin}: {step['uses']}"
        for origin, step in all_steps()
        if "uses" in step and not step["uses"].startswith("./") and not PINNED.match(step["uses"])
    ]
    assert unpinned == [], "fija cada action por el SHA completo del commit, con el tag en un comentario"
    lines = [
        line.strip()
        for path in (*workflow_files(), *action_files())
        for line in path.read_text(encoding="utf-8").splitlines()
        if re.search(r"uses:\s*[^.\s]", line)
    ]
    assert [line for line in lines if not PINNED_LINE.search(line)] == [], (
        "cada SHA lleva su versión en un comentario (# v1.2.3)"
    )


def test_every_job_has_a_timeout_and_every_run_step_declares_its_shell() -> None:
    for job_id, job in load(WORKFLOW)["jobs"].items():
        assert isinstance(job.get("timeout-minutes"), int) and job["timeout-minutes"] <= 60, job_id
    for action in action_files():
        for step in load(action)["runs"]["steps"]:
            assert "run" not in step or step.get("shell") == "bash", (
                f"{rel(action)}: un paso `run` de una acción compuesta exige `shell`"
            )


def test_starting_the_stack_does_not_print_its_keys_to_the_log() -> None:
    """`supabase start` imprime en stdout las claves de la pila; no son secretas, pero un registro no es sitio para ellas."""
    starts = [line.strip() for line in run_text().splitlines() if "supabase start" in line]
    assert starts and all(line.endswith("> /dev/null") for line in starts), starts


# --- Deriva spec ↔ CI ----------------------------------------------------------------------------------------------------------------


def test_the_ci_runs_every_command_of_the_specs_sequence() -> None:
    commands = run_text()
    missing = []
    for command in spec_sequence():
        expected = EXECUTED_DIFFERENTLY.get(command, command)
        if expected is not None and expected not in commands:
            missing.append(command)
    assert missing == [], f"§8.2 pide estos comandos y el workflow no los ejecuta: {missing}"


def test_the_sequence_parser_sees_the_commands_it_should() -> None:
    commands = spec_sequence()
    assert RLS_COMMAND in commands
    assert 'pytest backend/tests -m "not rls" -q' in commands
    assert "npm --prefix frontend run test:e2e" in commands
    assert not [c for c in commands if c.startswith("#") or "  #" in c]


def test_the_readme_documents_every_job_by_its_name() -> None:
    readme = README.read_text(encoding="utf-8")
    missing = [name for name in EXPECTED_JOBS.values() if name not in readme]
    assert missing == [], f"README, «Integración continua»: faltan los trabajos {missing}"


@pytest.mark.parametrize("path", [WORKFLOW, *action_files()], ids=lambda p: p.name if p == WORKFLOW else p.parent.name)
def test_the_ci_files_are_valid_yaml_with_utf8_and_lf(path: Path) -> None:
    raw = path.read_bytes()
    assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert load(path)
