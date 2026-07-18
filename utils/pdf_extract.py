from pypdf import PdfReader
from pypdf.errors import PdfReadError

MIN_USABLE_CHARS = 40  # below this, we assume extraction failed


class PDFExtractionError(Exception):
    # Raised when can't get usable text out of the uploaded PDF.
    pass


def extract_text_from_pdf(file_stream) -> str:
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
            "PDF instead."
        )

    return cleaned


def _normalize_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)