"""Leakage-free training pipeline for Clearance.

Methodology (non-negotiable):
1. Exact-duplicate resumes are dropped BEFORE any split. The original
   Resume-Screening notebook skipped this: UpdatedResumeDataSet.csv has 962
   rows but only 166 unique resumes, so a random split puts copies of the
   same resume in both train and test -> fake ~99% accuracy.
2. Train/test split happens FIRST (stratified, 80/20). The TfidfVectorizer
   is fitted only on train (it lives inside a Pipeline, so cross-validation
   refits it per fold and never sees validation text).
3. Three models compared with StratifiedKFold(5) on f1_macro:
   LinearSVC, LogisticRegression, RandomForestClassifier,
   all class_weight='balanced'.
4. The CV winner is refit on the full training set and evaluated ONCE on
   the untouched test set. Full report + confusion matrix -> artifacts/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score,
                             top_k_accuracy_score)
from sklearn.model_selection import (StratifiedKFold, cross_val_score,
                                     train_test_split)
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from preprocessing.cleaning import clean_text  # noqa: E402

ARTIFACTS = BACKEND / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
RANDOM_STATE = 42


def load_dataset(csv_path: str, text_col: str, label_col: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df.rename(columns={text_col: "text", label_col: "category"})
    df["clean"] = df["text"].map(clean_text)
    before = len(df)
    df = df.drop_duplicates(subset="clean").reset_index(drop=True)
    print(f"Loaded {before} rows -> {len(df)} after exact-duplicate removal "
          f"({df['category'].nunique()} classes)")
    return df


def make_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2),
                           min_df=2, stop_words="english",
                           max_features=100_000)


def candidate_models() -> dict:
    return {
        "LinearSVC": LinearSVC(class_weight="balanced", C=1.0,
                               random_state=RANDOM_STATE),
        "LogisticRegression": LogisticRegression(class_weight="balanced",
                                                 max_iter=2000, C=5.0,
                                                 random_state=RANDOM_STATE),
        "RandomForest": RandomForestClassifier(class_weight="balanced",
                                               n_estimators=300,
                                               n_jobs=-1,
                                               random_state=RANDOM_STATE),
    }


def main(csv_path: str, text_col: str, label_col: str, tag: str) -> None:
    df = load_dataset(csv_path, text_col, label_col)
    X, y = df["clean"].values, df["category"].values

    # ---- 1. Split first. Test text is never touched again until the end.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    print(f"Train {len(X_train)} / test {len(X_test)} (stratified)")

    # ---- 2. Five-fold CV comparison on the training set only.
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_rows = []
    for name, clf in candidate_models().items():
        pipe = Pipeline([("tfidf", make_vectorizer()), ("clf", clf)])
        t0 = time.time()
        scores = cross_val_score(pipe, X_train, y_train, cv=skf,
                                 scoring="f1_macro", n_jobs=1)
        cv_rows.append({"model": name,
                        "cv_f1_macro_mean": round(scores.mean(), 4),
                        "cv_f1_macro_std": round(scores.std(), 4),
                        "fit_seconds": round(time.time() - t0, 1)})
        print(f"  {name}: f1_macro {scores.mean():.4f} +/- {scores.std():.4f}"
              f" ({time.time()-t0:.0f}s)")

    cv_df = pd.DataFrame(cv_rows).sort_values("cv_f1_macro_mean",
                                              ascending=False)
    cv_df.to_csv(ARTIFACTS / f"cv_comparison_{tag}.csv", index=False)
    winner_name = cv_df.iloc[0]["model"]
    print(f"CV winner: {winner_name}")

    # ---- 3. Refit winner on full train, evaluate once on held-out test.
    winner = Pipeline([("tfidf", make_vectorizer()),
                       ("clf", candidate_models()[winner_name])])
    winner.fit(X_train, y_train)
    y_pred = winner.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1m = f1_score(y_test, y_pred, average="macro")
    report = classification_report(y_test, y_pred, zero_division=0)

    # Top-3 accuracy: this is a shortlisting tool, so "is the true category in
    # the model's top 3 guesses?" reflects real use better than top-1 alone.
    # Uses decision_function (LinearSVC/LogReg) or predict_proba (RandomForest).
    top3 = None
    try:
        if hasattr(winner, "decision_function"):
            y_scores = winner.decision_function(X_test)
        else:
            y_scores = winner.predict_proba(X_test)
        top3 = top_k_accuracy_score(y_test, y_scores, k=3,
                                    labels=winner.classes_)
    except Exception as exc:  # noqa: BLE001
        print(f"  (top-3 accuracy unavailable: {exc})")
    top3_str = f" | top-3 acc {top3:.4f}" if top3 is not None else ""
    print(f"HELD-OUT accuracy {acc:.4f} | f1_macro {f1m:.4f}{top3_str}")

    (ARTIFACTS / f"classification_report_{tag}.txt").write_text(
        f"winner: {winner_name}\naccuracy: {acc:.4f}\nf1_macro: {f1m:.4f}\n"
        + (f"top_3_accuracy: {top3:.4f}\n" if top3 is not None else "")
        + "\n" + report)

    labels = sorted(np.unique(y))
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=7)
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    ax.set_title(f"Confusion matrix — {winner_name} ({tag}), "
                 f"held-out acc {acc:.3f}")
    fig.colorbar(im, shrink=0.7)
    fig.tight_layout()
    fig.savefig(ARTIFACTS / f"confusion_matrix_{tag}.png", dpi=150)
    plt.close(fig)

    joblib.dump(winner, ARTIFACTS / f"model_{tag}.joblib")
    summary = {"dataset": csv_path, "tag": tag, "n_after_dedup": len(df),
               "n_train": len(X_train), "n_test": len(X_test),
               "winner": winner_name,
               "cv": cv_rows,
               "held_out_accuracy": round(acc, 4),
               "held_out_f1_macro": round(f1m, 4),
               "held_out_top3_accuracy": round(top3, 4) if top3 is not None
               else None}
    (ARTIFACTS / f"summary_{tag}.json").write_text(json.dumps(summary,
                                                              indent=2))
    print(f"Artifacts written to {ARTIFACTS}")


if __name__ == "__main__":
    # Primary dataset: archive.zip Resume.csv (2,484 resumes, 24 classes)
    ROOT = BACKEND.parent
    main(str(ROOT / "data/Resume/Resume.csv"),
         "Resume_str", "Category", tag="archive")
    # Repo dataset, honest version (dedup first)
    main(str(ROOT / "data/Resume-Screening-main/DataSet/UpdatedResumeDataSet.csv"), "Resume", "Category", tag="repo")
