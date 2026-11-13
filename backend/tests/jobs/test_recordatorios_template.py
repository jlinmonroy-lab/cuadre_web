"""AC-01, AC-10 (formato) y AC-11 · El correo del recordatorio (SPEC-W-014 §5.1, ADR-0008). Python puro."""

import inspect
from datetime import date

import pytest

from cuadre.notifications import QUARTER_REMINDER_KIND, EmailMessage, MemoryEmailSender, quarter_reminder
from cuadre.notifications import templates as templates_module

TO = "alicia@example.test"


def build(**over: object) -> EmailMessage:
    base: dict[str, object] = {
        "to": TO,
        "name": "Alicia",
        "year": 2026,
        "quarter": 4,
        "deadline": date(2027, 1, 30),
        "days_left": 10,
        "modelo_303": (123456, "a_ingresar"),
        "modelo_130": (-21200, "a_ingresar"),
        "pending_documents": 4,
        "app_url": "https://app.example.test/",
    }
    return quarter_reminder(**{**base, **over})  # type: ignore[arg-type]


def test_the_story_email() -> None:
    message = build()
    assert message.to == TO and message.kind == QUARTER_REMINDER_KIND == "quarter_reminder"
    assert message.subject == "Plazo del 4T 2026 (modelos 303 y 130): 30 de enero"
    text = message.text
    assert text.startswith("Hola, Alicia:")
    assert "4T 2026 termina el 30 de enero de 2027" in text
    assert "Quedan 10 días para presentar." in text
    assert "Modelo 303: a ingresar, 1.234,56 €." in text
    assert "Modelo 130: a ingresar, 212,00 €." in text  # el importe va en positivo; el texto dice el sentido
    assert "Tienes 4 facturas pendientes de revisar." in text
    assert "https://app.example.test/trimestres" in text and "//trimestres" not in text
    assert "orientativas" in text and "AEAT" in text


@pytest.mark.parametrize(
    ("kind", "cents", "expected"),
    [
        ("a_ingresar", 5, "a ingresar, 0,05 €."),
        ("a_compensar", -21200, "a compensar en próximos trimestres, 212,00 €."),
        ("a_cero", 0, "resultado a cero, sin importe a ingresar."),
        ("sin_actividad", 0, "sin actividad en el trimestre."),
    ],
)
def test_every_result_of_the_303(kind: str, cents: int, expected: str) -> None:
    assert f"Modelo 303: {expected}" in build(modelo_303=(cents, kind)).text


@pytest.mark.parametrize(
    ("kind", "cents", "expected"),
    [
        ("a_ingresar", 100000000, "a ingresar, 1.000.000,00 €."),
        ("nada_que_ingresar", -500, "resultado a cero, sin importe a ingresar."),
        ("sin_actividad", 0, "sin actividad en el trimestre."),
    ],
)
def test_every_result_of_the_130(kind: str, cents: int, expected: str) -> None:
    assert f"Modelo 130: {expected}" in build(modelo_130=(cents, kind)).text


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, "El plazo termina hoy."), (1, "Queda 1 día para presentar."), (7, "Quedan 7 días para presentar.")],
)
def test_days_left(days: int, expected: str) -> None:
    assert expected in build(days_left=days).text


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "No tienes facturas pendientes de revisar."),
        (1, "Tienes 1 factura pendiente de revisar."),
        (12, "Tienes 12 facturas pendientes de revisar."),
    ],
)
def test_pending_documents(count: int, expected: str) -> None:
    assert expected in build(pending_documents=count).text


def test_without_a_name_the_greeting_is_plain() -> None:
    assert build(name="  ").text.startswith("Hola:")


def test_the_subject_follows_the_deadline_month() -> None:
    message = build(year=2026, quarter=2, deadline=date(2026, 7, 20), days_left=3)
    assert message.subject == "Plazo del 2T 2026 (modelos 303 y 130): 20 de julio"


def test_nothing_sensitive_is_in_the_message() -> None:
    message = build()
    whole = (message.subject + message.text).lower()
    assert TO not in whole and "iban" not in whole and "nif" not in whole and "token" not in whole


def test_the_template_never_uses_float() -> None:
    source = inspect.getsource(templates_module)
    assert "float(" not in source and "locale" not in source


def test_the_memory_sender_receives_it() -> None:
    sender, message = MemoryEmailSender(), build()
    sender.send(message)
    assert sender.sent == [message]
