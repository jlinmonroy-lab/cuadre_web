"""VIES simulado (SPEC-W-006 D-05, RES-04): el estado se **calcula**, no se consulta. Nada sale de la aplicación.

`ViesChecker` es el puerto por el que, en el futuro, se enchufaría la consulta real (Should del PRD, fuera de la v1) sin tocar la regla de
validación. `FakeViesChecker` es determinista: un NIF-IVA de la UE que ya pasó el control de `normalize_tax_id` es «válido (simulado)».
"""

from typing import Protocol

from cuadre.clients.types import ViesStatus


class ViesChecker(Protocol):
    def check(self, country: str, tax_id: str) -> ViesStatus:
        """Estado de un NIF-IVA (`tax_id` es la clave compacta, con su prefijo) de un cliente de la UE."""
        ...


class FakeViesChecker:
    def check(self, country: str, tax_id: str) -> ViesStatus:
        return "valid_simulated"
