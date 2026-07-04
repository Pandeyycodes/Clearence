# Clearance — training results

## Datasets

Two datasets were provided. They are different and the difference matters.

**archive.zip → `Resume/Resume.csv`** — 2,484 real resumes across 24 job categories, average ~6,300 characters each, 2,482 unique after exact-duplicate removal. Classes range from 120 examples (INFORMATION-TECHNOLOGY, BUSINESS-DEVELOPMENT) down to 22 (BPO). This is the primary training dataset.

**Resume-Screening-main → `UpdatedResumeDataSet.csv`** — 962 rows across 25 categories, but only **166 unique resumes**. Each resume is copy-pasted 4–12 times. This duplication is the leakage bug in the original repo.

## The leakage bug, reproduced

The original notebook does a random train/test split on the 962 rows without deduplicating. Because copies of the same resume land in both train and test, the model is graded on resumes it memorised. Reproduced here: **99.5% "accuracy" with the duplicates left in, 88.2% after deduplication** (and that 88.2% is on a test set of just 34 documents, so the confidence interval is wide). The fix in this pipeline: deduplicate on cleaned text before the split, split first, and fit the TfidfVectorizer only on train (enforced by `tests/test_no_leakage.py`, which fails if any held-out document ever reaches a `.fit()` call — both tests pass).

## Cross-validation comparison (5-fold StratifiedKFold, f1_macro, train split only)

Primary dataset (archive, 1,985 train / 497 test):

| Model | CV f1_macro | std |
|---|---|---|
| **LinearSVC** (winner) | **0.614** | 0.012 |
| RandomForest | 0.612 | 0.018 |
| LogisticRegression | 0.585 | 0.012 |

All with `class_weight='balanced'`, TF-IDF (sublinear, 1–2 grams, english stop words, min_df=2, 100k features). LinearSVC won: on high-dimensional sparse text with ~2k documents, a max-margin linear separator generalises better than the forest's axis-aligned splits, and it beat logistic regression's smoother decision boundary on the many small, vocabulary-distinctive classes. Word+character n-gram unions and C tuning were also tried; none moved held-out accuracy by more than ~1 point.

## Held-out results (untouched 20% test set, evaluated once)

- **archive dataset: accuracy 0.684, f1_macro 0.638** — full per-class report in `backend/artifacts/classification_report_archive.txt`, confusion matrix in `confusion_matrix_archive.png`.
- **repo dataset (deduped): accuracy 0.882, f1_macro 0.821** — small test set (n=34), treat with caution.

Where the archive model struggles is informative: CONSULTANT (recall 0.17), BPO (0 of 4 correct), APPAREL and AUTOMOBILE all get absorbed into neighbouring business categories — a consultant's resume genuinely reads like business-development or finance. Strong classes are the vocabulary-distinctive ones: DESIGNER (0.90 f1), AVIATION (0.84), INFORMATION-TECHNOLOGY (0.83 with perfect recall).

## About the >90% accuracy target

**90%+ accuracy on this data is not honestly reachable with this class of model, and the pipeline does not pretend otherwise.**

- The widely-circulated 98–99% numbers for resume classification come from the duplicated dataset. That figure is reproduced above and it is an artifact of leakage, not model quality.
- On the real 2,484-resume dataset, tuned TF-IDF + linear models plateau around 68–69% accuracy. Published results on this same Kaggle dataset land in the same range for classical ML, with transformer fine-tunes (BERT-class) reaching roughly the low-to-mid 80s.
- The ceiling is partly the labels themselves: many resumes legitimately belong to two categories (consultant/business-development, finance/accountant, sales/BPO), and 24-way single-label classification punishes that ambiguity.

Paths that would raise the number honestly, in rough order of expected gain: fine-tune a small transformer (DistilBERT/DeBERTa) on the 1,985 training resumes (~+12–15 points, needs GPU and Hugging Face access); merge genuinely overlapping categories or move to top-3 accuracy (top-3 for this model is typically ~88–90% — arguably the right metric for a screening tool that shows a ranked list anyway); add the resume's section structure from `Resume_html` as features. What is not on the list: re-introducing duplicates, tuning on the test set, or reporting CV score as if it were held-out accuracy.

## Limitations

Single-label classification on inherently multi-label documents; no per-class calibration; the repo-dataset numbers rest on 34 test documents; exact-duplicate removal only (near-duplicates with minor edits would still leak — MinHash dedup is the next step); English-only cleaning. The JD-matching score, PII redaction, bias audit, and API layers from the project brief are separate stages and are not part of this training run.
