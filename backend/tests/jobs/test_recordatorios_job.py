"""AC-01 a AC-12 · El job de recordatorios con la base de datos real (SPEC-W-014 §5.4, D-03, D-05, D-07).

Las cuentas sembradas y las de otras pruebas también existen en la base: cada prueba limita el job a sus propias cuentas con `only_owners`.
"""

import threading
from datetime import UTC, date, datetime
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.auth import CurrentUser
from cuadre.jobs.reminders_job import ReminderResult, run_reminders
from cuadre.notifications import EmailDeliveryError, EmailMessage, MemoryEmailSender
from cuadre.quarters.service import QuarterService
from tests.agents.support import captured_logs
from tests.clocks import FixedClock
from tests.rls.expenses_support import insert, params
from tests.rls.invoices_support import issue, made, ready
from tests.support import Cast, Person, Pool, call, new_document

APP_URL = "https://app.example.test"
JAN_20 = datetime(2027, 1, 20, 8, 0, tzinfo=UTC)


def at(day: int, month: int = 1, year: int = 2027) -> datetime:
    return datetime(year, month, day, 8, 0, tzinfo=UTC)


def run(
    service_pool: Pool,
    app_pool: Pool,
    sender: Any,
    now: datetime,
    owners: list[Person] | None,
) -> ReminderResult:
    return run_reminders(
        service_pool=service_pool,
        app_pool=app_pool,
        sender=sender,
        now=now,
        app_url=APP_URL,
        only_owners=[p.id for p in owners] if owners is not None else None,
    )


def log_rows(admin: Connection[DictRow], person: Person) -> list[dict[str, Any]]:
    return admin.execute(
        "select period, kind, status from public.reminder_log where owner_id = %s order by period", (person.id,)
    ).fetchall()


def sent_to(sender: MemoryEmailSender, person: Person) -> list[EmailMessage]:
    return [m for m in sender.sent if m.to == person.email]


def user_of(person: Person) -> CurrentUser:
    return CurrentUser(person.id, person.email, "", "usuario", "active", {})


def with_figures(admin: Connection[DictRow], app_pool: Pool, person: Person, *, base: int = 100_000) -> None:
    """Una factura nacional con IVA y un gasto con IVA deducible del cuarto trimestre de 2026."""
    r = ready(admin, person)
    made(
        issue(
            app_pool,
            person,
            r.clients[("national", "business")],
            r.series,
            when=date(2026, 10, 15),
            base=base,
            vat="21",
        )
    )
    insert(admin, params(person, new_document(app_pool, person), date=date(2026, 11, 3)))


# --- Cuándo y a quién ---------------------------------------------------------------------------------------------------------------


def test_the_fourth_quarter_reminder_of_the_story(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sender = MemoryEmailSender()
    result = run(service_pool, app_pool, sender, JAN_20, [cast.alicia])
    assert result == ReminderResult(sent=1, skipped=0, failed=0)
    (message,) = sent_to(sender, cast.alicia)
    assert message.kind == "quarter_reminder"
    assert "30 de enero de 2027" in message.text and "Quedan 10 días" in message.text
    assert "Modelo 303" in message.text and "Modelo 130" in message.text
    assert [(r["period"], r["kind"], r["status"]) for r in log_rows(admin, cast.alicia)] == [
        ("2026-Q4", "quarter_deadline", "sent")
    ]


@pytest.mark.parametrize("when", [at(19), at(31), at(15, 5, 2026)])
def test_outside_the_window_nothing_is_sent(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, when: datetime
) -> None:
    sender = MemoryEmailSender()
    assert run(service_pool, app_pool, sender, when, [cast.alicia]) == ReminderResult(sent=0, skipped=1, failed=0)
    assert sender.sent == [] and log_rows(admin, cast.alicia) == []


def test_the_day_is_the_one_in_madrid(app_pool: Pool, service_pool: Pool, cast: Cast) -> None:
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, datetime(2027, 1, 19, 22, 30, tzinfo=UTC), [cast.alicia])  # 23:30 del 19
    assert sender.sent == []
    run(service_pool, app_pool, sender, datetime(2027, 1, 19, 23, 30, tzinfo=UTC), [cast.alicia])  # 00:30 del 20
    assert len(sent_to(sender, cast.alicia)) == 1


def test_repeating_the_job_never_duplicates(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sender = MemoryEmailSender()
    for day in (20, 20, 21, 30):
        run(service_pool, app_pool, sender, at(day), [cast.alicia])
    assert len(sent_to(sender, cast.alicia)) == 1
    assert len(log_rows(admin, cast.alicia)) == 1


def test_two_simultaneous_runs_send_one_email(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sender = MemoryEmailSender()
    barrier = threading.Barrier(2)
    results: list[ReminderResult] = []

    def worker() -> None:
        barrier.wait()
        results.append(run(service_pool, app_pool, sender, JAN_20, [cast.alicia]))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(sent_to(sender, cast.alicia)) == 1
    assert sorted(r.sent for r in results) == [0, 1]
    assert len(log_rows(admin, cast.alicia)) == 1


def test_a_day_without_a_run_does_not_lose_the_reminder(app_pool: Pool, service_pool: Pool, cast: Cast) -> None:
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, at(22), [cast.alicia])  # el job no corrió el 20 ni el 21
    (message,) = sent_to(sender, cast.alicia)
    assert "Quedan 8 días" in message.text


def test_a_custom_lead_time_is_respected(app_pool: Pool, service_pool: Pool, cast: Cast) -> None:
    assert not call(app_pool, cast.alicia, "set_reminder_settings", True, 5).error
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, at(24), [cast.alicia])
    assert sender.sent == []
    run(service_pool, app_pool, sender, at(25), [cast.alicia])
    assert len(sent_to(sender, cast.alicia)) == 1


def test_a_user_who_turned_reminders_off_gets_nothing(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    assert not call(app_pool, cast.alicia, "set_reminder_settings", False, 10).error
    sender = MemoryEmailSender()
    assert run(service_pool, app_pool, sender, JAN_20, [cast.alicia]).sent == 0
    assert sender.sent == [] and log_rows(admin, cast.alicia) == []


def test_only_active_users_receive_reminders(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.beto.id,))
    sender = MemoryEmailSender()
    everyone = [cast.alicia, cast.beto, cast.gina, cast.gus, cast.adan]
    result = run(service_pool, app_pool, sender, JAN_20, everyone)
    assert result.sent == 1
    assert [m.to for m in sender.sent] == [cast.alicia.email]
    for person in (cast.beto, cast.gina, cast.gus, cast.adan):
        assert log_rows(admin, person) == []


# --- Fallos ---------------------------------------------------------------------------------------------------------------------------


class FailsFor(MemoryEmailSender):
    """Un proveedor que rechaza solo a algunas direcciones."""

    def __init__(self, *refused: str) -> None:
        super().__init__()
        self.refused = set(refused)

    def send(self, message: EmailMessage) -> None:
        if message.to in self.refused:
            raise EmailDeliveryError("rechazado")
        super().send(message)


def test_a_delivery_failure_is_retried_and_does_not_stop_the_others(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    sender = FailsFor(cast.alicia.email)
    result = run(service_pool, app_pool, sender, JAN_20, [cast.alicia, cast.beto])
    assert result == ReminderResult(sent=1, skipped=0, failed=1)
    assert [m.to for m in sender.sent] == [cast.beto.email]
    assert [r["status"] for r in log_rows(admin, cast.alicia)] == ["failed"]
    assert [r["status"] for r in log_rows(admin, cast.beto)] == ["sent"]

    sender.refused.clear()  # vuelve el proveedor y el job corre otra vez dentro de la ventana
    result = run(service_pool, app_pool, sender, at(21), [cast.alicia, cast.beto])
    assert result == ReminderResult(sent=1, skipped=1, failed=0)
    assert sorted(m.to for m in sender.sent) == sorted([cast.alicia.email, cast.beto.email])
    assert [r["status"] for r in log_rows(admin, cast.alicia)] == ["sent"]


def test_an_unexpected_error_marks_the_reservation_failed_and_continues(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cuadre.jobs import reminders_job

    real = reminders_job.quarter_reminder

    def explode(**kwargs: Any) -> EmailMessage:
        if kwargs["to"] == cast.alicia.email:
            raise RuntimeError("datos de Alicia que no deben salir en el registro")
        return real(**kwargs)

    monkeypatch.setattr(reminders_job, "quarter_reminder", explode)
    sender = MemoryEmailSender()
    with captured_logs("cuadre.jobs.reminders") as logs:
        result = run(service_pool, app_pool, sender, JAN_20, [cast.alicia, cast.beto])
    assert result == ReminderResult(sent=1, skipped=0, failed=1)
    assert [r["status"] for r in log_rows(admin, cast.alicia)] == ["failed"]
    assert "datos de Alicia" not in " ".join(str(r.__dict__) for r in logs)


# --- Cifras y contenido --------------------------------------------------------------------------------------------------------------


def test_the_figures_in_the_email_are_the_ones_on_the_screens(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    from cuadre.invoicing.texts import format_euros

    with_figures(admin, app_pool, cast.alicia)
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, JAN_20, [cast.alicia])
    (message,) = sent_to(sender, cast.alicia)

    service = QuarterService(app_pool, FixedClock(JAN_20))
    m303 = service.modelo_303(user_of(cast.alicia), 2026, 4)
    m130 = service.modelo_130(user_of(cast.alicia), 2026, 4)
    assert m303.result_kind != "sin_actividad" and m130.result_kind != "sin_actividad"
    assert format_euros(abs(m303.result_cents)) in message.text
    assert format_euros(abs(m130.result_cents)) in message.text


def test_without_activity_the_email_says_so(app_pool: Pool, service_pool: Pool, cast: Cast) -> None:
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, JAN_20, [cast.alicia])
    (message,) = sent_to(sender, cast.alicia)
    assert message.text.count("sin actividad en el trimestre") == 2


def test_each_email_carries_only_its_owners_figures(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    with_figures(admin, app_pool, cast.alicia, base=100_000)
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, JAN_20, [cast.alicia, cast.beto])
    alicia, beto = sent_to(sender, cast.alicia)[0], sent_to(sender, cast.beto)[0]
    assert "sin actividad" not in alicia.text
    assert beto.text.count("sin actividad en el trimestre") == 2


def test_pending_documents_are_counted(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    from tests.support import advance

    advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), "review")
    sender = MemoryEmailSender()
    run(service_pool, app_pool, sender, JAN_20, [cast.alicia, cast.beto])
    assert "Tienes 1 factura pendiente de revisar." in sent_to(sender, cast.alicia)[0].text
    assert "No tienes facturas pendientes de revisar." in sent_to(sender, cast.beto)[0].text


def test_the_logs_carry_no_address_subject_body_or_amounts(
    app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    with_figures(admin, app_pool, cast.alicia)
    sender = MemoryEmailSender()
    with captured_logs("cuadre.jobs.reminders", "cuadre.quarters", "cuadre.notifications") as logs:
        run(service_pool, app_pool, sender, JAN_20, [cast.alicia])
    (message,) = sent_to(sender, cast.alicia)
    text = " ".join(str(r.__dict__) + r.getMessage() for r in logs)
    assert cast.alicia.email not in text and message.subject not in text and "€" not in text
    processed = [r for r in logs if r.getMessage() == "reminder_processed"]
    assert len(processed) == 1
    assert (processed[0].user_id, processed[0].period, processed[0].result) == (
        str(cast.alicia.id),
        "2026-Q4",
        "sent",
    )
    assert "iban" not in (message.subject + message.text).lower()
