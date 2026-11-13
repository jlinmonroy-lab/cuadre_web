"""El registro de jobs y sus comprobaciones previas (SPEC-W-012 §5.4): lo que la ruta interna y la CLI exigen antes de abrir nada."""

import os
from datetime import UTC, datetime

import pytest

from cuadre.closing import YearMonth
from cuadre.jobs.runner import JOB_NAMES, JOBS, MONTHLY_JOBS, JobConfigurationError, UnknownJob, run_named_job
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


def call(name: str, **over: object):  # noqa: ANN202
    args = {"settings": settings(), "app_pool": None, "sender": MemoryEmailSender(), "now": NOW, **over}
    return run_named_job(name, **args)  # type: ignore[arg-type]


def test_both_jobs_are_registered_and_only_the_monthly_one_takes_a_month() -> None:
    assert JOB_NAMES == ("reminders", "monthly_closing") == tuple(JOBS)
    assert {"monthly_closing"} == MONTHLY_JOBS


def test_an_unknown_job_is_refused_before_opening_anything() -> None:
    with pytest.raises(UnknownJob):
        call("nada")


def test_a_time_without_a_zone_is_refused_for_both_jobs() -> None:
    for name in JOB_NAMES:
        with pytest.raises(ValueError, match="zona horaria"):
            call(name, now=datetime(2027, 1, 20, 8, 0))


def test_a_month_is_refused_for_a_job_that_does_not_work_by_months() -> None:
    with pytest.raises(ValueError, match="meses"):
        call("reminders", month=YearMonth(2026, 9))


def test_without_the_service_database_neither_job_can_run() -> None:
    for name in JOB_NAMES:
        with pytest.raises(JobConfigurationError):
            call(name, settings=settings(database_service_url=None))
