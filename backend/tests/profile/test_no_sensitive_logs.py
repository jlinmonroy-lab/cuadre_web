"""AC-06, T5-05, NFR-11 · Ni NIF, ni IBAN, ni nombre, ni domicilio, ni URL firmadas ni tokens en los registros ni en los errores."""

import logging

from cuadre.documents.storage import StorageUnavailable
from tests.agents.support import captured_logs, rendered
from tests.profile.conftest import ADDRESS, IBAN, NAME, NIF, PNG, VALID, Api

SENSITIVE = [NIF, IBAN, "ES91 2100", ADDRESS, NAME, "SIGNED-", "storage.test"]


def test_nothing_personal_reaches_the_logs_or_the_errors(api: Api) -> None:
    alicia = api.cast.alicia
    with captured_logs("cuadre") as records:
        responses = [
            api.save(alicia, **VALID, iban="es91 2100 0418 4502 0005 1332"),
            api.save(alicia, **{**VALID, "tax_id": "12345678A"}, iban="ES91 2100 0418 4502 0005 1333"),  # 422
            api.profile(alicia),
            api.request("GET", "/api/invoice-series", alicia),
            api.request("POST", "/api/invoice-series", alicia, json={"code": "FAC"}),
            api.request("POST", "/api/invoice-series", alicia, json={"code": "FAC"}),  # 409
            api.complete(alicia, api.logo(alicia)),
            api.complete(alicia, api.logo(alicia, data=b"CONTENIDO-PRIVADO-DEL-LOGO")),  # 422
            api.request("GET", "/api/profile/logo", alicia),
        ]
        api.storage.fail["delete"] = StorageUnavailable()
        api.request("DELETE", "/api/profile/logo", alicia)  # el borrado falla: se avisa, sin datos
        api.request("GET", "/api/profile", api.cast.gina)  # 403
        api.client.get("/api/profile")  # 401
    text = rendered(records)
    assert "logo_delete_failed" in text
    for secret in SENSITIVE + [api.signer.token(alicia)]:
        assert secret not in text, secret
    for response in responses[1:2] + responses[5:6] + responses[7:8]:  # los errores no repiten lo escrito
        for needle in ("12345678A", "ES91 2100 0418 4502 0005 1333", "CONTENIDO-PRIVADO-DEL-LOGO"):
            assert needle not in response.text, (response.text, needle)
    assert PNG.decode("latin-1") not in text
    assert all(r.levelno <= logging.WARNING for r in records)
