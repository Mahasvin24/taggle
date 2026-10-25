"""Matched-image 100% source-label versus 70% source / 30% gameplay comparison.

Runs against the original frozen snapshot by default. Never edits the game database.
The random mixes vary label origin, not training images, model settings, or test set.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import sklearn

from run_experiment import (
    HERE,
    ROOT,
    SEED,
    PARAMETERS,
    aggregate_votes,
    csv_write,
    extract_features,
    fit_model,
    metrics,
    write_json,
)
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

MIX_SEEDS = tuple(SEED + i for i in range(30))
RATIO = 0.30


def select_mix(train, game_labels, seed):
    """One label per image. Select by deterministic random ranks, never by correctness.

    A global rank per seed keeps the selection reasonably stable between held-out folds.
    Exact integer counts are nearest-integer to 30% of that fold's training pool.
    """
    n = int(np.floor(len(train) * RATIO + 0.5))
    candidates = [a["id"] for a in train if a["id"] in game_labels]
    if len(candidates) < n:
        raise ValueError(
            f"Need {n} game-labeled images; only {len(candidates)} available"
        )
    ranking = sorted(
        candidates,
        key=lambda identity: hashlib.sha256(f"{seed}:{identity}".encode()).digest(),
    )
    selected = set(ranking[:n])
    source = np.array([int(a["source_label"] == "rotten") for a in train])
    mixed = np.array(
        [
            (
                game_labels[a["id"]]
                if a["id"] in selected
                else int(a["source_label"] == "rotten")
            )
            for a in train
        ]
    )
    assert len(selected) == n and len(mixed) == len(source)
    return mixed, selected, int((mixed != source).sum())


def photo_scores(truth, probabilities, photos):
    groups = np.unique(photos)
    scores = np.array(
        [
            np.mean((probabilities[photos == g] >= 0.5) == truth[photos == g])
            for g in groups
        ]
    )
    labels = np.array([truth[photos == g][0] for g in groups])
    for g in groups:
        assert len(np.unique(truth[photos == g])) == 1
    return scores, labels


def uncertainty(truth, normal, mixtures, photos, iterations=4000):
    """Paired photo bootstrap; also vary the random composition of the mixed model.

    Each draw samples one complete predeclared mix seed and reference photos within
    each class. Conditional on this snapshot and fitted folds, not a full new-data CI.
    """
    base, labels = photo_scores(truth, normal, photos)
    mixed = np.stack([photo_scores(truth, p, photos)[0] for p in mixtures])
    rng = np.random.default_rng(SEED)
    base_boot, mix_boot, delta_boot = [], [], []
    for _ in range(iterations):
        cls_indices = [
            rng.choice(
                np.flatnonzero(labels == cls),
                size=int((labels == cls).sum()),
                replace=True,
            )
            for cls in [0, 1]
        ]
        seed_index = int(rng.integers(len(mixtures)))
        b = np.mean([base[idx].mean() for idx in cls_indices])
        m = np.mean([mixed[seed_index, idx].mean() for idx in cls_indices])
        base_boot.append(float(b))
        mix_boot.append(float(m))
        delta_boot.append(float(m - b))
    return {
        "normal_photo_balanced_accuracy_ci95": np.quantile(
            base_boot, [0.025, 0.975]
        ).tolist(),
        "mixture_photo_balanced_accuracy_ci95": np.quantile(
            mix_boot, [0.025, 0.975]
        ).tolist(),
        "mixture_minus_normal_photo_balanced_accuracy_ci95": np.quantile(
            delta_boot, [0.025, 0.975]
        ).tolist(),
        "bootstrap_iterations": iterations,
        "interpretation": "Paired, class-stratified source-photo bootstrap plus random mix selection; conditional on frozen data and fitted folds, not a population or new-training-data guarantee.",
    }


def save_model(
    path, model, feature_names, train, game_labels, source_ids, seed, snapshot_hash
):
    origins = {
        a["id"]: ("gameplay" if a["id"] in source_ids else "historical_source")
        for a in train
    }
    labels = {
        a["id"]: (
            game_labels[a["id"]]
            if a["id"] in source_ids
            else int(a["source_label"] == "rotten")
        )
        for a in train
    }
    joblib.dump(
        {
            "model": model,
            "feature_names": feature_names,
            "feature_version": "masked-color-texture-v1",
            "training_asset_ids": [a["id"] for a in train],
            "training_label_origins": origins,
            "training_labels": labels,
            "mixture_seed": seed,
            "snapshot_sha256": snapshot_hash,
            "classes": {0: "fresh", 1: "rotten"},
            "threshold": 0.5,
        },
        path,
    )


def report(summary, out):
    b = summary["normal"]
    m = summary["mixture_mean"]
    variability = summary["mixture_variation"]
    delta = m["photo_balanced_accuracy"] - b["photo_balanced_accuracy"]
    lo, hi = summary["uncertainty"]["mixture_minus_normal_photo_balanced_accuracy_ci95"]
    point_word = "better" if delta > 0 else "worse" if delta < 0 else "the same"
    confident = lo > 0 or hi < 0
    write_json(out / "summary.json", summary)
    (out / "REPORT.md").write_text(
        f"""# 100% normal labels versus 70% normal / 30% gameplay labels

The mixed model performed **{point_word} by {abs(delta)*100:.1f} percentage points** on photo-balanced accuracy in this pilot. The paired 95% interval for mixed minus normal is **{lo*100:+.1f} to {hi*100:+.1f} points**; {"it excludes zero for this conditional comparison" if confident else "it includes zero, so the apparent difference is inconclusive"}.

| Training labels | Cutout accuracy | Class-balanced accuracy | Photo-balanced accuracy | Rotten recall |
|---|---:|---:|---:|---:|
| 100% normal | {b['accuracy']:.1%} | {b['balanced_accuracy']:.1%} | {b['photo_balanced_accuracy']:.1%} | {b['rotten_recall']:.1%} |
| 70% normal / 30% gameplay, mean of 30 runs | {m['accuracy']:.1%} | {m['balanced_accuracy']:.1%} | {m['photo_balanced_accuracy']:.1%} | {m['rotten_recall']:.1%} |

Ordinary cutout accuracy and photo-balanced accuracy can rank the arms differently: the latter gives every source photo equal weight within class instead of allowing photos with many cutouts to dominate. Rotten recall also matters, so the table reports it explicitly. The primary metric should not be changed after seeing a tradeoff.

The mixed model's photo-balanced accuracy ranged from **{variability['min']:.1%} to {variability['max']:.1%}** over the 30 predeclared label selections (SD {variability['std']*100:.1f} percentage points). It beat the all-normal baseline in {variability['runs_better_than_normal']}/30 runs and tied it in {variability['runs_equal_to_normal']}/30 runs. These runs reuse the same photos; they are not 30 independent experiments. No best run was selected. The headline is the mean metric of 30 separately trained models, not the performance of an ensemble.

## What was compared

- **Normal means historical original-dataset source labels**, including all 183 kept cutouts. These are inherited from photographs; they are not newly expert-adjudicated cutout labels.
- Both arms use the **same image identities and same number of training rows within each fold**, the same 57 color/texture features, fixed gradient-boosting settings and class/photo weighting algorithm. Only label origin changes. No duplicate copy of the same image is added under another label.
- In the mixed arm, approximately 30% of training image labels come from eligible gameplay strict-majority votes. They are sampled from the 68 cutouts with non-tied gameplay labels in the frozen snapshot; all other rows retain normal labels. Labels which agree across both origins still count toward the 30%. Four gameplay ties remain eligible for a normal label, but cannot supply a gameplay label.
- Integer counts are rounded to the nearest whole image in each fold. The actual gameplay proportions range from {summary['fold_gameplay_ratio_min']:.2%} to {summary['fold_gameplay_ratio_max']:.2%}. Model sample weights may change when labels change, so 30% describes **rows by label origin**, not 30% of effective training weight.
- Evaluate all 91 frozen reference cutouts from 28 photos, leaving the entire test photo out of **both** training arms by source-photo SHA-256. Other reference photos may be in the training pool; the held-out photo and its target/control siblings never are. Every reference cutout has one prediction per arm/run.
- Selection seeds are fixed before fitting, based on hashed image IDs, without using reference outcomes or selecting for agreement with source labels. All 30 seeds and each fold's selections/changed labels are saved. The representative saved mixed model uses the **first predeclared seed**, not the best-scoring seed.

Final saved models are separately refit on all 183 images. The mixed artifact uses **{summary['final_normal_rows']} normal labels / {summary['final_gameplay_rows']} gameplay labels**; {summary['final_changed_labels']} of those gameplay labels actually differ from their historical source labels. A 30% gameplay-origin mix does not mean 30% label disagreement.

## Why this differs from the earlier experiment

The earlier source-label comparator trained on only the 68 target cutouts with usable gameplay labels. This experiment uses the full normally labeled pool (183 cutouts before excluding each test photo), as requested. It tests replacing the label source for 30% of a matched training set. It does **not** test increasing the number of images, adding unseen photographs, or whether a 70/30 mix is optimal.

## Limits

This is an exploratory extension using the same small prototype references already inspected during the prior pilot. Original source labels and reference answers share the same inherited convention, so this evaluation favors agreement with that convention; a disagreement is not necessarily a player error. The 28 reference photos, 26 gameplay-label photos, correlated cutouts, and possibly single human behind multiple profiles limit generalization.

The bootstrap resamples held-out photos within class and samples one random mix per draw, pairing normal/mixed results. It includes variability across label selections and test photos **conditional on this snapshot and fitted folds**. It does not capture full training-population uncertainty. No tuning or mix-seed cherry-picking was performed. A new blind, adjudicated photo holdout is still needed for a stronger conclusion.

## Reproduce and inspect

See `../README.md` for the command. `protocol.json` freezes settings; `folds.json` records every training/test image, origin selection and realized ratio; `per_mix_metrics.csv` records all runs; `reference_predictions.csv` stores every held-out prediction. `normal_gradient_boosting.joblib` and `mixed_70_30_gradient_boosting.joblib` work with `../predict.py --model ...`. The saved models contain label-origin metadata and the frozen snapshot hash `{summary['snapshot_sha256']}`. No gameplay database labels were changed.
"""
    )
    values = [b["photo_balanced_accuracy"], m["photo_balanced_accuracy"]]
    intervals = [
        summary["uncertainty"]["normal_photo_balanced_accuracy_ci95"],
        summary["uncertainty"]["mixture_photo_balanced_accuracy_ci95"],
    ]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for i, (value, interval, color) in enumerate(
        zip(values, intervals, ["#6c7880", "#217d8c"])
    ):
        ax.errorbar(
            value,
            i,
            xerr=[[value - interval[0]], [interval[1] - value]],
            fmt="o",
            capsize=5,
            color=color,
            markersize=9,
        )
        ax.annotate(
            f"{value:.1%}",
            (value, i),
            xytext=(0, 17),
            textcoords="offset points",
            ha="center",
            fontsize=12,
        )
    ax.set(
        yticks=[0, 1],
        yticklabels=["100% normal labels", "70% normal / 30% gameplay"],
        xlim=(0, 1),
        ylim=(-0.6, 1.6),
        xlabel="Photo-balanced accuracy",
        title="Same training images, different label origins\n91 reference cutouts · 28 held-out source photos",
    )
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.axvline(0.5, color="#bac2c7", linestyle="--", linewidth=1)
    fig.text(
        0.5,
        0.02,
        f"Mixed − normal: {delta*100:+.1f} points; paired 95% interval {lo*100:+.1f} to {hi*100:+.1f}.\nMixed result is mean of 30 label selections. Conditional pilot uncertainty.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    fig.savefig(out / "comparison.png", dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=HERE / "results/snapshot.json")
    parser.add_argument("--out", type=Path, default=HERE / "results_mix")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    snapshot = json.loads(args.snapshot.read_text())
    snapshot_hash = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True).encode()
    ).hexdigest()
    protocol = {
        "comparison": "100% historical source labels vs 70% historical source / 30% gameplay origin labels",
        "training_pool": "All kept catalog assets; identical unique images and row count in both arms per fold",
        "test_pool": "All frozen reference controls, leaving each entire source-photo SHA-256 out of training",
        "gameplay_pool": "Strict-majority eligible target labels from the earlier frozen snapshot; ties excluded as gameplay candidates",
        "ratio": RATIO,
        "ratio_rounding": "floor(0.30*n_training_rows + 0.5)",
        "selection": "Select required gameplay IDs uniformly by deterministic SHA-256 ranks of seed:asset_id, without using outcomes; no duplicates",
        "mix_seeds": MIX_SEEDS,
        "saved_mixed_model_seed": MIX_SEEDS[0],
        "parameters": PARAMETERS,
        "training_weight_rule": "Unchanged algorithm: equal class/photo weight; actual weights depend on labels",
        "primary_endpoint": "Mean photo-balanced accuracy across 30 separate mixed runs versus normal baseline; no ensembling",
        "uncertainty": "4000 paired class-stratified photo bootstrap draws, sampling one mix seed per draw; conditional on fitted folds/snapshot",
        "snapshot_sha256": snapshot_hash,
        "hyperparameter_search": False,
    }
    write_json(out / "protocol.json", protocol)
    write_json(out / "snapshot.json", snapshot)
    assets = sorted(snapshot["assets"], key=lambda a: a["id"])
    game_labels, ties, _ = aggregate_votes(snapshot["eligible_target_votes"])
    reference = [a for a in assets if a["role"] == "control"]
    features = {}
    feature_names = None
    for a in assets:
        path = ROOT / "backend/assets/fruit_ninja" / a["metadata"]["original_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != a["metadata"]["sha256"]:
            raise ValueError("Asset hash mismatch: " + a["id"])
        vector, names = extract_features(path)
        if feature_names is not None:
            assert names == feature_names
        features[a["id"]] = vector
        feature_names = names
    truth = np.array([int(a["reference_label"] == "rotten") for a in reference])
    photos = np.array([a["metadata"]["source_photo_sha256"] for a in reference])
    normal = np.full(len(reference), np.nan)
    mixtures = np.full((len(MIX_SEEDS), len(reference)), np.nan)
    folds = []
    ratios = []
    for i, held_out in enumerate(sorted(set(photos))):
        train = [a for a in assets if a["metadata"]["source_photo_sha256"] != held_out]
        test = np.flatnonzero(photos == held_out)
        assert held_out not in {a["metadata"]["source_photo_sha256"] for a in train}
        x = np.stack([features[a["id"]] for a in train])
        xt = np.stack([features[reference[j]["id"]] for j in test])
        yt = np.array([int(a["source_label"] == "rotten") for a in train])
        groups = np.array([a["metadata"]["source_photo_sha256"] for a in train])
        normal[test] = fit_model(x, yt, groups).predict_proba(xt)[:, 1]
        selections = []
        for k, seed in enumerate(MIX_SEEDS):
            ym, selected, changed = select_mix(train, game_labels, seed)
            mixtures[k, test] = fit_model(x, ym, groups).predict_proba(xt)[:, 1]
            ratio = len(selected) / len(train)
            ratios.append(ratio)
            selections.append(
                {
                    "seed": seed,
                    "gameplay_asset_ids": sorted(selected),
                    "normal_rows": len(train) - len(selected),
                    "gameplay_rows": len(selected),
                    "gameplay_ratio": ratio,
                    "changed_labels": changed,
                }
            )
        folds.append(
            {
                "held_out_photo_sha256": held_out,
                "test_asset_ids": [reference[j]["id"] for j in test],
                "training_asset_ids": [a["id"] for a in train],
                "mixtures": selections,
            }
        )
        if (i + 1) % 7 == 0:
            print(f"Evaluated {i+1}/{len(set(photos))} held-out photos", flush=True)
    assert np.isfinite(normal).all() and np.isfinite(mixtures).all()
    baseline = metrics(truth, normal, photos)
    per_mix = [metrics(truth, p, photos) for p in mixtures]
    keys = [
        "accuracy",
        "balanced_accuracy",
        "photo_balanced_accuracy",
        "rotten_recall",
        "healthy_recall",
        "macro_f1",
        "roc_auc",
    ]
    means = {key: float(np.mean([m[key] for m in per_mix])) for key in keys}
    scores = np.array([m["photo_balanced_accuracy"] for m in per_mix])
    final_x = np.stack([features[a["id"]] for a in assets])
    final_groups = np.array([a["metadata"]["source_photo_sha256"] for a in assets])
    final_source = np.array([int(a["source_label"] == "rotten") for a in assets])
    final_mixed, selected, changed = select_mix(assets, game_labels, MIX_SEEDS[0])
    save_model(
        out / "normal_gradient_boosting.joblib",
        fit_model(final_x, final_source, final_groups),
        feature_names,
        assets,
        game_labels,
        set(),
        None,
        snapshot_hash,
    )
    save_model(
        out / "mixed_70_30_gradient_boosting.joblib",
        fit_model(final_x, final_mixed, final_groups),
        feature_names,
        assets,
        game_labels,
        selected,
        MIX_SEEDS[0],
        snapshot_hash,
    )
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_sha256": snapshot_hash,
        "sklearn": sklearn.__version__,
        "pool_cutouts": len(assets),
        "eligible_gameplay_cutouts": len(game_labels),
        "gameplay_ties": len(ties),
        "test_reference_cutouts": len(reference),
        "test_photos": len(set(photos)),
        "mix_runs": len(MIX_SEEDS),
        "normal": baseline,
        "mixture_mean": means,
        "mixture_variation": {
            "min": float(scores.min()),
            "max": float(scores.max()),
            "std": float(scores.std(ddof=1)),
            "runs_better_than_normal": int(
                (scores > baseline["photo_balanced_accuracy"] + 1e-12).sum()
            ),
            "runs_equal_to_normal": int(
                np.isclose(
                    scores, baseline["photo_balanced_accuracy"], rtol=0, atol=1e-12
                ).sum()
            ),
        },
        "uncertainty": uncertainty(truth, normal, mixtures, photos),
        "fold_gameplay_ratio_min": min(ratios),
        "fold_gameplay_ratio_max": max(ratios),
        "final_normal_rows": len(assets) - len(selected),
        "final_gameplay_rows": len(selected),
        "final_changed_labels": changed,
    }
    write_json(out / "folds.json", folds)
    csv_write(
        out / "per_mix_metrics.csv",
        [
            {"seed": seed, **{key: m[key] for key in keys}}
            for seed, m in zip(MIX_SEEDS, per_mix)
        ],
    )
    csv_write(
        out / "reference_predictions.csv",
        [
            {
                "asset_id": a["id"],
                "source_photo_sha256": photos[i],
                "reference_label": a["reference_label"],
                "normal_p_rotten": float(normal[i]),
                **{
                    f"mix_{seed}_p_rotten": float(mixtures[k, i])
                    for k, seed in enumerate(MIX_SEEDS)
                },
            }
            for i, a in enumerate(reference)
        ],
    )
    report(summary, out)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
