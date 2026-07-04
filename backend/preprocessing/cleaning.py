"""Text cleaning for resume classification.

Deliberately minimal: lowercase, strip URLs/emails/non-letters, collapse
whitespace. Heavier normalisation (stemming, lemmatisation) was tested and
did not improve CV score, so it is not used.
"""
import re

_URL_EMAIL = re.compile(r"http\S+|www\.\S+|\S+@\S+")
_NON_ALPHA = re.compile(r"[^a-zA-Z ]")
_WS = re.compile(r"\s+")


def clean_text(text: str) -> str:
    text = _URL_EMAIL.sub(" ", text)
    text = _NON_ALPHA.sub(" ", text)
    return _WS.sub(" ", text).lower().strip()
