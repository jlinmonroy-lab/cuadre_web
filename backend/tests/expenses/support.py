"""Ayudas de las pruebas de gastos: llevar un documento hasta registrarlo y ver la base como la ve el administrador."""

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.rows import DictRow

from tests.documents.conftest import Api
from tests.support import Person

# Lo que admite `PUT /review` (extra="forbid"); `review` sustituye a la lectura entera, así que hay que mandarlo todo.
REVIEW_FIELDS = (
    "doc_type",
    "supplier_name",
    "supplier_tax_id",
    "recipient_tax_id",
    "invoice_number",
    "issue_date",
    "currency",
    "tax_breakdown",
    "withholding",
    "total_cents",
)

GOOD_REVIEW: dict[str, Any] = {
    "doc_type": "full_invoice",
    "supplier_name": "Proveedor Sintético SL",
    "supplier_tax_id": "B00000042",
    "recipient_tax_id": None,
    "invoice_number": "A-311",
    "issue_date": "2026-10-15",
    "currency": "EUR",
    "tax_breakdown": [{"vat_rate": "21", "base_cents": 10000, "vat_cents": 2100}],
    "withholding": None,
    "total_cents": 12100,
}


def review_of(api: Api, person: Person, document_id: UUID | str, **changes: Any) -> dict[str, Any]:
    """El formulario tal como lo mandaría la interfaz: lo que hay guardado (`review` o, si no, la lectura) con los cambios encima."""
    document = api.get(person, document_id).json()
    source = document["review"] or document["extraction"] or {}
    body = {field: source.get(field) for field in REVIEW_FIELDS}
    body["tax_breakdown"] = [dict(line) for line in body["tax_breakdown"] or []]
    return {**body, **changes}


def save(api: Api, person: Person, document_id: UUID | str, **changes: Any) -> dict[str, Any]:
    response = api.save_review(person, document_id, review_of(api, person, document_id, **changes))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def confirm(
    api: Api, person: Person, document_id: UUID | str, *, category: str = "software", acknowledge: bool | None = None
) -> Any:
    body: dict[str, Any] = {"category": category}
    if acknowledge is not None:
        body["acknowledge_suspicion"] = acknowledge
    return api.request("POST", f"/api/documents/{document_id}/confirm", person, json=body)


def read(api: Api, person: Person, name: str = "invoice_ok") -> UUID:
    """Sube y lee un ejemplo del contrato: el documento queda en `review`."""
    api.script(name)
    return api.read(person)


def registered(api: Api, person: Person, name: str = "invoice_ok", **kwargs: Any) -> tuple[UUID, dict[str, Any]]:
    document_id = read(api, person, name)
    response = confirm(api, person, document_id, **kwargs)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return document_id, body


def create(api: Api, person: Person, **overrides: Any) -> Any:
    body = {
        "expense_date": "2026-10-01",
        "concept": "Cuota de autónomos",
        "category": "self_employed_fee",
        "amount_cents": 29400,
        **overrides,
    }
    return api.request("POST", "/api/expenses", person, json=body)


def manual(api: Api, person: Person, **overrides: Any) -> dict[str, Any]:
    response = create(api, person, **overrides)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def void(api: Api, person: Person, expense_id: UUID | str) -> Any:
    return api.request("POST", f"/api/expenses/{expense_id}/void", person)


# --- La base, como la ve el administrador (solo para comprobar) ---------------------------------------------------------------


def all_expenses(admin: Connection[DictRow], person: Person) -> list[DictRow]:
    return admin.execute(
        "select * from public.expenses where owner_id = %s order by created_at, id", (person.id,)
    ).fetchall()


def live_expenses(admin: Connection[DictRow], person: Person) -> list[DictRow]:
    return [row for row in all_expenses(admin, person) if row["voided_at"] is None]


def set_profile_tax_id(admin: Connection[DictRow], person: Person, tax_id: str | None) -> None:
    admin.execute("update public.business_profiles set tax_id = %s where owner_id = %s", (tax_id, person.id))


def actions(admin: Connection[DictRow], person: Person) -> list[str]:
    rows = admin.execute(
        "select action from public.activity_log where owner_id = %s and action like 'expense.%%' order by id",
        (person.id,),
    ).fetchall()
    return [r["action"] for r in rows]
