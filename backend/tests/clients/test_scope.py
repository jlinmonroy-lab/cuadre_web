"""D-01, D-02 · El ámbito se deduce del país y el mapeo al vocabulario del MCP está en un solo sitio."""

import pytest

from cuadre.clients import COUNTRIES, EU_COUNTRIES, from_mcp_scope, scope_of, to_mcp_scope


def test_spain_is_national() -> None:
    assert scope_of("ES") == "national"


@pytest.mark.parametrize("code", sorted(EU_COUNTRIES - {"ES"}))
def test_every_other_member_is_eu(code: str) -> None:
    assert scope_of(code) == "eu"


@pytest.mark.parametrize("code", ["GB", "CH", "NO", "MX", "US", "AR", "CO", "BR", "XI", "XK", "ZZ", "AD", "MC"])
def test_the_rest_is_non_eu(code: str) -> None:
    assert scope_of(code) == "non_eu"


def test_the_whole_catalogue_splits_into_1_26_and_222() -> None:
    scopes = [scope_of(code) for code in COUNTRIES]
    assert (scopes.count("national"), scopes.count("eu"), scopes.count("non_eu")) == (1, 26, 222)


def test_the_mcp_names_are_the_ones_of_the_tools() -> None:
    assert (to_mcp_scope("national"), to_mcp_scope("eu"), to_mcp_scope("non_eu")) == ("nacional", "ue", "fuera_ue")


def test_the_mapping_goes_both_ways() -> None:
    for scope in ("national", "eu", "non_eu"):
        assert from_mcp_scope(to_mcp_scope(scope)) == scope  # type: ignore[arg-type]
    for name in ("nacional", "ue", "fuera_ue"):
        assert to_mcp_scope(from_mcp_scope(name)) == name  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["national", "eu", "non_eu", "", "UE", "Nacional", "fuera-ue", None, 3, b"ue", ["ue"]])
def test_an_unknown_mcp_name_is_none(name: object) -> None:
    assert from_mcp_scope(name) is None
