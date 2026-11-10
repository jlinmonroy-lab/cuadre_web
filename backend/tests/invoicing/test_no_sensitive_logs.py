"""AC-20, T7-06, NFR-11 · Ni el nombre, ni el NIF, ni el domicilio, ni el IBAN, ni el concepto de una factura en los registros, los errores ni el
registro de actividad (SPEC-W-007)."""

import json
from typing import Any

import pytest

from cuadre.documents.storage import StorageUnavailable
from cuadre.invoicing import repository
from tests.agents.support import captured_logs, rendered
from tests.invoicing.conftest import Api, invoice_body
from tests.rls.invoices_support import D1, D2, D3, ISSUER

CONCEPT = "Concepto secretísimo 5519"
REASON = "Motivo secretísimo 8842"
CLIENT_NAME = "Cliente Secreto Reservado S.L."
CLIENT_ADDRESS = "Calle Reservada 41, Ciudad Oculta"
SECRETS = [
    CONCEPT,
    REASON,
    CLIENT_NAME,
    CLIENT_ADDRESS,
    ISSUER["legal_name"],
    ISSUER["tax_id"],
    ISSUER["iban"],
    ISSUER["fiscal_address"],
]


def test_nothing_about_an_invoice_reaches_the_logs_the_errors_or_the_activity_log(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    alicia, beto, gina = api.cast.alicia, api.cast.beto, api.cast.gina
    api.admin.execute(
        "update public.clients set name = %s, address = %s where id = %s", (CLIENT_NAME, CLIENT_ADDRESS, api.cid())
    )
    errors: list[Any] = []
    with captured_logs("cuadre") as records:
        issued = api.issue(alicia, invoice_body(api.cid(), concept=CONCEPT))
        invoice_id = issued.json()["id"]
        api.preview(alicia, invoice_body(api.cid(), concept=CONCEPT))
        errors += [
            api.issue(alicia, invoice_body(api.cid(), concept="a")),  # 422 de campo
            api.issue(
                alicia, invoice_body(api.cid(), concept=CONCEPT, issue_date="2026-02-30")
            ),  # 422 con el concepto en la petición
            api.issue(
                alicia, invoice_body(api.cid(), concept=CONCEPT, issue_date=D1.isoformat(), series_id="no-uuid")
            ),  # 422
            api.get(beto, invoice_id),  # 404
            api.issue(gina, invoice_body(api.cid(), concept=CONCEPT)),  # 403
            api.client.post("/api/invoices", json=invoice_body(api.cid(), concept=CONCEPT)),  # 401
            api.rectify(beto, invoice_id, reason=REASON),  # 404
            api.rectify(alicia, invoice_id, reason=REASON, corrected_base_cents=999_999),  # 409
            api.rectify(alicia, invoice_id, reason="x", corrected_base_cents=1),  # 422
            api.pay(alicia, invoice_id, "yes"),  # 422 de forma
        ]
        api.issue(alicia, invoice_body(api.cid(), concept=CONCEPT, issue_date=D2.isoformat()))
        api.rectify(alicia, invoice_id, reason=REASON, corrected_base_cents=50_000)
        api.pay(alicia, invoice_id, True)
        api.get(alicia, invoice_id)
        api.listing(alicia, year=2026)
        api.billing(alicia, year=2026)
        # El PDF: bajar, completar uno que falló al emitir, el archivo alterado y Storage caído
        api.pdf(alicia, invoice_id)
        api.storage.fail["upload"] = StorageUnavailable()
        failed = api.issue(alicia, invoice_body(api.cid(), concept=CONCEPT, issue_date=D3.isoformat()))
        del api.storage.fail["upload"]
        api.create_pdf(alicia, failed.json()["id"])
        for path in list(api.storage.objects):
            api.storage.objects[path] = b"%PDF-1.4 alterado"
        errors.append(api.pdf(alicia, invoice_id))  # 409 alterado
        api.storage.fail["download"] = StorageUnavailable()
        errors.append(api.pdf(alicia, invoice_id))  # 503
        errors += [
            api.pdf(beto, invoice_id),
            api.create_pdf(beto, invoice_id),
            api.pdf(gina, invoice_id),
        ]  # 404, 404, 403

        # Un fallo cuyo mensaje trae datos (una excepción de la base, de la librería…): se registra su tipo, nunca su texto
        def leaky(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError(f"fallo con {CONCEPT} y {CLIENT_NAME}")

        monkeypatch.setattr(repository, "attach_pdf", leaky)
        api.issue(alicia, invoice_body(api.cid(), concept=CONCEPT, issue_date=api.today().isoformat()))
        api.admin.execute("update public.clients set archived_at = now() where id = %s", (api.cid(),))
        errors.append(api.issue(alicia, invoice_body(api.cid(), concept=CONCEPT)))  # 409 cliente archivado

    text = rendered(records)
    for secret in SECRETS:
        assert secret not in text, secret
    assert "invoice_pdf_failed" in text  # el fallo del PDF se registra con su causa, no con lo que contenía
    for path in api.storage.objects:  # ni las rutas con la huella ni el contenido de los archivos
        assert path not in text and path.split("/")[1] not in text
    assert "%PDF" not in text and "alterado" not in text
    assert api.signer.token(alicia) not in text
    for response in errors:
        assert response.status_code >= 400
        for secret in SECRETS:
            assert secret not in response.text, (response.status_code, secret)

    log = api.admin.execute(
        "select action, metadata from public.activity_log where owner_id = %s and action like 'invoice.%%'",
        (alicia.id,),
    ).fetchall()
    assert {r["action"] for r in log} == {"invoice.issued", "invoice.rectified", "invoice.payment_changed"}
    dumped = json.dumps(log, default=str)
    for secret in SECRETS:
        assert secret not in dumped, secret
