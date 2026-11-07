"""AC-14, AC-15 · Tipo, tamaño y firma del logo (T5-06, Anexo B.1: Storage no mira el contenido)."""

import struct
import zlib

import pytest

from cuadre.profile import declared_problem, extension_for, signature_matches

MIB = 1_048_576


def png_head() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))


PNG = png_head()[:12]  # lo que lee `Range: bytes=0-11`
JPEG = bytes.fromhex("ffd8ffe000104a46494600" + "01")
WEBP = b"RIFF" + struct.pack("<I", 26) + b"WEBP"


@pytest.mark.parametrize(("mime", "ext"), [("image/png", "png"), ("image/jpeg", "jpg"), ("image/webp", "webp")])
def test_the_three_allowed_types(mime: str, ext: str) -> None:
    assert extension_for(mime) == ext
    assert declared_problem(mime, 1) is None


@pytest.mark.parametrize(
    "mime",
    [
        "image/svg+xml",
        "image/gif",
        "text/plain",
        "application/pdf",
        "image/png; charset=binary",
        "IMAGE/PNG",
        " image/png",
        "",
        None,
        5,
        b"image/png",
    ],
)
def test_every_other_type_is_unsupported(mime: object) -> None:
    assert extension_for(mime) is None
    assert declared_problem(mime, 100) == "unsupported_type"


def test_one_mebibyte_is_fine_and_one_byte_more_is_not() -> None:
    assert declared_problem("image/png", MIB) is None
    assert declared_problem("image/png", MIB + 1) == "too_large"
    assert declared_problem("image/webp", 10 * MIB) == "too_large"
    assert declared_problem("image/png", 1) is None


@pytest.mark.parametrize("size", [0, -1, None, "100", 1.5, True, False])
def test_a_size_that_is_not_a_positive_integer_is_invalid(size: object) -> None:
    assert declared_problem("image/png", size) == "invalid"


def test_the_type_is_judged_before_the_size() -> None:
    assert declared_problem("image/svg+xml", 10 * MIB) == "unsupported_type"
    assert declared_problem("image/svg+xml", 0) == "unsupported_type"


def test_real_headers_match_their_type() -> None:
    assert signature_matches("image/png", PNG)
    assert signature_matches("image/jpeg", JPEG)
    assert signature_matches("image/webp", WEBP)
    assert signature_matches("image/png", PNG + b"\x00" * 100)
    assert signature_matches("image/png", bytearray(PNG))


def test_a_header_declared_as_another_type_does_not_match() -> None:
    assert not signature_matches("image/jpeg", PNG)
    assert not signature_matches("image/webp", PNG)
    assert not signature_matches("image/png", JPEG)
    assert not signature_matches("image/png", WEBP)
    assert not signature_matches("image/webp", JPEG)


def test_text_renamed_as_an_image_does_not_match() -> None:
    text = b"esto no es una imagen"
    for mime in ("image/png", "image/jpeg", "image/webp"):
        assert not signature_matches(mime, text)
        assert not signature_matches(mime, b"")


def test_png_needs_all_eight_bytes_and_jpeg_all_three() -> None:
    assert not signature_matches("image/png", PNG[:7])
    assert signature_matches("image/png", PNG[:8])
    assert not signature_matches("image/jpeg", JPEG[:2])
    assert signature_matches("image/jpeg", JPEG[:3])


def test_webp_needs_riff_the_size_and_webp() -> None:
    assert not signature_matches("image/webp", b"RIFF" + b"\x1a\x00\x00\x00" + b"WEB")  # 11 bytes
    assert not signature_matches("image/webp", b"RIFF" + b"\x1a\x00\x00\x00" + b"WAVE")  # RIFF de audio
    assert not signature_matches("image/webp", b"RIFX" + b"\x1a\x00\x00\x00" + b"WEBP")
    assert not signature_matches("image/webp", b"RIFF" + b"WEBP" + b"\x00\x00\x00\x00")  # WEBP en el sitio equivocado
    assert signature_matches("image/webp", b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP")


@pytest.mark.parametrize("head", [None, "RIFF", 12, ["RIFF"], object()])
def test_a_head_that_is_not_bytes_never_matches(head: object) -> None:
    for mime in ("image/png", "image/jpeg", "image/webp"):
        assert not signature_matches(mime, head)


@pytest.mark.parametrize("mime", ["image/svg+xml", "image/gif", None, "image/png "])
def test_an_unknown_type_never_matches(mime: object) -> None:
    assert not signature_matches(mime, PNG)
    assert not signature_matches(mime, WEBP)
