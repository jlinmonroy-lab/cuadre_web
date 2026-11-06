"""Interfaz del cliente de agentes (ADR-0012, SPEC-W-002 §5.4).

Este repositorio no llama a ningún modelo de lenguaje: todo lo que necesita IA pasa por un `AgentsClient`. `stream_chat` lo añade
SPEC-W-004; añadir un método al Protocol no rompe a quien ya lo implementa mientras no lo use.
"""

from typing import Protocol

from cuadre_contracts import ExtractRequest, ExtractResponse


class AgentsClient(Protocol):
    def extract_invoice(self, request: ExtractRequest, *, request_id: str) -> ExtractResponse:
        """Lee un documento. Lanza `AgentsError` ante cualquier fallo; nunca devuelve datos a medias.

        La respuesta es entrada no confiable: quien la recibe la pasa por `normalize_extraction` antes de guardar nada.
        """
        ...
