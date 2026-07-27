"""PII redaction guarantees.

These back the product's core privacy claim: whatever `redact()` returns is
the only resume text that is ever persisted, so it must actually remove the
sensitive values and report honestly what it removed. No dataset needed.
"""
import pytest

from preprocessing.pii import MASK, redact
from preprocessing import pii


def test_email_is_removed_and_reported():
    redacted, fields = redact("Reach me at john.doe@example.com any time.")
    assert "email" in fields
    assert "john.doe@example.com" not in redacted
    assert MASK in redacted


def test_phone_is_removed_and_reported():
    redacted, fields = redact("Call 415-555-1234 for an interview.")
    assert "phone" in fields
    assert "415-555-1234" not in redacted


def test_international_mobile_is_removed():
    redacted, fields = redact("Reach me on +91 98200 45317 anytime.")
    assert "phone" in fields
    assert "98200 45317" not in redacted


def test_year_range_is_not_mistaken_for_phone():
    """Guard against over-redaction: '2019 - 2022' must survive untouched."""
    redacted, fields = redact("Senior Accountant, 2019 - 2022, led close.")
    assert "phone" not in fields
    assert "2019 - 2022" in redacted


def test_url_is_removed_and_reported():
    redacted, fields = redact("Portfolio: https://linkedin.com/in/johndoe")
    assert "url" in fields
    assert "linkedin.com/in/johndoe" not in redacted


def test_street_address_is_removed_and_reported():
    redacted, fields = redact("Lives at 123 Main Street, apt 4.")
    assert "address" in fields
    assert "123 Main Street" not in redacted


def test_clean_text_has_no_pii_and_no_false_fields():
    """A resume body with no contact details must come back untouched with an
    empty field list — redaction must not invent things to redact."""
    text = "Senior accountant with ten years of general ledger experience."
    redacted, fields = redact(text)
    assert fields == []
    assert redacted == text
    assert MASK not in redacted


def test_multiple_pii_types_all_removed():
    text = ("Jane Roe — jane@corp.io — 212-555-9000 — "
            "https://github.com/janeroe — 42 Oak Avenue")
    redacted, fields = redact(text)
    for expected in ("email", "phone", "url", "address"):
        assert expected in fields
    for raw in ("jane@corp.io", "212-555-9000", "github.com/janeroe",
                "42 Oak Avenue"):
        assert raw not in redacted


@pytest.mark.skipif(pii._NLP is None,
                    reason="spaCy + en_core_web_sm not installed")
def test_person_name_redacted_when_spacy_present():
    redacted, fields = redact("Barack Obama worked as a project manager.")
    assert "name" in fields
    assert "Barack Obama" not in redacted
