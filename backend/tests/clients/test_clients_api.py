"""AC-01 a AC-11 · Los clientes por la API: un cliente de cada ámbito, validación todo o nada, NIF único entre activos, editar, archivar (SPEC-W-006 §5.3)."""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.clients.conftest import AMERICAN, BODY, GERMAN, MEXICAN, NIF, VAT_DE, VAT_FR, Api
from tests.validators import corpus

ZERO_WIDTH = chr(0x200B)


def fields_of(response: Any) -> list[tuple[str, str]]:
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "invalid_client"
    return [(f["field"], f["message"]) for f in body["fields"]]


# --- Un cliente de cada ámbito (AC-01 a AC-03) -------------------------------------------------------------------------------------


def test_ac01_a_national_company_is_created_normalized(api: Api) -> None:
    response = api.create(
        api.cast.alicia, name="  Estudio Norte S.L.  ", country=" es ", tax_id=" b-0000 0018 ", address="  Calle 1  "
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["name"], body["kind"], body["country"], body["scope"], body["tax_id"], body["address"]) == (
        "Estudio Norte S.L.",
        "business",
        "ES",
        "national",
        NIF,
        "Calle 1",
    )
    assert (body["vies_status"], body["archived"]) == ("not_applicable", False)
    assert api.get(api.cast.alicia, body["id"]).json() == body


def test_ac02_a_german_company_with_a_vat_number_is_valid_simulated(api: Api) -> None:
    body = api.made(api.cast.alicia, **{**GERMAN, "country": "de", "tax_id": VAT_DE.lower()})
    assert (body["scope"], body["country"], body["tax_id"], body["vies_status"]) == (
        "eu",
        "DE",
        VAT_DE,
        "valid_simulated",
    )


def test_ac03_companies_and_individuals_outside_the_eu(api: Api) -> None:
    mexican = api.made(api.cast.alicia, **{**MEXICAN, "tax_id": "mx-test 0001"})
    assert (mexican["scope"], mexican["tax_id"], mexican["vies_status"]) == ("non_eu", "MXTEST0001", "not_applicable")
    american = api.made(api.cast.alicia, **AMERICAN)
    assert (american["scope"], american["tax_id"]) == ("non_eu", None)
    assert fields_of(api.create(api.cast.alicia, **{**MEXICAN, "tax_id": None})) == [
        ("tax_id", "Escribe el identificador fiscal del cliente.")
    ]


@pytest.mark.parametrize("prefix", ["GR", "EL", "gr", "el"])
def test_greece_accepts_both_prefixes_and_stores_el(api: Api, prefix: str) -> None:
    digits = corpus.EU_VAT["EL"][2:]
    body = api.made(api.cast.alicia, name="Hellas AE", country="GR", tax_id=prefix + digits, address=None)
    assert (body["scope"], body["tax_id"], body["vies_status"]) == ("eu", "EL" + digits, "valid_simulated")


@pytest.mark.parametrize(
    ("country", "scope"),
    [
        ("ES", "national"),
        ("DE", "eu"),
        ("FR", "eu"),
        ("GB", "non_eu"),
        ("CH", "non_eu"),
        ("MX", "non_eu"),
        ("US", "non_eu"),
        ("AD", "non_eu"),
    ],
)
def test_ac07_the_scope_is_deduced_from_the_country(api: Api, country: str, scope: str) -> None:
    body = api.made(api.cast.alicia, name="Persona", kind="individual", country=country, tax_id=None)
    assert body["scope"] == scope


@pytest.mark.parametrize("country", ["XI", "XK", "EU", "ZZ", "UK", "ESP", "E", "", "ß"])
def test_ac07_a_country_that_is_not_in_the_catalogue_is_the_country_error(api: Api, country: str) -> None:
    assert fields_of(api.create(api.cast.alicia, kind="individual", country=country, tax_id=None)) == [
        ("country", "Elige un país de la lista.")
    ]


# --- Errores (AC-04 a AC-06) --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"tax_id": "12345678A"}, "El NIF no es válido: revisa el dígito o la letra de control."),
        ({"tax_id": VAT_DE}, "Escribe un NIF, NIE o CIF español."),
        ({"country": "DE", "tax_id": VAT_FR}, "El NIF-IVA no es válido o no corresponde al país elegido."),
        ({"country": "DE", "tax_id": NIF}, "El NIF-IVA no es válido o no corresponde al país elegido."),
        (
            {"country": "MX", "tax_id": "ab#12"},
            "El identificador fiscal solo lleva letras, números y guiones, hasta 32 caracteres.",
        ),
    ],
)
def test_ac04_a_wrong_tax_id_is_one_error_on_its_field_and_nothing_is_saved(
    api: Api, over: dict[str, Any], message: str
) -> None:
    response = api.create(api.cast.alicia, **over)
    assert fields_of(response) == [("tax_id", message)]
    assert str(over["tax_id"]) not in response.text
    assert api.listing(api.cast.alicia, archived=True) == []


def test_ac05_every_error_at_once_in_screen_order(api: Api) -> None:
    response = api.create(
        api.cast.alicia, name="", kind="desconocido", country="zz", tax_id="no importa", address="x" * 301
    )
    assert fields_of(response) == [
        ("name", "Escribe el nombre o la razón social del cliente."),
        ("kind", "Elige si es una empresa o profesional, o un particular."),
        ("country", "Elige un país de la lista."),
        ("address", "El domicilio admite hasta 300 caracteres."),
    ]
    assert api.listing(api.cast.alicia, archived=True) == []


def test_an_empty_body_reports_the_three_required_fields(api: Api) -> None:
    response = api.request("POST", "/api/clients", api.cast.alicia, json={})
    assert [f for f, _ in fields_of(response)] == ["name", "kind", "country"]


def test_ac06_an_individual_without_a_tax_id_is_fine_and_with_a_bad_one_is_not(api: Api) -> None:
    api.made(api.cast.alicia, name="Persona Uno", kind="individual", tax_id=None)
    assert fields_of(api.create(api.cast.alicia, name="Persona Dos", kind="individual", tax_id="12345678A")) == [
        ("tax_id", "El NIF no es válido: revisa el dígito o la letra de control.")
    ]


@pytest.mark.parametrize("bad", [chr(10), chr(0), ZERO_WIDTH, chr(0x202E)])
def test_a_control_character_in_the_name_is_an_error_on_the_name(api: Api, bad: str) -> None:
    assert fields_of(api.create(api.cast.alicia, name=f"Estudio{bad}Norte")) == [
        ("name", "No puede llevar saltos de línea ni caracteres de control.")
    ]


@pytest.mark.parametrize(
    "extra", [{"scope": "eu"}, {"vies_status": "valid_simulated"}, {"id": "x"}, {"archived": True}, {"owner_id": "x"}]
)
def test_the_scope_and_the_vies_status_cannot_be_sent(api: Api, extra: dict[str, Any]) -> None:
    response = api.request("POST", "/api/clients", api.cast.alicia, json={**BODY, **extra})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


@pytest.mark.parametrize("value", [5, True, ["x"], {"a": 1}])
def test_a_field_that_is_not_text_is_a_shape_error(api: Api, value: object) -> None:
    response = api.request("POST", "/api/clients", api.cast.alicia, json={**BODY, "name": value})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


# --- Un NIF por persona (AC-08) -----------------------------------------------------------------------------------------------------


def test_ac08_a_tax_id_is_unique_among_the_active_clients_of_a_person(api: Api) -> None:
    first = api.made(api.cast.alicia)
    duplicate = api.create(api.cast.alicia, name="Otro S.L.")
    assert (duplicate.status_code, duplicate.json()["code"]) == (409, "client_tax_id_taken")
    assert NIF not in duplicate.text
    assert api.archive(api.cast.alicia, first["id"], True).status_code == 200
    assert api.create(api.cast.alicia, name="Otro S.L.").status_code == 201  # los archivados no cuentan
    assert api.create(api.cast.beto).status_code == 201  # otra persona, bien


def test_individuals_without_an_identifier_can_repeat(api: Api) -> None:
    api.made(api.cast.alicia, name="Persona Uno", kind="individual", tax_id=None)
    api.made(api.cast.alicia, name="Persona Dos", kind="individual", tax_id=None)
    assert len(api.listing(api.cast.alicia)) == 2


def test_the_same_identifier_written_differently_is_still_the_same(api: Api) -> None:
    api.made(api.cast.alicia)
    assert api.create(api.cast.alicia, name="Otro S.L.", tax_id="b 0000-0018").status_code == 409
    assert api.create(api.cast.alicia, name="Otro S.L.", tax_id="ES" + NIF.lower()).status_code == 409


# --- Editar (AC-09) -----------------------------------------------------------------------------------------------------------------


def test_ac09_updating_the_country_changes_the_scope_and_the_vies_status(api: Api) -> None:
    created = api.made(api.cast.alicia)
    response = api.update(api.cast.alicia, created["id"], country="FR", tax_id=VAT_FR, name="Estudio Nord SARL")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["scope"], body["vies_status"], body["tax_id"], body["name"]) == (
        created["id"],
        "eu",
        "valid_simulated",
        VAT_FR,
        "Estudio Nord SARL",
    )
    assert body["updated_at"] > created["updated_at"]
    back = api.update(api.cast.alicia, created["id"], country="ES", tax_id=NIF).json()
    assert (back["scope"], back["vies_status"]) == ("national", "not_applicable")


def test_updating_with_its_own_tax_id_is_fine_and_with_another_clients_is_not(api: Api) -> None:
    mine = api.made(api.cast.alicia)
    other = api.made(api.cast.alicia, name="Otro S.L.", tax_id="B00000026")
    assert api.update(api.cast.alicia, mine["id"], name="Renombrado S.L.").status_code == 200
    taken = api.update(api.cast.alicia, other["id"], name="Otro S.L.", tax_id=NIF)
    assert (taken.status_code, taken.json()["code"]) == (409, "client_tax_id_taken")
    assert api.get(api.cast.alicia, other["id"]).json()["tax_id"] == "B00000026"


def test_the_response_of_an_update_or_an_archive_is_that_client_and_not_another(api: Api) -> None:
    """Hueco que encontró la mutación S25: con un solo cliente, devolver «el primero» pasaba por el editado."""
    first = api.made(api.cast.alicia, name="Alfa S.L.", tax_id="B00000018")
    second = api.made(api.cast.alicia, name="Zeta S.L.", tax_id="B00000026")
    edited = api.update(api.cast.alicia, second["id"], name="Zeta Nueva S.L.", tax_id="B00000026").json()
    assert (edited["id"], edited["name"]) == (second["id"], "Zeta Nueva S.L.")
    archived = api.archive(api.cast.alicia, second["id"], True).json()
    assert (archived["id"], archived["archived"]) == (second["id"], True)
    assert api.get(api.cast.alicia, first["id"]).json()["name"] == "Alfa S.L."


def test_an_update_with_errors_changes_nothing(api: Api) -> None:
    created = api.made(api.cast.alicia)
    assert fields_of(api.update(api.cast.alicia, created["id"], name="", country="zz")) == [
        ("name", "Escribe el nombre o la razón social del cliente."),
        ("country", "Elige un país de la lista."),
    ]
    assert api.get(api.cast.alicia, created["id"]).json() == created


def test_an_archived_client_cannot_be_edited(api: Api) -> None:
    created = api.made(api.cast.alicia)
    api.archive(api.cast.alicia, created["id"], True)
    response = api.update(api.cast.alicia, created["id"], name="Nuevo S.L.")
    assert (response.status_code, response.json()["code"]) == (409, "client_archived")
    assert api.get(api.cast.alicia, created["id"]).json()["name"] == created["name"]


def test_editing_a_missing_or_anothers_client_is_a_404(api: Api) -> None:
    mine = api.made(api.cast.alicia)
    for target in (mine["id"], "00000000-0000-4000-8000-000000000000"):
        response = api.update(api.cast.beto, target, name="Hackeado S.L.")
        assert (response.status_code, response.json()["code"]) == (404, "client_not_found")
    assert api.get(api.cast.alicia, mine["id"]).json()["name"] == mine["name"]


# --- Archivar y reactivar (AC-10) -----------------------------------------------------------------------------------------------------


def test_ac10_archiving_and_reactivating(api: Api) -> None:
    created = api.made(api.cast.alicia)
    archived = api.archive(api.cast.alicia, created["id"], True)
    assert archived.status_code == 200 and archived.json()["archived"] is True
    assert api.listing(api.cast.alicia) == []
    assert [c["id"] for c in api.listing(api.cast.alicia, archived=True)] == [created["id"]]
    reactivated = api.archive(api.cast.alicia, created["id"], False)
    assert reactivated.status_code == 200 and reactivated.json()["archived"] is False
    assert [c["id"] for c in api.listing(api.cast.alicia)] == [created["id"]]


def test_archiving_twice_and_reactivating_an_active_one_are_fine(api: Api) -> None:
    created = api.made(api.cast.alicia)
    assert api.archive(api.cast.alicia, created["id"], False).status_code == 200
    assert api.archive(api.cast.alicia, created["id"], True).status_code == 200
    assert api.archive(api.cast.alicia, created["id"], True).status_code == 200


def test_reactivating_a_client_whose_tax_id_an_active_one_uses_is_a_409(api: Api) -> None:
    old = api.made(api.cast.alicia)
    api.archive(api.cast.alicia, old["id"], True)
    api.made(api.cast.alicia, name="Nuevo S.L.")
    response = api.archive(api.cast.alicia, old["id"], False)
    assert (response.status_code, response.json()["code"]) == (409, "client_tax_id_taken")
    assert api.get(api.cast.alicia, old["id"]).json()["archived"] is True


@pytest.mark.parametrize("value", ["yes", "true", "1", 1, 0, None, [], {}])
def test_archived_must_be_a_real_boolean(api: Api, value: object) -> None:
    created = api.made(api.cast.alicia)
    response = api.archive(api.cast.alicia, created["id"], value)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
    assert api.get(api.cast.alicia, created["id"]).json()["archived"] is False


def test_there_is_no_way_to_delete_a_client(api: Api) -> None:
    created = api.made(api.cast.alicia)
    assert api.request("DELETE", f"/api/clients/{created['id']}", api.cast.alicia).status_code == 405
    assert api.get(api.cast.alicia, created["id"]).status_code == 200


def test_a_missing_client_is_a_404_and_a_bad_id_is_a_shape_error(api: Api) -> None:
    missing = api.get(api.cast.alicia, "00000000-0000-4000-8000-000000000000")
    assert (missing.status_code, missing.json()["code"]) == (404, "client_not_found")
    bad = api.get(api.cast.alicia, "no-es-un-uuid")
    assert bad.status_code == 422 and bad.json()["code"] == "validation_error"
    assert (
        api.archive(api.cast.alicia, "00000000-0000-4000-8000-000000000000", True).json()["code"] == "client_not_found"
    )


# --- Una lectura no escribe (AC-11) -----------------------------------------------------------------------------------------------


def test_ac11_reading_never_writes(api: Api, admin: Connection[DictRow]) -> None:
    created = api.made(api.cast.alicia)
    before = admin.execute(
        "select id, updated_at, archived_at from public.clients where owner_id = %s", (api.cast.alicia.id,)
    ).fetchall()
    api.listing(api.cast.alicia)
    api.listing(api.cast.alicia, archived=True)
    api.get(api.cast.alicia, created["id"])
    after = admin.execute(
        "select id, updated_at, archived_at from public.clients where owner_id = %s", (api.cast.alicia.id,)
    ).fetchall()
    assert before == after and len(before) == 1


def test_every_client_has_the_documented_shape(api: Api) -> None:
    body = api.made(api.cast.alicia)
    assert set(body) == {
        "id",
        "name",
        "kind",
        "country",
        "scope",
        "tax_id",
        "address",
        "vies_status",
        "archived",
        "created_at",
        "updated_at",
    }
