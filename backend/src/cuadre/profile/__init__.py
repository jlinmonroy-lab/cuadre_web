"""Dominio del perfil y de las series de facturación (SPEC-W-005, RF-004, US-007): Python puro, sin base de datos, sin red y sin reloj propio.

La API lo usa para validar lo que escribe la persona y decir qué falta para emitir. El NIF y el IBAN los normaliza `cuadre.validators`
(la única puerta a `python-stdnum`); aquí no se importa `stdnum`.
"""

from cuadre.profile.logo import declared_problem, extension_for, signature_matches
from cuadre.profile.rules import completeness, format_rate, retention, validate_profile
from cuadre.profile.series import (
    normalize_series_code,
    validate_code,
    validate_description,
    validate_first_number,
    validate_series,
    year_series_code,
)
from cuadre.profile.types import (
    Completeness,
    FieldError,
    Missing,
    ProfileResult,
    ProfileValues,
    RawProfile,
    Retention,
    SeriesResult,
    StoredIdentity,
)

__all__ = [
    "Completeness",
    "FieldError",
    "Missing",
    "ProfileResult",
    "ProfileValues",
    "RawProfile",
    "Retention",
    "SeriesResult",
    "StoredIdentity",
    "completeness",
    "declared_problem",
    "extension_for",
    "format_rate",
    "normalize_series_code",
    "retention",
    "signature_matches",
    "validate_code",
    "validate_description",
    "validate_first_number",
    "validate_profile",
    "validate_series",
    "year_series_code",
]
