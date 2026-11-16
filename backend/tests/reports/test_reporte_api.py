"""AC-01 a AC-13 y AC-16 · El reporte mensual por la API (SPEC-W-013 §5.3), con la aplicación REAL y la base de datos real.

Agosto y septiembre de 2026 quedan cerrados por el job de verdad; octubre (terminado, sin cierre) y noviembre (en curso) se calculan en vivo. El reloj de la API es fijo.
"""

from datetime import UTC, date, datetime

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.reports import EXPENSES_NOTE
from tests.agents.support import captured_logs
from tests.clocks import FixedClock
from tests.jobs.test_cierre_mensual_job import bill
from tests.quarters.conftest import standing_of
from tests.reports.conftest import Api, close_until, expense, story
from tests.rls.invoices_support import ready, rectify, series
from tests.support import Cast, Pool

SCOPES = ["national", "eu", "non_eu"]


# --- AC-01 · AC-13 · Un mes cerrado --------------------------------------------------------------------------------------------------------


def test_a_closed_month_has_the_figures_of_the_monthly_closings_and_everything_the_report_draws(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    response = api.report(cast.alicia, 2026, 9)
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    body = response.json()

    detail = api.month(cast.alicia, 2026, 9).json()
    assert all(
        body[key] == value for key, value in detail.items()
    )  # las mismas cifras que /mensual, también el desglose por cliente
    assert (body["status"], body["revision"], body["year"], body["month"]) == ("closed", 1, 2026, 9)
    assert (body["national_cents"], body["eu_cents"], body["total_cents"], body["expenses_cents"]) == (
        90_000,
        30_000,
        120_000,
        36_050,
    )
    assert (body["result_cents"], body["ytd_cents"]) == (83_950, 220_000)
    assert (body["quarter"], body["quarter_year"]) == (3, 2026)
    assert "set_aside" not in body and not any("apart" in key for key in body)  # sin importe a apartar (D-08)

    assert [(s["scope"], s["base_cents"], s["share_bp"]) for s in body["scopes"]] == [
        ("national", 90_000, 7_500),
        ("eu", 30_000, 2_500),
        ("non_eu", 0, 0),
    ]


def test_the_expenses_by_category_exclude_the_voided_and_count_the_non_deductible_vat(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    body = api.report(cast.alicia, 2026, 9).json()
    assert [
        (c["category"], c["label"], c["expenses_cents"], c["expense_count"]) for c in body["expenses_by_category"]
    ] == [
        ("advisory", "Asesoría", 30_000, 1),
        ("software", "Software", 6_050, 1),  # 5.000 de base + 1.050 de IVA no deducible; el anulado de material no sale
    ]
    assert body["expenses_by_category_total_cents"] == body["expenses_cents"] == 36_050
    assert body["expenses_note"] is None

    august = api.report(cast.alicia, 2026, 8).json()
    assert [(c["category"], c["expenses_cents"]) for c in august["expenses_by_category"]] == [
        ("software", 10_000)
    ]  # IVA deducible: no cuenta


# --- AC-03 · AC-04 · La comparación ------------------------------------------------------------------------------------------------------


def test_the_comparison_has_the_previous_month_deltas_and_variations(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    comparison = api.report(cast.alicia, 2026, 9).json()["comparison"]
    assert comparison == {
        "previous_year": 2026,
        "previous_month": 8,
        "previous_status": "closed",
        "total_cents": 100_000,
        "expenses_cents": 10_000,
        "result_cents": 90_000,
        "total_delta_cents": 20_000,
        "expenses_delta_cents": 26_050,
        "result_delta_cents": -6_050,
        "total_variation_bp": 2_000,  # +20 %
        "expenses_variation_bp": 26_050,
    }


def test_the_first_month_has_no_comparison_and_the_months_before_it_are_not_found(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    assert api.report(cast.alicia, 2026, 8).json()["comparison"] is None
    for year, month in ((2026, 7), (2026, 1), (2025, 12)):
        response = api.report(cast.alicia, year, month)
        assert response.status_code == 404 and response.json()["code"] == "closing_not_found"


# --- AC-09 · Mes pendiente y mes en curso ---------------------------------------------------------------------------------------------------


def test_a_pending_and_an_in_progress_month_are_calculated_live_with_their_trend(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    october = api.report(cast.alicia, 2026, 10).json()
    assert (october["status"], october["total_cents"], october["revision"]) == ("pending", 20_000, None)
    assert october["comparison"]["previous_status"] == "closed"
    assert (october["comparison"]["total_delta_cents"], october["comparison"]["total_variation_bp"]) == (
        -100_000,
        -8_333,
    )
    assert october["quarter"] == 4

    november = api.report(cast.alicia, 2026, 11).json()
    assert (november["status"], november["total_cents"], november["quarter"]) == ("in_progress", 7_000, 4)
    assert november["comparison"]["previous_status"] == "pending"
    assert november["comparison"]["total_variation_bp"] == -6_500
    assert [(c["category"], c["expenses_cents"]) for c in november["expenses_by_category"]] == [("other", 4_000)]
    assert [(p["year"], p["month"], p["status"], p["total_cents"]) for p in november["trend"]] == [
        (2026, 8, "closed", 100_000),
        (2026, 9, "closed", 120_000),
        (2026, 10, "pending", 20_000),
        (2026, 11, "in_progress", 7_000),
    ]  # de la primera actividad al mes pedido, en orden
    assert [p["result_cents"] for p in november["trend"]] == [90_000, 83_950, 20_000, 3_000]


# --- AC-05 · AC-07 · Rectificativas y cuotas -------------------------------------------------------------------------------------------------


def test_a_rectification_counts_in_its_own_month_with_its_sign_and_leaves_no_share(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    original = bill(app_pool, admin, cast.alicia, r, "national", date(2026, 8, 20), 100_000)
    out = rectify(
        app_pool, cast.alicia, original, corrected=60_000, when=date(2026, 9, 5), standing=standing_of(admin, original)
    )
    assert not out.error, out.message
    close_until(service_pool, app_pool, cast.alicia)

    august, september = api.report(cast.alicia, 2026, 8).json(), api.report(cast.alicia, 2026, 9).json()
    assert august["total_cents"] == 100_000  # agosto conserva su importe
    assert (september["national_cents"], september["total_cents"]) == (-40_000, -40_000)
    assert [s["share_bp"] for s in september["scopes"]] == [
        None,
        None,
        None,
    ]  # un total que no es positivo no tiene cuotas
    assert [(c["scope"], c["base_cents"]) for c in september["by_client"]] == [("national", -40_000)]
    assert september["comparison"]["total_delta_cents"] == -140_000
    assert september["comparison"]["total_variation_bp"] == -14_000


# --- AC-08 · La tendencia ---------------------------------------------------------------------------------------------------------------


def test_the_trend_has_twelve_months_across_the_year_boundary(
    api: Api, app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    r = ready(admin, cast.alicia)
    for n, (year, month) in enumerate([(2025, m) for m in range(3, 13)] + [(2026, 1), (2026, 2), (2026, 3)], start=1):
        bill(app_pool, admin, cast.alicia, r, "national", date(year, month, 5), n * 1_000)
    api.app.state.clock = FixedClock(datetime(2026, 3, 20, 8, 0, tzinfo=UTC))

    body = api.report(cast.alicia, 2026, 3).json()
    trend = [(p["year"], p["month"], p["total_cents"]) for p in body["trend"]]
    assert (
        len(trend) == 12 and trend[0] == (2025, 4, 2_000) and trend[-1] == (2026, 3, 13_000)
    )  # marzo de 2025 ya no entra
    assert trend == sorted(trend)
    assert (body["comparison"]["previous_year"], body["comparison"]["previous_month"]) == (2026, 2)

    january = api.report(cast.alicia, 2026, 1).json()
    assert (january["comparison"]["previous_year"], january["comparison"]["previous_month"]) == (
        2025,
        12,
    )  # el año anterior
    assert (january["trend"][0]["year"], january["trend"][0]["month"]) == (2025, 3)  # y llega a la primera actividad


# --- AC-10 · El desglose y el cierre no cuadran ------------------------------------------------------------------------------------------


def test_a_late_expense_in_a_closed_month_is_flagged_until_the_job_runs_again(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    expense(admin, app_pool, cast.alicia, date(2026, 9, 28), "training", 1_000)

    body = api.report(cast.alicia, 2026, 9).json()
    assert body["expenses_cents"] == 36_050  # la foto del cierre no se refresca al leer
    assert body["expenses_by_category_total_cents"] == 37_050
    assert "training" in [c["category"] for c in body["expenses_by_category"]]
    assert body["expenses_note"] == EXPENSES_NOTE and not any(ch.isdigit() for ch in body["expenses_note"])

    close_until(service_pool, app_pool, cast.alicia)
    after = api.report(cast.alicia, 2026, 9).json()
    assert after["expenses_cents"] == after["expenses_by_category_total_cents"] == 37_050
    assert after["expenses_note"] is None and after["revision"] == 2


# --- AC-11 · Errores y acceso --------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("year", "month", "code"),
    [
        (2026, 12, "period_in_future"),
        (2027, 1, "period_in_future"),
        (2026, 0, "invalid_period"),
        (2026, 13, "invalid_period"),
        (1999, 5, "invalid_period"),
        (10000, 5, "invalid_period"),
    ],
)
def test_a_period_that_does_not_exist_or_has_not_started_is_refused(
    api: Api, cast: Cast, year: int, month: int, code: str
) -> None:
    response = api.report(cast.alicia, year, month)
    assert response.status_code == 422 and response.json()["code"] == code
    assert response.headers["content-type"].startswith("application/problem+json")


def test_a_month_that_is_not_a_number_is_a_validation_error(api: Api, cast: Cast) -> None:
    response = api.get(cast.alicia, "/api/monthly-report/2026/septiembre")
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


def test_too_many_expenses_are_refused_without_any_data(
    api: Api,
    app_pool: Pool,
    service_pool: Pool,
    admin: Connection[DictRow],
    cast: Cast,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    monkeypatch.setattr("cuadre.reports.rules.CLOSING_MAX_DOCUMENTS", 1)  # septiembre tiene dos gastos vivos
    response = api.report(cast.alicia, 2026, 9)
    assert response.status_code == 422 and response.json()["code"] == "report_too_large"
    assert "36050" not in response.text and "Asesoría" not in response.text


def test_without_a_session_the_answer_is_401(api: Api) -> None:
    assert api.report(None, 2026, 9).status_code == 401


@pytest.mark.parametrize("who", ["gina", "adan"])
def test_gestores_and_admins_cannot_use_it(api: Api, cast: Cast, who: str) -> None:
    assert api.report(cast[who], 2026, 9).status_code == 403


def test_a_suspended_account_cannot_use_it(api: Api, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert api.report(cast.alicia, 2026, 11).status_code == 403


# --- AC-12 · AC-16 · Aislamiento, registros y contrato ----------------------------------------------------------------------------------


def test_one_person_never_sees_the_figures_categories_or_trend_of_another(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    r = ready(admin, cast.beto)
    bill(app_pool, admin, cast.beto, r, "eu", date(2026, 10, 12), 55_000)
    expense(admin, app_pool, cast.beto, date(2026, 10, 14), "utilities", 3_000)

    assert api.report(cast.beto, 2026, 9).status_code == 404  # septiembre no existe para Beto
    body = api.report(cast.beto, 2026, 10).json()
    assert (body["total_cents"], body["eu_cents"], body["expenses_cents"]) == (55_000, 55_000, 3_000)
    assert [c["category"] for c in body["expenses_by_category"]] == ["utilities"]
    assert [(p["year"], p["month"]) for p in body["trend"]] == [(2026, 10)] and body["comparison"] is None
    assert {c["name"] for c in body["by_client"]}.isdisjoint(
        {c["name"] for c in api.report(cast.alicia, 2026, 9).json()["by_client"]}
    )


def test_the_logs_carry_no_amounts_names_or_emails(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    with captured_logs("cuadre") as logs:
        assert api.report(cast.alicia, 2026, 9).status_code == 200
    text = " ".join(str(record.__dict__) + record.getMessage() for record in logs)
    assert cast.alicia.email not in text and "36050" not in text and "120000" not in text and "Asesoría" not in text


def test_the_route_is_in_the_public_contract(api: Api) -> None:
    operation = api.app.openapi()["paths"]["/api/monthly-report/{year}/{month}"]["get"]
    assert operation["operationId"] == "get_monthly_report"
    assert set(operation["responses"]) >= {"200", "401", "403", "404", "422"}


def test_a_series_in_another_year_is_not_needed_to_close_a_month_twice(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """Un documento atrasado en otra serie reabre septiembre y el reporte lo recoge tras el job (las dos partes usan la misma foto)."""
    r = story(admin, app_pool, service_pool, cast.alicia)
    other = series(admin, cast.alicia, "TARDE")
    bill(app_pool, admin, cast.alicia, r, "non_eu", date(2026, 9, 14), 5_000, series_id=other)
    assert api.report(cast.alicia, 2026, 9).json()["total_cents"] == 120_000
    close_until(service_pool, app_pool, cast.alicia)
    after = api.report(cast.alicia, 2026, 9).json()
    assert (after["total_cents"], after["non_eu_cents"], after["revision"]) == (125_000, 5_000, 2)
    assert after["scopes"][2]["share_bp"] == 400  # 5 000 / 125 000


def test_the_first_and_the_last_day_belong_to_their_month_and_the_next_first_does_not(
    api: Api, app_pool: Pool, service_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    story(admin, app_pool, service_pool, cast.alicia)
    expense(admin, app_pool, cast.alicia, date(2026, 9, 1), "training", 100)
    expense(admin, app_pool, cast.alicia, date(2026, 9, 30), "utilities", 200)
    expense(admin, app_pool, cast.alicia, date(2026, 10, 1), "utilities", 700)
    expense(admin, app_pool, cast.alicia, date(2026, 8, 31), "training", 50)

    september = {
        c["category"]: c["expenses_cents"] for c in api.report(cast.alicia, 2026, 9).json()["expenses_by_category"]
    }
    assert september == {
        "advisory": 30_000,
        "software": 6_050,
        "training": 100,
        "utilities": 200,
    }  # no el del 31 de agosto ni el del 1 de octubre
    october = {
        c["category"]: c["expenses_cents"] for c in api.report(cast.alicia, 2026, 10).json()["expenses_by_category"]
    }
    assert october == {"utilities": 700}


def test_the_query_asks_for_one_row_more_than_the_limit_so_an_excess_is_seen() -> None:
    from cuadre.closing.limits import CLOSING_MAX_DOCUMENTS
    from cuadre.reports import repository

    assert repository.LIMIT == CLOSING_MAX_DOCUMENTS + 1 and "LIMIT %(limit)s" in repository.EXPENSES_SQL
