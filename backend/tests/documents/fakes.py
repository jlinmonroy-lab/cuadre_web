"""Doble en memoria de Storage para las pruebas de la API de documentos (los tokens de prueba no los acepta el Storage real).

Registra cada llamada con el JWT que recibió: así se prueba que Storage siempre se llama en nombre de la persona (T2-03). Las URL que
fabrica llevan `token=` a propósito, para que `test_no_sensitive_logs` pueda comprobar que no salen en ningún registro.
"""

import threading
from collections.abc import Sequence
from dataclasses import dataclass

from cuadre.agents import FakeAgentsClient
from cuadre.agents.fake import ScriptItem
from cuadre.documents.storage import ObjectInfo, StorageError, StorageNotFound
from cuadre_contracts import ExtractRequest, ExtractResponse


@dataclass(frozen=True)
class Call:
    operation: str
    path: str
    token: str


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}  # ruta -> (contenido, tipo registrado)
        self.calls: list[Call] = []
        self.fail: dict[str, StorageError] = {}  # operación -> error a lanzar
        self.read_expiries: list[int] = []
        self.signed_urls: list[str] = []
        self._counter = 0

    # --- Preparación de las pruebas -----------------------------------------------------------------------------------------

    def put(self, path: str, data: bytes, content_type: str) -> None:
        """Lo que haría el navegador al hacer el PUT a la URL firmada."""
        self.objects[path] = (data, content_type)

    def operations(self, operation: str) -> list[Call]:
        return [c for c in self.calls if c.operation == operation]

    # --- StorageGateway -------------------------------------------------------------------------------------------------

    def _enter(self, operation: str, path: str, token: str) -> None:
        self.calls.append(Call(operation, path, token))
        if operation in self.fail:
            raise self.fail[operation]

    def _signed(self, kind: str, path: str) -> str:
        self._counter += 1
        url = f"https://storage.test/storage/v1/object/{kind}/documents/{path}?token=SIGNED-{kind.upper().replace('/', '-')}-{self._counter}"
        self.signed_urls.append(url)
        return url

    def sign_upload(self, path: str, *, token: str) -> str:
        self._enter("sign_upload", path, token)
        return self._signed("upload/sign", path)

    def object_info(self, path: str, *, token: str) -> ObjectInfo | None:
        self._enter("object_info", path, token)
        if path not in self.objects:
            return None
        data, content_type = self.objects[path]
        return ObjectInfo(len(data), content_type)

    def read_head(self, path: str, *, token: str, length: int) -> bytes:
        self._enter("read_head", path, token)
        if path not in self.objects:
            raise StorageNotFound
        return self.objects[path][0][:length]

    def sign_read(self, path: str, *, token: str, expires_in: int) -> str:
        self._enter("sign_read", path, token)
        if path not in self.objects:
            raise StorageNotFound
        self.read_expiries.append(expires_in)
        return self._signed("sign", path)

    def delete(self, path: str, *, token: str) -> None:
        self._enter("delete", path, token)
        self.objects.pop(path, None)


class GatedAgents(FakeAgentsClient):
    """Se queda esperando dentro de `extract_invoice` hasta que el test lo suelte: sirve para probar qué pasa MIENTRAS se lee."""

    def __init__(self, script: Sequence[ScriptItem]) -> None:
        super().__init__(script)
        self.started = threading.Event()
        self.release = threading.Event()

    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        self.started.set()
        assert self.release.wait(timeout=30), "el test no soltó la lectura"
        return super().extract_invoice(request, request_id=request_id)


class BrokenAgents:
    """Un cliente que falla de una forma que `cuadre.agents` no prevé (un fallo nuestro, no del servicio)."""

    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        raise RuntimeError("fallo inesperado del cliente")


class SpyAgents(FakeAgentsClient):
    """Anota el `request_id` con el que se le pide cada lectura."""

    def __init__(self, script: Sequence[ScriptItem]) -> None:
        super().__init__(script)
        self.request_ids: list[str] = []

    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        self.request_ids.append(request_id)
        return super().extract_invoice(request, request_id=request_id)
