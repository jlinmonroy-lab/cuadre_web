"""Servidor de agentes para el E2E (SPEC-W-002 §8.1 y Anexo B.7): un `cuadre-agents` de mentira que habla el contrato de verdad.

    python -m tests.agents.e2e_server --port 8765        # desde `backend/`; la clave, en la variable AGENTS_API_KEY

Con la API apuntando aquí (`AGENTS_BASE_URL`), el E2E usa `HttpAgentsClient` y no el simulado cíclico: el simulado reparte sus
fixtures en orden global, y con seis proyectos de Playwright en paralelo ninguna prueba sabría cuál le toca. Aquí **cada prueba decide
qué lee el agente con el contenido del archivo que sube**: un marcador dentro del archivo (sintético, T2-12) elige el ejemplo de
`contracts/examples/extract/`:

    [[fixture:<nombre>[>otro...][;delay=<ms>]]]

El marcador va entre corchetes dobles a propósito: en un PNG los bytes del CRC siguen al texto, y sin un cierre explícito el primero que
fuese una letra minúscula se pegaría al nombre y nombraría un ejemplo que no existe.

- `<nombre>`: un ejemplo del contrato, servido tal cual (`<nombre>.response.json` con 200, `<nombre>.error.json` con su estado HTTP).
- `a>b`: la primera lectura de ese `document_id` devuelve `a` y las siguientes `b` (para probar «Volver a leer»).
- `delay`: espera antes de contestar, hasta 10 s (para ver «Leyendo…»).

Como el agente real: exige `Authorization: Bearer`, `X-Cuadre-Contract-Version: 1` y `X-Request-Id`, valida el cuerpo con `ExtractRequest`
y **descarga la URL firmada** del documento; si no puede, 502 `upstream_error`. Sin marcador, 400 `invalid_request`: un fallo de la
prueba no debe confundirse con un documento ilegible. No escribe nada del archivo ni de la URL (lleva un token).
"""

import argparse
import hmac
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx2 as httpx
from pydantic import ValidationError

from cuadre_contracts import ExtractRequest

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "extract"
CONTRACT_VERSION = "1"
MAX_DELAY_MS = 10_000
MAX_REQUEST_BYTES = 65_536
MAX_DOCUMENT_BYTES = 1_048_576  # los archivos del E2E son de unos cientos de bytes; el marcador está al principio

# Estado HTTP con el que el servicio real responde cada error (contracts/agents-api/v1/openapi.yaml).
STATUS_OF_ERROR = {
    "unreadable": 422,
    "unsupported_media_type": 415,
    "payload_too_large": 413,
    "invalid_request": 400,
    "unauthorized": 401,
    "upstream_error": 502,
}

MARKER = re.compile(rb"\[\[fixture:([a-z][a-z_]*(?:>[a-z][a-z_]*)*)(?:;delay=(\d{1,6}))?\]\]")


@dataclass(frozen=True)
class Marker:
    names: tuple[str, ...]
    delay_ms: int


def parse_marker(data: bytes) -> Marker | None:
    """El primer marcador `[[fixture:…]]` de los bytes del archivo, o `None`."""
    found = MARKER.search(data)
    if found is None:
        return None
    delay = min(int(found.group(2)), MAX_DELAY_MS) if found.group(2) else 0
    return Marker(tuple(found.group(1).decode("ascii").split(">")), delay)


def fixture_reply(name: str) -> tuple[int, bytes] | None:
    """Estado y cuerpo del ejemplo `name`, o `None` si el contrato no tiene ese ejemplo."""
    response = EXAMPLES / f"{name}.response.json"
    if response.is_file():
        return 200, response.read_bytes()
    error = EXAMPLES / f"{name}.error.json"
    if error.is_file():
        body = error.read_bytes()
        return STATUS_OF_ERROR[json.loads(body)["code"]], body
    return None


def error_body(code: str, message: str) -> bytes:
    return json.dumps({"code": code, "message": message, "trace_id": "trc_e2e"}, ensure_ascii=False).encode()


class AgentsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, api_key: str, *, fetch_timeout_s: float = 10.0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.api_key = api_key
        self.fetch_timeout_s = fetch_timeout_s
        self._reads: dict[str, int] = {}
        self._lock = threading.Lock()

    def next_turn(self, document_id: str) -> int:
        """Cuántas lecturas de este documento ha habido antes de esta (0 la primera)."""
        with self._lock:
            turn = self._reads.get(document_id, 0)
            self._reads[document_id] = turn + 1
            return turn

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: AgentsServer

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, b'{"status":"ok"}')
        else:
            self._send(404, error_body("invalid_request", "Ruta desconocida."))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(length, MAX_REQUEST_BYTES + 1))
        if self.path != "/v1/extract":
            self._send(404, error_body("invalid_request", "Ruta desconocida."))
            return
        status, payload = self._extract(body)
        self._send(status, payload)

    def _extract(self, body: bytes) -> tuple[int, bytes]:
        sent_key = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
        if not hmac.compare_digest(sent_key.encode(), self.server.api_key.encode()):
            return 401, error_body("unauthorized", "Clave del servicio de agentes no válida.")
        if self.headers.get("X-Cuadre-Contract-Version") != CONTRACT_VERSION:
            return 400, error_body("invalid_request", "Falta X-Cuadre-Contract-Version: 1.")
        if not self.headers.get("X-Request-Id"):
            return 400, error_body("invalid_request", "Falta X-Request-Id.")
        try:
            if len(body) > MAX_REQUEST_BYTES:
                raise ValueError
            request = ExtractRequest.model_validate_json(body)
        except (ValidationError, ValueError):
            return 400, error_body("invalid_request", "La petición no cumple el contrato de lectura.")

        document = self._download(str(request.document_url))
        if document is None:
            return 502, error_body("upstream_error", "No se ha podido descargar el documento.")
        marker = parse_marker(document)
        if marker is None:
            return 400, error_body("invalid_request", "El archivo no lleva ningún marcador [[fixture:<nombre>]].")

        turn = self.server.next_turn(str(request.document_id))
        reply = fixture_reply(marker.names[min(turn, len(marker.names) - 1)])
        if reply is None:
            return 400, error_body("invalid_request", "El marcador nombra un ejemplo que el contrato no tiene.")
        if marker.delay_ms:
            time.sleep(marker.delay_ms / 1000)
        return reply

    def _download(self, url: str) -> bytes | None:
        """Lo que haría el agente real con la URL firmada: un GET anónimo, sin redirecciones ni proxies."""
        try:
            with (
                httpx.Client(timeout=self.server.fetch_timeout_s, follow_redirects=False, trust_env=False) as client,
                client.stream("GET", url) as response,
            ):
                if response.status_code != 200:
                    return None
                data = b""
                for chunk in response.iter_bytes():
                    data += chunk
                    if len(data) > MAX_DOCUMENT_BYTES:
                        return None
                return data
        except httpx.HTTPError:
            return None

    def _send(self, status: int, payload: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # quien preguntaba ya se fue

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - firma de la clase base; la URL lleva un token
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Servidor de agentes de E2E (SPEC-W-002 B.7)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    api_key = os.environ.get("AGENTS_API_KEY")
    if not api_key:
        print("Falta la variable de entorno AGENTS_API_KEY.", file=sys.stderr)
        return 2
    server = AgentsServer(args.port, api_key)
    print(f"Servidor de agentes de E2E en {server.url}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
