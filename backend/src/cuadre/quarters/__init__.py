"""Lectura de lo registrado en un periodo para los borradores de los modelos trimestrales (SPEC-W-008 §3.2 y §5.4; la comparte SPEC-W-009).

Trae de la base de datos las facturas y los gastos de la persona y los convierte en las filas de entrada del dominio puro (`cuadre.tax`). Es un
paquete aparte y no parte de `cuadre.tax` porque necesita el número de factura de `cuadre.invoicing`, y `cuadre.tax` no depende de ese paquete.
"""

from cuadre.quarters.repository import expense_rows, invoice_rows

__all__ = ["expense_rows", "invoice_rows"]
