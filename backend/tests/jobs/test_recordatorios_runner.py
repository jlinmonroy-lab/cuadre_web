"""El punto de entrada común de los jobs (SPEC-W-014 §5.4): lo que la ruta interna y la CLI comprueban antes de abrir nada."""

import os
from datetime import UTC, datetime

import pytest

from cuadre.jobs.runner import JobConfigurationError, UnknownJob, run_named_job
from cuadre.notifications import MemoryEmailSender
from tests.agents.support import make_settings

NOW = datetime(2027, 1, 20, 8, 0, tzinfo=UTC)


def settings(**over: object):  # noqa: ANN202
    values = {
        "database_url": os.environ["DATABASE_URL"],
        "database_service_url": os.environ["DATABASE_SERVICE_URL"],
        "supabase_url": os.environ["SUPABASE_URL"],
        **over,
    }
    return make_settings(**values)


def test_an_unknown_job_is_refused_before_opening_anything() -> None:
    with pytest.raises(UnknownJob):
        run_named_job("nada", settings=settings(), app_pool=None, sender=MemoryEmailSender(), now=NOW)  # type: ignore[arg-type]


def test_a_time_without_a_zone_is_refused_before_opening_anything() -> None:
    with pytest.raises(ValueError, match="zona horaria"):
        run_named_job(
            "reminders",
            settings=settings(),
            app_pool=None,  # type: ignore[arg-type]
            sender=MemoryEmailSender(),
            now=datetime(2027, 1, 20, 8, 0),
        )


def test_without_the_service_database_it_cannot_run() -> None:
    with pytest.raises(JobConfigurationError):
        run_named_job(
            "reminders",
            settings=settings(database_service_url=None),
            app_pool=None,  # type: ignore[arg-type]
            sender=MemoryEmailSender(),
            now=NOW,
        )
