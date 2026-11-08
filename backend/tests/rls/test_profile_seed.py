"""El seed de desarrollo (SPEC-W-005 §5.2, B.1): Alicia y Beto tienen un perfil que el propio dominio da por bueno.

Antes llevaban `TEST-0001` y un IBAN `ES00…` que no valían; con ellos ninguna simplificada era deducible y no se podía probar una factura. Los
valores son sintéticos (RES-07) pero válidos. Estas pruebas leen las filas del seed (usuarios de `supabase/seed.sql`), no las del reparto de
cada test.
"""

from datetime import date

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.profile import StoredIdentity, completeness, retention, validate_profile
from cuadre.profile.types import RawProfile
from cuadre.validators import normalize_iban, normalize_tax_id

EXPECTED = {
    "alicia@example.test": ("12345678Z", "ES3600000000050000000001", 7),
    "beto@example.test": ("01230956L", "ES6300000000010000000002", 15),
}


def profile(admin: Connection[DictRow], email: str) -> DictRow:
    row = admin.execute(
        "select b.*, p.email from public.business_profiles b join public.profiles p on p.id = b.owner_id where p.email = %s",
        (email,),
    ).fetchone()
    assert row is not None, f"falta {email} en el seed: ¿se ejecutó `supabase db reset`?"
    return row


@pytest.mark.parametrize("email", sorted(EXPECTED))
def test_the_seeded_profile_can_issue(admin: Connection[DictRow], email: str) -> None:
    row = profile(admin, email)
    result = completeness(StoredIdentity(row["legal_name"], row["tax_id"], row["fiscal_address"]))
    assert result.can_issue is True and result.missing_for_invoicing == ()


@pytest.mark.parametrize("email", sorted(EXPECTED))
def test_the_seeded_values_are_the_normalized_ones_the_api_will_store(admin: Connection[DictRow], email: str) -> None:
    tax_id, iban, rate = EXPECTED[email]
    row = profile(admin, email)
    assert (row["tax_id"], row["iban"], int(row["irpf_rate"])) == (tax_id, iban, rate)
    found = normalize_tax_id(row["tax_id"])
    assert found is not None and found.scope == "national" and found.key == row["tax_id"]
    assert normalize_iban(row["iban"]) == row["iban"]


@pytest.mark.parametrize("email", sorted(EXPECTED))
def test_saving_the_seeded_profile_through_the_domain_changes_nothing(admin: Connection[DictRow], email: str) -> None:
    row = profile(admin, email)
    result = validate_profile(
        RawProfile(
            legal_name=row["legal_name"],
            tax_id=row["tax_id"],
            fiscal_address=row["fiscal_address"],
            activity=row["activity"],
            iae_epigraph=row["iae_epigraph"],
            activity_start_date=row["activity_start_date"],
            vat_regime=row["vat_regime"],
            irpf_rate=str(row["irpf_rate"]),
            home_pct=None if row["home_pct"] is None else str(row["home_pct"]),
            iban=row["iban"],
        ),
        date(2026, 11, 7),
    )
    assert result.errors == ()
    assert result.values is not None and result.values.tax_id == row["tax_id"] and result.values.iban == row["iban"]


def test_the_retention_advice_matches_the_seeded_start_dates(admin: Connection[DictRow]) -> None:
    today = date(2026, 11, 7)
    alicia, beto = profile(admin, "alicia@example.test"), profile(admin, "beto@example.test")
    assert (
        retention(alicia["activity_start_date"], alicia["irpf_rate"], today).warning is None
    )  # alta de 2025 con el 7 %
    assert retention(beto["activity_start_date"], beto["irpf_rate"], today).warning is None  # alta de 2023 con el 15 %


def test_alicia_and_beto_have_a_default_year_series_and_nobody_else_has_any(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select p.email, s.code, s.is_default, s.first_number, s.next_number from public.invoice_series s "
        "join public.profiles p on p.id = s.owner_id where p.email like '%%@example.test' and p.email in "
        "('alicia@example.test','beto@example.test','gina@example.test','gus@example.test','adan@example.test') order by p.email"
    ).fetchall()
    assert rows == [
        {"email": "alicia@example.test", "code": "2026", "is_default": True, "first_number": 1, "next_number": 1},
        {"email": "beto@example.test", "code": "2026", "is_default": True, "first_number": 1, "next_number": 1},
    ]
