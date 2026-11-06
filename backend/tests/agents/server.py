"""Servidor HTTP local y guionado que hace de cuadre-agents en los tests (SPEC-W-002 §8.3, AC-05 y AC-08).

Es un servidor de verdad en `127.0.0.1` (puerto efímero), no un transporte simulado: así se prueban de verdad los tiempos agotados,
las conexiones rechazadas y las cabeceras que salen por el cable. Registra todo lo que recibe.
"""

import json
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


@dataclass
class Reply:
    """Una respuesta del guion. `body` en `dict`/`list` se envía como JSON."""

    status: int = 200
    body: bytes | str | dict[str, Any] | list[Any] = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay_ms: int = 0  # espera antes de contestar (para provocar tiempos agotados)
    chunk_size: int = 0  # si > 0, el cuerpo se envía en trozos de este tamaño con `chunk_delay_ms` entre ellos
    chunk_delay_ms: int = 0


@dataclass
class Seen:
    method: str
    path: str
    headers: dict[str, str]  # nombres en minúsculas
    body: bytes


class ScriptedServer:
    def __init__(self) -> None:
        self.script: list[Reply] = []
        self.seen: list[Seen] = []
        self.exhausted = 0  # peticiones recibidas con el guion agotado: en un test es casi siempre un fallo
        self.written = (
            0  # bytes de cuerpo que se llegaron a escribir en el socket (cuenta lo que el cliente dejó de leer)
        )
        self.on_request: Callable[[], None] | None = None
        self._httpd: ThreadingHTTPServer | None = None

    def serve(self, *replies: Reply) -> None:
        self.script = list(replies)
        self.seen.clear()
        self.exhausted = 0

    @property
    def url(self) -> str:
        assert self._httpd is not None
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def start(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def handle_any(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                owner.seen.append(Seen(self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, body))
                if owner.on_request is not None:
                    owner.on_request()
                if owner.script:
                    reply = owner.script.pop(0)
                else:
                    owner.exhausted += 1
                    reply = Reply(500, {"code": "upstream_error", "message": "guion agotado"})
                if reply.delay_ms:
                    time.sleep(reply.delay_ms / 1000)
                payload = reply.body
                if isinstance(payload, dict | list):
                    payload = json.dumps(payload).encode()
                elif isinstance(payload, str):
                    payload = payload.encode()
                try:
                    self.send_response(reply.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.send_header("Connection", "close")
                    for name, value in reply.headers.items():
                        self.send_header(name, value)
                    self.end_headers()
                    if reply.chunk_size:
                        for start in range(0, len(payload), reply.chunk_size):
                            piece = payload[start : start + reply.chunk_size]
                            self.wfile.write(piece)
                            self.wfile.flush()
                            owner.written += len(piece)
                            time.sleep(reply.chunk_delay_ms / 1000)
                    else:
                        self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass  # el cliente ya se fue (p. ej. cortó por tiempo): es lo que se estaba probando

            do_POST = do_GET = do_PUT = do_DELETE = handle_any

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - firma de la clase base
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        # `poll_interval` corto: `shutdown()` espera a un sondeo y el valor por defecto (0,5 s) alargaba cada prueba.
        threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()


def closed_port_url() -> str:
    """URL de un puerto en el que no escucha nadie (conexión rechazada)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"
