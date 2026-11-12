"""AC-18 (parte del hito 1) y contrato · Ni el correo del gestor ni el nombre del autónomo en los registros; las seis operaciones en el contrato (SPEC-W-010)."""

from fastapi import FastAPI

from cuadre.notifications import ConsoleEmailSender
from tests.agents.support import captured_logs, rendered
from tests.gestor.conftest import Api

OPERATIONS = {
    "invite_gestor_access": ("post", "/api/gestor/accesos", {"201", "401", "403", "409", "422"}),
    "list_gestor_accesses": ("get", "/api/gestor/accesos", {"200", "401", "403"}),
    "revoke_gestor_access": ("post", "/api/gestor/accesos/{access_id}/revocar", {"204", "401", "403", "404", "409"}),
    "list_gestor_invitations": ("get", "/api/gestor/invitaciones", {"200", "401", "403"}),
    "accept_gestor_invitation": (
        "post",
        "/api/gestor/invitaciones/{access_id}/aceptar",
        {"204", "401", "403", "404", "409"},
    ),
    "decline_gestor_invitation": (
        "post",
        "/api/gestor/invitaciones/{access_id}/rechazar",
        {"204", "401", "403", "404", "409"},
    ),
}


def test_no_log_line_carries_an_address_or_a_name_through_the_whole_flow(api: Api) -> None:
    api.app.state.email_sender = ConsoleEmailSender()  # lo que usa el desarrollo: la consola
    secret_address = f"reservada.{api.cast.gina.email}"
    with captured_logs("cuadre") as records:
        link = api.invited(api.cast.alicia, secret_address)
        api.invite(api.cast.alicia, secret_address)  # 409
        api.invite(api.cast.alicia, "no-es-un-correo")  # 422
        api.accesses(api.cast.alicia)
        api.invitations(api.cast.gina)
        api.accept(api.cast.gina, link)
        api.revoke(api.cast.alicia, link)
    seen = rendered(records)
    assert "r***@" in seen  # la consola enmascara la dirección y deja el tipo de mensaje
    for secret in (secret_address, secret_address.split("@")[0], "reservada.", "Alicia", "Gestor", "no-es-un-correo"):
        assert secret not in seen, secret
    assert "te ha invitado" not in seen  # ni el asunto ni el cuerpo


def test_the_failed_email_warning_carries_the_invitation_id_only(api: Api) -> None:
    api.sender.fail = True
    with captured_logs("cuadre") as records:
        link = api.invited(api.cast.alicia, f"reservada.{api.cast.gina.email}")
    failures = [r for r in records if r.getMessage() == "gestor_invitation_email_failed"]
    assert len(failures) == 1 and failures[0].access_id == link  # type: ignore[attr-defined]
    assert "reservada" not in rendered(records) and "Alicia" not in rendered(records)


def test_every_operation_is_in_the_contract_with_its_responses(app: FastAPI) -> None:
    schema = app.openapi()
    for operation_id, (method, path, responses) in OPERATIONS.items():
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert set(operation["responses"]) >= responses, operation_id
    invite = schema["paths"]["/api/gestor/accesos"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]
    assert invite["$ref"].endswith("/InvitedAccess")
    props = schema["components"]["schemas"]["InvitedAccess"]["properties"]
    assert set(props) == {"id", "gestor_email", "status", "invited_at", "expires_at", "email_sent"}
    assert set(schema["components"]["schemas"]["GestorAccess"]["properties"]["status"]["enum"]) == {
        "pending",
        "active",
        "revoked",
        "declined",
        "expired",
    }
