"""AC-15, AC-11, AC-12 · Los cinco ejercicios simulados a mano de la spec (SPEC-W-009, Anexo B.1) reproducidos al céntimo.

Los datos salen del **bloque JSON del Anexo B.1** de la propia spec: una sola fuente de verdad. Son «simulados, no externos»: calculados a mano con las
mismas reglas que implementa el código (D-02 a D-07) y contrastados con un script independiente, no validados por la AEAT ni por una gestoría (DEP-01 sigue
pendiente como mejora). Se pasan **todos los documentos juntos** y se pide cada trimestre por separado: así se ejercitan las fronteras de trimestre y de año y
que nada se cuele de otro periodo.
"""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from cuadre.tax import Box130, CostRow, IncomeRow, Modelo130, build_modelo_130

SPEC = Path(__file__).resolve().parents[3] / "docs" / "04-specs" / "SPEC-W-009-modelo-130.md"
TODAY = date(2026, 6, 1)  # después de 2026-04-01: ningún trimestre de los casos es futuro
CODES = ("01", "02", "03", "04", "05", "06", "07")


def load_cases() -> dict:
    text = SPEC.read_text(encoding="utf-8")
    start = text.find("**Formato para las pruebas del hito 1**")
    assert start != -1, "No se encontró el bloque «Formato para las pruebas del hito 1» en el Anexo B.1 de la spec."
    match = re.search(r"```json\n(.*?)\n```", text[start:], re.DOTALL)
    assert match, "El Anexo B.1 no lleva el bloque JSON con los cinco ejercicios."
    data = json.loads(match.group(1))
    assert [e["caso"] for e in data["ejercicios"]] == ["E-1", "E-2", "E-3", "E-4", "E-5"]
    assert [e["caso"] for e in data["adicionales"]] == ["E-5b"]
    return data


CASES = load_cases()
EVERY_CASE = CASES["ejercicios"] + CASES["adicionales"]
CASE_IDS = [c["caso"] for c in EVERY_CASE]


def rows() -> tuple[list[IncomeRow], list[CostRow]]:
    incomes, costs = [], []
    for d in CASES["documentos"]:
        day = date.fromisoformat(d["fecha"])
        if d["tipo"] in ("factura", "rectificativa"):
            incomes.append(IncomeRow(d["id"], d["id"], day, d["base"], d["retencion"]))
        else:
            costs.append(CostRow(d["id"], d["id"], day, d["base"], d["iva"], d["iva_deducible"], d["anulado"]))
    return incomes, costs


def model_of(case: dict) -> Modelo130:
    incomes, costs = rows()
    return build_modelo_130(case["anio"], case["trimestre"], incomes, costs, TODAY)


def box(model: Modelo130, code: str) -> Box130:
    return next(b for b in model.boxes if b.code == code)


def test_the_spec_carries_the_exercises_and_the_documents() -> None:
    assert len(CASES["documentos"]) == 23
    for case in EVERY_CASE:
        assert tuple(case["casillas"]) == CODES
    # Los casos cubren a propósito las tres formas del resultado.
    assert {c["resultado"] for c in EVERY_CASE} == {"a_ingresar", "nada_que_ingresar", "sin_actividad"}


@pytest.mark.parametrize("case", EVERY_CASE, ids=CASE_IDS)
def test_every_box_the_result_and_the_share_match_the_hand_calculation_to_the_cent(case: dict) -> None:  # AC-15
    model = model_of(case)
    assert {b.code: b.amount_cents for b in model.boxes} == case["casillas"]
    assert model.result_kind == case["resultado"]
    assert model.result_cents == case["casillas"]["07"]
    assert model.withheld_share_percent == case["porcentaje_retencion"]


@pytest.mark.parametrize("case", EVERY_CASE, ids=CASE_IDS)
def test_every_box_lists_the_documents_that_compose_it_and_their_sum_is_the_box(case: dict) -> None:  # AC-11, NFR-08
    model = model_of(case)
    for code in ("01", "02", "05", "06"):
        listed = box(model, code)
        assert [item.id for item in listed.items] == case["documentos"][code], f"{case['caso']} casilla {code}"
        assert sum(item.amount_cents for item in listed.items) == listed.amount_cents, f"{case['caso']} casilla {code}"
    for code in ("03", "04", "07"):
        assert box(model, code).items == ()
    assert box(model, "03").components == ("01", "02")
    assert box(model, "04").components == ("03",)
    assert box(model, "07").components == ("04", "05", "06")


def test_the_second_quarter_adds_to_the_first_it_does_not_replace_it() -> None:  # AC-07
    first, second = (model_of(c) for c in CASES["ejercicios"][:2])
    first_ids = {i.id for i in box(first, "01").items}
    assert first_ids < {i.id for i in box(second, "01").items}  # todo lo del T1 sigue en el T2 (y hay más)
    assert box(second, "05").amount_cents == first.result_cents  # su pago, el único anterior


def test_the_previous_payments_chain_with_zero_for_a_quarter_that_owed_nothing() -> None:  # AC-08
    fourth = model_of(CASES["ejercicios"][3])
    payments = {item.id: item.amount_cents for item in box(fourth, "05").items}
    assert payments == {"T1": 50_723, "T2": 1_871, "T3": 0}  # el T3 salió a −153.613: paga 0
    assert box(fourth, "05").amount_cents == sum(payments.values())


def test_a_negative_net_yield_gives_no_twenty_percent_and_nothing_to_pay() -> None:  # AC-05, AC-10
    third = model_of(CASES["ejercicios"][2])
    assert box(third, "03").amount_cents < 0
    assert box(third, "04").amount_cents == 0
    assert third.result_cents < 0 and third.result_kind == "nada_que_ingresar"


def test_the_rectification_subtracts_income_and_withholding_in_its_own_period() -> None:  # AC-02, AC-09
    second = model_of(CASES["ejercicios"][1])
    rectification = next(i for i in box(second, "01").items if i.id == "B3")
    assert rectification.amount_cents == -50_000
    assert next(i for i in box(second, "06").items if i.id == "B3").amount_cents == -7_500
    first = model_of(CASES["ejercicios"][0])
    assert "B3" not in [i.id for i in box(first, "01").items]  # del T2: no cuenta en el T1


def test_the_year_boundary_keeps_the_documents_of_december_out_of_january() -> None:  # AC-12
    fourth, fifth, extra = (
        model_of(c) for c in (CASES["ejercicios"][3], CASES["ejercicios"][4], CASES["adicionales"][0])
    )
    assert {"D2", "G12"} <= {i.id for b in fourth.boxes for i in b.items}  # el 31/12/2025 cuenta en el T4
    assert all(not b.items for b in fifth.boxes) and fifth.result_kind == "sin_actividad"  # y no en el T1 de 2026
    assert [i.id for i in box(extra, "01").items] == ["X1"]  # el T2 de 2026 solo ve lo suyo
    assert box(extra, "05").amount_cents == 0  # y el T1 de 2026 no pagó nada
