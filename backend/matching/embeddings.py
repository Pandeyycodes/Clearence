"""JD-vs-resume match score.

Two implementations, best-available wins:

1. sentence-transformers (all-MiniLM-L6-v2), if installed: cosine
   similarity between resume and JD embeddings, rescaled so ~0.80 raw
   similarity reads as 100.
2. Fallback (default, zero downloads): **JD term coverage** — the
   idf-weighted share of the job description's content terms (1-2 grams,
   stop words removed) that appear in the resume. This is interpretable on
   its face: 60% means the resume covers 60% of what the JD asks for,
   weighted so rare/specific JD terms count more than filler. Calibration
   on real resume/JD pairs: on-target pairs score ~45-60 raw, off-target
   ~10-15, so raw is rescaled by /0.70 (capped) to a readable 0-100.

The active method is reported in every API response — the UI never claims
semantic embeddings when the coverage fallback is in use.

This score is deliberately separate from the category classifier: the
classifier answers "what kind of resume is this?" from supervised labels;
the match score answers "how close is this resume to THIS JD?" and needs
no labels. Merging them would make both unexplainable (see RESULTS.md).
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

try:  # optional
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    _ST = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    _ST = None

METHOD = ("sentence-transformers/all-MiniLM-L6-v2" if _ST
          else "jd-term-coverage (tfidf)")


def match_score(resume_text: str, jd_text: str) -> float:
    """Return a 0-100 match percentage."""
    if _ST is not None:
        emb = _ST.encode([resume_text, jd_text])
        sim = float(cosine_similarity([emb[0]], [emb[1]])[0][0])
        return round(min(sim / 0.80, 1.0) * 100, 2)

    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                          sublinear_tf=True)
    try:
        vec.fit([jd_text])
    except ValueError:  # JD had only stop words
        return 0.0
    jd_v = vec.transform([jd_text]).toarray()[0]
    present = (vec.transform([resume_text]).toarray()[0] > 0)
    denom = jd_v.sum()
    raw = float((jd_v * present).sum() / denom) if denom else 0.0
    return round(min(raw / 0.70, 1.0) * 100, 2)
