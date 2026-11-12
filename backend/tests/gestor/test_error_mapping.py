"""Los errores con código estable de las funciones `app.*` se traducen a problem+json (SPEC-W-010 §5.3), uno por uno."""

from types import SimpleNamespace
from typing import Any

import pytest

from cuadre.gestor.repository import translate_db_error


def error(sqlstate: str, message: str | None = None) -> Any:
    return SimpleNamespace(sqlstate=sqlstate, diag=SimpleNamespace(message_primary=message))


@pytest.mark.parametrize(
    ("code", "status", "problem"),
    [
        ("invalid_email", 422, "invalid_email"),
        ("cannot_invite_self", 422, "cannot_invite_self"),
        ("gestor_access_already_open", 409, "invitation_already_open"),
        ("too_many_open_invitations", 422, "too_many_open_invitations"),
        ("gestor_access_not_found", 404, "gestor_access_not_found"),
        ("not_the_owner", 404, "gestor_access_not_found"),  # quien no es el dueño no averigua que la invitación existe
        ("gestor_access_not_open", 409, "gestor_access_not_open"),
        ("gestor_access_not_pending", 409, "gestor_access_not_pending"),
        ("gestor_access_expired", 409, "gestor_access_expired"),
    ],
)
def test_every_stable_code_has_its_problem(code: str, status: int, problem: str) -> None:
    translated = translate_db_error(error("P0001", code))
    assert translated is not None and (translated.status, translated.code) == (status, problem)


def test_an_insufficient_privilege_is_a_403_and_what_is_not_known_is_not_translated() -> None:
    forbidden = translate_db_error(error("42501"))
    assert forbidden is not None and (forbidden.status, forbidden.code) == (403, "forbidden")
    assert translate_db_error(error("P0001", "algo_desconocido")) is None
    assert translate_db_error(error("P0001", None)) is None
    assert translate_db_error(error("23505", "x")) is None
