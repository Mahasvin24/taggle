# Fruit gameplay label-quality pilot

The gradient-boosted model learned a weak, uncertain signal across independent source photos. It is **not yet evidence that the current gameplay labels train a reliable classifier**. This is a pilot diagnosis of a small dataset and a simple color/texture model, not a measured label-error rate.

Snapshot: `608efbe30dbee0a0a92578b0ff0f1bfe407c3f6691526c6405bf50e4a827bddc`. Captured/run at 2026-10-25T00:15:16.045392+00:00 (UTC). The initial inventory was 64 votes; new gameplay before the frozen run increased it to **80 eligible votes on 72 unique target cutouts**. After excluding 4 tied cutouts, training uses **68 cutouts from 26 source photos** (48 healthy / 20 rotten). Counts refer to this snapshot, not the live game.

## Experiment

Train a fixed `GradientBoostingClassifier` on eligible gameplay target labels only. Repeated votes produce one majority label per asset; ties are excluded. Extract 57 fixed foreground color/texture features from transparent originals. No player, fruit type, filename, ID, crop dimensions or source label enters the gameplay model. Balance training weights by class and source photo. No data augmentation, pretrained model, tuning, or label correction.

Test on 91 frozen reference cutouts (52 healthy / 39 rotten) from 28 source photos. For each test photo, exclude **all cutouts of that photo by SHA-256** from that fold's training, including any target cutouts. Each reference cutout is predicted once. The final saved model is separately refit on all resolved target labels; its in-sample predictions are not these test results.

## Results

| Training / comparator | Cutout accuracy | Class-balanced accuracy | Photo-balanced accuracy (95% interval) |
|---|---:|---:|---:|
| Always healthy | 57.1% | 50.0% | 50.0% (50.0%–50.0%) |
| Fruit-type-only baseline | 38.5% | 34.3% | 49.0% (34.6%–62.8%) |
| Gameplay labels · gradient boosting | 69.2% | 68.6% | 55.3% (39.0%–71.5%) |
| Same images · source-photo labels (diagnostic) | 75.8% | 76.0% | 69.7% (52.8%–84.7%) |
| Reference controls · gradient boosting (diagnostic) | 80.2% | 80.4% | 79.0% (64.7%–91.3%) |

The primary metric gives every source photo equal weight within each class, then averages healthy and rotten recall. Ordinary cutout metrics overweight photos with many segmented berries/grapes. The gameplay model's 69.2% ordinary accuracy falls to **55.3%** on the primary metric. Its 95% interval includes the 50% constant-class baseline. A useful predictive signal across unseen photos is not established by this run.

The bootstrap resamples reference photos within class, uses the same resamples for every model, and uses 4,000 iterations. Its interval describes variation over these test photos conditional on the fitted folds; it does **not** capture full uncertainty from retraining on new gameplay data. The paired gameplay-minus-source-label interval crosses zero, so the apparent source-label advantage is uncertain too. See `summary.json` for paired intervals.

The source-label model uses identical training images/features/folds but replaces only the training labels with historical source-photo labels. It is a sensitivity check, **not a corrected dataset**: source-inherited labels are not independent expert truth. The reference-trained comparator uses the other reference photos and has different training coverage/size. Its higher score suggests the features can encode some reference condition, but neither comparison isolates a causal label-noise effect.

Gameplay model confusion matrix (rows: reference; columns: prediction):

| | Predicted healthy | Predicted rotten |
|---|---:|---:|
| Reference healthy | 38 | 14 |
| Reference rotten | 14 | 25 |

Rotten recall: **64.1%**; healthy recall: **73.1%**. Predicted probabilities are uncalibrated scores, not validated confidence estimates.

## Direct label audit

- On hidden controls in qualifying games, original player calls agree with the prototype reference on **68/80 (85.0%)**. This is conditional on passing the game's 13/16 gate; it is selection-biased and does not estimate all-play or target-label accuracy.
- Across targets, **52/80 votes (65.0%)** and **45/68 resolved majority labels (66.2%)** agree with historical source-photo labels. These disagreements are review candidates, not automatically player mistakes.
- Of 29 source-rotten target cutouts, **16 were called healthy** by the resolved majority. Of 39 source-healthy targets, 7 were called rotten. Missing visible decay, intentional disagreement with source labels, and ambiguity in inherited crop labels are all plausible. This experiment cannot distinguish them.
- The dataset comes from local profiles, not authenticated independent annotators. Profiles may be the same person. Repeat appearances and nearby cutouts are not independent raters or independent photos.

Open `audit.html` for every voted target, including the ties, with its image, votes, historical source label, and a prediction trained on other photos. The model only flags candidates; no game labels were changed. `target_audit.csv` and `reference_predictions.csv` retain the underlying rows.

## Fruit breakdown (descriptive only)

| Fruit | Reference cutouts | Source photos | Cutout accuracy | Rotten recall |
|---|---:|---:|---:|---:|
| apple | 10 | 5 | 60.0% | 0.0% |
| banana | 6 | 3 | 66.7% | 50.0% |
| grape | 26 | 6 | 88.5% | 87.5% |
| guava | 4 | 4 | 75.0% | 50.0% |
| jujube | 3 | 1 | 100.0% | No rotten references |
| orange | 3 | 3 | 33.3% | 0.0% |
| pomegranate | 3 | 3 | 33.3% | 50.0% |
| strawberry | 36 | 3 | 61.1% | 71.4% |

These subgroups are tiny and correlated. They are not reliable per-fruit performance estimates; jujube has no rotten reference in this catalog.

## Next experiment to establish quality

1. Independently adjudicate the existing voted cutouts, with the reviewer blind to game votes, source labels and model scores. Use two reviewers for ambiguous items and resolve disagreements. Keep these evaluation labels separate from live gameplay data.
2. Build a new holdout of roughly **200 independent source photos**, with both conditions for each fruit and enough subtle decay. Have reviewers label the actual cutouts rather than inheriting a label from a group photo. Keep the holdout out of examples, calibration and model development. This is a practical pilot target, not a power calculation.
3. Collect game labels and a slower untimed labeling condition on the **same training images**, randomizing image assignment/order and counterbalancing who sees which condition. Avoid repeating the same image for a person. Record condition, timing, device, game version, prior exposure and annotator identity/consent separately. Current logs lack game-version tags, so this run cannot attribute quality to the recent UI changes.
4. Freeze the same feature extractor, model settings, training image counts and test set for both conditions. Compare photo-balanced accuracy, rotten recall, direct adjudicated-label agreement, and labels per minute using paired photo/participant resampling. Set an acceptable quality-versus-throughput tradeoff before looking at results.
5. Review the four current ties and the largest disagreements now, but do not silently overwrite original events. If a feature/model change is chosen using these pilot reference results, evaluate it once on the new untouched holdout.

## Artifacts and reproducibility

- `gameplay_gradient_boosting.joblib`: final model fitted to all resolved gameplay targets.
- `protocol.json`: fixed settings, labels, weights and evaluation rule.
- `snapshot.json`: consistent read-only database snapshot, including event IDs and provenance; no SQLite writes or QA database used.
- `folds.json`: exact train/test identities for every held-out photo.
- `features.npz`: feature matrix and schema.
- `summary.json`, prediction/audit CSVs, `evaluation.png`: complete outputs.

See `../README.md` for rerun and prediction commands. Snapshot and model contain local data; do not treat this research folder as an anonymous public export. Only load a trusted joblib artifact.
