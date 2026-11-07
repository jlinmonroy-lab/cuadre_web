"""T5-03 · Las constantes que la base repetirá en CHECK (hito 2) están fijadas aquí: si cambia una, esta prueba obliga a cambiar la migración."""

from datetime import date
from decimal import Decimal

from cuadre.profile import limits


def test_text_limits_are_the_ones_in_the_spec() -> None:
    assert (limits.LEGAL_NAME_MIN, limits.LEGAL_NAME_MAX) == (2, 200)
    assert (limits.FISCAL_ADDRESS_MIN, limits.FISCAL_ADDRESS_MAX) == (5, 300)
    assert limits.ACTIVITY_MAX == 200
    assert (
        limits.IAE_RAW.pattern == "[0-9A-Za-z. -]{1,20}"
    )  # `CHECK (iae_epigraph ~ '^[0-9A-Za-z. -]+$')` y longitud ≤ 20


def test_retention_and_regime() -> None:
    assert (Decimal(7), Decimal(15)) == limits.IRPF_RATES  # `CHECK (irpf_rate IN (7, 15))`
    assert limits.REDUCED_YEARS_AFTER_START == 2
    assert limits.REGIME == "general"  # `CHECK (vat_regime = 'general')`
    assert Decimal(100) == limits.HOME_PCT_MAX
    assert date(1950, 1, 1) == limits.EARLIEST_START


def test_the_decimal_pattern_is_ascii_only() -> None:
    """`\\d` casa también `٧` (B.1, bloque C): el patrón usa `[0-9]`."""
    assert limits.DECIMAL_RAW.pattern == r"[0-9]{1,3}(\.[0-9]{1,2})?"
    assert "\\d" not in limits.DECIMAL_RAW.pattern


def test_series_limits_are_the_ones_the_database_check_will_repeat() -> None:
    """El CHECK de `invoice_series.code` es `^[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?$` (probado en PostgreSQL en el spike)."""
    assert limits.SERIES_CODE.pattern == "[A-Z0-9]([A-Z0-9-]{0,6}[A-Z0-9])?"
    assert limits.SERIES_RAW.pattern == "[0-9A-Za-z-]{1,8}"
    assert limits.SERIES_CODE_MAX == 8
    assert limits.SERIES_DESCRIPTION_MAX == 80
    assert (limits.SERIES_FIRST_NUMBER_MIN, limits.SERIES_FIRST_NUMBER_MAX) == (1, 999_999)


def test_logo_limits_are_the_bucket_ones() -> None:
    assert limits.LOGO_MAX_BYTES == 1_048_576  # `file_size_limit` del bucket `logos`
    assert limits.LOGO_TYPES == {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}  # `allowed_mime_types`
    assert limits.LOGO_HEAD_BYTES == 12
    assert limits.PNG_SIGNATURE == b"\x89PNG\r\n\x1a\n"
    assert limits.JPEG_SIGNATURE == b"\xff\xd8\xff"


def test_forbidden_text_categories() -> None:
    assert {"Cc", "Cf", "Zl", "Zp"} == limits.FORBIDDEN_CATEGORIES
