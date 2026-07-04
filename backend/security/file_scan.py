"""Security pre-check. Runs BEFORE any text extraction.

DOCX: a .docx is a zip; the presence of vbaProject.bin (or a .docm/.dotm
extension) means embedded VBA macros -> reject. olevba is used in addition
if installed.

PDF: parse the document structure with pypdf and reject only actions that
actually execute something: /JavaScript actions (document-level name tree,
OpenAction, or annotation actions) and /Launch actions. A bare /OpenAction
is NOT grounds for rejection — LaTeX, Canva, and many resume exporters add
a benign "go to page 1 / fit width" OpenAction, and a naive byte-level
marker scan produces false positives on legitimate resumes (it can even
trip on marker-like byte sequences inside compressed streams). If the PDF
is too malformed to parse, fall back to a byte scan for /JavaScript and
/Launch only.

Anything failing here is written to the audit trail as
status='rejected_unsafe' with a reject_reason, and is never parsed for
text, scored, or persisted.
"""
from __future__ import annotations

import io
import zipfile

try:
    from oletools.olevba import VBA_Parser  # optional
except ImportError:
    VBA_Parser = None

DANGEROUS_ACTIONS = {"/JavaScript", "/Launch"}


def _action_type(obj) -> str | None:
    """Return the /S subtype of a PDF action dict, if any."""
    try:
        obj = obj.get_object()
        s = obj.get("/S")
        return str(s) if s is not None else None
    except Exception:
        return None


def _scan_pdf(data: bytes) -> tuple[bool, str | None]:
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject, DictionaryObject

    try:
        reader = PdfReader(io.BytesIO(data))
        catalog = reader.trailer["/Root"].get_object()

        # 1. Document-level JavaScript name tree.
        names = catalog.get("/Names")
        if names is not None and "/JavaScript" in names.get_object():
            return False, "Document-level JavaScript detected in PDF."

        # 2. OpenAction: reject only if it executes JS or launches a file.
        oa = catalog.get("/OpenAction")
        if oa is not None:
            oa_obj = oa.get_object()
            if isinstance(oa_obj, DictionaryObject):
                t = _action_type(oa_obj)
                if t in DANGEROUS_ACTIONS:
                    return False, f"PDF runs a {t.strip('/')} action on open."
            # An ArrayObject OpenAction is a plain go-to-page destination —
            # benign, common in LaTeX/Canva exports. Allowed.

        # 3. Page and annotation actions.
        for page in reader.pages:
            for key in ("/AA",):
                aa = page.get(key)
                if aa is not None:
                    for act in aa.get_object().values():
                        if _action_type(act) in DANGEROUS_ACTIONS:
                            return False, "Page action executes active content."
            annots = page.get("/Annots")
            if annots is None:
                continue
            annots = annots.get_object()
            if not isinstance(annots, ArrayObject):
                continue
            for a in annots:
                act = a.get_object().get("/A")
                if act is not None and _action_type(act) in DANGEROUS_ACTIONS:
                    return False, ("An annotation in the PDF executes "
                                   "active content.")
        return True, None
    except Exception:
        # Malformed beyond parsing: minimal byte fallback for real threats.
        for marker in (b"/JavaScript", b"/Launch"):
            if marker in data:
                return False, (f"Could not fully parse PDF; {marker.decode()}"
                               " marker present.")
        return True, None


def scan(filename: str, data: bytes) -> tuple[bool, str | None]:
    """Return (is_safe, reject_reason)."""
    name = filename.lower()

    if name.endswith((".docm", ".dotm")):
        return False, "Macro-enabled Word format (.docm/.dotm) is not accepted."

    if name.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if any("vbaproject.bin" in n.lower() for n in z.namelist()):
                    return False, "Embedded VBA macro detected in DOCX."
        except zipfile.BadZipFile:
            return False, "File claims to be DOCX but is not a valid zip."
        if VBA_Parser is not None:
            vp = VBA_Parser(filename, data=data)
            try:
                if vp.detect_vba_macros():
                    return False, "Embedded VBA macro detected (olevba)."
            finally:
                vp.close()

    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            return False, "File claims to be PDF but has no PDF header."
        return _scan_pdf(data)

    return True, None
