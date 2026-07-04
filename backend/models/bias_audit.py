"""Name-swap bias audit.

Method: take a sample of resumes, prepend each with a masculine-coded name
and then a feminine-coded name (12 pairs), and check whether the
classifier's predicted category ever changes because of the name alone.
Results — including any skew — are written to bias_audit_runs verbatim.

This tests one narrow thing: sensitivity of the category prediction to
first names. It does NOT certify the system as unbiased; names are only
one proxy, and the JD match score and skill list have their own potential
biases (see notes written with each run).

Run:  python -m models.bias_audit
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import joblib
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from db.session import SessionLocal, init_db  # noqa: E402
from db.models import BiasAuditRun  # noqa: E402
from preprocessing.cleaning import clean_text  # noqa: E402

NAME_PAIRS = [
    ("James", "Emily"), ("Michael", "Sarah"), ("Robert", "Jessica"),
    ("David", "Ashley"), ("William", "Amanda"), ("Richard", "Jennifer"),
    ("Thomas", "Elizabeth"), ("Daniel", "Stephanie"), ("Matthew", "Lauren"),
    ("Anthony", "Megan"), ("Mark", "Rachel"), ("Steven", "Nicole"),
]

MODEL = BACKEND / "artifacts" / "model_archive.joblib"
DATA = Path(__file__).resolve().parents[2] / "data" / "Resume" / "Resume.csv"


def run_audit(sample_size: int = 100) -> dict:
    pipe = joblib.load(MODEL)
    df = pd.read_csv(DATA).drop_duplicates(subset="Resume_str")
    sample = df.sample(n=min(sample_size, len(df)), random_state=7)

    flips = 0
    total = 0
    flip_examples = []
    masc_dist, fem_dist = Counter(), Counter()

    for _, row in sample.iterrows():
        base = row["Resume_str"]
        for masc, fem in NAME_PAIRS:
            pm = pipe.predict([clean_text(f"{masc} Anderson {base}")])[0]
            pf = pipe.predict([clean_text(f"{fem} Anderson {base}")])[0]
            masc_dist[pm] += 1
            fem_dist[pf] += 1
            total += 1
            if pm != pf:
                flips += 1
                if len(flip_examples) < 20:
                    flip_examples.append({"pair": f"{masc}/{fem}",
                                          "masc_pred": pm, "fem_pred": pf,
                                          "true": row["Category"]})

    flip_rate = flips / total
    summary = {
        "n_resumes": len(sample), "n_name_pairs": len(NAME_PAIRS),
        "n_comparisons": total, "prediction_flips": flips,
        "flip_rate": round(flip_rate, 4),
        "masc_category_distribution": dict(masc_dist),
        "fem_category_distribution": dict(fem_dist),
        "flip_examples": flip_examples,
    }
    notes = (
        f"Name-swap audit over {total} comparisons: the predicted category "
        f"changed because of the first name alone in {flips} cases "
        f"({flip_rate:.2%}). "
        + ("At this rate name-sensitivity is negligible for this model, "
           if flip_rate < 0.005 else
           "This is a non-trivial sensitivity and is disclosed as-is. ")
        + "Scope: this measures first-name sensitivity of the TF-IDF "
          "category classifier only. It says nothing about bias entering "
          "through school names, gaps in employment, gendered activity "
          "words, or the JD match score. A production system would need a "
          "far broader audit before any hiring decision touches it."
    )

    init_db()
    db = SessionLocal()
    try:
        db.add(BiasAuditRun(summary=summary, notes=notes))
        db.commit()
    finally:
        db.close()
    print(notes)
    return summary


if __name__ == "__main__":
    run_audit()
