"""AC-06 y AC-07 · Quién recibe el recordatorio y los valores por defecto (SPEC-W-014 D-01, D-04). Python puro."""

import pytest

from cuadre.jobs.reminders import DEFAULT_ENABLED, DEFAULT_LEAD_DAYS, effective_settings, is_recipient

OK = {"role": "usuario", "status": "active", "enabled": True, "email": "alicia@example.test"}


def test_an_active_user_with_reminders_on_receives() -> None:
    assert is_recipient(**OK) is True  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "change",
    [
        {"role": "gestor"},
        {"role": "admin"},
        {"status": "suspended"},
        {"enabled": False},
        {"email": ""},
        {"email": "   "},
        {"email": None},
    ],
)
def test_everyone_else_does_not(change: dict[str, object]) -> None:
    assert is_recipient(**{**OK, **change}) is False  # type: ignore[arg-type]


def test_without_a_row_the_defaults_apply() -> None:
    assert effective_settings(None) == (DEFAULT_ENABLED, DEFAULT_LEAD_DAYS) == (True, 10)


def test_a_row_overrides_the_defaults() -> None:
    assert effective_settings({"enabled": False, "lead_days": 3}) == (False, 3)


def test_a_row_with_an_impossible_lead_is_refused() -> None:
    with pytest.raises(ValueError, match="entre 1 y 30"):
        effective_settings({"enabled": True, "lead_days": 0})
