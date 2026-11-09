"""AC-14, T6-04, NFR-11 · Ni el nombre, ni el NIF, ni el domicilio de un cliente (datos de un tercero) en los registros ni en los errores."""

from typing import Any

from tests.agents.support import captured_logs, rendered
from tests.clients.conftest import Api

NAME = "Secreto Cliente S.L."
ADDRESS = "Calle Secreta 99, Ciudad Oculta"
TAX = "B00000018"
BAD_TAX = "B00000019"
SECRETS = [NAME, ADDRESS, TAX, BAD_TAX, "Renombrado Secreto", "Calle Reservada 7"]


def test_nothing_about_a_client_reaches_the_logs_or_the_errors(api: Api) -> None:
    alicia, beto, gina = api.cast.alicia, api.cast.beto, api.cast.gina
    errors: list[Any] = []
    with captured_logs("cuadre") as records:
        created = api.create(alicia, name=NAME, address=ADDRESS, tax_id=TAX)
        client_id = created.json()["id"]
        errors += [
            api.create(alicia, name="Otro S.L.", tax_id=BAD_TAX),  # 422
            api.create(alicia, name="Otro Secreto S.L.", tax_id=TAX, address=ADDRESS),  # 409
            api.create(alicia, name="", kind="x", country="zz", address=ADDRESS),  # 422 con varios
            api.update(beto, client_id, name="Renombrado Secreto", address="Calle Reservada 7"),  # 404
            api.get(beto, client_id),  # 404
            api.create(gina, name=NAME, address=ADDRESS, tax_id=TAX),  # 403
            api.client.post("/api/clients", json={"name": NAME}),  # 401
            api.update(
                alicia, client_id, name="Renombrado Secreto", address="Calle Reservada 7", tax_id=BAD_TAX
            ),  # 422
        ]
        api.get(alicia, client_id)
        api.listing(alicia)
        api.update(alicia, client_id, name="Renombrado Secreto", address="Calle Reservada 7")
        api.archive(alicia, client_id, True)
        errors.append(api.update(alicia, client_id, name="Renombrado Secreto"))  # 409 archivado
        api.archive(alicia, client_id, False)
        api.archive(alicia, client_id, "yes")  # 422 de forma

    text = rendered(records)
    for secret in SECRETS:
        assert secret not in text, secret
    assert api.signer.token(alicia) not in text
    for response in errors:
        assert response.status_code >= 400
        for secret in SECRETS:
            assert secret not in response.text, (response.status_code, secret)
