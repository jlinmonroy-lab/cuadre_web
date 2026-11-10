"""Las facturas de ejemplo (SPEC-W-007 §5.2, RES-07) son sintéticas, las emitió la propia aplicación y el dominio las da por buenas.

Requiere la base sembrada (`supabase db reset`), como `test_clients_seed.py`. Alicia tiene una factura de cada uno de los cinco tratamientos, una de
ellas cobrada, y una rectificativa de esa misma; Beto y el resto, ninguna. El seed las emite por `app.issue_invoice` con las claims de Alicia, así que
también quedaron la numeración, las copias del emisor y del cliente y el registro de actividad: aquí se comprueba contra `cuadre.tax`, que calcula lo
que el seed escribió a mano.
"""

from decimal import Decimal
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.tax import (
    NOTE_NON_EU,
    NOTE_REVERSE_CHARGE,
    TREATMENTS,
    Standing,
    compute_amounts,
    invoice_terms,
    rectification_amounts,
)
from tests.rls.invoices_support import today

ALICIA = "a1000000-0000-4000-8000-000000000001"
BETO = "a1000000-0000-4000-8000-000000000002"


def invoices(admin: Connection[DictRow], kind: str) -> list[dict[str, Any]]:
    return admin.execute(
        "select * from public.invoices where owner_id = %s and kind = %s order by series_code, number", (ALICIA, kind)
    ).fetchall()


def test_alicia_has_five_invoices_numbered_one_to_five_and_a_rectification(admin: Connection[DictRow]) -> None:
    standard = invoices(admin, "standard")
    assert [(i["series_code"], i["number"]) for i in standard] == [("2026", n) for n in range(1, 6)]
    (rect,) = invoices(admin, "rectifying")
    assert rect["number"] == 1 and rect["series_code"].startswith("R-") and rect["rectifies_id"] == standard[0]["id"]


def test_the_five_treatments_are_all_there(admin: Connection[DictRow]) -> None:
    assert [i["tax_treatment"] for i in invoices(admin, "standard")] == [
        "national_vat",
        "eu_reverse_charge",
        "eu_consumer_vat",
        "non_eu_not_subject",
        "non_eu_consumer_vat",
    ]
    assert {i["tax_treatment"] for i in invoices(admin, "standard")} == set(TREATMENTS)


def test_nobody_else_has_any_invoice_or_pdf(admin: Connection[DictRow]) -> None:
    others = admin.execute(
        "select count(*) as n from public.invoices where owner_id <> %s and owner_id in (select id from public.profiles where email like '%%@example.test' and email in ('alicia@example.test','beto@example.test','gina@example.test','gus@example.test','adan@example.test'))",
        (ALICIA,),
    ).fetchone()
    assert others == {"n": 0}
    pdfs = admin.execute("select count(*) as n from public.invoice_files where owner_id = %s", (ALICIA,)).fetchone()
    assert pdfs == {"n": 0}, "las facturas sembradas no llevan PDF (`pdf_status: pending`)"


def test_every_seeded_amount_is_what_the_domain_computes(admin: Connection[DictRow]) -> None:
    for row in invoices(admin, "standard"):
        terms = invoice_terms(row["client_scope"], row["client_kind"])
        assert row["tax_treatment"] == terms.treatment, row["number"]
        vat = Decimal(row["vat_rate"]) if terms.vat_editable else None
        irpf = Decimal(row["irpf_rate"]) if terms.withholds else None
        amounts = compute_amounts(terms, row["base_cents"], vat, irpf)
        assert (row["vat_rate"], row["vat_cents"], row["irpf_rate"], row["irpf_cents"], row["total_cents"]) == (
            amounts.vat_rate,
            amounts.vat_cents,
            amounts.irpf_rate,
            amounts.irpf_cents,
            amounts.total_cents,
        ), row["number"]
        assert row["legal_note"] == terms.legal_note


def test_the_legal_notes_are_the_domains_two(admin: Connection[DictRow]) -> None:
    notes = {i["tax_treatment"]: i["legal_note"] for i in invoices(admin, "standard")}
    assert notes == {
        "national_vat": None,
        "eu_reverse_charge": NOTE_REVERSE_CHARGE,
        "eu_consumer_vat": None,
        "non_eu_not_subject": NOTE_NON_EU,
        "non_eu_consumer_vat": None,
    }


def test_the_rectification_is_the_difference_of_values_the_domain_computes(admin: Connection[DictRow]) -> None:
    first = invoices(admin, "standard")[0]
    (rect,) = invoices(admin, "rectifying")
    corrected = first["base_cents"] + rect["base_cents"]
    standing = Standing(first["base_cents"], first["vat_cents"], first["irpf_cents"])
    amounts = rectification_amounts(standing, Decimal(first["vat_rate"]), Decimal(first["irpf_rate"]), corrected)
    assert (rect["base_cents"], rect["vat_cents"], rect["irpf_cents"], rect["total_cents"]) == (
        amounts.base_cents,
        amounts.vat_cents,
        amounts.irpf_cents,
        amounts.total_cents,
    )
    assert (rect["tax_treatment"], rect["vat_rate"], rect["irpf_rate"], rect["client_id"]) == (
        first["tax_treatment"],
        first["vat_rate"],
        first["irpf_rate"],
        first["client_id"],
    )
    assert rect["total_cents"] < 0 and rect["paid_at"] is None


def test_the_dates_are_not_future_and_do_not_go_back_within_a_series(admin: Connection[DictRow]) -> None:
    standard, (rect,) = invoices(admin, "standard"), invoices(admin, "rectifying")
    dates = [i["issue_date"] for i in standard]
    assert dates == sorted(dates) and max(dates) <= today(admin) and rect["issue_date"] <= today(admin)
    assert rect["issue_date"] >= standard[0]["issue_date"]


def test_only_the_first_invoice_is_paid(admin: Connection[DictRow]) -> None:
    paid = [i["number"] for i in invoices(admin, "standard") if i["paid_at"] is not None]
    assert paid == [1]


def test_every_seeded_invoice_is_billable_to_a_real_client_with_a_copy_of_its_address(
    admin: Connection[DictRow],
) -> None:
    for row in invoices(admin, "standard"):
        client = admin.execute("select * from public.clients where id = %s", (row["client_id"],)).fetchone()
        assert client is not None and client["archived_at"] is None
        assert (row["client_name"], row["client_address"], row["client_scope"], row["client_kind"]) == (
            client["name"],
            client["address"],
            client["scope"],
            client["kind"],
        )
        assert row["issuer_name"] and row["issuer_tax_id"] == "12345678Z"


def test_the_seeded_particulars_are_individuals_with_an_address(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select name, kind, scope, address from public.clients where owner_id = %s and name in ('Lena Müller', 'Mia Carter') order by name",
        (ALICIA,),
    ).fetchall()
    assert [(r["name"], r["kind"], r["scope"]) for r in rows] == [
        ("Lena Müller", "individual", "eu"),
        ("Mia Carter", "individual", "non_eu"),
    ]
    assert all(r["address"] for r in rows)


def test_the_seed_left_its_trace_in_the_activity_log_without_personal_data(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select action, count(*) as n from public.activity_log where owner_id = %s and action like 'invoice.%%' group by 1 order by 1",
        (ALICIA,),
    ).fetchall()
    assert rows == [
        {"action": "invoice.issued", "n": 5},
        {"action": "invoice.payment_changed", "n": 1},
        {"action": "invoice.rectified", "n": 1},
    ]


@pytest.mark.parametrize("owner", [ALICIA, BETO])
def test_the_series_counters_match_the_invoices_issued(admin: Connection[DictRow], owner: str) -> None:
    rows = admin.execute(
        "select s.code, s.kind, s.next_number, (select count(*) from public.invoices i where i.series_id = s.id) as issued "
        "from public.invoice_series s where s.owner_id = %s order by s.code",
        (owner,),
    ).fetchall()
    for row in rows:
        assert row["next_number"] == 1 + row["issued"], row["code"]
    assert [r["kind"] for r in rows if r["code"].startswith("R-")] in ([], ["rectifying"])
