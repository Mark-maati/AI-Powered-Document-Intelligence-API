import io
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document as DocxDocument


class ExtractionError(Exception):
    pass


async def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Dispatch to the correct extractor based on file extension.
    Returns raw extracted text.
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(file_bytes)
    elif suffix == ".docx":
        return _extract_docx(file_bytes)
    else:
        raise ExtractionError(f"Unsupported file type: {suffix}")


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text("text") for page in doc]
        doc.close()
        text = "\n\n".join(pages).strip()
        if not text:
            raise ExtractionError("PDF appears to be empty or image-only (no extractable text).")
        return text
    except fitz.FileDataError as e:
        raise ExtractionError(f"Failed to parse PDF: {e}") from e


def _extract_docx(file_bytes: bytes) -> str:
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()
        if not text:
            raise ExtractionError("DOCX file contains no readable paragraphs.")
        return text
    except Exception as e:
        raise ExtractionError(f"Failed to parse DOCX: {e}") from e
