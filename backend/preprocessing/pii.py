"""PII redaction. Returns redacted text plus a list of what was masked.

Two tiers:
- Always on: regex redaction of emails, phone numbers, URLs/handles, and
  street-address-looking lines.
- If spaCy + en_core_web_sm are installed: PERSON entities are also
  redacted. The app degrades gracefully without spaCy so the demo runs
  with zero model downloads; install spacy for full name redaction.

Whatever this module returns is the ONLY resume text that is ever
persisted. The raw text lives in memory inside a single request and is
discarded.
"""
from __future__ import annotations

import re

try:  # optional dependency
    import spacy
    try:
        _NLP = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except OSError:
        _NLP = None
except ImportError:
    _NLP = None

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?"
                   r"\d{3,4}[\s.-]\d{3,4}(?:[\s.-]\d{2,4})?(?!\d)")
URL = re.compile(r"(?:https?://|www\.|linkedin\.com/\S*|github\.com/\S*)\S+",
                 re.I)
STREET = re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}"
                    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Drive|Dr)"
                    r"\b\.?", re.I)

MASK = "\u2588" * 6  # solid block characters — reads as a redaction bar


def redact(text: str) -> tuple[str, list[str]]:
    fields: list[str] = []
    for label, pattern in (("email", EMAIL), ("phone", PHONE),
                           ("url", URL), ("address", STREET)):
        if pattern.search(text):
            fields.append(label)
            text = pattern.sub(MASK, text)

    if _NLP is not None:
        doc = _NLP(text[:100_000])
        spans = [(e.start_char, e.end_char) for e in doc.ents
                 if e.label_ == "PERSON"]
        if spans:
            fields.append("name")
            out, last = [], 0
            for s, e in spans:
                out.append(text[last:s]); out.append(MASK); last = e
            out.append(text[last:])
            text = "".join(out)

    return text, fields
