"""AC-17, T3-08, NFR-11 · Ni NIF, ni nombres, ni números de factura, ni importes, ni el concepto, ni URLs firmadas ni tokens en los registros.

Se recorre el flujo completo (registrar, fallar la validación, anotar un gasto sin factura, listar, ver, recategorizar, anular, y los errores de la
API) con todos los registros de la aplicación capturados. El registro de actividad de la base lo comprueba `tests/rls/test_expenses_states.py`.
"""

from tests.agents.support import captured_logs, rendered
from tests.documents.conftest import FILENAME, Api
from tests.expenses.support import confirm, create, manual, read, save, void

# Datos de `invoice_ok`, de `invoice_sum_mismatch` y de lo que se escribe en las pruebas: ninguno puede salir.
SENSITIVE = [
    "B00000042",
    "Nubesoft",
    "NS-2026-9921",
    "12345678Z",
    "B00000075",
    "Imprenta Sol",
    "A-318",
    "Secreto",
    "autónomos",
    "29400",
    "145,20",
]


def test_ac17_nothing_sensitive_reaches_the_logs(api: Api) -> None:
    alicia, beto, gina = api.cast.alicia, api.cast.beto, api.cast.gina

    with captured_logs("cuadre") as records:
        good = read(api, alicia)
        assert confirm(api, alicia, good, category="advisory").status_code == 201

        bad = read(api, alicia, "invoice_sum_mismatch")
        save(api, alicia, bad)
        assert confirm(api, alicia, bad).status_code == 422  # la suma no cuadra

        created = manual(api, alicia, concept="Concepto Secreto de autónomos", amount_cents=29400)
        assert create(api, alicia, expense_date="2999-01-01").status_code == 422  # fecha futura
        assert create(api, alicia, concept="").status_code == 422  # cuerpo mal formado

        api.request("GET", "/api/expenses", alicia, params={"year": 2026, "category": "advisory"})
        api.request("GET", "/api/expenses", alicia, params={"cursor": "no-es-nuestro"})
        api.request("GET", f"/api/expenses/{created['id']}", alicia)
        api.request("PUT", f"/api/expenses/{created['id']}/category", alicia, json={"category": "other"})
        assert void(api, alicia, created["id"]).status_code == 200
        assert void(api, alicia, created["id"]).status_code == 409

        assert api.request("GET", f"/api/expenses/{created['id']}", beto).status_code == 404
        assert api.request("GET", "/api/expenses", gina).status_code == 403
        assert api.client.get("/api/expenses").status_code == 401
        assert confirm(api, beto, good).status_code == 404

    assert records, "debería haber registros de las peticiones"
    text = rendered(records)
    tokens = {call.token for call in api.storage.calls}
    forbidden = [
        FILENAME,
        "token=",
        "SIGNED-",
        "Bearer",
        "Authorization",
        *api.storage.signed_urls,
        *(part for token in tokens for part in token.split(".")),
        *SENSITIVE,
    ]
    for needle in forbidden:
        assert needle not in text, f"el registro contiene {needle!r}"


def test_the_request_log_has_the_route_template_not_the_expense_id(api: Api) -> None:
    alicia = api.cast.alicia
    expense = manual(api, alicia)
    with captured_logs("cuadre.request") as records:
        api.request("GET", f"/api/expenses/{expense['id']}", alicia)
    (record,) = records
    assert record.route == "/api/expenses/{expense_id}"  # type: ignore[attr-defined]
    assert record.status == 200 and record.user_id == str(alicia.id)  # type: ignore[attr-defined]
    assert expense["id"] not in rendered(records)
