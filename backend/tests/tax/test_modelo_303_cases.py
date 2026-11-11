"""AC-13, AC-08, AC-09 · Los cinco trimestres simulados a mano de la spec (SPEC-W-008, Anexo B.1) reproducidos al céntimo.

Los datos salen del **bloque JSON del Anexo B.1** de la propia spec: una sola fuente de verdad. Son «simulados, no externos»: calculados a mano
con las mismas reglas que implementa el código (D-02 a D-06) y contrastados con un script independiente, no validados por la AEAT ni por una
gestoría (DEP-01 sigue pendiente como mejora). Se pasan **todos los documentos de los cinco casos juntos**, más `X1`, y se pide cada trimestre
por separado: así se ejercitan las fronteras (31/03, 01/04, 31/12) y que nada se cuele en otro trimestre.
"""

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cuadre.tax import Box, ExpenseLine, ExpenseRow, InvoiceRow, Modelo303, build_modelo_303

SPEC = Path(__file__).resolve().parents[3] / "docs" / "04-specs" / "SPEC-W-008-modelo-303.md"
TODAY = date(2026, 6, 1)  # después de 2026-04-01: ningún trimestre de los casos es futuro
ALL_CODES = ("01", "03", "04", "06", "07", "09", "27", "28", "29", "45", "46", "59", "120")

# Los documentos de cada casilla con items, copiados de las tablas del Anexo B.1 (en el orden de la pantalla: fecha y etiqueta).
EXPECTED_ITEMS = {
    "Q-A": {"01": ["A5", "A6"], "03": ["A5", "A6"], "04": ["A3", "A4"], "06": ["A3", "A4"], "07": ["A1", "A2"], "09": ["A1", "A2"]},
    "Q-B": {
        "04": ["B5"], "06": ["B5"], "07": ["B1", "B4", "B6"], "09": ["B1", "B4", "B6"],
        "28": ["EB1", "EB2", "EB3"], "29": ["EB1", "EB2", "EB3"], "59": ["B2"], "120": ["B3"],
    },
    "Q-C": {
        "01": ["C4"], "03": ["C4"], "04": ["C2", "C3", "R5", "R4", "R6"], "06": ["C2", "C3", "R5", "R4", "R6"],
        "07": ["C1", "R1", "R3"], "09": ["C1", "R1", "R3"], "59": ["R2"],
    },
    "Q-D": {"07": ["D1"], "09": ["D1"], "28": ["ED1", "ED4", "ED6"], "29": ["ED1", "ED4", "ED6"]},
    "Q-E": {},
}  # fmt: skip


def load_cases() -> dict:
    text = SPEC.read_text(encoding="utf-8")
    start = text.find("**Formato para las pruebas del hito 1**")
    assert start != -1, "No se encontró el bloque «Formato para las pruebas del hito 1» en el Anexo B.1 de la spec."
    match = re.search(r"```json\n(.*?)\n```", text[start:], re.DOTALL)
    assert match, "El Anexo B.1 no lleva el bloque JSON con los cinco trimestres."
    data = json.loads(match.group(1))
    assert [t["caso"] for t in data["trimestres"]] == ["Q-A", "Q-B", "Q-C", "Q-D", "Q-E"]
    return data


CASES = load_cases()


def _day(text: str) -> date:
    return date.fromisoformat(text)


def rows(documents: list[dict]) -> tuple[list[InvoiceRow], list[ExpenseRow]]:
    invoices, expenses = [], []
    for d in documents:
        if d["tipo"] in ("factura", "rectificativa"):
            invoices.append(
                InvoiceRow(
                    d["id"], d["id"], _day(d["fecha"]), d["tratamiento"], Decimal(d["iva"]), d["base"], d["cuota"]
                )
            )
        else:
            lines = tuple(ExpenseLine(Decimal(x["iva"]), x["base"], x["cuota"]) for x in d["lineas"])
            expenses.append(ExpenseRow(d["id"], d["id"], _day(d["fecha"]), d["iva_deducible"], d["anulado"], lines))
    return invoices, expenses


def all_documents() -> list[dict]:
    return [d for t in CASES["trimestres"] for d in t["documentos"]] + CASES["fuera_de_los_cinco"]


def model_of(case: dict) -> Modelo303:
    invoices, expenses = rows(all_documents())
    return build_modelo_303(case["anio"], case["trimestre"], invoices, expenses, TODAY)


def box(model: Modelo303, code: str) -> Box:
    return next(b for b in model.boxes if b.code == code)


def test_the_spec_carries_five_cases_with_all_the_boxes() -> None:
    assert len(CASES["trimestres"]) == 5
    for case in CASES["trimestres"]:
        assert tuple(case["casillas"]) == ALL_CODES
    # Los casos cubren a propósito las cuatro formas del resultado.
    assert {t["resultado"] for t in CASES["trimestres"]} == {"a_ingresar", "a_compensar", "sin_actividad"}


@pytest.mark.parametrize("case", CASES["trimestres"], ids=[t["caso"] for t in CASES["trimestres"]])
def test_every_box_and_the_result_match_the_hand_calculation_to_the_cent(case: dict) -> None:  # AC-13
    model = model_of(case)
    got = {b.code: b.amount_cents for b in model.boxes}
    assert got == case["casillas"]
    assert model.result_kind == case["resultado"]
    assert model.result_cents == case["casillas"]["46"]


@pytest.mark.parametrize("case", CASES["trimestres"], ids=[t["caso"] for t in CASES["trimestres"]])
def test_every_box_lists_the_documents_that_compose_it(case: dict) -> None:  # AC-08, NFR-08
    model = model_of(case)
    expected = EXPECTED_ITEMS[case["caso"]]
    for b in model.boxes:
        assert [i.id for i in b.items] == expected.get(b.code, []), f"{case['caso']} casilla {b.code}"
        if b.measure is not None:
            total = sum(i.base_cents if b.measure == "base" else i.vat_cents for i in b.items)
            assert total == b.amount_cents, (
                f"{case['caso']} casilla {b.code}: la suma de sus documentos no es la casilla"
            )


def test_rounding_per_document_differs_from_rounding_the_total_in_the_first_case() -> None:  # D-05
    model = model_of(CASES["trimestres"][0])
    # 105 y 2345 al 10 %: 11 + 235 = 246 por documento; sobre la base total (2450) saldría 245.
    assert box(model, "04").amount_cents == 2_450 and box(model, "06").amount_cents == 246 != 2_450 // 10


def test_a_chain_of_rectifications_leaves_zero_vat_not_one_cent() -> None:  # AC-04
    model = model_of(CASES["trimestres"][2])
    chain = [i for i in box(model, "06").items if i.id in ("C3", "R5", "R6")]
    assert [i.vat_cents for i in chain] == [11, -6, -5]
    assert [i.base_cents for i in chain] == [105, -52, -53]
    assert sum(i.vat_cents for i in chain) == 0 and sum(i.base_cents for i in chain) == 0


def test_rectifications_of_the_second_quarter_subtract_in_the_third_and_leave_the_second_intact() -> (
    None
):  # AC-04, D-02
    second = model_of(CASES["trimestres"][1])
    assert [i.id for i in box(second, "07").items] == ["B1", "B4", "B6"]
    assert box(second, "07").amount_cents == 185_050  # B1 completa, aunque R1 la corrija en el T3
    assert box(second, "59").amount_cents == 150_000
    third = model_of(CASES["trimestres"][2])
    assert box(third, "59").amount_cents == -50_000


def test_the_quarter_between_two_neighbours_has_no_activity_and_the_neighbours_land_in_their_own_quarters() -> (
    None
):  # AC-09
    fifth = model_of(CASES["trimestres"][4])
    assert fifth.result_kind == "sin_actividad" and all(b.amount_cents == 0 and not b.items for b in fifth.boxes)
    invoices, expenses = rows(all_documents())
    second_2026 = build_modelo_303(2026, 2, invoices, expenses, TODAY)
    assert [i.id for i in box(second_2026, "07").items] == ["X1"]  # 2026-04-01
    fourth = build_modelo_303(2025, 4, invoices, expenses, TODAY)
    assert "ED6" in [i.id for i in box(fourth, "28").items]  # 2025-12-31 sigue en el T4


def test_the_amounts_do_not_depend_on_the_order_of_the_documents() -> None:
    invoices, expenses = rows(all_documents())
    for case in CASES["trimestres"]:
        direct = build_modelo_303(case["anio"], case["trimestre"], invoices, expenses, TODAY)
        reverse = build_modelo_303(
            case["anio"], case["trimestre"], list(reversed(invoices)), list(reversed(expenses)), TODAY
        )
        assert direct == reverse
