"""El seed de clientes (SPEC-W-006 §5.2, RES-07) es sintético y VÁLIDO: pasa el dominio y guardarlo por él no cambia nada.

Requiere la base sembrada (`supabase db reset`), como `test_profile_seed.py`.
"""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.clients import RawClient, validate_client

ALICIA = "a1000000-0000-4000-8000-000000000001"
BETO = "a1000000-0000-4000-8000-000000000002"

EXPECTED = {
    ALICIA: {"Estudio Norte S.L.": "national", "Kreativ GmbH": "eu", "Taller Zócalo": "non_eu"},
    BETO: {"Café Liebre S.L.": "national", "Atelier Lune SARL": "eu", "Sam Rivers": "non_eu"},
}


def seeded(admin: Connection[DictRow], owner: str) -> list[dict[str, Any]]:
    return admin.execute("select * from public.clients where owner_id = %s order by name", (owner,)).fetchall()


@pytest.mark.parametrize("owner", [ALICIA, BETO])
def test_each_seeded_person_has_one_client_of_each_scope(admin: Connection[DictRow], owner: str) -> None:
    found = {r["name"]: r["scope"] for r in seeded(admin, owner)}
    assert found == EXPECTED[owner]


@pytest.mark.parametrize("owner", [ALICIA, BETO])
def test_the_seeded_clients_pass_the_domain_and_saving_them_through_it_changes_nothing(
    admin: Connection[DictRow], owner: str
) -> None:
    for row in seeded(admin, owner):
        result = validate_client(RawClient(row["name"], row["kind"], row["country"], row["tax_id"], row["address"]))
        assert result.errors == (), (row["name"], result.errors)
        values = result.values
        assert values is not None
        assert (
            values.name,
            values.kind,
            values.country,
            values.scope,
            values.tax_id,
            values.address,
            values.vies_status,
        ) == (
            row["name"],
            row["kind"],
            row["country"],
            row["scope"],
            row["tax_id"],
            row["address"],
            row["vies_status"],
        )


def test_the_seed_has_no_archived_clients_and_only_eu_companies_carry_vies(admin: Connection[DictRow]) -> None:
    found = admin.execute("select * from public.clients where owner_id in (%s, %s)", (ALICIA, BETO)).fetchall()
    assert len(found) == 6 and all(r["archived_at"] is None for r in found)
    assert {r["name"] for r in found if r["vies_status"] == "valid_simulated"} == {"Kreativ GmbH", "Atelier Lune SARL"}
