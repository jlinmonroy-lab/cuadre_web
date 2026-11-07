"""Gastos registrados (SPEC-W-003, hito 3): validar una lectura con `cuadre.validators` y registrarla con las funciones `app.*`.

Este paquete no importa nada de `cuadre.documents.service` (lo importa a él), y `__init__` queda vacío a propósito: así `documents` y
`expenses` se pueden referir sin ciclos (`documents.models` -> `expenses.validation_models`; `expenses.*` -> `documents.repository`).
"""
