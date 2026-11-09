# ruff: noqa: F811 - los fixtures importados (`api`, `app`, `storage`) sustituyen a los del conftest de este paquete
"""AC-18 · El NIF que se guarda por `PUT /api/profile` es el que usan los gastos: deducibilidad de simplificadas y tickets, y `recipient_mismatch`.

Usa el montaje de documentos (agente simulado y Storage en memoria), que sustituye aquí al de `conftest.py` de este paquete.
"""

from typing import Any

from tests.documents.conftest import Api, api, app, storage  # noqa: F401 - fixtures de otro conftest
from tests.expenses.support import read, save
from tests.profile.conftest import ADDRESS, NAME, NIF


def set_profile(api: Api, person: Any, tax_id: str | None) -> None:
    response = api.request(
        "PUT", "/api/profile", person, json={"legal_name": NAME, "tax_id": tax_id, "fiscal_address": ADDRESS}
    )
    assert response.status_code == 200, response.text


def validation(api: Api, person: Any, document_id: Any) -> dict[str, Any]:
    body = api.get(person, document_id).json()["validation"]
    assert body is not None
    result: dict[str, Any] = body
    return result


def warnings(validation: dict[str, Any]) -> list[str]:
    return [w["code"] for w in validation["warnings"]]


def test_ac18_a_simplified_ticket_is_deductible_with_the_profile_nif_and_not_without_it(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia, "ticket_simplified")
    save(api, alicia, document_id, recipient_tax_id=NIF)

    assert validation(api, alicia, document_id)["preview"]["deductible_vat"] is False  # perfil vacío
    set_profile(api, alicia, NIF)
    assert validation(api, alicia, document_id)["preview"]["deductible_vat"] is True
    set_profile(api, alicia, "01230956L")
    other = validation(api, alicia, document_id)
    assert other["preview"]["deductible_vat"] is False
    assert warnings(other) == ["recipient_mismatch"]


def test_ac18_a_full_invoice_warns_only_when_the_recipient_is_another_nif(api: Api) -> None:
    alicia = api.cast.alicia
    document_id = read(api, alicia)
    save(api, alicia, document_id, recipient_tax_id=NIF)

    set_profile(api, alicia, NIF)
    assert warnings(validation(api, alicia, document_id)) == []
    set_profile(api, alicia, "01230956L")
    assert warnings(validation(api, alicia, document_id)) == ["recipient_mismatch"]
