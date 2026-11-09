"""§5.3 · El listado: orden alfabético del español (`es-x-icu`, Anexo B.1-C), archivados solo si se piden y cada persona ve lo suyo."""

from tests.clients.conftest import AMERICAN, Api

NAMES = ["Zeta S.L.", "Ñandú S.L.", "nube S.L.", "Álamo S.L.", "abel S.L.", "Éxito S.L.", "Zamora S.L."]


def individual(api: Api, name: str, person: object = None) -> dict[str, object]:
    return api.made(person or api.cast.alicia, **{**AMERICAN, "name": name})  # type: ignore[arg-type]


def test_the_list_is_in_the_alphabetical_order_of_spanish_with_the_enye_after_the_n(api: Api) -> None:
    for name in NAMES:
        individual(api, name)
    assert [c["name"] for c in api.listing(api.cast.alicia)] == [
        "abel S.L.",
        "Álamo S.L.",
        "Éxito S.L.",
        "nube S.L.",
        "Ñandú S.L.",
        "Zamora S.L.",
        "Zeta S.L.",
    ]


def test_the_order_does_not_depend_on_the_creation_order(api: Api) -> None:
    for name in reversed(NAMES):
        individual(api, name)
    assert [c["name"] for c in api.listing(api.cast.alicia)][:3] == ["abel S.L.", "Álamo S.L.", "Éxito S.L."]


def test_archived_clients_only_appear_when_asked_for_and_keep_their_place(api: Api) -> None:
    keep = individual(api, "Beta S.L.")
    gone = individual(api, "Alfa S.L.")
    api.archive(api.cast.alicia, gone["id"], True)
    assert [c["name"] for c in api.listing(api.cast.alicia)] == ["Beta S.L."]
    listed = api.listing(api.cast.alicia, archived=True)
    assert [c["name"] for c in listed] == ["Alfa S.L.", "Beta S.L."]
    assert [c["archived"] for c in listed] == [True, False]
    assert keep["id"] in {c["id"] for c in listed}


def test_include_archived_must_be_a_boolean(api: Api) -> None:
    response = api.request("GET", "/api/clients", api.cast.alicia, params={"include_archived": "quizas"})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_each_person_sees_only_their_own_clients(api: Api) -> None:
    individual(api, "De Alicia S.L.")
    individual(api, "De Beto S.L.", api.cast.beto)
    assert [c["name"] for c in api.listing(api.cast.alicia)] == ["De Alicia S.L."]
    assert [c["name"] for c in api.listing(api.cast.beto, archived=True)] == ["De Beto S.L."]


def test_an_empty_list_is_an_empty_array(api: Api) -> None:
    assert api.listing(api.cast.alicia) == []
