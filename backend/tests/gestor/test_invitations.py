"""AC-01, AC-02, AC-03 · Invitar a un gestor por la API: el correo, la ausencia de enumeración de cuentas y los límites (SPEC-W-010 hito 1).

La aplicación es la real, con la base real; el correo va a `MemoryEmailSender`, así que se ve exactamente lo que se enviaría.
"""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.agents.support import captured_logs, rendered
from tests.gestor.conftest import Api
from tests.support import Pool

KEYS = {"id", "gestor_email", "status", "invited_at", "expires_at", "email_sent"}


def test_inviting_creates_a_pending_invitation_and_sends_the_email(api: Api) -> None:
    response = api.invite(api.cast.alicia, f"  {api.cast.gina.email.upper()} ")
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == KEYS
    assert (body["gestor_email"], body["status"], body["email_sent"]) == (api.cast.gina.email, "pending", True)
    assert body["expires_at"] > body["invited_at"]
    assert response.headers["cache-control"] == "private, no-store"

    [message] = api.sender.sent
    assert message.to == api.cast.gina.email and message.kind == "gestor_invitation"
    assert message.text.startswith("Alicia te ha invitado")
    assert "http://localhost:3000" in message.text
    for forbidden in ("€", "IBAN", "token", "?"):
        assert forbidden not in message.text, forbidden  # sin datos financieros ni enlaces con token (D-01)


def test_the_invitation_is_listed_as_pending(api: Api) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    rows = api.accesses(api.cast.alicia).json()
    assert [(r["id"], r["gestor_email"], r["status"]) for r in rows] == [(link, api.cast.gina.email, "pending")]
    assert set(rows[0]) == {
        "id",
        "gestor_email",
        "status",
        "invited_at",
        "expires_at",
    }  # `email_sent` solo en la respuesta de invitar


def test_the_log_records_the_invitation_without_the_address(api: Api, admin: Connection[DictRow]) -> None:
    link = api.invited(api.cast.alicia, api.cast.gina.email)
    rows = admin.execute(
        "select action, entity_id, metadata from public.activity_log where owner_id = %s and category = 'access'",
        (api.cast.alicia.id,),
    ).fetchall()
    assert rows == [{"action": "gestor_access.invited", "entity_id": link, "metadata": {}}]


# --- AC-02 · sin enumeración de cuentas --------------------------------------------------------------------------------------------


def shape(response: Any) -> tuple[int, tuple[str, ...], str, bool]:
    body = response.json()
    return response.status_code, tuple(sorted(body)), body["status"], body["email_sent"]


def test_the_answer_and_the_email_are_equivalent_for_a_gestor_a_usuario_the_admin_and_nobody(api: Api) -> None:
    targets = [
        api.cast.gina.email,  # un gestor
        api.cast.beto.email,  # un autónomo
        api.cast.adan.email,  # el administrador
        f"nadie.{api.cast.alicia.email}",  # nadie
    ]
    responses = [api.invite(api.cast.alicia, email) for email in targets]
    assert len({shape(r) for r in responses}) == 1
    assert all(r.status_code == 201 for r in responses)
    assert len(api.sender.sent) == 4
    assert [m.to for m in api.sender.sent] == targets
    assert len({(m.subject, m.text, m.kind) for m in api.sender.sent}) == 1  # el mismo correo, solo cambia la dirección


def test_the_errors_do_not_depend_on_whether_the_account_exists_either(api: Api) -> None:
    for email in (api.cast.gina.email, f"nadie.{api.cast.alicia.email}"):
        api.invited(api.cast.alicia, email)
        again = api.invite(api.cast.alicia, email)
        assert (again.status_code, again.json()["code"]) == (409, "invitation_already_open")


# --- AC-03 · límites ------------------------------------------------------------------------------------------------------------------


def test_nobody_invites_themselves(api: Api) -> None:
    response = api.invite(api.cast.alicia, api.cast.alicia.email.upper())
    assert (response.status_code, response.json()["code"]) == (422, "cannot_invite_self")
    assert api.sender.sent == []


def test_an_open_invitation_is_not_repeated_and_nothing_is_sent_the_second_time(api: Api) -> None:
    api.invited(api.cast.alicia, api.cast.gina.email)
    response = api.invite(api.cast.alicia, api.cast.gina.email)
    assert (response.status_code, response.json()["code"]) == (409, "invitation_already_open")
    assert len(api.sender.sent) == 1


@pytest.mark.parametrize("bad", ["", "   ", "sin-arroba", "a@b", "a b@c.de", "@c.de"])
def test_a_malformed_email_is_invalid_email_and_the_answer_does_not_repeat_it(api: Api, bad: str) -> None:
    response = api.invite(api.cast.alicia, bad)
    body = response.json()
    assert (response.status_code, body["code"]) == (422, "invalid_email")
    assert bad.strip() not in response.text or bad.strip() == ""
    assert api.sender.sent == []


def test_a_body_that_is_not_an_object_with_an_email_is_a_validation_error(api: Api) -> None:
    for payload in ({}, {"email": 5}, {"email": None}, {"email": "x" * 321}):
        response = api.request("POST", "/api/gestor/accesos", api.cast.alicia, json=payload)
        assert (response.status_code, response.json()["code"]) == (422, "validation_error"), payload
    assert api.request("POST", "/api/gestor/accesos", api.cast.alicia, content=b"no es json").status_code == 422


def test_the_sixth_open_invitation_is_refused_and_a_revocation_frees_one(api: Api) -> None:
    ids = [api.invited(api.cast.alicia, f"g{n}.{api.cast.alicia.email}") for n in range(5)]
    refused = api.invite(api.cast.alicia, f"g9.{api.cast.alicia.email}")
    assert (refused.status_code, refused.json()["code"]) == (422, "too_many_open_invitations")
    assert len(api.sender.sent) == 5
    assert api.revoke(api.cast.alicia, ids[0]).status_code == 204
    assert api.invite(api.cast.alicia, f"g9.{api.cast.alicia.email}").status_code == 201


def test_the_limit_is_per_person(api: Api) -> None:
    for n in range(5):
        api.invited(api.cast.alicia, f"g{n}.{api.cast.alicia.email}")
    assert api.invite(api.cast.beto, f"g0.{api.cast.alicia.email}").status_code == 201


# --- Correo que falla -------------------------------------------------------------------------------------------------------------------


def test_if_the_email_cannot_be_delivered_the_invitation_stays_pending_and_says_so(api: Api) -> None:
    api.sender.fail = True
    with captured_logs("cuadre") as records:
        response = api.invite(api.cast.alicia, api.cast.gina.email)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["status"], body["email_sent"]) == ("pending", False)
    assert [r["status"] for r in api.accesses(api.cast.alicia).json()] == ["pending"]
    seen = rendered(records)
    assert "gestor_invitation_email_failed" in seen
    assert (
        api.cast.gina.email not in seen and "Alicia" not in seen
    )  # el aviso lleva el id de la invitación, no la dirección ni el nombre


# --- Listado ------------------------------------------------------------------------------------------------------------------------------


def test_an_expired_pending_invitation_shows_as_expired_and_can_be_invited_again(
    api: Api, admin: Connection[DictRow]
) -> None:
    old = api.invited(api.cast.alicia, api.cast.gina.email)
    admin.execute("update public.gestor_access set expires_at = now() - interval '1 day' where id = %s", (old,))
    assert [r["status"] for r in api.accesses(api.cast.alicia).json()] == ["expired"]
    fresh = api.invited(api.cast.alicia, api.cast.gina.email)
    rows = {r["id"]: r["status"] for r in api.accesses(api.cast.alicia).json()}
    assert rows == {fresh: "pending", old: "revoked"}  # la caducada se retiró al volver a invitar


def test_each_person_lists_only_their_own_accesses_most_recent_first(api: Api) -> None:
    first = api.invited(api.cast.alicia, f"a.{api.cast.alicia.email}")
    second = api.invited(api.cast.alicia, f"b.{api.cast.alicia.email}")
    api.invited(api.cast.beto, f"c.{api.cast.alicia.email}")
    assert [r["id"] for r in api.accesses(api.cast.alicia).json()] == [second, first]
    assert len(api.accesses(api.cast.beto).json()) == 1


def test_the_list_never_exceeds_one_hundred_rows(app_pool: Pool, api: Api, admin: Connection[DictRow]) -> None:
    admin.execute(
        "insert into public.gestor_access (owner_id, gestor_email, status, revoked_at) "
        "select %s, 'x' || n || '@example.test', 'revoked', now() from generate_series(1, 120) n",
        (api.cast.alicia.id,),
    )
    assert len(api.accesses(api.cast.alicia).json()) == 100
