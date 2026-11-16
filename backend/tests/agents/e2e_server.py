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

Chat (SPEC-W-004 hito 6): `POST /v1/chat` habla C2 de verdad (SSE) y **cada prueba decide qué dice el agente con marcadores en el último
mensaje del usuario**, los mismos que el simulado (`cuadre.agents.fake.CHAT_MARKER`) más dos solo de este servidor:

    [fixture:<nombre>]        un ejemplo de `contracts/examples/chat/*.sse`, o uno de los de E2E de abajo
    [then:<nombre>]           (opcional) desde la 2.ª petición de esa conversación se sirve este en lugar del primero: «Reintentar»
    [pace=<ms>]               (opcional, hasta 5 s) pausa ANTES de cada frame, también el primero: «Preparando…», el primer token antes del
                              final y tiempo para pulsar «Detener»

Fixtures solo de E2E (no son del contrato; sus frames sí lo cumplen): `hostile` (HTML, Markdown y una palabra de 300 caracteres en el texto, y una
cita con `http:` en vez de `https:`), `plain` (una respuesta que termina en `stop` sin ninguna cita ni herramienta: la nota de «sin fuente», NFR-08;
ningún ejemplo del contrato es así) y `http_unavailable` (503 ANTES del primer frame; el cliente solo reintenta 429 y 502). Sin marcador o con un
nombre desconocido, 400 `invalid_request`. Exige `mcp_url` nulo y ningún `X-User-Token` hasta que SPEC-W-011 dé herramientas al chat. No escribe
nada del mensaje.
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

from cuadre.agents.fake import CHAT_MARKER
from cuadre_contracts import ChatRequest, ChatStreamFrame, ExtractRequest

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "extract"
CHAT_EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "chat"
CONTRACT_VERSION = "1"
MAX_DELAY_MS = 10_000
MAX_PACE_MS = 5_000
MAX_REQUEST_BYTES = 65_536
MAX_CHAT_REQUEST_BYTES = 262_144  # el historial va entero en cada petición de chat
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


# --- Chat -----------------------------------------------------------------------------------------------------------------

PACE_MARKER = re.compile(r"\[pace=(\d{1,5})\]")
THEN_MARKER = re.compile(r"\[then:([a-z0-9_]+)\]")
HOSTILE_WORD = "A" * 300  # sin espacios: si algo no parte la línea, la página desborda


@dataclass(frozen=True)
class ChatMarker:
    first: str
    then: str | None
    pace_ms: int


def parse_chat_marker(text: str) -> ChatMarker | None:
    """Los marcadores del último mensaje del usuario, o `None` si no lleva `[fixture:…]`. Manda el primero de cada tipo."""
    found = CHAT_MARKER.search(text)
    if found is None:
        return None
    then = THEN_MARKER.search(text)
    pace = PACE_MARKER.search(text)
    return ChatMarker(
        found.group(1),
        then.group(1) if then else None,
        min(int(pace.group(1)), MAX_PACE_MS) if pace else 0,
    )


def encode_frame(frame: ChatStreamFrame) -> bytes:
    """Un frame como lo escribe un servidor SSE: `event:`, `data:` y la línea en blanco."""
    return f"event: {frame.root.event}\ndata: {frame.root.data.model_dump_json()}\n\n".encode()


def _hostile_events() -> list[bytes]:
    frames = [
        {
            "event": "token",
            "data": {
                "delta": "<img src=x onerror=\"document.title='hackeado'\"> **negrita** [enlace](javascript:alert(1)) "
            },
        },
        {"event": "token", "data": {"delta": f"`código` <script>alert(1)</script> {HOSTILE_WORD}"}},
        {
            "event": "citation",
            "data": {
                "id": "1",
                "title": "<b>Título en HTML</b>",
                "publisher": "<i>Editor</i>",
                "url": "http://www.boe.es/buscar/act.php?id=BOE-A-2012-14696",  # `http:`, no `https:`: no puede ser un enlace
                "valid_as_of": "2026-09-01",
                "quote": "<script>alert(2)</script>",
            },
        },
        {"event": "done", "data": {"finish_reason": "stop", "trace_id": "trc_e2e_hostile"}},
    ]
    return [encode_frame(ChatStreamFrame.model_validate(frame)) for frame in frames]


def _plain_events() -> list[bytes]:
    frames = [
        {"event": "token", "data": {"delta": "Te lo cuento sin citar ninguna "}},
        {"event": "token", "data": {"delta": "fuente oficial."}},
        {"event": "done", "data": {"finish_reason": "stop", "trace_id": "trc_e2e_plain"}},
    ]
    return [encode_frame(ChatStreamFrame.model_validate(frame)) for frame in frames]


# Respuestas de E2E: nombre → eventos SSE ya codificados, o `(estado, cuerpo)` si el agente falla antes del primer frame.
E2E_CHAT_FIXTURES: dict[str, list[bytes] | tuple[int, bytes]] = {
    "hostile": _hostile_events(),
    "plain": _plain_events(),
    "http_unavailable": (503, error_body("upstream_error", "El servicio de agentes no está disponible.")),
}


def chat_reply(name: str) -> list[bytes] | tuple[int, bytes] | None:
    """Los eventos (uno por elemento, con su línea en blanco) o el fallo HTTP de `name`; `None` si no existe. Los ejemplos del contrato, tal cual."""
    if name in E2E_CHAT_FIXTURES:
        return E2E_CHAT_FIXTURES[name]
    example = CHAT_EXAMPLES / f"{name}.sse"
    if not example.is_file():
        return None
    return [event + b"\n\n" for event in example.read_bytes().split(b"\n\n") if event]


class AgentsServer(ThreadingHTTPServer):
    daemon_threads = True
    # `SO_REUSEADDR` en Windows deja que dos procesos escuchen en el mismo puerto sin ningún error: con otro servidor en el 8765, las
    # peticiones de la API iban al ajeno y esta prueba fallaba sin explicación. Sin él, un puerto ocupado es un `OSError` al arrancar.
    allow_reuse_address = sys.platform != "win32"

    def __init__(self, port: int, api_key: str, *, fetch_timeout_s: float = 10.0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.api_key = api_key
        self.fetch_timeout_s = fetch_timeout_s
        self._reads: dict[str, int] = {}
        self._chats: dict[str, int] = {}
        self.chat_events_sent = 0  # para las pruebas: un cliente que se va debe cortar la respuesta
        self._lock = threading.Lock()

    def next_turn(self, document_id: str) -> int:
        """Cuántas lecturas de este documento ha habido antes de esta (0 la primera)."""
        with self._lock:
            turn = self._reads.get(document_id, 0)
            self._reads[document_id] = turn + 1
            return turn

    def next_chat_turn(self, conversation_id: str) -> int:
        """Cuántas peticiones de esta conversación ha habido antes de esta (0 la primera)."""
        with self._lock:
            turn = self._chats.get(conversation_id, 0)
            self._chats[conversation_id] = turn + 1
            return turn

    def count_chat_event(self) -> None:
        with self._lock:
            self.chat_events_sent += 1

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
        limit = MAX_CHAT_REQUEST_BYTES if self.path == "/v1/chat" else MAX_REQUEST_BYTES
        body = self.rfile.read(min(length, limit + 1))
        if self.path == "/v1/extract":
            status, payload = self._extract(body)
            self._send(status, payload)
        elif self.path == "/v1/chat":
            self._chat(body)
        else:
            self._send(404, error_body("invalid_request", "Ruta desconocida."))

    def _rejected(self) -> tuple[int, bytes] | None:
        """Lo que el agente real exige en toda petición: la clave, la versión del contrato y un identificador."""
        sent_key = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
        if not hmac.compare_digest(sent_key.encode(), self.server.api_key.encode()):
            return 401, error_body("unauthorized", "Clave del servicio de agentes no válida.")
        if self.headers.get("X-Cuadre-Contract-Version") != CONTRACT_VERSION:
            return 400, error_body("invalid_request", "Falta X-Cuadre-Contract-Version: 1.")
        if not self.headers.get("X-Request-Id"):
            return 400, error_body("invalid_request", "Falta X-Request-Id.")
        return None

    def _chat(self, body: bytes) -> None:
        rejected = self._rejected()
        if rejected is None:
            rejected = self._chat_rejected(body)
        if rejected is not None:
            self._send(*rejected)
            return
        request = ChatRequest.model_validate_json(body)  # ya validada en `_chat_rejected`
        marker = parse_chat_marker(request.messages[-1].content)
        if marker is None:
            self._send(400, error_body("invalid_request", "El mensaje no lleva ningún marcador [fixture:<nombre>]."))
            return
        turn = self.server.next_chat_turn(str(request.conversation_id))
        reply = chat_reply(marker.then if turn > 0 and marker.then else marker.first)
        if reply is None:
            self._send(400, error_body("invalid_request", "El marcador nombra un ejemplo que no existe."))
        elif isinstance(reply, tuple):
            self._send(*reply)
        else:
            self._stream(reply, marker.pace_ms)

    def _chat_rejected(self, body: bytes) -> tuple[int, bytes] | None:
        # C2 1.1.0: sin herramientas no hay `mcp_url` ni `X-User-Token` (y con ellas, los dos).
        if self.headers.get("X-User-Token"):
            return 400, error_body("invalid_request", "Este agente de E2E no admite X-User-Token.")
        try:
            if len(body) > MAX_CHAT_REQUEST_BYTES:
                raise ValueError
            request = ChatRequest.model_validate_json(body)
        except (ValidationError, ValueError):
            return 400, error_body("invalid_request", "La petición no cumple el contrato de chat.")
        if request.mcp_url is not None or request.messages[-1].role != "user":
            return 400, error_body("invalid_request", "La petición no cumple el contrato de chat.")
        return None

    def _stream(self, events: list[bytes], pace_ms: int) -> None:
        """Un evento por escritura y vaciado, con la pausa antes de cada uno. Si quien lee se fue, se corta (no sigue durmiendo)."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            for event in events:
                if pace_ms:
                    time.sleep(pace_ms / 1000)
                self.wfile.write(event)
                self.wfile.flush()
                self.server.count_chat_event()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # quien preguntaba ya se fue
        self.close_connection = True

    def _extract(self, body: bytes) -> tuple[int, bytes]:
        rejected = self._rejected()
        if rejected is not None:
            return rejected
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
