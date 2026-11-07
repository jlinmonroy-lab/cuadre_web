"""`Validation`: el resultado de las comprobaciones tal como lo ve el cliente (SPEC-W-003 §5.3).

Módulo hoja a propósito: lo importan `documents.models` (para `Document.validation`) y `expenses.models`, y no importa ninguno de los dos.
Es el espejo de `cuadre.validators.Validation` (dataclasses puras) hecho con Pydantic, que es lo que entiende OpenAPI.
"""

from typing import Literal

from pydantic import BaseModel

from cuadre.validators import CheckCode, ExpenseCategory, WarningCode


class CheckItem(BaseModel):
    code: CheckCode
    label: str
    status: Literal["ok", "failed"]
    detail: str | None


class WarningItem(BaseModel):
    code: WarningCode
    message: str


class Preview(BaseModel):
    supplier_scope: Literal["national", "eu"] | None
    deductible_vat: bool
    deductible_note: str | None
    suggested_category: ExpenseCategory


class Validation(BaseModel):
    can_register: bool
    requires_acknowledgement: bool
    checks: list[CheckItem]
    warnings: list[WarningItem]
    preview: Preview
