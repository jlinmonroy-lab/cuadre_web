"""`python -m cuadre.cli run-job reminders` (SPEC-W-014 §5.5, D-06)."""

import os

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre import cli
from cuadre.config import Settings
from tests.agents.support import make_settings
from tests.support import Cast

NOW = "2027-01-20T08:00:00+00:00"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    built = make_settings(
        database_url=os.environ["DATABASE_URL"],
        database_service_url=os.environ["DATABASE_SERVICE_URL"],
        supabase_url=os.environ["SUPABASE_URL"],
    )
    monkeypatch.setattr(cli, "Settings", lambda: built)
    return built


def test_it_runs_the_job_and_prints_only_counters(
    settings: Settings, admin: Connection[DictRow], cast: Cast, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["run-job", "reminders", "--now", NOW, "--user", str(cast.alicia.id)])
    out = capsys.readouterr().out
    assert code == 0
    assert out.strip() == "Listo: 1 enviados, 0 omitidos, 0 fallidos."
    assert cast.alicia.email not in out
    row = admin.execute("select status from public.reminder_log where owner_id = %s", (cast.alicia.id,)).fetchone()
    assert row == {"status": "sent"}

    assert cli.main(["run-job", "reminders", "--now", NOW, "--user", str(cast.alicia.id)]) == 0
    assert capsys.readouterr().out.strip() == "Listo: 0 enviados, 1 omitidos, 0 fallidos."


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["run-job", "nada"], "No existe esa tarea"),
        (["run-job", "reminders", "--now", "2027-01-20T08:00:00"], "zona horaria"),
        (["run-job", "reminders", "--now", "ayer"], "ISO-8601"),
        (["run-job", "reminders", "--user", "no-es-un-uuid"], "uuid"),
    ],
)
def test_bad_arguments_exit_with_one(
    settings: Settings, capsys: pytest.CaptureFixture[str], args: list[str], message: str
) -> None:
    assert cli.main(args) == 1
    assert message in capsys.readouterr().err
