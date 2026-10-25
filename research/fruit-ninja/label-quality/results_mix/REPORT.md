# 100% normal labels versus 70% normal / 30% gameplay labels

The mixed model performed **better by 2.9 percentage points** on photo-balanced accuracy in this pilot. The paired 95% interval for mixed minus normal is **-6.5 to +15.6 points**; it includes zero, so the apparent difference is inconclusive.

| Training labels | Cutout accuracy | Class-balanced accuracy | Photo-balanced accuracy | Rotten recall |
|---|---:|---:|---:|---:|
| 100% normal | 86.8% | 87.2% | 79.5% | 89.7% |
| 70% normal / 30% gameplay, mean of 30 runs | 82.8% | 83.0% | 82.4% | 84.0% |

Ordinary cutout accuracy and photo-balanced accuracy can rank the arms differently: the latter gives every source photo equal weight within class instead of allowing photos with many cutouts to dominate. Rotten recall also matters, so the table reports it explicitly. The primary metric should not be changed after seeing a tradeoff.

The mixed model's photo-balanced accuracy ranged from **77.5% to 86.8%** over the 30 predeclared label selections (SD 3.0 percentage points). It beat the all-normal baseline in 24/30 runs and tied it in 0/30 runs. These runs reuse the same photos; they are not 30 independent experiments. No best run was selected. The headline is the mean metric of 30 separately trained models, not the performance of an ensemble.

## What was compared

- **Normal means historical original-dataset source labels**, including all 183 kept cutouts. These are inherited from photographs; they are not newly expert-adjudicated cutout labels.
- Both arms use the **same image identities and same number of training rows within each fold**, the same 57 color/texture features, fixed gradient-boosting settings and class/photo weighting algorithm. Only label origin changes. No duplicate copy of the same image is added under another label.
- In the mixed arm, approximately 30% of training image labels come from eligible gameplay strict-majority votes. They are sampled from the 68 cutouts with non-tied gameplay labels in the frozen snapshot; all other rows retain normal labels. Labels which agree across both origins still count toward the 30%. Four gameplay ties remain eligible for a normal label, but cannot supply a gameplay label.
- Integer counts are rounded to the nearest whole image in each fold. The actual gameplay proportions range from 29.78% to 30.29%. Model sample weights may change when labels change, so 30% describes **rows by label origin**, not 30% of effective training weight.
- Evaluate all 91 frozen reference cutouts from 28 photos, leaving the entire test photo out of **both** training arms by source-photo SHA-256. Other reference photos may be in the training pool; the held-out photo and its target/control siblings never are. Every reference cutout has one prediction per arm/run.
- Selection seeds are fixed before fitting, based on hashed image IDs, without using reference outcomes or selecting for agreement with source labels. All 30 seeds and each fold's selections/changed labels are saved. The representative saved mixed model uses the **first predeclared seed**, not the best-scoring seed.

Final saved models are separately refit on all 183 images. The mixed artifact uses **128 normal labels / 55 gameplay labels**; 18 of those gameplay labels actually differ from their historical source labels. A 30% gameplay-origin mix does not mean 30% label disagreement.

## Why this differs from the earlier experiment

The earlier source-label comparator trained on only the 68 target cutouts with usable gameplay labels. This experiment uses the full normally labeled pool (183 cutouts before excluding each test photo), as requested. It tests replacing the label source for 30% of a matched training set. It does **not** test increasing the number of images, adding unseen photographs, or whether a 70/30 mix is optimal.

## Limits

This is an exploratory extension using the same small prototype references already inspected during the prior pilot. Original source labels and reference answers share the same inherited convention, so this evaluation favors agreement with that convention; a disagreement is not necessarily a player error. The 28 reference photos, 26 gameplay-label photos, correlated cutouts, and possibly single human behind multiple profiles limit generalization.

The bootstrap resamples held-out photos within class and samples one random mix per draw, pairing normal/mixed results. It includes variability across label selections and test photos **conditional on this snapshot and fitted folds**. It does not capture full training-population uncertainty. No tuning or mix-seed cherry-picking was performed. A new blind, adjudicated photo holdout is still needed for a stronger conclusion.

## Reproduce and inspect

See `../README.md` for the command. `protocol.json` freezes settings; `folds.json` records every training/test image, origin selection and realized ratio; `per_mix_metrics.csv` records all runs; `reference_predictions.csv` stores every held-out prediction. `normal_gradient_boosting.joblib` and `mixed_70_30_gradient_boosting.joblib` work with `../predict.py --model ...`. The saved models contain label-origin metadata and the frozen snapshot hash `608efbe30dbee0a0a92578b0ff0f1bfe407c3f6691526c6405bf50e4a827bddc`. No gameplay database labels were changed.
