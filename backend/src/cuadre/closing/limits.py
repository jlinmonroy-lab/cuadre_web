"""Constantes del cierre mensual (SPEC-W-012 §5.1). Un solo sitio: cambiar una es cambiar esta línea y su prueba."""

# El primer año que admite la base de datos (`monthly_closings_year_range`) y el que admiten los periodos del 303 y del 130.
FIRST_YEAR = 2000
LAST_YEAR = 9998
# Cuántos meses ya terminados recalcula cada ejecución del job para detectar documentos atrasados (D-05).
WINDOW_MONTHS = 12
MAX_WINDOW_MONTHS = 120
# Más facturas y gastos que esto en una ventana no caben en una ejecución: la persona falla (`failed`) y las demás siguen (§6). El repositorio pide una
# fila por encima del tope para que el dominio vea que se pasa y falle en vez de callar, como el modelo 130.
CLOSING_MAX_DOCUMENTS = 20_000
