"""D-05, RES-04 · VIES simulado: el estado se calcula, sin red; `unchecked` queda reservado para la consulta real."""

from typing import get_args

from cuadre.clients import ClientValues, FakeViesChecker, RawClient, ViesChecker, ViesStatus, validate_client
from tests.validators import corpus


class Recording:
    """Un `ViesChecker` que anota lo que se le pregunta y devuelve lo que se le diga."""

    def __init__(self, answer: ViesStatus = "valid_simulated") -> None:
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def check(self, country: str, tax_id: str) -> ViesStatus:
        self.calls.append((country, tax_id))
        return self.answer


def values(**fields: object) -> ClientValues:
    result = validate_client(RawClient(**fields))
    assert result.values is not None, result.errors
    return result.values


def german(**over: object) -> dict[str, object]:
    return {"name": "Kreativ GmbH", "kind": "business", "country": "DE", "tax_id": corpus.EU_VAT["DE"], **over}


def test_the_status_type_has_the_three_values() -> None:
    assert set(get_args(ViesStatus)) == {"valid_simulated", "unchecked", "not_applicable"}


def test_the_fake_is_deterministic_and_always_valid() -> None:
    fake = FakeViesChecker()
    assert [fake.check("DE", corpus.EU_VAT["DE"]) for _ in range(3)] == ["valid_simulated"] * 3
    assert isinstance(fake, object) and callable(getattr(fake, "check", None))


def test_an_eu_company_with_a_valid_vat_number_is_valid_simulated() -> None:
    assert values(**german()).vies_status == "valid_simulated"


def test_it_never_produces_unchecked() -> None:
    for code, vat in corpus.EU_VAT.items():
        country = "GR" if code == "EL" else code
        assert values(name="X Y", kind="business", country=country, tax_id=vat).vies_status == "valid_simulated"
    assert values(name="X Y", kind="individual", country="DE").vies_status == "not_applicable"


def test_an_eu_individual_is_not_applicable_even_with_an_identifier() -> None:
    assert values(**german(kind="individual", tax_id=None)).vies_status == "not_applicable"
    assert values(**german(kind="individual")).vies_status == "not_applicable"


def test_a_national_company_is_not_applicable() -> None:
    assert (
        values(name="Estudio Norte", kind="business", country="ES", tax_id="B00000018").vies_status == "not_applicable"
    )


def test_a_company_outside_the_eu_is_not_applicable() -> None:
    assert (
        values(name="Taller Zocalo", kind="business", country="MX", tax_id="MXTEST0001").vies_status == "not_applicable"
    )
    assert values(name="Acme Ltd", kind="business", country="GB", tax_id="GB123456789").vies_status == "not_applicable"


def test_the_checker_is_only_asked_for_an_eu_company_and_gets_the_country_and_the_key() -> None:
    spy = Recording()
    validate_client(RawClient("Kreativ GmbH", "business", "de", corpus.EU_VAT["DE"].lower()), spy)
    validate_client(RawClient("Estudio Norte", "business", "ES", "B00000018"), spy)
    validate_client(RawClient("Sam Rivers", "individual", "DE"), spy)
    validate_client(RawClient("Taller", "business", "MX", "X1"), spy)
    validate_client(RawClient("Hellas AE", "business", "GR", corpus.EU_VAT["EL"]), spy)
    assert spy.calls == [("DE", corpus.EU_VAT["DE"]), ("GR", corpus.EU_VAT["EL"])]


def test_the_checker_is_not_asked_when_the_client_is_invalid() -> None:
    spy = Recording()
    validate_client(RawClient("", "business", "DE", corpus.EU_VAT["DE"]), spy)
    validate_client(RawClient("Kreativ GmbH", "business", "DE", "DE1"), spy)
    assert spy.calls == []


def test_a_real_checker_could_say_unchecked_and_the_rule_would_pass_it_on() -> None:
    """La costura para la consulta real (Should): la regla no decide el estado, lo decide quien lo comprueba."""
    assert values_with(Recording("unchecked")).vies_status == "unchecked"


def values_with(checker: ViesChecker) -> ClientValues:
    result = validate_client(RawClient(**german()), checker)
    assert result.values is not None
    return result.values
