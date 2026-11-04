"""En el CI un test omitido es un fallo.

Varios tests se omiten si falta una clave de la pila local (`TEST_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) o el pooler. En local
es cómodo; en el CI convertiría la puerta NFR-06 en un falso verde: «0 failed» con la mitad de las pruebas sin correr. Este plugin se carga
desde `conftest.py` y, si existe la variable `CI` (GitHub Actions la define), termina la sesión con código 1 cuando algo se omitió.
"""

import os

import pytest


def _is_ci() -> bool:
    return os.environ.get("CI", "").lower() not in ("", "0", "false")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _is_ci():
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = reporter.stats.get("skipped", []) if reporter is not None else []
    if not skipped:
        return
    reporter.write_sep("!", f"CI: {len(skipped)} test(s) omitido(s); en el CI no se permite omitir", red=True)
    for report in skipped:
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        reporter.write_line(f"  {report.nodeid}: {reason}")
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
