"""Leakage-aware pilot: learn from game labels, test against frozen photo-held-out controls.

No database writes, label correction, pretrained downloads, or hyperparameter search.
Run with this directory's isolated Python environment; see README.md.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3
import sys
import os
import tempfile

import joblib

# Keep plotting caches writable in restricted desktop sessions.
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "taggle-matplotlib")
)
os.environ.setdefault(
    "XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "taggle-model-cache")
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SEED = 20261024
PARAMETERS = dict(
    n_estimators=80,
    learning_rate=0.05,
    max_depth=2,
    min_samples_leaf=3,
    subsample=1.0,
    random_state=SEED,
)
MODEL_NAMES = {
    "gameplay": "Gameplay labels · gradient boosting",
    "always_healthy": "Always healthy",
    "fruit_type": "Fruit-type-only baseline",
    "source_label": "Same images · source-photo labels (diagnostic)",
    "reference": "Reference controls · gradient boosting (diagnostic)",
}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read_snapshot(database):
    """One read-only SQLite transaction, including committed WAL data."""
    with closing(
        sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
    ) as c:
        c.row_factory = sqlite3.Row
        c.execute("BEGIN")
        assets = [dict(r) for r in c.execute("SELECT * FROM assets ORDER BY id")]
        for a in assets:
            a["metadata"] = json.loads(a["metadata"])
        votes = [
            dict(r)
            for r in c.execute(
                """
            SELECT p.asset_id,p.id AS presentation_id,r.id AS round_id,r.player_id,
                   e.event_id,e.label,e.phase,e.received_at
            FROM presentations p JOIN rounds r ON r.id=p.round_id
            JOIN label_events e ON e.presentation_id=p.id
            WHERE p.role='target' AND r.kind='game' AND r.eligible=1
              AND r.status='completed'
              AND e.sequence=(SELECT MAX(e2.sequence) FROM label_events e2 WHERE e2.presentation_id=p.id)
            ORDER BY e.sequence
        """
            )
        ]
        controls = [
            dict(r)
            for r in c.execute(
                """
            SELECT p.asset_id,p.reference_label,e.label,r.id AS round_id,r.player_id
            FROM presentations p JOIN rounds r ON r.id=p.round_id
            JOIN label_events e ON e.presentation_id=p.id
            WHERE p.role='control' AND r.kind='game' AND r.eligible=1
              AND r.status='completed' AND e.phase='initial' ORDER BY e.sequence
        """
            )
        ]
        rounds = [
            dict(r)
            for r in c.execute(
                """
            SELECT id,kind,status,eligible,first_pass_correct,first_pass_total,exclusion_reason
            FROM rounds ORDER BY created_at,id
        """
            )
        ]
        c.rollback()
    snapshot = {
        "assets": assets,
        "eligible_target_votes": votes,
        "qualified_first_pass_control_calls": controls,
        "rounds": rounds,
    }
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return snapshot, digest


def aggregate_votes(votes):
    groups = defaultdict(list)
    for v in votes:
        groups[v["asset_id"]].append(v)
    labeled, ties = {}, []
    for asset_id, own in sorted(groups.items()):
        rotten = sum(v["label"] == "rotten" for v in own)
        if rotten * 2 == len(own):
            ties.append(asset_id)
        else:
            labeled[asset_id] = int(rotten * 2 > len(own))
    return labeled, ties, groups


def extract_features(path):
    """Only opaque photo pixels: color distribution and local texture, no identities.

    Per-image transforms are fixed; nothing is learned from held-out data.
    Alpha identifies foreground but mask area, crop size and file names are not features.
    """
    with Image.open(path) as image:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.float64) / 255
    mask = rgba[:, :, 3] > 0.8
    if mask.sum() < 20:
        raise ValueError(f"Insufficient opaque foreground: {path}")
    rgb = rgba[:, :, :3]
    hsv = (
        np.asarray(
            Image.fromarray(np.uint8(np.round(rgb * 255))).convert("HSV"), dtype=float
        )
        / 255
    )
    gray = rgb @ np.array([0.2126, 0.7152, 0.0722])
    names, values = [], []
    for name, channel in [
        ("red", rgb[:, :, 0]),
        ("green", rgb[:, :, 1]),
        ("blue", rgb[:, :, 2]),
        ("saturation", hsv[:, :, 1]),
        ("value", hsv[:, :, 2]),
        ("luminance", gray),
    ]:
        x = channel[mask]
        for stat, value in [
            ("mean", x.mean()),
            ("std", x.std()),
            ("p10", np.quantile(x, 0.1)),
            ("median", np.median(x)),
            ("p90", np.quantile(x, 0.9)),
        ]:
            names.append(f"{name}_{stat}")
            values.append(float(value))
    # Hue is circular; keep its histogram and sine/cosine rather than a false red discontinuity.
    hue = hsv[:, :, 0][mask]
    hist, _ = np.histogram(hue, bins=12, range=(0, 1))
    for i, count in enumerate(hist):
        names.append(f"hue_bin_{i}")
        values.append(float(count / len(hue)))
    for label, value in [
        ("hue_cos", np.cos(hue * 2 * np.pi).mean()),
        ("hue_sin", np.sin(hue * 2 * np.pi).mean()),
    ]:
        names.append(label)
        values.append(float(value))
    for channel_name, channel in [("luminance", gray), ("saturation", hsv[:, :, 1])]:
        for direction, first, second, valid in [
            ("horizontal", channel[:, 1:], channel[:, :-1], mask[:, 1:] & mask[:, :-1]),
            ("vertical", channel[1:, :], channel[:-1, :], mask[1:, :] & mask[:-1, :]),
        ]:
            d = np.abs(first - second)[valid]
            for stat, value in [
                ("mean", d.mean() if len(d) else 0),
                ("p90", np.quantile(d, 0.9) if len(d) else 0),
            ]:
                names.append(f"{channel_name}_{direction}_difference_{stat}")
                values.append(float(value))
    # Relative thresholds describe surface patches without a fixed background color.
    g, sat = gray[mask], hsv[:, :, 1][mask]
    for label, value in [
        ("dark_fraction", (g < 0.18).mean()),
        ("pale_fraction", ((g > 0.65) & (sat < 0.25)).mean()),
        ("low_saturation_fraction", (sat < 0.2).mean()),
        ("red_minus_green", (rgb[:, :, 0][mask] - rgb[:, :, 1][mask]).mean()),
        ("green_minus_blue", (rgb[:, :, 1][mask] - rgb[:, :, 2][mask]).mean()),
    ]:
        names.append(label)
        values.append(float(value))
    result = np.asarray(values, dtype=float)
    assert np.isfinite(result).all()
    return result, names


def train_weights(labels, photos):
    """Equal weight per class and per photo within a class, not per cutout count."""
    pairs = Counter(zip(labels, photos))
    class_photos = Counter(label for label, _ in pairs)
    weights = np.array(
        [1 / (class_photos[y] * pairs[y, g]) for y, g in zip(labels, photos)]
    )
    return weights * len(weights) / weights.sum()


def fit_model(x, y, photos):
    if len(np.unique(y)) != 2:
        raise ValueError("Both classes required in every training fold")
    model = GradientBoostingClassifier(**PARAMETERS)
    model.fit(x, y, sample_weight=train_weights(y, photos))
    return model


def photo_weights(groups):
    sizes = Counter(groups)
    return np.asarray([1 / sizes[g] for g in groups])


def metrics(y, probability, photos):
    prediction = probability >= 0.5
    weighted = photo_weights(photos)
    return {
        "accuracy": float(accuracy_score(y, prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
        "photo_balanced_accuracy": float(
            balanced_accuracy_score(y, prediction, sample_weight=weighted)
        ),
        "rotten_recall": float(((prediction == 1) & (y == 1)).sum() / (y == 1).sum()),
        "healthy_recall": float(((prediction == 0) & (y == 0)).sum() / (y == 0).sum()),
        "macro_f1": float(f1_score(y, prediction, average="macro", zero_division=0)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist(),
    }


def cluster_bootstrap(y, predictions, photos, iterations=4000):
    """Resample photos within each reference class, paired across all models.

    This describes variability across these test photos, conditional on the fitted folds;
    it is not a full training-sample uncertainty interval or an independent validation study.
    """
    groups = np.unique(photos)
    per_photo = {
        name: np.array(
            [
                np.mean((probability[photos == g] >= 0.5) == y[photos == g])
                for g in groups
            ]
        )
        for name, probability in predictions.items()
    }
    truth = np.array([y[photos == g][0] for g in groups])
    for g in groups:
        assert len(np.unique(y[photos == g])) == 1
    rng = np.random.default_rng(SEED)
    boot = {name: np.empty(iterations) for name in predictions}
    for b in range(iterations):
        indices = [
            rng.choice(
                np.flatnonzero(truth == cls),
                size=int((truth == cls).sum()),
                replace=True,
            )
            for cls in [0, 1]
        ]
        for name, score in per_photo.items():
            boot[name][b] = np.mean([score[idx].mean() for idx in indices])
    intervals = {
        name: np.quantile(values, [0.025, 0.975]).tolist()
        for name, values in boot.items()
    }
    differences = {
        name: np.quantile(boot["gameplay"] - boot[name], [0.025, 0.975]).tolist()
        for name in boot
        if name != "gameplay"
    }
    return intervals, differences


def evaluate(targets, reference, features, consensus):
    """Leave one reference source-photo hash out. Drop ALL its training cutouts."""
    y = np.array([int(a["reference_label"] == "rotten") for a in reference])
    photos = np.array([a["metadata"]["source_photo_sha256"] for a in reference])
    x_test = np.stack([features[a["id"]] for a in reference])
    predictions = {name: np.full(len(reference), np.nan) for name in MODEL_NAMES}
    folds = []
    for held_out in sorted(set(photos)):
        test = np.flatnonzero(photos == held_out)
        train = [a for a in targets if a["metadata"]["source_photo_sha256"] != held_out]
        ref_train = [
            a for a in reference if a["metadata"]["source_photo_sha256"] != held_out
        ]
        assert not {a["id"] for a in train} & {reference[i]["id"] for i in test}
        assert held_out not in {
            a["metadata"]["source_photo_sha256"] for a in train + ref_train
        }
        x = np.stack([features[a["id"]] for a in train])
        labels = np.array([consensus[a["id"]] for a in train])
        train_photos = np.array([a["metadata"]["source_photo_sha256"] for a in train])
        model = fit_model(x, labels, train_photos)
        predictions["gameplay"][test] = model.predict_proba(x_test[test])[:, 1]
        source_y = np.array([int(a["source_label"] == "rotten") for a in train])
        foil = fit_model(x, source_y, train_photos)
        predictions["source_label"][test] = foil.predict_proba(x_test[test])[:, 1]
        reference_model = fit_model(
            np.stack([features[a["id"]] for a in ref_train]),
            np.array([int(a["reference_label"] == "rotten") for a in ref_train]),
            np.array([a["metadata"]["source_photo_sha256"] for a in ref_train]),
        )
        predictions["reference"][test] = reference_model.predict_proba(x_test[test])[
            :, 1
        ]
        # Fixed always-healthy comparator: no inspection of held-out answers to choose it.
        predictions["always_healthy"][test] = 0
        for i in test:
            own = [
                consensus[a["id"]]
                for a in train
                if a["fruit_type"] == reference[i]["fruit_type"]
            ]
            predictions["fruit_type"][i] = (
                float(np.mean(own)) if own else float(labels.mean())
            )
        folds.append(
            {
                "held_out_photo_sha256": held_out,
                "test_asset_ids": [reference[i]["id"] for i in test],
                "train_asset_ids": [a["id"] for a in train],
                "reference_train_asset_ids": [a["id"] for a in ref_train],
                "training_game_label_counts": dict(Counter(map(str, labels.tolist()))),
            }
        )
    assert all(np.isfinite(p).all() for p in predictions.values())
    results = {
        name: metrics(y, probability, photos)
        for name, probability in predictions.items()
    }
    ci, differences = cluster_bootstrap(y, predictions, photos)
    for name in results:
        results[name]["photo_balanced_accuracy_ci95"] = ci[name]
    return results, predictions, folds, differences


def csv_write(path, rows):
    import csv

    if not rows:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(results, path):
    order = ["always_healthy", "fruit_type", "gameplay", "source_label", "reference"]
    fig, (ax, matrix_ax) = plt.subplots(
        1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [1.65, 1]}
    )
    colors = ["#8c969d", "#8c969d", "#217d8c", "#ab8254", "#646a96"]
    for i, (name, color) in enumerate(zip(order, colors)):
        value = results[name]["photo_balanced_accuracy"]
        lo, hi = results[name]["photo_balanced_accuracy_ci95"]
        ax.errorbar(
            value,
            i,
            xerr=[[max(0, value - lo)], [max(0, hi - value)]],
            fmt="o",
            color=color,
            capsize=4,
            markersize=8,
        )
        ax.text(0.995, i, f"{value:.1%}", va="center", ha="right", fontsize=10)
    ax.set(
        yticks=range(len(order)),
        yticklabels=[MODEL_NAMES[n] for n in order],
        xlim=(0, 1),
        xlabel="Photo-balanced accuracy (95% photo bootstrap interval)",
        title="Held-out reference photos · 91 cutouts / 28 photos",
    )
    ax.invert_yaxis()
    ax.axvline(0.5, color="#bbc2c7", linestyle="--", linewidth=1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    matrix = np.array(results["gameplay"]["confusion_matrix"])
    matrix_ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(1, matrix.max()))
    for (i, j), count in np.ndenumerate(matrix):
        matrix_ax.text(
            j,
            i,
            str(count),
            ha="center",
            va="center",
            fontsize=20,
            color="white" if count > matrix.max() / 2 else "#203e49",
        )
    matrix_ax.set(
        xticks=[0, 1],
        yticks=[0, 1],
        xticklabels=["Healthy", "Rotten"],
        yticklabels=["Healthy", "Rotten"],
        xlabel="Predicted",
        ylabel="Reference",
        title="Gameplay-trained model\nCutout-level counts",
    )
    fig.suptitle(
        "Can game labels train a model that transfers to unseen fruit photos?",
        fontsize=15,
    )
    fig.text(
        0.5,
        0.01,
        "Pilot references, not expert ground truth. Error bars do not include full training-sample uncertainty.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.93))
    fig.savefig(path, dpi=170)
    plt.close(fig)


def write_report(summary, path):
    """Generate the concise result interpretation from the frozen run, not live counts."""
    s = summary
    rows = []
    for name in [
        "always_healthy",
        "fruit_type",
        "gameplay",
        "source_label",
        "reference",
    ]:
        r = s["model_results"][name]
        lo, hi = r["photo_balanced_accuracy_ci95"]
        rows.append(
            f"| {MODEL_NAMES[name]} | {r['accuracy']:.1%} | {r['balanced_accuracy']:.1%} | {r['photo_balanced_accuracy']:.1%} ({lo:.1%}–{hi:.1%}) |"
        )
    per_fruit = [
        f"| {fruit} | {r['cutouts']} | {r['photos']} | {r['accuracy']:.1%} | "
        + (
            f"{r['rotten_recall']:.1%}"
            if r["rotten_recall"] is not None
            else "No rotten references"
        )
        + " |"
        for fruit, r in s["reference_results_by_fruit"].items()
    ]
    control = s["qualified_control_agreement"]
    agree = s["target_consensus_source_agreement"]
    direct = s["target_vote_source_agreement"]
    source = s["target_source_disagreement_by_source_class"]
    g = s["model_results"]["gameplay"]
    text = (
        f"""# Fruit gameplay label-quality pilot

The gradient-boosted model learned a weak, uncertain signal across independent source photos. It is **not yet evidence that the current gameplay labels train a reliable classifier**. This is a pilot diagnosis of a small dataset and a simple color/texture model, not a measured label-error rate.

Snapshot: `{s['snapshot_sha256']}`. Captured/run at {s['created_at_utc']} (UTC). The initial inventory was 64 votes; new gameplay before the frozen run increased it to **{s['eligible_votes']} eligible votes on {s['unique_voted_cutouts']} unique target cutouts**. After excluding {len(s['tied_assets'])} tied cutouts, training uses **{s['training_cutouts']} cutouts from {s['training_photos']} source photos** ({s['training_class_counts']['healthy']} healthy / {s['training_class_counts']['rotten']} rotten). Counts refer to this snapshot, not the live game.

## Experiment

Train a fixed `GradientBoostingClassifier` on eligible gameplay target labels only. Repeated votes produce one majority label per asset; ties are excluded. Extract {s['feature_count']} fixed foreground color/texture features from transparent originals. No player, fruit type, filename, ID, crop dimensions or source label enters the gameplay model. Balance training weights by class and source photo. No data augmentation, pretrained model, tuning, or label correction.

Test on {s['test_reference_cutouts']} frozen reference cutouts ({s['test_class_counts']['fresh']} healthy / {s['test_class_counts']['rotten']} rotten) from {s['test_reference_photos']} source photos. For each test photo, exclude **all cutouts of that photo by SHA-256** from that fold's training, including any target cutouts. Each reference cutout is predicted once. The final saved model is separately refit on all resolved target labels; its in-sample predictions are not these test results.

## Results

| Training / comparator | Cutout accuracy | Class-balanced accuracy | Photo-balanced accuracy (95% interval) |
|---|---:|---:|---:|
"""
        + "\n".join(rows)
        + f"""

The primary metric gives every source photo equal weight within each class, then averages healthy and rotten recall. Ordinary cutout metrics overweight photos with many segmented berries/grapes. The gameplay model's {g['accuracy']:.1%} ordinary accuracy falls to **{g['photo_balanced_accuracy']:.1%}** on the primary metric. Its 95% interval includes the 50% constant-class baseline. A useful predictive signal across unseen photos is not established by this run.

The bootstrap resamples reference photos within class, uses the same resamples for every model, and uses 4,000 iterations. Its interval describes variation over these test photos conditional on the fitted folds; it does **not** capture full uncertainty from retraining on new gameplay data. The paired gameplay-minus-source-label interval crosses zero, so the apparent source-label advantage is uncertain too. See `summary.json` for paired intervals.

The source-label model uses identical training images/features/folds but replaces only the training labels with historical source-photo labels. It is a sensitivity check, **not a corrected dataset**: source-inherited labels are not independent expert truth. The reference-trained comparator uses the other reference photos and has different training coverage/size. Its higher score suggests the features can encode some reference condition, but neither comparison isolates a causal label-noise effect.

Gameplay model confusion matrix (rows: reference; columns: prediction):

| | Predicted healthy | Predicted rotten |
|---|---:|---:|
| Reference healthy | {g['confusion_matrix'][0][0]} | {g['confusion_matrix'][0][1]} |
| Reference rotten | {g['confusion_matrix'][1][0]} | {g['confusion_matrix'][1][1]} |

Rotten recall: **{g['rotten_recall']:.1%}**; healthy recall: **{g['healthy_recall']:.1%}**. Predicted probabilities are uncalibrated scores, not validated confidence estimates.

## Direct label audit

- On hidden controls in qualifying games, original player calls agree with the prototype reference on **{control['correct']}/{control['n']} ({control['accuracy']:.1%})**. This is conditional on passing the game's 13/16 gate; it is selection-biased and does not estimate all-play or target-label accuracy.
- Across targets, **{direct['correct']}/{direct['n']} votes ({direct['correct']/direct['n']:.1%})** and **{agree['correct']}/{agree['n']} resolved majority labels ({agree['correct']/agree['n']:.1%})** agree with historical source-photo labels. These disagreements are review candidates, not automatically player mistakes.
- Of {source['rotten']['n']} source-rotten target cutouts, **{source['rotten']['disagree']} were called healthy** by the resolved majority. Of {source['fresh']['n']} source-healthy targets, {source['fresh']['disagree']} were called rotten. Missing visible decay, intentional disagreement with source labels, and ambiguity in inherited crop labels are all plausible. This experiment cannot distinguish them.
- The dataset comes from local profiles, not authenticated independent annotators. Profiles may be the same person. Repeat appearances and nearby cutouts are not independent raters or independent photos.

Open `audit.html` for every voted target, including the ties, with its image, votes, historical source label, and a prediction trained on other photos. The model only flags candidates; no game labels were changed. `target_audit.csv` and `reference_predictions.csv` retain the underlying rows.

## Fruit breakdown (descriptive only)

| Fruit | Reference cutouts | Source photos | Cutout accuracy | Rotten recall |
|---|---:|---:|---:|---:|
"""
        + "\n".join(per_fruit)
        + """

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
"""
    )
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "backend/data.db")
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Replay a frozen snapshot instead of querying live SQLite",
    )
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    # Record protocol before fitting anything. No tuning against controls is performed.
    protocol = {
        "model": "sklearn.ensemble.GradientBoostingClassifier",
        "parameters": PARAMETERS,
        "primary_endpoint": "Source-photo-balanced reference accuracy (mean class recall, equal photo weight within class)",
        "validation": "Leave-one-reference-source-photo-out, train on eligible target consensus only; exclude entire held-out photo by SHA-256",
        "label_rule": "One row per unique asset; strict vote majority; exclude ties; no vote-count sample weighting",
        "training_weight_rule": "Equal class weight and equal source-photo weight within class",
        "features": "Fixed alpha-masked RGB/HSV distributions and local texture; no type, ID, label, player, filename or source metadata",
        "threshold": 0.5,
        "seed": SEED,
        "bootstrap_iterations": 4000,
        "comparators": MODEL_NAMES,
        "hyperparameter_search": False,
        "reference_limit": "Controls are source-inherited, visually reviewed pilot references; not independent expert truth",
    }
    write_json(args.out / "protocol.json", protocol)
    if args.snapshot:
        snapshot = json.loads(args.snapshot.read_text())
        snapshot_hash = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode()
        ).hexdigest()
    else:
        snapshot, snapshot_hash = read_snapshot(args.db)
    write_json(args.out / "snapshot.json", snapshot)
    votes = snapshot["eligible_target_votes"]
    consensus, ties, vote_groups = aggregate_votes(votes)
    assets = {a["id"]: a for a in snapshot["assets"]}
    targets = [assets[key] for key in consensus]
    reference = [a for a in snapshot["assets"] if a["role"] == "control"]
    if len(targets) < 20 or len(set(consensus.values())) < 2:
        raise ValueError(
            "Need at least 20 resolved target cutouts and both classes for this pilot"
        )
    features, names, hashes = {}, None, {}
    for a in targets + reference:
        path = ROOT / "backend/assets/fruit_ninja" / a["metadata"]["original_path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != a["metadata"]["sha256"]:
            raise ValueError(f"Asset hash mismatch: {a['id']}")
        vector, feature_names = extract_features(path)
        if names is not None:
            assert feature_names == names
        features[a["id"]], names, hashes[a["id"]] = vector, feature_names, digest
    result, probabilities, folds, paired_ci = evaluate(
        targets, reference, features, consensus
    )
    reference_predictions = []
    for i, a in enumerate(reference):
        reference_predictions.append(
            {
                "asset_id": a["id"],
                "photo_sha256": a["metadata"]["source_photo_sha256"],
                "fruit_type": a["fruit_type"],
                "reference_label": a["reference_label"],
                **{
                    name + "_p_rotten": float(p[i]) for name, p in probabilities.items()
                },
            }
        )
    csv_write(args.out / "reference_predictions.csv", reference_predictions)
    # Out-of-photo predictions for target audit: model flags disagreement, never changes labels.
    # Train exclusively on OTHER photos, and do not use source labels in the gameplay audit model.
    audit = []
    for a in [assets[key] for key in sorted(vote_groups)]:
        photo = a["metadata"]["source_photo_sha256"]
        train = [t for t in targets if t["metadata"]["source_photo_sha256"] != photo]
        model = fit_model(
            np.stack([features[t["id"]] for t in train]),
            np.array([consensus[t["id"]] for t in train]),
            np.array([t["metadata"]["source_photo_sha256"] for t in train]),
        )
        if (
            a["id"] not in features
        ):  # Tied rows are audit-only, never training examples.
            path = ROOT / "backend/assets/fruit_ninja" / a["metadata"]["original_path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != a["metadata"]["sha256"]:
                raise ValueError(f"Asset hash mismatch: {a['id']}")
            hashes[a["id"]] = digest
            features[a["id"]], _ = extract_features(path)
        probability = float(model.predict_proba([features[a["id"]]])[0, 1])
        own = vote_groups[a["id"]]
        label = consensus.get(a["id"])
        audit.append(
            {
                "asset_id": a["id"],
                "photo_sha256": photo,
                "fruit_type": a["fruit_type"],
                "healthy_votes": sum(v["label"] == "fresh" for v in own),
                "rotten_votes": sum(v["label"] == "rotten" for v in own),
                "game_consensus": (
                    "tie" if label is None else "rotten" if label else "fresh"
                ),
                "historical_source_label_not_expert_truth": a["source_label"],
                "photo_held_out_model_p_rotten": probability,
                "consensus_disagrees_with_source": label is not None
                and label != int(a["source_label"] == "rotten"),
                "model_disagrees_with_consensus": label is not None
                and int(probability >= 0.5) != label,
            }
        )
    csv_write(args.out / "target_audit.csv", audit)
    x = np.stack([features[a["id"]] for a in targets])
    y = np.array([consensus[a["id"]] for a in targets])
    photos = np.array([a["metadata"]["source_photo_sha256"] for a in targets])
    final = fit_model(x, y, photos)
    joblib.dump(
        {
            "model": final,
            "feature_names": names,
            "feature_version": "masked-color-texture-v1",
            "training_asset_ids": [a["id"] for a in targets],
            "snapshot_sha256": snapshot_hash,
            "classes": {0: "fresh", 1: "rotten"},
            "threshold": 0.5,
        },
        args.out / "gameplay_gradient_boosting.joblib",
    )
    np.savez_compressed(
        args.out / "features.npz",
        asset_ids=list(features),
        matrix=np.stack(list(features.values())),
        names=names,
    )
    write_json(args.out / "folds.json", folds)
    write_json(args.out / "asset_hashes.json", hashes)
    control_calls = snapshot["qualified_first_pass_control_calls"]
    true_control = np.array(
        [int(v["reference_label"] == "rotten") for v in control_calls]
    )
    pred_control = np.array([int(v["label"] == "rotten") for v in control_calls])
    controls_photo = np.array(
        [
            assets[v["asset_id"]]["metadata"]["source_photo_sha256"]
            for v in control_calls
        ]
    )
    by_fruit = {}
    for fruit in sorted({a["fruit_type"] for a in reference}):
        idx = np.array([i for i, a in enumerate(reference) if a["fruit_type"] == fruit])
        truth = np.array(
            [int(reference[i]["reference_label"] == "rotten") for i in idx]
        )
        prediction = probabilities["gameplay"][idx] >= 0.5
        by_fruit[fruit] = {
            "cutouts": len(idx),
            "photos": len(
                {reference[i]["metadata"]["source_photo_sha256"] for i in idx}
            ),
            "healthy": int((truth == 0).sum()),
            "rotten": int((truth == 1).sum()),
            "accuracy": float(np.mean(truth == prediction)),
            "rotten_recall": (
                float(prediction[truth == 1].mean()) if (truth == 1).any() else None
            ),
        }
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_sha256": snapshot_hash,
        "python": sys.version.split()[0],
        "sklearn": sklearn.__version__,
        "numpy": np.__version__,
        "eligible_votes": len(votes),
        "unique_voted_cutouts": len(vote_groups),
        "tied_assets": ties,
        "training_cutouts": len(targets),
        "training_photos": len(set(photos)),
        "training_class_counts": {
            "healthy": int((y == 0).sum()),
            "rotten": int((y == 1).sum()),
        },
        "test_reference_cutouts": len(reference),
        "test_reference_photos": len(folds),
        "test_class_counts": dict(Counter(a["reference_label"] for a in reference)),
        "reference_results_by_fruit": by_fruit,
        "feature_count": len(names),
        "source_photo_overlap_per_fold": 0,
        "model_results": result,
        "gameplay_minus_comparator_photo_accuracy_ci95": paired_ci,
        "qualified_control_agreement": {
            "n": len(control_calls),
            "correct": int((true_control == pred_control).sum()),
            **metrics(true_control, pred_control.astype(float), controls_photo),
        },
        "target_vote_source_agreement": {
            "correct": sum(
                v["label"] == assets[v["asset_id"]]["source_label"] for v in votes
            ),
            "n": len(votes),
        },
        "target_consensus_source_agreement": {
            "correct": sum(
                consensus[a["id"]] == int(a["source_label"] == "rotten")
                for a in targets
            ),
            "n": len(targets),
        },
        "target_source_disagreement_by_source_class": {
            label: {
                "n": sum(a["source_label"] == label for a in targets),
                "disagree": sum(
                    a["source_label"] == label
                    and consensus[a["id"]] != int(label == "rotten")
                    for a in targets
                ),
            }
            for label in ["fresh", "rotten"]
        },
    }
    write_json(args.out / "summary.json", summary)
    plot_results(result, args.out / "evaluation.png")
    write_report(summary, args.out / "REPORT.md")
    # Minimal static audit gallery, referencing local originals rather than copying/recoloring photos.
    cards = []
    for row in sorted(
        audit,
        key=lambda r: (
            r["game_consensus"] != "tie",
            not r["consensus_disagrees_with_source"],
            r["asset_id"],
        ),
    ):
        asset = assets[row["asset_id"]]
        import os

        image_path = os.path.relpath(
            ROOT / "backend/assets/fruit_ninja" / asset["metadata"]["original_path"],
            args.out,
        )
        cards.append(
            f'<article><img src="{html.escape(image_path)}" alt="{html.escape(row["fruit_type"])} cutout"><p>Game: <b>{row["game_consensus"]}</b> ({row["healthy_votes"]} healthy / {row["rotten_votes"]} rotten)</p><p>Historical source: {row["historical_source_label_not_expert_truth"]}</p><p>Other-photo model p(rotten): {row["photo_held_out_model_p_rotten"]:.2f}</p><small>{row["asset_id"]}</small></article>'
        )
    (args.out / "audit.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Fruit label audit</title><style>body{font:16px system-ui;margin:28px;color:#203e49}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(235px,1fr));gap:20px}article{background:#edf4f5;padding:16px}img{width:100%;height:170px;object-fit:contain}p{margin:8px 0}small{overflow-wrap:anywhere}</style><h1>Fruit label audit</h1><p>Ties and historical-source disagreements first. Neither source labels nor this small model establish individual truth. Review candidates only; no saved labels were changed.</p><main>'
        + "".join(cards)
        + "</main>"
    )
    print(
        json.dumps(
            {
                "training_cutouts": len(targets),
                "reference_test_photos": len(folds),
                "photo_balanced_accuracy": {
                    name: round(m["photo_balanced_accuracy"], 4)
                    for name, m in result.items()
                },
                "output": str(args.out),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
