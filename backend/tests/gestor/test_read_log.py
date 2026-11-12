"""AC-10 · Cada lectura del gestor queda registrada (una entrada por petición, solo ids y tipo) y el registro es parte de la lectura (SPEC-W-010 hito 2)."""

import json
import uuid
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.gestor.conftest import Api
from tests.gestor.support import access_log, documents, link, reads
from tests.rls.invoices_support import issue, made, ready
from tests.support import Pool

IBAN = "ES3600000000050000000001"


@pytest.fixture
def client_with_data(api: Api, app_pool: Pool, admin: Connection[DictRow]) -> dict[str, Any]:
    """Alicia con vínculo activo con Gina, un perfil con IBAN, una factura y un documento para revisar."""
    link(app_pool, api.cast.alicia, api.cast.gina)
    r = ready(admin, api.cast.alicia)
    invoice = made(issue(app_pool, api.cast.alicia, r.clients[("national", "business")], r.series, base=123_459))
    document = documents(app_pool, api.cast.alicia, "review", 1)[0]
    return {"base": f"/api/gestor/autonomos/{api.cast.alicia.id}", "invoice": invoice, "document": document}


def get(api: Api, url: str, **params: Any) -> Any:
    return api.request("GET", url, api.cast.gina, params=params or None)


def test_every_request_leaves_exactly_one_read_with_its_type_id_and_period(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:
    base, invoice = client_with_data["base"], client_with_data["invoice"]
    calls = [
        (f"{base}/perfil", {}, "profile", None, {}),
        (f"{base}/clientes", {}, "clients", None, {}),
        (f"{base}/facturas", {"year": 2026}, "invoices", None, {"year": 2026}),
        (f"{base}/facturas", {}, "invoices", None, {}),
        (f"{base}/facturas/{invoice}", {}, "invoice", str(invoice), {}),
        (f"{base}/gastos", {"year": 2026}, "expenses", None, {"year": 2026}),
        (f"{base}/documentos", {}, "documents", None, {}),
        (f"{base}/anotaciones", {}, "notes", None, {}),
        (f"{base}/trimestres/303", {"year": 2025, "quarter": 3}, "modelo_303", None, {"year": 2025, "quarter": 3}),
        (f"{base}/trimestres/130", {"year": 2025, "quarter": 4}, "modelo_130", None, {"year": 2025, "quarter": 4}),
        (f"{base}", {}, "portfolio", str(api.cast.alicia.id), {}),
    ]
    for index, (url, params, entity_type, entity_id, metadata) in enumerate(calls, start=1):
        assert get(api, url, **params).status_code == 200, url
        rows = reads(admin, api.cast.alicia)
        assert len(rows) == index, url  # una entrada por petición, ni más ni menos
        last = rows[-1]
        assert (last["category"], last["actor_id"], last["actor_role"]) == ("access", api.cast.gina.id, "gestor")
        assert (last["entity_type"], last["entity_id"], last["metadata"]) == (entity_type, entity_id, metadata), url


def test_the_default_period_is_resolved_and_logged(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:
    assert get(api, f"{client_with_data['base']}/trimestres/303").status_code == 200
    [row] = reads(admin, api.cast.alicia)
    assert set(row["metadata"]) == {"year", "quarter"} and 1 <= row["metadata"]["quarter"] <= 4


def test_the_downloads_are_logged_by_resource_and_never_with_the_url(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:
    from tests.gestor.support import FakeStorage

    api.app.state.storage = FakeStorage()
    document = client_with_data["document"]
    assert get(api, f"{client_with_data['base']}/documentos/{document.id}/original").status_code == 200
    [row] = reads(admin, api.cast.alicia)
    assert (row["entity_type"], row["entity_id"]) == ("document_original", str(document.id))
    assert "storage.example.test" not in json.dumps(access_log(admin, api.cast.alicia), default=str)


def test_nothing_sensitive_goes_to_the_log(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:
    base = client_with_data["base"]
    for suffix in (
        "/perfil",
        "/clientes",
        "/facturas",
        f"/facturas/{client_with_data['invoice']}",
        "/gastos",
        "/documentos",
    ):
        assert get(api, f"{base}{suffix}").status_code == 200
    everything = json.dumps(access_log(admin, api.cast.alicia), default=str)
    for secret in (
        IBAN,
        "Alicia",
        api.cast.alicia.email,
        "Cliente",
        "123459",
        "1234,59",
        "Emisor Sintético",
        "12345678Z",
        "Servicios de diseño",
    ):
        assert secret not in everything, secret
    for row in reads(admin, api.cast.alicia):
        assert set(row["metadata"]) <= {"year", "quarter"}
        assert row["entity_id"] is None or uuid.UUID(row["entity_id"])  # solo identificadores


# --- El registro es parte de la lectura ------------------------------------------------------------------------------------------------


def test_without_a_link_nothing_is_read_and_nothing_is_logged(api: Api, admin: Connection[DictRow]) -> None:
    for suffix in ("", "/perfil", "/facturas", "/gastos", "/clientes", "/documentos", "/trimestres/303"):
        assert get(api, f"/api/gestor/autonomos/{api.cast.alicia.id}{suffix}").status_code == 404
    assert [
        r for r in access_log(admin, api.cast.alicia) if r["category"] == "access"
    ] == []  # el alta de la cuenta es de otra categoría


def test_a_read_that_fails_after_the_log_leaves_no_entry_either(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:
    """La transacción es una: si el dato no se puede entregar (aquí, una factura que no existe), tampoco queda el registro."""
    response = get(api, f"{client_with_data['base']}/facturas/{uuid.uuid4()}")
    assert (response.status_code, response.json()["code"]) == (404, "invoice_not_found")
    assert reads(admin, api.cast.alicia) == []


def test_if_the_log_cannot_be_written_the_data_is_not_returned(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:
    """Se rompe la función de registro (como si la base no pudiera escribir): la lectura entera falla y no se entrega ningún dato."""
    admin.execute("revoke execute on function app.log_gestor_read(uuid, text, text, jsonb) from authenticated")
    try:
        response = get(api, f"{client_with_data['base']}/perfil")
    finally:
        admin.execute("grant execute on function app.log_gestor_read(uuid, text, text, jsonb) to authenticated")
    assert response.status_code in (404, 500) and "iban" not in response.text.lower() and IBAN not in response.text
    assert reads(admin, api.cast.alicia) == []


def test_each_repeated_request_is_a_new_entry_without_deduplicating(
    api: Api, admin: Connection[DictRow], client_with_data: dict[str, Any]
) -> None:  # P-05
    for _ in range(3):
        assert get(api, f"{client_with_data['base']}/perfil").status_code == 200
    assert len(reads(admin, api.cast.alicia)) == 3
