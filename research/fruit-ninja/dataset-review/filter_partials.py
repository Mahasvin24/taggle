#!/usr/bin/env python3
"""Partition existing fruit masks into kept candidates and excluded partials.

Preserves every candidate, ID, PNG, mask, and inherited label. Only inclusion
decisions, review overlays, and the default kept-labels export change.
"""

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
KEPT_COLOR = (34, 120, 83)
EXCLUDED_COLOR = (185, 68, 44)
REASONS = {
    "frame_crop": "A large part of the fruit is cut off by the photo edge.",
    "missing_section": "A large section is missing from this fruit's outline.",
    "straight_cut": "The remaining fruit has a long cut edge and is small compared with its neighbors.",
    "sliver": "Only a thin sliver remains compared with the other fruit in this photo.",
}


def longest_run(values):
    padded = np.pad(np.asarray(values, dtype=np.int8), (1, 1))
    changes = np.diff(padded)
    starts, ends = np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)
    return int((ends-starts).max(initial=0))


def largest_component(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if count < 2:
        raise ValueError("Cannot assess an empty fruit mask")
    return labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))


def measure_mask(mask, opening_fraction):
    """Measure the body, removing narrow stems from the shape assessment only."""
    mask = largest_component(mask)
    x, y, width, height = cv2.boundingRect(mask.astype(np.uint8))
    radius = max(1, round(min(width, height)*opening_fraction))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*radius+1, 2*radius+1))
    # Padding closes contours on source-frame boundaries and prevents OpenCV's
    # morphology border defaults from manufacturing or erasing edge contact.
    padded = np.pad(mask.astype(np.uint8), radius+2)
    opened = cv2.morphologyEx(padded, cv2.MORPH_OPEN, kernel)
    opened = opened[radius+2:-radius-2, radius+2:-radius-2]
    body = largest_component(opened) if opened.any() else mask
    if body.sum() < mask.sum()*.55:
        body = mask
    contours, _ = cv2.findContours(body.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    (_, _), (rotated_width, rotated_height), _ = cv2.minAreaRect(contour)
    short_side = max(1.0, min(rotated_width, rotated_height))
    aspect = max(rotated_width, rotated_height)/short_side
    # Two-pixel tolerance captures a boundary predicted one pixel inside the photo.
    sides = [body[:2].any(axis=0), body[-2:].any(axis=0),
             body[:, :2].any(axis=1), body[:, -2:].any(axis=1)]
    contact = sum(int(side.sum()) for side in sides)
    polygon = cv2.approxPolyDP(contour, max(1.0, perimeter*.012), True).reshape(-1, 2)
    edges = np.linalg.norm(polygon-np.roll(polygon, 1, axis=0), axis=1)
    return {
        "body_area": int(body.sum()),
        "solidity": round(area/max(hull_area, 1), 5),
        "aspect_ratio": round(aspect, 5),
        "frame_outline_fraction": round(contact/max(perimeter, 1), 5),
        "frame_run_to_short_side": round(max(map(longest_run, sides))/short_side, 5),
        "longest_straight_edge_fraction": round(float(edges.max(initial=0))/max(perimeter, 1), 5),
    }


def decide(metrics, fruit, policy):
    reasons = []
    if (metrics["frame_outline_fraction"] >= policy["frame_outline_fraction"]
            and metrics["frame_run_to_short_side"] >= policy["frame_run_to_short_side"]):
        reasons.append("frame_crop")
    # Banana curvature and elongation are intrinsic to the fruit. Border clipping
    # still applies, but the general round-fruit shape rules do not.
    if not (fruit == "banana" and policy["banana_shape_exemption"]):
        relative_area = metrics["relative_area"]
        if (metrics["solidity"] < policy["missing_section_solidity"]
                and relative_area < policy["missing_section_relative_area"]):
            reasons.append("missing_section")
        if (metrics["longest_straight_edge_fraction"] >= policy["straight_cut_fraction"]
                and relative_area < policy["straight_cut_relative_area"]):
            reasons.append("straight_cut")
        aspect_limit = policy["grape_sliver_aspect_ratio"] if fruit == "grape" else policy["sliver_aspect_ratio"]
        if metrics["aspect_ratio"] >= aspect_limit and relative_area < policy["sliver_relative_area"]:
            reasons.append("sliver")
    return {
        "decision": "excluded_partial" if reasons else "kept",
        "reason_codes": reasons,
        "reasons": [REASONS[reason] for reason in reasons],
        "metrics": metrics,
        "policy_version": policy["version"],
    }


def filter_document(document, root, policy, overrides):
    known_ids = {instance["id"] for source in document["sources"] for instance in source["instances"]}
    if set(overrides)-known_ids:
        raise ValueError(f"Unknown partial-filter override IDs: {sorted(set(overrides)-known_ids)}")
    for source in document["sources"]:
        measured = []
        for instance in source["instances"]:
            mask = np.array(Image.open(root/instance["source_mask"])) > 0
            measured.append(measure_mask(mask, policy["body_opening_fraction"]))
        # The median of the largest quarter is resistant to numerous tiny
        # fragments, while keeping the comparison local to a single photo.
        areas = sorted((item["body_area"] for item in measured), reverse=True)
        reference = float(np.median(areas[:max(1, (len(areas)+3)//4)])) if areas else 1.0
        for number, (instance, metrics) in enumerate(zip(source["instances"], measured), 1):
            metrics["relative_area"] = round(metrics["body_area"]/max(reference, 1), 5)
            quality = decide(metrics, instance["fruit"], policy)
            if instance["id"] in overrides:
                override = overrides[instance["id"]]
                if override["decision"] not in ("kept", "excluded_partial") or not override.get("reason"):
                    raise ValueError(f"Invalid partial-filter override: {instance['id']}")
                quality["automatic_decision"] = quality["decision"]
                quality["decision"] = override["decision"]
                quality["reason_codes"] = ["visual_review"]
                quality["reasons"] = [override["reason"]]
            instance["instance_number"] = number
            instance["quality"] = quality
            instance["review_status"] = "excluded_partial" if quality["decision"] == "excluded_partial" else "candidate"
        source["kept_count"] = sum(item["quality"]["decision"] == "kept" for item in source["instances"])
        source["excluded_count"] = len(source["instances"])-source["kept_count"]
    document["kept_instance_count"] = sum(source["kept_count"] for source in document["sources"])
    document["excluded_instance_count"] = sum(source["excluded_count"] for source in document["sources"])
    document["partial_filter"] = {
        "policy": policy,
        "description": "All candidates are preserved. Counts and segment-labels.csv include only kept cutouts. Excluded partials remain visible with reasons and retain their inherited labels.",
        "limitations": "Geometric heuristics and any recorded visual overrides identify likely heavy partials, not exact fruit completeness. Natural shape variation and occlusion can still require review.",
    }
    return document


def write_labels(document, root):
    fields = ["id", "source_id", "source_row_idx", "fruit", "state", "action", "label_origin",
              "cutout", "alpha_mask", "review_status", "source_edge_clipped", "decision", "exclusion_reason"]
    rows = []
    for source in document["sources"]:
        for instance in source["instances"]:
            record = {key: instance.get(key, "") for key in fields}
            record["decision"] = instance["quality"]["decision"]
            record["exclusion_reason"] = " ".join(instance["quality"]["reasons"]) if record["decision"] != "kept" else ""
            rows.append(record)
    for filename, selected in (("segment-labels.csv", [row for row in rows if row["decision"] == "kept"]),
                               ("segment-review.csv", rows)):
        with (root/filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader(); writer.writerows(selected)


def write_review_assets(document, root):
    sources = {row["id"]: row for row in json.loads((root/"manifest.json").read_text())["rows"]}
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    for source in document["sources"]:
        original = ImageOps.exif_transpose(Image.open(root/sources[source["source_id"]]["original"])).convert("RGB")
        size = tuple(source["instances"][0]["source_mask_size"]) if source["instances"] else original.size
        base = original.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
        for mode, key in (("all", "overlay"), ("kept", "kept_overlay"), ("excluded_partial", "excluded_overlay")):
            overlay = base.copy()
            for instance in source["instances"]:
                decision = instance["quality"]["decision"]
                if mode != "all" and mode != decision:
                    continue
                mask = np.array(Image.open(root/instance["source_mask"])) > 0
                color = KEPT_COLOR if decision == "kept" else EXCLUDED_COLOR
                tint = Image.new("RGBA", size, (*color, 0))
                tint.putalpha(Image.fromarray(mask.astype(np.uint8)*95))
                overlay = Image.alpha_composite(overlay, tint)
                draw = ImageDraw.Draw(overlay)
                contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    points = [tuple(point[0]) for point in contour]
                    if len(points) > 1:
                        draw.line(points+[points[0]], fill=(*color, 255), width=2)
                x, y, _, _ = cv2.boundingRect(mask.astype(np.uint8))
                label = str(instance["instance_number"])
                width = 14+int(draw.textlength(label, font=font))
                draw.rectangle((x, y, x+width, y+24), fill=(*color, 255))
                draw.text((x+6, y+3), label, fill="white", font=font)
            path = f"segments/overlays/{source['source_id']}-{mode}.jpg"
            overlay.convert("RGB").save(root/path, quality=87)
            source[key] = path


def apply_filter(root=ROOT):
    path = root/"segmentation-manifest.json"
    document = json.loads(path.read_text())
    policy = json.loads((root/"partial-filter-policy.json").read_text())
    overrides = json.loads((root/"partial-filter-overrides.json").read_text())
    filter_document(document, root, policy, overrides)
    write_review_assets(document, root)
    write_labels(document, root)
    path.write_text(json.dumps(document, indent=2)+"\n")
    print(f"Partial filter: {document['kept_instance_count']} kept / {document['excluded_instance_count']} excluded; all {document['instance_count']} candidates preserved", flush=True)
    return document


if __name__ == "__main__":
    apply_filter()
