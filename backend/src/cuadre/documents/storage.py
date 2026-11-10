"""Storage privado de documentos, siempre en nombre de la persona (SPEC-W-002 §3.3, §5.4, T2-03, Anexo B.1).

Todas las llamadas llevan el JWT de la persona (`Authorization: Bearer`); no hace falta `apikey` ni interviene la service key. Lo que
descubrió el spike del hito 0 y se aplica aquí:

* Storage devuelve las URL firmadas **relativas** a `/storage/v1`; aquí se componen con `SUPABASE_URL`.
* Casi todos los errores llegan con HTTP 400 y el estado real en `statusCode` del cuerpo: se decide por ese.
* Un objeto ajeno responde igual que uno inexistente (404).
* El tamaño y el tipo registrados salen de `object/info`; la firma del archivo, de sus primeros bytes con `Range`. Nunca se descarga el
  archivo entero (Vercel limita el cuerpo a 4,5 MB): si Storage ignorase `Range`, se corta la lectura a los bytes pedidos.

Ni las URL firmadas, ni el JWT, ni las rutas con nombre de archivo (no las hay: la ruta solo lleva identificadores) entran en un registro.
"""

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx2 as httpx

logger = logging.getLogger("cuadre.documents")

BUCKET = "documents"
TIMEOUT_SECONDS = 10
MAX_JSON_BYTES = 65_536
PATH = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f-]{36}\.(pdf|jpg|png|heic|webp)"
)


class StorageError(Exception):
    """Fallo de Storage. Nunca lleva el cuerpo de la respuesta (puede traer rutas o tokens)."""


class StorageNotFound(StorageError):
    """El objeto no existe, o no es de quien pregunta (Storage no lo distingue)."""


class StorageDenied(StorageError):
    """Una política de Storage lo deniega."""


class StorageUnavailable(StorageError):
    """No responde, responde algo inesperado o rechaza la credencial."""


UploadResult = Literal["created", "exists"]


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str


class StorageGateway(Protocol):
    def sign_upload(self, path: str, *, token: str) -> str:
        """URL completa de subida (`PUT`, una sola vez, 2 h)."""
        ...

    def object_info(self, path: str, *, token: str) -> ObjectInfo | None:
        """Tamaño y tipo que Storage registró, o `None` si no hay objeto."""
        ...

    def read_head(self, path: str, *, token: str, length: int) -> bytes:
        """Los primeros `length` bytes del archivo (como mucho)."""
        ...

    def sign_read(self, path: str, *, token: str, expires_in: int) -> str:
        """URL completa de lectura que caduca en `expires_in` segundos."""
        ...

    def delete(self, path: str, *, token: str) -> None:
        """Borra el objeto; si ya no existe, no es un error."""
        ...


@dataclass(frozen=True)
class _Reply:
    status: int  # el real: el de `statusCode` del cuerpo cuando HTTP dice 4xx
    body: bytes


def _real_status(http_status: int, body: bytes) -> int:
    if http_status < 400:
        return http_status
    try:
        return int(json.loads(body)["statusCode"])
    except (ValueError, KeyError, TypeError):
        return http_status


def _json_object(reply: _Reply) -> dict[str, Any]:
    try:
        data = json.loads(reply.body)
    except ValueError:
        raise StorageUnavailable from None
    if not isinstance(data, dict):
        raise StorageUnavailable
    return data


class HttpStorage:
    def __init__(
        self,
        supabase_url: str,
        *,
        bucket: str = BUCKET,
        path: re.Pattern[str] = PATH,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._base = supabase_url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._path_re = path
        self._clock_ns = clock_ns

    # --- Operaciones -----------------------------------------------------------------------------------------------------

    def sign_upload(self, path: str, *, token: str) -> str:
        reply = self._call("sign_upload", "POST", f"/object/upload/sign/{self._bucket}/{self._path(path)}", token)
        if reply.status == 403:
            raise StorageDenied
        return self._relative_url(reply, "url", f"/object/upload/sign/{self._bucket}/")

    def object_info(self, path: str, *, token: str) -> ObjectInfo | None:
        reply = self._call("object_info", "GET", f"/object/info/authenticated/{self._bucket}/{self._path(path)}", token)
        if reply.status == 404:
            return None
        if reply.status == 403:
            raise StorageDenied
        data = _json_object(self._ok(reply))
        size, content_type = data.get("size"), data.get("content_type")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or not isinstance(content_type, str):
            raise StorageUnavailable
        return ObjectInfo(size, content_type)

    def read_head(self, path: str, *, token: str, length: int) -> bytes:
        reply = self._call(
            "read_head",
            "GET",
            f"/object/authenticated/{self._bucket}/{self._path(path)}",
            token,
            extra_headers={"Range": f"bytes=0-{length - 1}"},
            max_bytes=length,
        )
        if reply.status == 404:
            raise StorageNotFound
        if reply.status == 403:
            raise StorageDenied
        return self._ok(reply, accepted=(200, 206)).body[:length]

    def sign_read(self, path: str, *, token: str, expires_in: int) -> str:
        reply = self._call(
            "sign_read",
            "POST",
            f"/object/sign/{self._bucket}/{self._path(path)}",
            token,
            json_body={"expiresIn": expires_in},
        )
        if reply.status == 404:
            raise StorageNotFound
        if reply.status == 403:
            raise StorageDenied
        return self._relative_url(reply, "signedURL", f"/object/sign/{self._bucket}/")

    def upload(self, path: str, data: bytes, content_type: str, *, token: str) -> UploadResult:
        """Sube un objeto en nombre de la persona (SPEC-W-007 §5.4, B.1-C). **409 = ya estaba** (con la huella en la ruta, el mismo contenido da
        siempre la misma ruta): no es un error. 403 es una política (un vínculo, un rol o una ruta que no es suya); 413, 415 y el resto, un fallo
        nuestro o de Storage, que la API responde como «no disponible»."""
        reply = self._call(
            "upload",
            "POST",
            f"/object/{self._bucket}/{self._path(path)}",
            token,
            content=data,
            extra_headers={"Content-Type": content_type},
        )
        if reply.status == 409:
            return "exists"
        if reply.status == 403:
            raise StorageDenied
        self._ok(reply)
        return "created"

    def download(self, path: str, *, token: str, max_bytes: int) -> bytes:
        """El objeto entero, con un tope: nunca se leen más de `max_bytes + 1` bytes (el último sobra y delata un objeto demasiado grande). Un objeto
        ajeno responde igual que uno inexistente (`StorageNotFound`)."""
        reply = self._call(
            "download",
            "GET",
            f"/object/authenticated/{self._bucket}/{self._path(path)}",
            token,
            max_bytes=max_bytes + 1,
        )
        if reply.status == 404:
            raise StorageNotFound
        if reply.status == 403:
            raise StorageDenied
        return self._ok(reply).body[: max_bytes + 1]

    def delete(self, path: str, *, token: str) -> None:
        reply = self._call("delete", "DELETE", f"/object/{self._bucket}/{self._path(path)}", token)
        if reply.status == 404:
            return
        if reply.status == 403:
            raise StorageDenied
        self._ok(reply)

    # --- Internos --------------------------------------------------------------------------------------------------------

    def _path(self, path: str) -> str:
        if (
            self._path_re.fullmatch(path) is None
        ):  # solo identificadores y extensión: si no, es un error nuestro, no de la persona
            raise ValueError("ruta de Storage con forma inesperada")
        return path

    @staticmethod
    def _ok(reply: _Reply, accepted: tuple[int, ...] = (200,)) -> _Reply:
        if reply.status not in accepted:
            raise StorageUnavailable
        return reply

    def _relative_url(self, reply: _Reply, key: str, expected_prefix: str) -> str:
        value = _json_object(self._ok(reply)).get(key)
        if not isinstance(value, str) or not value.startswith(expected_prefix):
            raise StorageUnavailable  # una URL que no es de nuestro bucket no se entrega a nadie
        return self._base + value

    def _call(
        self,
        operation: str,
        method: str,
        endpoint: str,
        token: str,
        *,
        json_body: dict[str, Any] | None = None,
        content: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        max_bytes: int = MAX_JSON_BYTES,
    ) -> _Reply:
        started = self._clock_ns()
        headers = {"Authorization": f"Bearer {token}", **(extra_headers or {})}
        # Una conexión por llamada, sin redirecciones y sin proxies del entorno: el JWT solo va a la URL de Storage configurada.
        client = httpx.Client(
            timeout=httpx.Timeout(TIMEOUT_SECONDS),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=0),
        )
        try:
            with (
                client,
                client.stream(
                    method, self._base + endpoint, headers=headers, json=json_body, content=content
                ) as response,
            ):
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) >= max_bytes:
                        break  # no se descarga más de lo que hace falta
                http_status = response.status_code
        except httpx.HTTPError:
            self._log(operation, None, started)
            raise StorageUnavailable from None
        reply = _Reply(_real_status(http_status, bytes(body)), bytes(body))
        self._log(operation, reply.status, started)
        if (
            http_status == 401 or reply.status == 401
        ):  # el JWT ya lo verificó la API: que Storage lo rechace es de configuración
            logger.error("storage_auth_rejected", extra={"operation": operation})
        return reply

    def _log(self, operation: str, status: int | None, started: int) -> None:
        logger.info(
            "storage_call",
            extra={
                "operation": operation,
                "status": status,
                "outcome": "unreachable" if status is None else "ok" if status < 400 else "error",
                "duration_ms": (self._clock_ns() - started) // 1_000_000,
            },
        )
