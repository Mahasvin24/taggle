# Fruit label-quality experiment

A reproducible gradient-boosted image-classification pilot for the labels collected by Fruit Shift. **[Read the evaluated results](results/REPORT.md)** or open [the figure](results/evaluation.png) and [visual label audit](results/audit.html).

The primary question is whether a model trained only on eligible gameplay target labels transfers to reference fruit from **different source photographs**. A high training score or random cutout split would not answer that question. We use leave-one-source-photo-out evaluation, fixed masked color/texture features, strict-majority target labels, and unchanged settings across all model comparisons. Historical source labels appear only in a separately named diagnostic comparator/audit, never as gameplay training truth.

## Run

From the repository root (Python 3.13 used for the recorded run):

```sh
python3 -m venv research/fruit-ninja/label-quality/.venv
research/fruit-ninja/label-quality/.venv/bin/python -m pip install -r research/fruit-ninja/label-quality/requirements.txt

# Freeze and evaluate the current committed gameplay labels, read-only.
research/fruit-ninja/label-quality/.venv/bin/python research/fruit-ninja/label-quality/run_experiment.py \
  --db backend/data.db --out research/fruit-ninja/label-quality/results-new

# Reproduce the recorded evaluation without querying a changing database.
research/fruit-ninja/label-quality/.venv/bin/python research/fruit-ninja/label-quality/run_experiment.py \
  --snapshot research/fruit-ninja/label-quality/results/snapshot.json \
  --out /tmp/fruit-label-quality-replay

# Verify majority/tie handling, alpha masking, photo weighting and every saved fold.
research/fruit-ninja/label-quality/.venv/bin/python -m unittest discover \
  -s research/fruit-ninja/label-quality -v
```

Use a new output directory for new data so the recorded pilot remains intact. SQLite is opened with `mode=ro` inside a consistent read transaction, including committed WAL records. Only `kind=game`, completed, eligible target appearances enter training; each appearance contributes only its latest effective event. Practice, demonstrations, controls, failed/incomplete rounds, superseded original events and separate QA databases are excluded. Votes are merged to one image row, without treating repeated votes as extra independent training examples. `snapshot.json` freezes the selected event IDs and provenance; `folds.json` makes every photo exclusion inspectable.

Training uses all qualifying profiles in that database. Local profile IDs are not proof of distinct people. The experiment does not alter labels, game eligibility, reference membership, or gameplay behavior.

## Use the saved model

Pass transparent cutout PNG/WebP images; this feature extractor is not a whole-scene detector or a camera pipeline. For example:

```sh
research/fruit-ninja/label-quality/.venv/bin/python research/fruit-ninja/label-quality/predict.py \
  backend/assets/fruit_ninja/originals/228792ab5acc5eeea8adff5fb8d668fb.png
```

The command prints a label and **uncalibrated** `p_rotten` score. The final model was refit on all resolved gameplay targets after the separate held-out evaluation. Its predictions on training images do not measure generalization. Only load this locally produced/trusted joblib artifact; serialized Python models can execute code.

## Method references

- [scikit-learn GradientBoostingClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingClassifier.html): the fitted estimator. We use 80 trees, depth 2, learning rate 0.05 and minimum leaf size 3, with no tuning against this test set.
- [Grouped cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data): keep correlated observations from the same source together. Here source-photo SHA-256 defines the group, not a cutout ID.
- [Balanced accuracy](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.balanced_accuracy_score.html): average class recall. The primary metric additionally weights each source photo equally within its class so one photo with many cutouts cannot dominate.
- [Existing fruit provenance and limitations](../dataset-review/README.md): original source labels are inherited from photographs and the fixed controls are visually reviewed prototype references, not expert-adjudicated cutout truth.

The report's proposed next experiment adds a blind adjudicated holdout and compares game versus untimed annotation on matched training images. This pilot cannot establish the true target-label error rate or a causal effect of the recent UI change.


## 100% normal versus 70/30 label mix

The follow-up comparison is in [`results_mix/REPORT.md`](results_mix/REPORT.md). “Normal” means original source-photo labels. Both arms use all 183 kept images before the test-photo exclusion, with identical training identities/row counts per fold. The mixed arm changes only the label source for approximately 30% of rows, selected from non-tied eligible gameplay labels. Repeating 30 predeclared selections measures sensitivity to which gameplay labels enter the mix; the reported mixed score averages the metrics of the separate models and is not an ensemble score.

```sh
research/fruit-ninja/label-quality/.venv/bin/python research/fruit-ninja/label-quality/run_mixture.py \
  --snapshot research/fruit-ninja/label-quality/results/snapshot.json \
  --out research/fruit-ninja/label-quality/results_mix

research/fruit-ninja/label-quality/.venv/bin/python research/fruit-ninja/label-quality/predict.py \
  --model research/fruit-ninja/label-quality/results_mix/mixed_70_30_gradient_boosting.joblib \
  backend/assets/fruit_ninja/originals/228792ab5acc5eeea8adff5fb8d668fb.png
```

`results_mix/normal_gradient_boosting.joblib` and `results_mix/mixed_70_30_gradient_boosting.joblib` are final refits to the full 183-image pool; their in-sample scores are not the held-out evaluation. The final mix is 128 normal / 55 gameplay-origin labels (nearest integer to 70/30), with the first predeclared seed rather than the best seed. The report states how many selected gameplay labels actually disagree with source labels. Full per-fold identities, origin selections, ratios, 30-run scores and reference predictions are retained. This comparison tests label replacement, not adding new images or finding an optimal mixture ratio.
