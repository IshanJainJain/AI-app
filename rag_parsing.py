from io import BytesIO
from pathlib import Path

from rag_config import SUPPORTED_DOCUMENT_EXTENSIONS


def supported_document_types() -> str:
    return ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))


def parse_document(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        return parse_pdf(content)
    if suffix == ".docx":
        return parse_docx(content)
    raise ValueError(f"Unsupported document type. Use: {supported_document_types()}")


def parse_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to ingest PDF documents.") from exc

    reader = PdfReader(BytesIO(content))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def parse_docx(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Install python-docx to ingest DOCX documents.") from exc

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
