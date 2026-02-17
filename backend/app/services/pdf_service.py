from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from tempfile import NamedTemporaryFile

from fpdf import FPDF
from PIL import Image

from app.models import DocumentType, DOCUMENT_TYPE_LABELS

logger = logging.getLogger(__name__)


def generate_two_sided_pdf(
    front_bytes: bytes,
    back_bytes: bytes,
    document_type: DocumentType,
) -> bytes:
    """Generate a PDF with front and back images of a document."""
    title = DOCUMENT_TYPE_LABELS.get(document_type, "Documento")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Fecha: {date_str}", ln=True, align="C")
    pdf.ln(5)

    usable_width = 170  # A4 width (210) - 2*20mm margins
    half_height = 115   # Approximate half page for each image

    # Front side
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Cara Frontal", ln=True, align="L")
    _place_image(pdf, front_bytes, 20, pdf.get_y(), usable_width, half_height)
    pdf.set_y(pdf.get_y() + half_height + 5)

    # Back side
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Cara Trasera", ln=True, align="L")
    _place_image(pdf, back_bytes, 20, pdf.get_y(), usable_width, half_height)

    return bytes(pdf.output())


def generate_single_page_pdf(
    image_bytes: bytes,
    document_type: DocumentType,
) -> bytes:
    """Generate a PDF with a single document page."""
    title = DOCUMENT_TYPE_LABELS.get(document_type, "Documento")
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Fecha: {date_str}", ln=True, align="C")
    pdf.ln(10)

    usable_width = 170
    max_height = 230

    _place_image(pdf, image_bytes, 20, pdf.get_y(), usable_width, max_height)

    return bytes(pdf.output())


def is_valid_pdf(data: bytes) -> bool:
    """Check if the bytes represent a valid PDF."""
    return data[:5] == b"%PDF-"


def _place_image(
    pdf: FPDF,
    image_bytes: bytes,
    x: float,
    y: float,
    max_w: float,
    max_h: float,
) -> None:
    """Place an image in the PDF, scaling to fit within max dimensions."""
    try:
        img = Image.open(BytesIO(image_bytes))
        img_w, img_h = img.size

        # Calculate scale to fit within bounds
        scale_w = max_w / img_w
        scale_h = max_h / img_h
        scale = min(scale_w, scale_h)

        final_w = img_w * scale
        final_h = img_h * scale

        # Center horizontally
        x_offset = x + (max_w - final_w) / 2

        # Write to a temp file for fpdf2
        with NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(tmp, format="JPEG", quality=92)
            tmp_path = tmp.name

        pdf.image(tmp_path, x=x_offset, y=y, w=final_w, h=final_h)

        import os
        os.unlink(tmp_path)

    except Exception as e:
        logger.error("Failed to place image in PDF: %s", e)
        pdf.set_font("Helvetica", "I", 10)
        pdf.text(x, y + 10, "[Error al procesar imagen]")
