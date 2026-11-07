"""Defensas en profundidad de `normalize_iban` (Anexo B.1): lo que el prefiltro ya impide se prueba sustituyendo la librería."""

import re

import pytest

from cuadre.validators import iban as iban_module
from cuadre.validators import normalize_iban
from tests.validators import corpus_iban as corpus

VALID = corpus.SEED_ALICIA
WEIRD = [" ", "\t", "\n", "\r", "\x0b", "\x0c", "\x85", "\u2028", "\u00a0", "\u200b", "\ufeff"]


def test_a_blank_or_a_line_break_inserted_anywhere_never_leaves_strange_characters() -> None:
    """B.1: 25 posiciones × 11 caracteres. Se acepta (espacio, `U+00A0`) o se rechaza; nunca queda algo que no sea `[A-Z0-9]` en el resultado."""
    dirty = []
    for ch in WEIRD:
        for i in range(len(VALID) + 1):
            result = normalize_iban(VALID[:i] + ch + VALID[i:])
            if result is not None and re.fullmatch(r"[A-Z0-9]+", result) is None:
                dirty.append((repr(ch), i))
    assert dirty == []


def test_only_spaces_and_non_breaking_spaces_are_accepted_inside() -> None:
    accepted = {
        repr(ch): sum(normalize_iban(VALID[:i] + ch + VALID[i:]) is not None for i in range(len(VALID) + 1))
        for ch in WEIRD
    }
    # El espacio y el `U+00A0` valen en cualquier posición (25); un tabulador o un salto de línea, ninguna: el prefiltro no los admite.
    assert accepted[repr(" ")] == len(VALID) + 1
    assert accepted[repr("\u00a0")] == len(VALID) + 1
    assert {k: v for k, v in accepted.items() if k not in (repr(" "), repr("\u00a0"))} == {
        repr(ch): 0 for ch in WEIRD if ch not in (" ", "\u00a0")
    }


@pytest.mark.parametrize(
    "returned",
    ["es3600000000050000000001", "ES36\n00000000050000000001", "ES36", "A" * 35, "ES36 0000 0000 0500 0000 0001", ""],
)
def test_a_result_that_is_not_a_clean_key_is_discarded(monkeypatch: pytest.MonkeyPatch, returned: str) -> None:
    monkeypatch.setattr(iban_module.stdnum_iban, "validate", lambda text: returned)
    assert normalize_iban(VALID) is None


@pytest.mark.parametrize("returned", [None, 3600000000050000000001, b"ES3600000000050000000001"])
def test_a_result_that_is_not_text_is_discarded(monkeypatch: pytest.MonkeyPatch, returned: object) -> None:
    monkeypatch.setattr(iban_module.stdnum_iban, "validate", lambda text: returned)
    assert normalize_iban(VALID) is None


@pytest.mark.parametrize(
    "error", [ValueError, TypeError, KeyError, RuntimeError, OverflowError, UnicodeError, RecursionError]
)
def test_any_exception_from_the_library_means_not_valid(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    def boom(_: str) -> str:
        raise error("fallo de la librería")

    monkeypatch.setattr(iban_module.stdnum_iban, "validate", boom)
    assert normalize_iban(VALID) is None


def test_what_the_library_returns_is_what_gets_stored_when_it_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iban_module.stdnum_iban, "validate", lambda text: "ES3600000000050000000009")
    assert normalize_iban(VALID) == "ES3600000000050000000009"


def test_the_library_is_called_with_the_country_check_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """`check_country=False` aceptaría un IBAN español con la CCC mal (B.1): la llamada no lleva ese argumento ni ninguno que lo apague."""
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def spy(*args: object, **kwargs: object) -> str:
        calls.append((args, kwargs))
        return VALID

    monkeypatch.setattr(iban_module.stdnum_iban, "validate", spy)
    assert normalize_iban(VALID) == VALID
    assert calls == [((VALID,), {})]


def test_the_library_does_not_see_what_the_prefilter_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_: str) -> str:
        raise AssertionError("la librería no debe verlo")

    monkeypatch.setattr(iban_module.stdnum_iban, "validate", boom)
    for raw in ("ES36\n0000", "ＥＳ" + "36", "ES36\u200b0000", "ES36_0000", "x" * 65, ""):
        assert normalize_iban(raw) is None
