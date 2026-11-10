"""AC-14 a AC-16 · Rectificativas por la API (SPEC-W-007 §5.1.5 y §5.3, D-12).

Una rectificativa resta: su base es la corregida menos la vigente y sus cuotas, las diferencias de valores (B.2). Va a la serie `R-AAAA` del año de
su fecha, que crea la propia emisión. La API lee lo vigente ANTES de bloquear; si otra rectificativa llegó entre medias, la base lo detecta y la API
relee una vez y, si vuelve a pasar, responde `invoice_changed`.
"""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from psycopg.rows import DictRow

from cuadre.invoicing import repository
from tests.invoicing.conftest import Api
from tests.rls.invoices_support import D1, D2, D3


@pytest.fixture
def original(api: Api) -> dict[str, Any]:
    """Una factura de base 100.000 al 21 % con retención del 15 %: IVA 21.000, retención 15.000, total 106.000."""
    return api.made(api.cast.alicia, issue_date=D1.isoformat())


def fields_of(response: Any) -> dict[str, str]:
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_invoice"
    return {f["field"]: f["message"] for f in response.json()["fields"]}


def count(api: Api, original: dict[str, Any]) -> int:
    row = api.admin.execute(
        "select count(*) as n from public.invoices where rectifies_id = %s", (original["id"],)
    ).fetchone()
    assert row is not None
    return row["n"]


# --- La rectificativa ----------------------------------------------------------------------------------------------------------------


def test_a_rectification_subtracts_the_difference(api: Api, original: dict[str, Any]) -> None:
    response = api.rectify(api.cast.alicia, original["id"])
    assert response.status_code == 201, response.text
    rect = response.json()
    assert (rect["kind"], rect["base_cents"], rect["vat_cents"], rect["irpf_cents"], rect["total_cents"]) == (
        "rectifying",
        -20_000,
        -4_200,
        -3_000,
        -21_200,
    )
    assert (rect["series_code"], rect["number"], rect["display_number"], rect["issue_date"]) == (
        "R-2026",
        1,
        "R-2026-001",
        D2.isoformat(),
    )
    assert rect["rectifies"] == {"id": original["id"], "display_number": "2026-001", "issue_date": D1.isoformat()}
    assert (rect["rectification_reason"], rect["standing"], rect["paid_at"], rect["rectified_by"]) == (
        "Importe mal calculado",
        None,
        None,
        [],
    )
    for key in ("tax_treatment", "vat_rate", "irpf_rate", "legal_note", "concept", "client"):
        assert rect[key] == original[key], key


def test_the_original_shows_its_rectifications_and_what_still_stands(api: Api, original: dict[str, Any]) -> None:
    api.rectify(api.cast.alicia, original["id"])
    shown = api.get(api.cast.alicia, original["id"]).json()
    assert shown["rectified_by"] == ["R-2026-001"]
    assert shown["standing"] == {"base_cents": 80_000, "vat_cents": 16_800, "irpf_cents": 12_000}
    assert shown["base_cents"] == 100_000  # la factura emitida no cambia


def test_a_full_cancellation_gives_everything_back(api: Api, original: dict[str, Any]) -> None:
    rect = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=0).json()
    assert (rect["base_cents"], rect["vat_cents"], rect["irpf_cents"], rect["total_cents"]) == (
        -100_000,
        -21_000,
        -15_000,
        -106_000,
    )
    assert api.get(api.cast.alicia, original["id"]).json()["standing"] == {
        "base_cents": 0,
        "vat_cents": 0,
        "irpf_cents": 0,
    }


def test_a_chain_ends_at_zero_and_then_nothing_is_left_to_rectify(api: Api, original: dict[str, Any]) -> None:
    first = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=80_000, issue_date=D2.isoformat()).json()
    second = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=0, issue_date=D3.isoformat()).json()
    assert (first["display_number"], second["display_number"]) == ("R-2026-001", "R-2026-002")
    assert (second["base_cents"], second["vat_cents"], second["irpf_cents"]) == (-80_000, -16_800, -12_000)
    assert api.get(api.cast.alicia, original["id"]).json()["rectified_by"] == ["R-2026-001", "R-2026-002"]
    again = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=0, issue_date=D3.isoformat())
    assert "corrected_base_cents" in fields_of(again)
    more = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=1, issue_date=D3.isoformat())
    assert more.json()["code"] == "rectification_exceeds"


def test_cancelling_105_at_10_percent_in_two_steps_leaves_nothing_standing(api: Api) -> None:
    """Las cuotas son DIFERENCIAS de valores y no un porcentaje del importe negativo: -52 y -53 dejaban 1 de cuota (B.2)."""
    original = api.made(api.cast.alicia, "national", "individual", base_cents=105, vat_rate="10.00")
    assert original["vat_cents"] == 11
    api.rectify(api.cast.alicia, original["id"], corrected_base_cents=53)
    api.rectify(api.cast.alicia, original["id"], corrected_base_cents=0)
    assert api.get(api.cast.alicia, original["id"]).json()["standing"] == {
        "base_cents": 0,
        "vat_cents": 0,
        "irpf_cents": 0,
    }


def test_the_rectification_goes_to_the_series_of_the_year_of_its_date_and_it_is_made_once(api: Api) -> None:
    original = api.made(api.cast.alicia, issue_date="2025-12-20")
    first = api.rectify(api.cast.alicia, original["id"], issue_date="2025-12-31", corrected_base_cents=90_000).json()
    second = api.rectify(api.cast.alicia, original["id"], issue_date=D1.isoformat(), corrected_base_cents=80_000).json()
    assert (first["display_number"], second["display_number"]) == ("R-2025-001", "R-2026-001")
    codes = api.admin.execute(
        "select code from public.invoice_series where owner_id = %s and kind = 'rectifying' order by code",
        (api.cast.alicia.id,),
    ).fetchall()
    assert [c["code"] for c in codes] == ["R-2025", "R-2026"]


def test_the_issuer_of_a_rectification_is_the_current_profile(api: Api, original: dict[str, Any]) -> None:
    api.admin.execute(
        "update public.business_profiles set legal_name = 'Nuevo nombre' where owner_id = %s", (api.cast.alicia.id,)
    )
    rect = api.rectify(api.cast.alicia, original["id"]).json()
    row = api.admin.execute("select issuer_name from public.invoices where id = %s", (rect["id"],)).fetchone()
    assert row == {"issuer_name": "Nuevo nombre"}


def test_a_paid_invoice_and_one_of_an_archived_client_can_be_rectified(api: Api, original: dict[str, Any]) -> None:
    api.pay(api.cast.alicia, original["id"], True)
    api.admin.execute("update public.clients set archived_at = now() where id = %s", (api.cid(),))
    assert api.rectify(api.cast.alicia, original["id"]).status_code == 201


# --- Errores -------------------------------------------------------------------------------------------------------------------------


def test_a_rectification_cannot_raise_the_invoice(api: Api, original: dict[str, Any]) -> None:
    response = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=100_001)
    assert response.status_code == 409
    assert (response.json()["code"], response.json()["field"]) == ("rectification_exceeds", "corrected_base_cents")
    assert count(api, original) == 0


def test_the_same_base_has_nothing_to_rectify(api: Api, original: dict[str, Any]) -> None:
    assert "corrected_base_cents" in fields_of(
        api.rectify(api.cast.alicia, original["id"], corrected_base_cents=100_000)
    )


def test_a_rectification_cannot_be_rectified(api: Api, original: dict[str, Any]) -> None:
    rect = api.rectify(api.cast.alicia, original["id"]).json()
    response = api.rectify(api.cast.alicia, rect["id"], issue_date=D3.isoformat())
    assert (response.status_code, response.json()["code"]) == (409, "invoice_not_rectifiable")


def test_every_bad_field_is_reported_at_once_and_nothing_is_issued(api: Api, original: dict[str, Any]) -> None:
    response = api.rectify(
        api.cast.alicia, original["id"], reason="a", corrected_base_cents=-1, issue_date="2026-02-30"
    )
    assert set(fields_of(response)) == {"reason", "corrected_base_cents", "issue_date"}
    assert count(api, original) == 0


@pytest.mark.parametrize("corrected", [True, "80000", 80_000.0, 1.5, None])
def test_the_corrected_base_must_be_a_real_integer(api: Api, original: dict[str, Any], corrected: object) -> None:
    response = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=corrected)
    if corrected is None:
        assert "corrected_base_cents" in fields_of(response)
    else:
        assert response.status_code == 422 and response.json()["code"] == "validation_error"
    assert count(api, original) == 0


def test_a_future_date_is_a_field_error_and_leaves_no_serie(api: Api, original: dict[str, Any]) -> None:
    tomorrow = (api.today() + timedelta(days=1)).isoformat()
    assert "issue_date" in fields_of(api.rectify(api.cast.alicia, original["id"], issue_date=tomorrow))
    row = api.admin.execute(
        "select count(*) as n from public.invoice_series where owner_id = %s and kind = 'rectifying'",
        (api.cast.alicia.id,),
    ).fetchone()
    assert row == {"n": 0}


def test_a_date_before_the_original_or_before_the_last_rectification_is_out_of_order(api: Api) -> None:
    late = api.made(api.cast.alicia, issue_date=D3.isoformat())
    before = api.rectify(api.cast.alicia, late["id"], issue_date=D2.isoformat())
    assert (before.status_code, before.json()["code"], before.json()["field"]) == (
        409,
        "invoice_date_out_of_order",
        "issue_date",
    )
    assert "16/03/2026" in before.json()["detail"]
    other = api.made(api.cast.alicia, issue_date=D3.isoformat())
    api.rectify(api.cast.alicia, other["id"], issue_date=api.today().isoformat())
    in_series = api.rectify(api.cast.alicia, late["id"], issue_date=D3.isoformat(), corrected_base_cents=10)
    assert (in_series.status_code, in_series.json()["code"]) == (409, "invoice_date_out_of_order")


def test_the_order_of_dates_is_checked_in_the_rectifying_series_of_the_year_of_the_date(api: Api) -> None:
    """La serie rectificativa de 2025 y la de 2026 llevan cada una su orden: el mensaje del dominio nombra la última de la del año de la fecha."""
    original = api.made(api.cast.alicia, issue_date="2025-12-20")
    api.rectify(api.cast.alicia, original["id"], issue_date="2025-12-31", corrected_base_cents=90_000)
    response = api.rectify(api.cast.alicia, original["id"], issue_date="2025-12-30", corrected_base_cents=80_000)
    assert (response.status_code, response.json()["code"]) == (409, "invoice_date_out_of_order")
    assert "última factura de la serie (31/12/2025)" in response.json()["detail"]


def test_another_persons_or_a_missing_invoice_is_not_found(api: Api, original: dict[str, Any]) -> None:
    for person, target in ((api.cast.beto, original["id"]), (api.cast.alicia, str(uuid.uuid4()))):
        response = api.rectify(person, target)
        assert (response.status_code, response.json()["code"]) == (404, "invoice_not_found")
    assert api.rectify(api.cast.alicia, "no-uuid").status_code == 422


def test_an_incomplete_profile_blocks_a_rectification(api: Api, original: dict[str, Any]) -> None:
    api.admin.execute(
        "update public.business_profiles set fiscal_address = null where owner_id = %s", (api.cast.alicia.id,)
    )
    response = api.rectify(api.cast.alicia, original["id"])
    assert (response.status_code, response.json()["code"]) == (422, "profile_incomplete")


# --- La carrera: lo vigente cambió entre la lectura y el cerrojo ---------------------------------------------------------------------------


def stale_once(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """La primera lectura de las rectificativas previas llega vacía (como si otra aún no hubiera confirmado); las siguientes, bien."""
    real: Callable[..., list[DictRow]] = repository.rectification_rows
    calls: list[int] = []

    def fake(conn: Any, original_id: object) -> list[DictRow]:
        calls.append(1)
        return [] if len(calls) == 1 else real(conn, original_id)

    monkeypatch.setattr(repository, "rectification_rows", fake)
    return calls


def test_a_stale_read_is_retried_once_and_then_succeeds(
    api: Api, original: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    api.rectify(api.cast.alicia, original["id"], corrected_base_cents=80_000)  # lo vigente es 80.000
    calls = stale_once(monkeypatch)
    response = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=70_000, issue_date=D3.isoformat())
    assert response.status_code == 201, response.text
    assert len(calls) == 2  # se leyó dos veces
    rect = response.json()
    assert (rect["base_cents"], rect["vat_cents"], rect["irpf_cents"]) == (
        -10_000,
        -2_100,
        -1_500,
    )  # respecto de lo vigente de verdad
    assert api.get(api.cast.alicia, original["id"]).json()["standing"]["base_cents"] == 70_000


def test_a_stale_read_that_the_retry_proves_wrong_is_the_normal_error(
    api: Api, original: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    api.rectify(api.cast.alicia, original["id"], corrected_base_cents=80_000)
    calls = stale_once(monkeypatch)
    response = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=90_000, issue_date=D3.isoformat())
    assert (response.status_code, response.json()["code"]) == (409, "rectification_exceeds")
    assert len(calls) == 2


def test_a_read_that_stays_stale_is_invoice_changed(
    api: Api, original: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    api.rectify(api.cast.alicia, original["id"], corrected_base_cents=80_000)
    calls: list[int] = []
    monkeypatch.setattr(repository, "rectification_rows", lambda conn, original_id: calls.append(1) or [])
    response = api.rectify(api.cast.alicia, original["id"], corrected_base_cents=70_000, issue_date=D3.isoformat())
    assert (response.status_code, response.json()["code"]) == (409, "invoice_changed")
    assert len(calls) == 2
    assert count(api, original) == 1  # no se emitió nada más
