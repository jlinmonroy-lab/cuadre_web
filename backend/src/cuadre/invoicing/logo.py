"""Guarda de dimensiones del logo (SPEC-W-007 §5.1.6, B.1-A). Python puro.

Un PNG de 269 KiB puede tener 88 Mpx y costar 872 MiB y 2 s al dibujarlo. Las dimensiones se leen **sin decodificar los píxeles**
(`Image.open(...).size`, 0,2 ms, en el hito 4) y esta regla decide si el logo se dibuja: si no cabe, la factura sale sin él.
"""

from cuadre.invoicing.limits import LOGO_MAX_PIXELS


def logo_fits(width_px: object, height_px: object) -> bool:
    for side in (width_px, height_px):
        if isinstance(side, bool) or not isinstance(side, int) or side < 1:
            return False
    assert isinstance(width_px, int) and isinstance(height_px, int)
    return width_px * height_px <= LOGO_MAX_PIXELS
