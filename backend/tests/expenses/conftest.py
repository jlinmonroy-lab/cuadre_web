"""Fixtures de la API de gastos: las de documentos (la aplicación REAL con base de datos real, Storage en memoria y agente simulado).

Los gastos nacen de documentos leídos, así que se reutiliza todo el montaje de `tests/documents/conftest.py`.
"""

from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.documents.conftest import Api, api, app, storage  # noqa: F401 - fixtures de otro conftest
