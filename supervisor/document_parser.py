"""
Document parsing helpers for Telegram attachments.
"""

from __future__ import annotations

from typing import Optional


TEXT_EXTENSIONS = (
    ".txt", ".md", ".csv", ".json", ".log",
    ".py", ".js", ".ts", ".html", ".xml",
    ".yaml", ".yml", ".toml",
)


def extract_document_text(raw_bytes: bytes, mime_type: str, filename: str) -> str:
    """
    Extract text from supported document formats (text/* and PDF).
    Returns a human-readable fallback message for unsupported formats/errors.
    """
    mime_type = str(mime_type or "")
    filename = str(filename or "unknown")
    lower_name = filename.lower()

    is_text = mime_type.startswith("text/") or lower_name.endswith(TEXT_EXTENSIONS)
    is_pdf = mime_type == "application/pdf" or lower_name.endswith(".pdf")

    if is_text:
        try:
            return raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - defensive fallback
            return f"[Ошибка чтения файла: {exc}]"

    if is_pdf:
        extracted = _extract_pdf_text(raw_bytes)
        if extracted is None:
            return (
                f"[PDF {filename!r} получен, но не удалось извлечь текст. "
                "Установите pdfminer.six или pypdf / PyPDF2.]"
            )
        if not extracted.strip():
            return (
                f"[PDF {filename!r} получен, но текст пустой — "
                f"возможно, это скан. Размер: {len(raw_bytes)} байт]"
            )
        return extracted

    ext = filename.rsplit(".", 1)[-1] if "." in filename else mime_type
    return f"[Файл {filename!r} получен, но формат {ext!r} не поддерживается для чтения текста]"


def make_document_block(
    filename: str,
    extracted_text: str,
    max_chars: int = 50_000,
) -> str:
    """
    Build text block injected into the LLM prompt for a file attachment.
    """
    text = extracted_text or f"[Файл {filename!r} получен, но текст не удалось извлечь]"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... текст обрезан ...]"
    return f"[Файл: {filename}]\n{text}"


def _extract_pdf_text(raw_bytes: bytes) -> Optional[str]:
    import io

    # 1) pdfminer.six (best layout reconstruction)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text
        return pdfminer_extract_text(io.BytesIO(raw_bytes))
    except Exception:
        pass

    # 2) pypdf (modern actively maintained fork)
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        pass

    # 3) PyPDF2 (legacy fallback)
    try:
        import PyPDF2  # type: ignore
        reader = PyPDF2.PdfReader(io.BytesIO(raw_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        pass

    return None
