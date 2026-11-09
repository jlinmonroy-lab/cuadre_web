"""D-05, RES-04 · La API usa el verificador de VIES de `app.state` (simulado por defecto) y solo le pregunta por lo que debe."""

from cuadre.clients import FakeViesChecker, ViesStatus
from tests.clients.conftest import AMERICAN, GERMAN, MEXICAN, VAT_DE, Api


class Spy:
    def __init__(self, answer: ViesStatus = "valid_simulated") -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def check(self, country: str, tax_id: str) -> ViesStatus:
        self.calls.append((country, tax_id))
        return self.answer


def test_the_app_ships_the_simulated_checker(api: Api) -> None:
    assert isinstance(api.app.state.vies_checker, FakeViesChecker)


def test_the_checker_is_only_asked_about_an_eu_company_with_a_valid_vat_number(api: Api) -> None:
    spy = Spy()
    api.app.state.vies_checker = spy
    api.made(api.cast.alicia, **{**GERMAN, "tax_id": VAT_DE.lower()})
    api.made(api.cast.alicia)  # nacional
    api.made(api.cast.alicia, **MEXICAN)
    api.made(api.cast.alicia, **AMERICAN)
    api.made(api.cast.alicia, name="Persona UE", kind="individual", country="DE", tax_id=None)
    assert api.create(api.cast.alicia, **{**GERMAN, "name": "Roto", "tax_id": "DE1"}).status_code == 422
    assert spy.calls == [("DE", VAT_DE)]


def test_what_the_checker_says_is_what_is_saved(api: Api) -> None:
    """La costura para la consulta real (Should): la regla no decide el estado, lo decide quien lo comprueba."""
    api.app.state.vies_checker = Spy("unchecked")
    body = api.made(api.cast.alicia, **GERMAN)
    assert body["vies_status"] == "unchecked"
    assert api.get(api.cast.alicia, body["id"]).json()["vies_status"] == "unchecked"


def test_an_update_asks_the_checker_again(api: Api) -> None:
    spy = Spy()
    api.app.state.vies_checker = spy
    created = api.made(api.cast.alicia, **GERMAN)
    api.update(api.cast.alicia, created["id"], **GERMAN)
    assert len(spy.calls) == 2


def test_archiving_does_not_ask_the_checker(api: Api) -> None:
    spy = Spy()
    api.app.state.vies_checker = spy
    created = api.made(api.cast.alicia, **GERMAN)
    api.archive(api.cast.alicia, created["id"], True)
    api.archive(api.cast.alicia, created["id"], False)
    assert len(spy.calls) == 1
