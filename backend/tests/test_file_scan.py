"""Security-scan guarantees.

These back the product's other core claim: unsafe files are rejected BEFORE
they are ever parsed. We exercise both the happy path (clean files pass) and
the threat paths (macros / executable actions / spoofed files are rejected).
No dataset needed — every fixture is built in memory here.
"""
import io
import zipfile

from security.file_scan import scan


# ----------------------------------------------------------------- helpers
def _clean_pdf_bytes() -> bytes:
    """A minimal, valid, action-free PDF."""
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _clean_docx_bytes() -> bytes:
    import docx
    d = docx.Document()
    d.add_paragraph("Senior accountant. General ledger, auditing, Excel.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _docx_with_macro_bytes() -> bytes:
    """A valid zip carrying the VBA payload marker a real macro doc would."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/vbaProject.bin", b"\x00\x01macro payload\x02")
    return buf.getvalue()


# ------------------------------------------------------------- happy paths
def test_clean_pdf_passes():
    safe, reason = scan("resume.pdf", _clean_pdf_bytes())
    assert safe is True
    assert reason is None


def test_clean_docx_passes():
    safe, reason = scan("resume.docx", _clean_docx_bytes())
    assert safe is True


def test_plain_txt_passes():
    safe, reason = scan("resume.txt", b"just some resume text")
    assert safe is True


# ------------------------------------------------------------ threat paths
def test_docm_extension_rejected():
    safe, reason = scan("resume.docm", b"anything")
    assert safe is False
    assert "macro-enabled" in reason.lower()


def test_docx_with_vba_macro_rejected():
    safe, reason = scan("resume.docx", _docx_with_macro_bytes())
    assert safe is False
    assert "macro" in reason.lower()


def test_docx_that_is_not_a_zip_rejected():
    safe, reason = scan("resume.docx", b"this is not a zip file")
    assert safe is False
    assert "zip" in reason.lower()


def test_pdf_without_header_rejected():
    safe, reason = scan("resume.pdf", b"MZ not a pdf at all")
    assert safe is False
    assert "header" in reason.lower()


def test_pdf_with_javascript_rejected():
    """Unparseable-but-hostile PDF: falls back to the byte scan and rejects."""
    evil = b"%PDF-1.4 /OpenAction /JavaScript (app.alert(1))"
    safe, reason = scan("evil.pdf", evil)
    assert safe is False
    assert "javascript" in reason.lower()


def test_pdf_with_launch_action_rejected():
    evil = b"%PDF-1.4 /Launch (/bin/sh)"
    safe, reason = scan("evil.pdf", evil)
    assert safe is False
    assert "launch" in reason.lower()
