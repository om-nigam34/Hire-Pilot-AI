"""
pdf_extract.py
--------------
Turns an uploaded resume PDF into plain text so the rest of the pipeline
(similarity scoring, LLM calls) can work with it as a normal string.

We use pypdf because it's dependency-light and good enough for text-based
resumes. If someone uploads a scanned/image-only PDF, pypdf will return
little or no text - we detect that case and raise a clear error instead
of silently sending an empty resume through the pipeline.
"""

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MIN_USABLE_CHARS = 40  # below this, we assume extraction failed (e.g. scanned PDF)


class PDFExtractionError(Exception):
    """Raised when we can't get usable text out of the uploaded PDF."""
    pass


def extract_text_from_pdf(file_stream) -> str:
    """
    Extract plain text from a PDF file-like object (e.g. a Flask
    `request.files['resume']` stream).

    Args:
        file_stream: a file-like object opened in binary mode.

    Returns:
        The extracted text, whitespace-normalized.

    Raises:
        PDFExtractionError: if the file isn't a readable PDF, or contains
        no usable text (e.g. it's a scanned image with no OCR layer).
    """
    try:
        reader = PdfReader(file_stream)
    except PdfReadError as exc:
        raise PDFExtractionError(
            "That file doesn't look like a valid PDF. Please export your "
            "resume as a standard PDF and try again."
        ) from exc

    if reader.is_encrypted:
        raise PDFExtractionError(
            "This PDF is password-protected. Please remove the password "
            "and upload it again."
        )

    pages_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages_text.append(page_text)

    full_text = "\n".join(pages_text)
    cleaned = _normalize_whitespace(full_text)

    if len(cleaned) < MIN_USABLE_CHARS:
        raise PDFExtractionError(
            "We couldn't find readable text in that PDF. If it's a scanned "
            "image or a design-heavy template, try exporting a text-based "
            "PDF instead (e.g. straight from Word/Google Docs)."
        )

    return cleaned


def _normalize_whitespace(text: str) -> str:
    """Collapse repeated blank lines/spaces so the LLM prompt isn't bloated
    with layout artifacts from column-based resume templates."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)