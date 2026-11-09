"""T6-02 · Una fuente por regla: lo que dice `cuadre.clients` y lo que impone la base son lo mismo (SPEC-W-006 §5.2).

Las fronteras salen de las constantes del dominio y se comprueban contra los CHECK: si alguien cambia un número en un sitio y no en el otro,
falla aquí. Es la prueba que dejó anotada B.2 para el hito 2.
"""

from typing import Any, get_args

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.clients import COUNTRIES, EU_COUNTRIES, Kind, Scope, ViesStatus, limits, scope_of
from tests.support import Cast, Person


def insert(admin: Connection[DictRow], person: Person, **fields: Any) -> bool:
    values: dict[str, Any] = {
        "owner_id": person.id,
        "name": "Paridad S.L.",
        "kind": "business",
        "country": "ES",
        "scope": "national",
        **fields,
    }
    try:
        admin.execute(
            f"insert into public.clients ({', '.join(values)}) values ({', '.join(['%s'] * len(values))})",
            tuple(values.values()),
        )
        return True
    except psycopg.errors.CheckViolation:
        return False


def test_the_name_bounds_are_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    low, high = limits.NAME_MIN, limits.NAME_MAX
    assert not insert(admin, cast.alicia, name="a" * (low - 1))
    assert insert(admin, cast.alicia, name="a" * low)
    assert insert(admin, cast.alicia, name="a" * high)
    assert not insert(admin, cast.alicia, name="a" * (high + 1))


def test_the_address_bound_is_the_domains(admin: Connection[DictRow], cast: Cast) -> None:
    assert insert(admin, cast.alicia, address="a" * limits.ADDRESS_MAX)
    assert not insert(admin, cast.alicia, address="a" * (limits.ADDRESS_MAX + 1))


def test_the_tax_id_bound_is_the_domains_free_maximum(admin: Connection[DictRow], cast: Cast) -> None:
    assert insert(admin, cast.alicia, tax_id="a")
    assert insert(admin, cast.alicia, tax_id="b" * limits.TAX_ID_FREE_MAX)
    assert not insert(admin, cast.alicia, tax_id="c" * (limits.TAX_ID_FREE_MAX + 1))
    assert not insert(admin, cast.alicia, tax_id="")


@pytest.mark.parametrize("code", ["ES", "DE", "MX", "ZZ", "AA"])
def test_every_code_the_domain_pattern_accepts_the_database_accepts(
    admin: Connection[DictRow], cast: Cast, code: str
) -> None:
    assert limits.COUNTRY_CODE.fullmatch(code)
    scope = "national" if code == "ES" else "non_eu"
    assert insert(admin, cast.alicia, country=code, scope=scope)


@pytest.mark.parametrize("code", ["", "E", "es", "ESP", "E1", "Es", "E-"])
def test_every_code_the_domain_pattern_rejects_the_database_rejects(
    admin: Connection[DictRow], cast: Cast, code: str
) -> None:
    assert limits.COUNTRY_CODE.fullmatch(code) is None
    assert not insert(admin, cast.alicia, country=code, scope="non_eu")


def test_the_whole_catalogue_is_accepted_by_the_database_with_the_scope_the_domain_deduces(
    admin: Connection[DictRow], cast: Cast
) -> None:
    for code in sorted(COUNTRIES):
        assert insert(admin, cast.alicia, name=f"Pais {code}", country=code, scope=scope_of(code)), code


def test_the_database_agrees_with_the_domain_about_spain_and_only_spain(admin: Connection[DictRow], cast: Cast) -> None:
    """`CHECK ((scope = 'national') = (country = 'ES'))`: el dominio dice `national` para `ES` y para nadie más."""
    assert limits.SPAIN == "ES" and scope_of("ES") == "national"
    for code in sorted(COUNTRIES - {"ES"}):
        assert scope_of(code) != "national"
        assert not insert(admin, cast.alicia, country=code, scope="national"), code
    assert not insert(admin, cast.alicia, country="ES", scope="eu")
    assert not insert(admin, cast.alicia, country="ES", scope="non_eu")


def test_the_eu_membership_is_the_domains_alone(admin: Connection[DictRow], cast: Cast) -> None:
    """D-10: la base no sabe qué países son de la UE; acepta cualquier `eu`/`non_eu` que no sea `ES`."""
    for code in sorted(EU_COUNTRIES - {"ES"}):
        assert insert(admin, cast.alicia, name=f"UE {code}", country=code, scope="eu")
        assert insert(admin, cast.alicia, name=f"No UE {code}", country=code, scope="non_eu")


def labels(admin: Connection[DictRow], enum: str) -> list[str]:
    found = admin.execute(
        "select e.enumlabel::text as label from pg_enum e join pg_type t on t.oid = e.enumtypid "
        "join pg_namespace n on n.oid = t.typnamespace where n.nspname = 'public' and t.typname = %s order by e.enumsortorder",
        (enum,),
    ).fetchall()
    return [r["label"] for r in found]


def test_the_database_enums_are_the_domains_types(admin: Connection[DictRow]) -> None:
    assert labels(admin, "client_kind") == list(limits.KINDS) == list(get_args(Kind))
    assert labels(admin, "client_scope") == list(get_args(Scope))
    assert labels(admin, "client_vies_status") == list(get_args(ViesStatus))


def test_the_database_functions_accept_what_the_domain_produces(admin: Connection[DictRow]) -> None:
    """La forma del identificador y del nombre que entrega `validate_client` cabe en lo que las funciones comprueban."""
    from cuadre.clients import RawClient, validate_client  # noqa: PLC0415

    result = validate_client(RawClient("  Kreativ GmbH  ", "business", "de", "de 446.120-774", " "))
    assert result.values is not None
    assert (result.values.name, result.values.country, result.values.tax_id, result.values.address) == (
        "Kreativ GmbH",
        "DE",
        "DE446120774",
        None,
    )
    assert len(result.values.name) <= limits.NAME_MAX and len(result.values.tax_id or "") <= limits.TAX_ID_FREE_MAX
