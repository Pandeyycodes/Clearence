"""Fails if test text ever reaches a .fit() call, or if duplicates cross the
train/test boundary."""
import sys
from pathlib import Path

import pandas as pd
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from preprocessing.cleaning import clean_text

DATA = Path(__file__).resolve().parents[2] / "data" / "Resume" / "Resume.csv"
pytestmark = pytest.mark.skipif(not DATA.exists(),
    reason="dataset not present — download archive.zip from Kaggle first")


class LeakDetectingVectorizer(TfidfVectorizer):
    """TfidfVectorizer that raises if any quarantined text is fitted."""

    forbidden: set = set()

    def fit(self, raw_documents, y=None):
        self._check(raw_documents)
        return super().fit(raw_documents, y)

    def fit_transform(self, raw_documents, y=None):
        self._check(raw_documents)
        return super().fit_transform(raw_documents, y)

    def _check(self, docs):
        hits = sum(1 for d in docs if d in LeakDetectingVectorizer.forbidden)
        if hits:
            raise AssertionError(
                f"LEAKAGE: {hits} held-out document(s) reached .fit()")


def _load():
    df = pd.read_csv(DATA)
    df["clean"] = df["Resume_str"].map(clean_text)
    df = df.drop_duplicates(subset="clean")
    return train_test_split(df["clean"].values, df["Category"].values,
                            test_size=0.2, stratify=df["Category"],
                            random_state=42)


def test_no_duplicates_cross_split():
    X_train, X_test, _, _ = _load()
    assert set(X_train).isdisjoint(set(X_test)), \
        "duplicate resumes appear in both train and test"


def test_vectorizer_never_fits_test_text():
    X_train, X_test, y_train, _ = _load()
    LeakDetectingVectorizer.forbidden = set(X_test)
    vec = LeakDetectingVectorizer(max_features=5000)
    vec.fit_transform(X_train, y_train)  # must pass
    with pytest.raises(AssertionError):
        vec.fit(X_test)  # must trip the alarm
