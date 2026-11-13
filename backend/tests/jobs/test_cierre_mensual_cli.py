"""`python -m cuadre.cli run-job monthly_closing` y `close-month` (SPEC-W-012 §5.4, D-07, AC-15)."""

import os

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre import cli
from cuadre.config import Settings
from tests.agents.support import make_settings
from tests.support import Cast

NOW = "2026-12-05T08:00:00+00:00"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    built = make_settings(
        database_url=os.environ["DATABASE_URL"],
        database_service_url=os.environ["DATABASE_SERVICE_URL"],
        supabase_url=os.environ["SUPABASE_URL"],
    )
    monkeypatch.setattr(cli, "Settings", lambda: built)
    return built


def count(admin: Connection[DictRow], cast: Cast) -> int:
    found = admin.execute(
        "select count(*) as n from public.monthly_closings where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert found is not None
    return found["n"]


def test_it_closes_and_prints_only_counters(
    settings: Settings, admin: Connection[DictRow], cast: Cast, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["run-job", "monthly_closing", "--now", NOW, "--user", str(cast.alicia.id)]) == 0
    out = capsys.readouterr().out
    assert out.strip() == "Listo: 1 cerrados, 0 reabiertos, 0 sin cambios, 0 fallidos."
    assert cast.alicia.email not in out and count(admin, cast) == 1

    assert cli.main(["run-job", "monthly_closing", "--now", NOW, "--user", str(cast.alicia.id)]) == 0
    assert capsys.readouterr().out.strip() == "Listo: 0 cerrados, 0 reabiertos, 1 sin cambios, 0 fallidos."
    assert count(admin, cast) == 1


def test_a_single_month_can_be_asked_for(
    settings: Settings, admin: Connection[DictRow], cast: Cast, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["run-job", "monthly_closing", "--now", NOW, "--user", str(cast.alicia.id), "--month", "2026-11"])
    assert (
        code == 0 and capsys.readouterr().out.strip() == "Listo: 1 cerrados, 0 reabiertos, 0 sin cambios, 0 fallidos."
    )
    assert admin.execute(
        "select month from public.monthly_closings where owner_id = %s", (cast.alicia.id,)
    ).fetchall() == [{"month": 11}]


def test_close_month_is_a_shortcut_for_the_same_thing(
    settings: Settings, cast: Cast, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["close-month", "--month", "2026-11", "--now", NOW, "--user", str(cast.alicia.id)]) == 0
    assert capsys.readouterr().out.strip() == "Listo: 1 cerrados, 0 reabiertos, 0 sin cambios, 0 fallidos."
    assert cli.main(["close-month", "--month", "2026-11", "--now", NOW, "--user", str(cast.alicia.id)]) == 0
    assert capsys.readouterr().out.strip() == "Listo: 0 cerrados, 0 reabiertos, 1 sin cambios, 0 fallidos."


def test_the_reminders_keep_their_own_summary(
    settings: Settings, capsys: pytest.CaptureFixture[str], cast: Cast
) -> None:
    assert cli.main(["run-job", "reminders", "--now", "2026-05-15T08:00:00+00:00", "--user", str(cast.alicia.id)]) == 0
    assert capsys.readouterr().out.strip() == "Listo: 0 enviados, 1 omitidos, 0 fallidos."


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["run-job", "monthly_closing", "--month", "2026-9"], "AAAA-MM"),
        (["run-job", "monthly_closing", "--month", "septiembre"], "AAAA-MM"),
        (["run-job", "reminders", "--month", "2026-09"], "solo vale"),
        (["run-job", "monthly_closing", "--now", NOW, "--month", "2026-12"], "todavía no ha terminado"),
        (["run-job", "monthly_closing", "--now", NOW, "--month", "2027-05"], "todavía no ha terminado"),
        (["run-job", "monthly_closing", "--now", NOW, "--month", "2026-13"], "no existe"),
        (["run-job", "monthly_closing", "--now", NOW, "--month", "1999-12"], "no existe"),
        (["run-job", "monthly_closing", "--now", "2026-12-05T08:00:00"], "zona horaria"),
        (["run-job", "monthly_closing", "--user", "no-es-un-uuid"], "uuid"),
        (["close-month", "--month", "2026-9"], "AAAA-MM"),
    ],
)
def test_bad_arguments_exit_with_one_and_no_traceback(
    settings: Settings,
    admin: Connection[DictRow],
    cast: Cast,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    message: str,
) -> None:
    assert cli.main(args) == 1
    err = capsys.readouterr().err
    assert message in err and "Traceback" not in err
    assert count(admin, cast) == 0
