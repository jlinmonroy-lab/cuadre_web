"""Tipos del dominio de clientes (SPEC-W-006 §5.3). Inmutables y sin lógica."""

from dataclasses import dataclass
from typing import Literal

Scope = Literal["national", "eu", "non_eu"]
McpScope = Literal["nacional", "ue", "fuera_ue"]
Kind = Literal["business", "individual"]
# `unchecked` existe en el tipo, pero NO lo produce el simulado: queda reservado para la consulta real cuando VIES no responda (D-05).
ViesStatus = Literal["valid_simulated", "unchecked", "not_applicable"]


@dataclass(frozen=True, slots=True)
class RawClient:
    """Lo que llega de la API, sin fiarse de nada: cada campo es `object` y un tipo inesperado es un error de campo, no una excepción."""

    name: object = None
    kind: object = None
    country: object = None
    tax_id: object = None
    address: object = None


@dataclass(frozen=True, slots=True)
class ClientValues:
    """La ficha validada y normalizada, lista para guardarse. El país va en mayúsculas, el ámbito deducido y el identificador es la clave
    compacta (el NIF español sin `ES`, el NIF-IVA con su prefijo, el texto libre en mayúsculas y sin espacios, puntos ni guiones)."""

    name: str
    kind: Kind
    country: str
    scope: Scope
    tax_id: str | None
    address: str | None
    vies_status: ViesStatus


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ClientResult:
    """O los valores, o **todos** los errores a la vez (nunca los dos)."""

    values: ClientValues | None
    errors: tuple[FieldError, ...]
