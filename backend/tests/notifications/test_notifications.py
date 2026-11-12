"""SPEC-W-010 T10-10 · El correo transaccional detrás de `EmailSender` (ADR-0008): consola, memoria, selección por entorno y plantilla de la invitación."""

import pytest

from cuadre.notifications import (
    GESTOR_INVITATION_SUBJECT,
    ConsoleEmailSender,
    EmailConfigurationError,
    EmailDeliveryError,
    EmailMessage,
    MemoryEmailSender,
    UnavailableEmailSender,
    gestor_invitation,
    get_email_sender,
    mask_address,
)
from tests.agents.support import captured_logs, make_settings, rendered

MESSAGE = EmailMessage(
    to="gestora@example.test", subject="Asunto reservado", text="Cuerpo reservado 4242", kind="gestor_invitation"
)


def test_memory_keeps_what_was_sent_in_order() -> None:
    sender = MemoryEmailSender()
    other = EmailMessage(to="otra@example.test", subject="s", text="t", kind="k")
    sender.send(MESSAGE)
    sender.send(other)
    assert sender.sent == [MESSAGE, other]


def test_memory_can_simulate_a_provider_that_is_down_and_keeps_nothing() -> None:
    sender = MemoryEmailSender(fail=True)
    with pytest.raises(EmailDeliveryError) as error:
        sender.send(MESSAGE)
    assert sender.sent == []
    assert "gestora" not in str(error.value) and "example.test" not in str(
        error.value
    )  # el error no lleva la dirección


def test_console_writes_a_masked_recipient_and_the_kind_but_never_the_subject_or_the_body() -> None:
    with captured_logs("cuadre") as records:
        ConsoleEmailSender().send(MESSAGE)
    seen = rendered(records)
    assert "g***@example.test" in seen and "gestor_invitation" in seen
    for secret in ("gestora@", "Asunto reservado", "Cuerpo reservado", "4242"):
        assert secret not in seen


@pytest.mark.parametrize(
    ("address", "masked"),
    [("gestora@example.test", "g***@example.test"), ("a@b.co", "a***@b.co"), ("sin-arroba", "***"), ("", "***")],
)
def test_masking_a_recipient(address: str, masked: str) -> None:
    assert mask_address(address) == masked


def test_console_is_the_default_outside_production() -> None:
    for env in ("local", "staging"):
        assert isinstance(get_email_sender(make_settings(app_env=env)), ConsoleEmailSender)
    assert isinstance(get_email_sender(make_settings(email_provider="  CONSOLE ")), ConsoleEmailSender)
    assert isinstance(
        get_email_sender(make_settings(email_provider="")), ConsoleEmailSender
    )  # vacío = el de por defecto


def test_production_without_a_real_provider_does_not_pretend_to_send() -> None:
    with captured_logs("cuadre") as records:
        sender = get_email_sender(make_settings(app_env="production"))
    assert isinstance(sender, UnavailableEmailSender)  # la API arranca, pero cada envío falla de forma explícita
    assert "email_provider_missing" in rendered(records)
    with pytest.raises(EmailDeliveryError) as error:
        sender.send(MESSAGE)
    assert "gestora" not in str(error.value)


def test_an_unknown_provider_is_a_configuration_error() -> None:
    with pytest.raises(EmailConfigurationError, match="smtp"):
        get_email_sender(make_settings(email_provider="SMTP"))


def test_the_invitation_names_the_inviter_the_app_and_the_validity_and_nothing_else() -> None:
    message = gestor_invitation(to="gestora@example.test", owner_name="  Alicia  ", app_url="http://localhost:3000")
    assert (message.to, message.subject, message.kind) == (
        "gestora@example.test",
        GESTOR_INVITATION_SUBJECT,
        "gestor_invitation",
    )
    assert message.text.startswith("Alicia te ha invitado a dar acceso a su contabilidad en Cuadre.")
    assert "http://localhost:3000" in message.text and "«Cartera»" in message.text and "14 días" in message.text
    for forbidden in ("€", "IBAN", "token", "?", "&", "NIF"):
        assert forbidden not in message.text, forbidden  # sin cifras, sin datos financieros y sin enlaces con token


def test_the_invitation_is_identical_for_every_recipient_except_the_address() -> None:
    a = gestor_invitation(to="uno@example.test", owner_name="Alicia", app_url="http://localhost:3000")
    b = gestor_invitation(to="otro@example.test", owner_name="Alicia", app_url="http://localhost:3000")
    assert (a.subject, a.text, a.kind) == (b.subject, b.text, b.kind) and a.to != b.to


def test_a_nameless_inviter_does_not_leave_a_blank() -> None:
    assert gestor_invitation(to="x@example.test", owner_name="  ", app_url="http://localhost:3000").text.startswith(
        "Una persona te ha invitado"
    )
