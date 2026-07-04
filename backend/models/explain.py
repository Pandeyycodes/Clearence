"""Explainability: top terms that pushed a prediction toward its class.

For the LinearSVC winner: contribution of term t to class c is
tfidf_weight(t, document) * coef[c, t]. The top positive contributions are
the honest answer to "why did the model say ACCOUNTANT?" — no
post-hoc approximation needed for a linear model.
"""
from __future__ import annotations

import numpy as np
from sklearn.pipeline import Pipeline


def top_terms(pipeline: Pipeline, clean_text: str, predicted_label: str,
              k: int = 10) -> list[dict]:
    vec = pipeline.named_steps["tfidf"]
    clf = pipeline.named_steps["clf"]
    x = vec.transform([clean_text])
    class_idx = list(clf.classes_).index(predicted_label)
    coef = clf.coef_[class_idx] if clf.coef_.shape[0] > 1 else clf.coef_[0]

    contrib = x.multiply(coef).tocoo()
    if contrib.nnz == 0:
        return []
    order = np.argsort(contrib.data)[::-1][:k]
    feats = vec.get_feature_names_out()
    return [{"term": feats[contrib.col[i]],
             "weight": round(float(contrib.data[i]), 4)}
            for i in order if contrib.data[i] > 0]
