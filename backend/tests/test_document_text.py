"""Unit tests for document validation and text extraction."""

import io
import zipfile

import pytest

from relationship_network_api.document_text import (
    MAX_DOCUMENT_BYTES,
    DocumentTooLargeError,
    InvalidDocumentError,
    extract_text,
    validate_document,
)


def test_validate_txt_document() -> None:
    document = validate_document(filename="profile.txt", data="你好公司".encode())
    assert document.kind == "txt"
    assert extract_text(document) == "你好公司"


def test_validate_rejects_executable_magic() -> None:
    with pytest.raises(InvalidDocumentError):
        _ = validate_document(filename="evil.txt", data=b"MZ\x90\x00fake")


def test_validate_rejects_unknown_extension() -> None:
    with pytest.raises(InvalidDocumentError):
        _ = validate_document(filename="notes.md", data=b"hello")


def test_validate_rejects_oversized_payload() -> None:
    with pytest.raises(DocumentTooLargeError):
        _ = validate_document(filename="big.txt", data=b"a" * (MAX_DOCUMENT_BYTES + 1))


def test_validate_pdf_magic() -> None:
    data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    document = validate_document(filename="co.pdf", data=data)
    assert document.kind == "pdf"


def test_validate_docx_zip_structure() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    document = validate_document(filename="co.docx", data=buffer.getvalue())
    assert document.kind == "docx"


def test_validate_rejects_pdf_extension_without_magic() -> None:
    with pytest.raises(InvalidDocumentError):
        _ = validate_document(filename="co.pdf", data=b"not a pdf")
