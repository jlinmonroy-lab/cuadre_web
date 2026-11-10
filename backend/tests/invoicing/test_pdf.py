"""AC-16, AC-17, T7-09, T7-10 · El contenido del PDF y que sea reproducible (SPEC-W-007 §5.1.6, D-10, D-11, B.1-A).

El contenido se comprueba extrayendo el texto con `pypdf` (solo de pruebas). Los mismos datos dan los mismos bytes: por eso la huella guardada manda
al descargar. Todo dato de la fila (las copias congeladas del emisor y del cliente) aparece y nada más: ni la hora, ni un identificador aleatorio.
"""

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from cuadre.invoicing.limits import QR_CAPTION
from cuadre.invoicing.pdf import render_invoice_pdf
from cuadre.tax import NOTE_NON_EU, NOTE_REVERSE_CHARGE
from tests.invoicing.pdf_support import ISSUER_IBAN, metadata_of, pages_of, pdf_invoice, rectifying, text_of


def test_an_ordinary_invoice_carries_every_datum() -> None:
    text = text_of(render_invoice_pdf(pdf_invoice()))
    for expected in (
        "FACTURA",
        "Número 2026-001",
        "Fecha de expedición",
        "2 de marzo de 2026",
        "EMISOR",
        "Alicia Demo (sintético)",
        "NIF: 12345678Z",
        "Calle Ficticia 1, 00000 Ciudad de Pruebas",
        "CLIENTE",
        "Estudio Norte S.L.",
        "NIF/NIF-IVA: B00000018",
        "Avenida Inventada 4, 28000 Madrid",
        "CONCEPTO",
        "Diseño de identidad visual",
        "Base imponible",
        "1.200,00 €",
        "IVA (21 %)",
        "252,00 €",
        "Retención IRPF (15 %)",
        "-180,00 €",
        "TOTAL",
        "1.272,00 €",
        "Forma de pago: transferencia a ES36 0000 0000 0500 0000 0001",
        QR_CAPTION,
    ):
        assert expected in text, expected
    assert "FACTURA RECTIFICATIVA" not in text and "Motivo" not in text and "rectificativa de la" not in text


def test_the_qr_caption_says_it_is_simulated_and_the_verifactu_phrase_never_appears() -> None:
    """AC-17: «QR VeriFactu simulado, no remitido a la AEAT»; ni «VERI*FACTU» ni «verificable en la sede electrónica»."""
    for invoice in (pdf_invoice(), rectifying()):
        text = text_of(render_invoice_pdf(invoice))
        assert "QR VeriFactu simulado, no remitido a la AEAT" in text
        assert "VERI*FACTU" not in text and "verificable en la sede" not in text
        assert "http" not in text  # el QR no apunta a ninguna URL


def test_the_issuer_iban_is_optional() -> None:
    text = text_of(render_invoice_pdf(pdf_invoice(issuer_iban=None)))
    assert "Forma de pago" not in text and ISSUER_IBAN not in text


def test_a_client_without_tax_id_has_no_nif_line() -> None:
    text = text_of(render_invoice_pdf(pdf_invoice(client_tax_id=None)))
    assert "NIF/NIF-IVA" not in text and "NIF: 12345678Z" in text


def test_an_invoice_without_vat_says_so_and_has_no_retention_line() -> None:
    text = text_of(
        render_invoice_pdf(
            pdf_invoice(
                vat_rate=Decimal("0.00"),
                vat_cents=0,
                irpf_rate=Decimal("0.00"),
                irpf_cents=0,
                base_cents=150_000,
                total_cents=150_000,
                legal_note=NOTE_REVERSE_CHARGE,
            )
        )
    )
    assert "Sin IVA" in text and "IVA (" not in text
    assert "Retención" not in text
    assert "1.500,00 €" in text
    assert NOTE_REVERSE_CHARGE in text


@pytest.mark.parametrize("note", [NOTE_REVERSE_CHARGE, NOTE_NON_EU])
def test_the_legal_note_appears_exactly(note: str) -> None:
    text = " ".join(text_of(render_invoice_pdf(pdf_invoice(legal_note=note))).split())
    assert note in text


def test_there_is_no_legal_note_when_there_is_none() -> None:
    text = text_of(render_invoice_pdf(pdf_invoice(legal_note=None)))
    assert "Inversión del sujeto pasivo" not in text and "art. 69" not in text


@pytest.mark.parametrize(("rate", "text"), [("10.00", "IVA (10 %)"), ("4.00", "IVA (4 %)"), ("21.00", "IVA (21 %)")])
def test_the_vat_rate_is_shown(rate: str, text: str) -> None:
    assert text in text_of(render_invoice_pdf(pdf_invoice(vat_rate=Decimal(rate))))


def test_the_retention_rate_is_shown() -> None:
    assert "Retención IRPF (7 %)" in text_of(render_invoice_pdf(pdf_invoice(irpf_rate=Decimal("7.00"))))


# --- Rectificativa ------------------------------------------------------------------------------------------------------------------


def test_a_rectification_names_what_it_rectifies_and_why_with_signed_amounts() -> None:
    text = " ".join(text_of(render_invoice_pdf(rectifying())).split())
    for expected in (
        "FACTURA RECTIFICATIVA",
        "Número R-2026-001",
        "9 de marzo de 2026",
        "Factura rectificativa de la 2026-001 de 2 de marzo de 2026",
        "Motivo: Importe mal calculado",
        "-200,00 €",
        "IVA (21 %)",
        "-42,00 €",
        "30,00 €",  # la retención se devuelve: resta una retención negativa
        "-212,00 €",
    ):
        assert expected in text, expected


def test_a_rectification_with_a_sign_in_the_total_only_shows_the_minus_where_it_belongs() -> None:
    text = text_of(render_invoice_pdf(rectifying()))
    assert "-30,00 €" not in text  # la retención negativa se muestra positiva (resta de nuevo)


# --- Metadatos y reproducibilidad --------------------------------------------------------------------------------------------------


def test_the_metadata_is_fixed_and_has_no_personal_data() -> None:
    meta = metadata_of(render_invoice_pdf(pdf_invoice()))
    assert meta["/Title"] == "Factura 2026-001"
    assert meta["/Creator"] == meta["/Author"] == "cuadre-web"
    flat = " ".join(meta.values())
    for secret in ("Alicia", "12345678Z", "Estudio Norte", "B00000018", ISSUER_IBAN):
        assert secret not in flat, secret


def test_the_creation_date_is_the_fixed_one_not_today() -> None:
    """`Canvas(invariant=1)` fija la fecha de creación: la de hoy cambiaría los bytes cada día."""
    assert metadata_of(render_invoice_pdf(pdf_invoice()))["/CreationDate"].startswith("D:2000")


def test_the_same_data_gives_the_same_bytes_every_time() -> None:
    invoice = pdf_invoice()
    first = render_invoice_pdf(invoice)
    digests = {hashlib.sha256(render_invoice_pdf(invoice)).hexdigest() for _ in range(5)}
    assert digests == {hashlib.sha256(first).hexdigest()}
    assert render_invoice_pdf(rectifying()) == render_invoice_pdf(rectifying())


@pytest.mark.parametrize(
    "changes",
    [
        {"display_number": "2026-002"},
        {"concept": "Otro concepto"},
        {"total_cents": 127_201},
        {"issue_date": date(2026, 3, 3)},
        {"client_name": "Otro cliente S.L."},
        {"issuer_iban": None},
    ],
)
def test_other_data_gives_other_bytes(changes: dict[str, object]) -> None:
    assert render_invoice_pdf(pdf_invoice(**changes)) != render_invoice_pdf(pdf_invoice())  # type: ignore[arg-type]


# --- Texto que Helvetica no dibuja y límites ----------------------------------------------------------------------------------------


def test_letters_helvetica_lacks_never_become_black_squares() -> None:
    text = text_of(
        render_invoice_pdf(
            pdf_invoice(
                client_name="Łukasz Şahin Sp. z o.o.",
                client_address="ul. Złota 5, 00-120 Warszawa",
                concept="Диза́йн 日本語 😀 y diseño",
            )
        )
    )
    assert "■" not in text
    assert "Lukasz Sahin Sp. z o.o." in text and "ul. Zlota 5" in text
    assert "diseño" in text and "??" in text  # cirílico y chino marcados con «?»


def test_the_longest_invoice_still_fits_one_page_and_well_under_the_bucket_limit() -> None:
    long = "palabra " * 37  # 296 caracteres
    invoice = rectifying(
        issuer_name="N" * 200,
        issuer_address=("Calle Muy Larga " * 19)[:300],
        client_name="C" * 200,
        client_address=("Avenida Interminable " * 15)[:300],
        concept=long,
        rectification_reason=long,
        legal_note=NOTE_NON_EU,
        issuer_iban="ES3600000000050000000001",
        base_cents=-9_999_999_999,
        vat_cents=-2_099_999_999,
        irpf_cents=-1_499_999_999,
        total_cents=-9_999_999_999 - 2_099_999_999 + 1_499_999_999,
    )
    pdf = render_invoice_pdf(invoice)
    assert pages_of(pdf) == 1
    assert len(pdf) < 1_048_576
    assert "-99.999.999,99 €" in text_of(pdf)


def test_a_300_character_concept_is_wrapped_in_several_lines_and_nothing_is_lost() -> None:
    concept = " ".join(f"término{n:02d}" for n in range(30))[:300]
    text = " ".join(text_of(render_invoice_pdf(pdf_invoice(concept=concept))).split())
    for n in range(28):
        assert f"término{n:02d}" in text


def test_a_line_break_in_the_concept_is_kept_as_a_new_line() -> None:
    text = text_of(render_invoice_pdf(pdf_invoice(concept="Primera línea\nSegunda línea")))
    assert "Primera línea\nSegunda línea" in text  # dos renglones, no uno


def test_a_typical_pdf_is_small() -> None:
    assert len(render_invoice_pdf(pdf_invoice())) < 20_000
