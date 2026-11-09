"""D-01 · El catálogo de países: los 249 códigos ISO 3166-1 alfa-2 asignados y los 27 Estados miembros de la UE (Anexo B.1-B)."""

import pytest

from cuadre.clients import COUNTRIES, EU_COUNTRIES
from cuadre.clients.limits import COUNTRY_CODE
from cuadre.validators.limits import EU_VAT_PREFIXES, PREFIX_ALIASES

# Códigos que ICU nombra pero que NO son ISO asignados (31 en Node y Chromium, 42 en Firefox): no entran en el catálogo.
_NOT_ISO = "AC AN BU CP CQ CS CT DD DG DY EA EU EZ FQ FX HV IC JT MI NH NQ NT PC PU PZ QO QU RH SU TA TP UK UN VD WK XA XB XI XK YD YU ZR ZZ"
NOT_ISO = _NOT_ISO.split()


def test_there_are_249_distinct_assigned_codes() -> None:
    assert len(COUNTRIES) == 249
    assert all(COUNTRY_CODE.fullmatch(code) for code in COUNTRIES)


@pytest.mark.parametrize("code", NOT_ISO)
def test_codes_that_are_not_iso_are_not_in_the_catalogue(code: str) -> None:
    assert code not in COUNTRIES


@pytest.mark.parametrize(
    "code",
    [
        "ES",
        "DE",
        "FR",
        "GR",
        "GB",
        "CH",
        "MX",
        "US",
        "AR",
        "CO",
        "BR",
        "CN",
        "JP",
        "IN",
        "AU",
        "NO",
        "UA",
        "BQ",
        "SS",
        "SX",
    ],
)
def test_well_known_codes_are_in(code: str) -> None:
    assert code in COUNTRIES


def test_the_eu_has_27_members_and_all_are_in_the_catalogue() -> None:
    assert len(EU_COUNTRIES) == 27
    assert EU_COUNTRIES <= COUNTRIES


@pytest.mark.parametrize(
    "code",
    [
        "GB",
        "CH",
        "NO",
        "IS",
        "LI",
        "UA",
        "TR",
        "MX",
        "US",
        "XI",
        "XK",
        "EU",
        "AD",
        "MC",
        "SM",
        "VA",
        "AL",
        "RS",
        "ME",
        "MK",
        "BA",
        "MD",
        "BY",
        "RU",
    ],
)
def test_non_members_are_not_in_the_eu(code: str) -> None:
    assert code not in EU_COUNTRIES


def test_the_eu_matches_the_vat_prefixes_of_the_validators_with_greece_as_el() -> None:
    """Un solo hecho en dos sitios: el prefijo de NIF-IVA de cada miembro (menos España, que tiene NIF) es el de `cuadre.validators`."""
    prefixes = {PREFIX_ALIASES.get(code, code) for code in EU_COUNTRIES - {"ES"}}
    assert prefixes == EU_VAT_PREFIXES
    assert PREFIX_ALIASES == {"GR": "EL"}
