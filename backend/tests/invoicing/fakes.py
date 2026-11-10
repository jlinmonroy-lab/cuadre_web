"""Dobles en memoria de Storage para las pruebas de la API de facturas (los tokens de prueba no los acepta el Storage real).

Registran cada llamada con el JWT que recibieron: así se prueba que Storage siempre se llama en nombre de la persona (T2-03). Se comportan como el
Storage real que midió el spike del hito 0 (B.1-C): una segunda subida a la misma ruta es «ya está» y un objeto ajeno responde como uno inexistente.
"""

from dataclasses import dataclass

from cuadre.documents.storage import ObjectInfo, StorageError, StorageNotFound, UploadResult


@dataclass(frozen=True)
class Call:
    operation: str
    path: str
    token: str


class FakePdfStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[Call] = []
        self.fail: dict[str, StorageError] = {}  # operación -> error a lanzar

    def operations(self, operation: str) -> list[Call]:
        return [c for c in self.calls if c.operation == operation]

    def _enter(self, operation: str, path: str, token: str) -> None:
        self.calls.append(Call(operation, path, token))
        if operation in self.fail:
            raise self.fail[operation]

    def upload(self, path: str, data: bytes, content_type: str, *, token: str) -> UploadResult:
        self._enter("upload", path, token)
        assert content_type == "application/pdf"
        if path in self.objects:
            return "exists"
        self.objects[path] = data
        return "created"

    def download(self, path: str, *, token: str, max_bytes: int) -> bytes:
        self._enter("download", path, token)
        if path not in self.objects:
            raise StorageNotFound
        return self.objects[path][: max_bytes + 1]

    def object_info(self, path: str, *, token: str) -> ObjectInfo | None:
        self._enter("object_info", path, token)
        if path not in self.objects:
            return None
        return ObjectInfo(len(self.objects[path]), "application/pdf")


class FakeLogoStorage:
    """Los logos del perfil: ruta -> bytes. Una ruta que no está responde como un objeto inexistente."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[Call] = []
        self.fail: StorageError | None = None

    def download(self, path: str, *, token: str, max_bytes: int) -> bytes:
        self.calls.append(Call("download", path, token))
        if self.fail is not None:
            raise self.fail
        if path not in self.objects:
            raise StorageNotFound
        return self.objects[path][: max_bytes + 1]
