"""AC-16, AC-19 · Ruta del PDF en el bucket `invoices` (SPEC-W-007 §5.2, D-03 y D-10, B.1-C)."""

import hashlib

import pytest

from cuadre.invoicing import invoice_pdf_path, pdf_path_owner

OWNER = "a1000000-0000-4000-8000-000000000001"
INVOICE = "1111aaaa-2222-4333-8444-5555bbbbcccc"  # con letras: su versión en mayúsculas es distinta
SHA = hashlib.sha256(b"un pdf cualquiera").hexdigest()


def test_the_path_is_owner_slash_invoice_dash_hash_prefix() -> None:
    assert invoice_pdf_path(OWNER, INVOICE, SHA) == f"{OWNER}/{INVOICE}-{SHA[:16]}.pdf"
    assert len(SHA) == 64


def test_the_same_content_always_gives_the_same_path_and_another_content_another() -> None:
    other = hashlib.sha256(b"otro pdf").hexdigest()
    assert invoice_pdf_path(OWNER, INVOICE, SHA) == invoice_pdf_path(OWNER, INVOICE, SHA)
    assert invoice_pdf_path(OWNER, INVOICE, SHA) != invoice_pdf_path(OWNER, INVOICE, other)


@pytest.mark.parametrize(
    ("owner", "invoice", "sha"),
    [
        (OWNER.upper(), INVOICE, SHA),
        (OWNER, INVOICE.upper(), SHA),
        (OWNER, INVOICE, SHA.upper()),
        (OWNER[:-1], INVOICE, SHA),
        (OWNER, INVOICE + "0", SHA),
        (OWNER, INVOICE, SHA[:-1]),
        (OWNER, INVOICE, SHA + "0"),
        ("", INVOICE, SHA),
        (OWNER, "no-uuid", SHA),
        (OWNER, INVOICE, "g" * 64),
        (OWNER + "/x", INVOICE, SHA),
        (OWNER, "../" + INVOICE, SHA),
        (None, INVOICE, SHA),
    ],
)
def test_anything_that_is_not_a_lowercase_uuid_or_sha256_is_a_programming_error(owner, invoice, sha) -> None:
    with pytest.raises(ValueError):
        invoice_pdf_path(owner, invoice, sha)  # type: ignore[arg-type]


def test_the_owner_of_a_valid_path_is_its_folder() -> None:
    assert pdf_path_owner(invoice_pdf_path(OWNER, INVOICE, SHA)) == OWNER


@pytest.mark.parametrize(
    "path",
    [
        "",
        "not-a-uuid/x.pdf",
        f"{OWNER}/factura.pdf",
        f"{OWNER}/{INVOICE}.pdf",  # sin el prefijo de la huella
        f"{OWNER}/{INVOICE}-{SHA[:16]}.png",
        f"{OWNER}/{INVOICE}-{SHA[:15]}.pdf",
        f"{OWNER}/{INVOICE}-{SHA[:17]}.pdf",
        f"{OWNER}/sub/{INVOICE}-{SHA[:16]}.pdf",
        f"{OWNER.upper()}/{INVOICE}-{SHA[:16]}.pdf",
        f"{OWNER}/{INVOICE}-{SHA[:16].upper()}.pdf",
        f"/{OWNER}/{INVOICE}-{SHA[:16]}.pdf",
        f"{OWNER}/{INVOICE}-{SHA[:16]}.pdf/",
        f"{OWNER}/{INVOICE}-{SHA[:16]}.pdf\n",
        f"{OWNER}\\{INVOICE}-{SHA[:16]}.pdf",
        None,
        5,
    ],
)
def test_a_path_with_another_shape_has_no_owner_and_never_raises(path) -> None:
    assert pdf_path_owner(path) is None  # type: ignore[arg-type]
