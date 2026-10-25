"""Idempotently import the kept sprites; no segmentation inference is required."""

import hashlib
import json
import shutil
import uuid

from PIL import Image

from .catalog import (
    ASSET_ROOT,
    BACKEND_ROOT,
    CONTROL_IDS,
    DEMONSTRATIONS,
    REFERENCE_VERSION,
)


def main():
    review = BACKEND_ROOT.parent / "research" / "fruit-ninja" / "dataset-review"
    manifest = json.loads((review / "segmentation-manifest.json").read_text())
    kept = [
        item
        for source in manifest["sources"]
        for item in source["instances"]
        if item["quality"]["decision"] == "kept"
    ]
    assert len(kept) == 183
    assert len(CONTROL_IDS) == 91 and CONTROL_IDS <= {item["id"] for item in kept}
    seed_path = ASSET_ROOT / "catalog.json"
    previous = json.loads(seed_path.read_text()) if seed_path.exists() else None
    if previous and previous["reference_version"] == REFERENCE_VERSION:
        frozen = {a["source_id"]: a for a in previous["assets"]}
        unchanged = set(frozen) == {a["id"] for a in kept} and all(
            frozen[a["id"]]["sha256"] == a["sha256"]
            and (frozen[a["id"]]["role"] == "control") == (a["id"] in CONTROL_IDS)
            and frozen[a["id"]]["reference_label"]
            == (a["state"] if a["id"] in CONTROL_IDS else None)
            for a in kept
        )
        if not unchanged:
            raise ValueError(
                "Bump REFERENCE_VERSION before changing frozen sprites or references"
            )
    for name in ("originals", "gameplay"):
        (ASSET_ROOT / name).mkdir(parents=True, exist_ok=True)
    photos = {
        source["source_id"]: source["source_sha256"] for source in manifest["sources"]
    }
    entries = []
    for item in kept:
        source = review / item["cutout"]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest == item["sha256"], item["id"]
        asset_id = uuid.uuid5(
            uuid.NAMESPACE_URL, "taggle-fruit-shift:" + item["id"]
        ).hex
        original = ASSET_ROOT / "originals" / f"{asset_id}.png"
        changed = (
            not original.exists()
            or hashlib.sha256(original.read_bytes()).hexdigest() != digest
        )
        if changed:
            shutil.copyfile(source, original)
        gameplay = ASSET_ROOT / "gameplay" / f"{asset_id}.webp"
        with Image.open(source) as image:
            image = image.convert("RGBA")
            image.thumbnail((384, 384), Image.Resampling.LANCZOS)
            if changed or not gameplay.exists():
                image.save(gameplay, "WEBP", quality=90, method=6)
            width, height = image.size
        control = item["id"] in CONTROL_IDS
        entries.append(
            {
                "id": asset_id,
                "source_id": item["id"],
                "source_photo_id": item["source_id"],
                "source_photo_sha256": photos[item["source_id"]],
                "fruit_type": item["fruit"],
                "source_label": item["state"],
                "role": "control" if control else "target",
                "reference_label": item["state"] if control else None,
                "reference_version": REFERENCE_VERSION,
                "reference_basis": (
                    "Source label and visually reviewed pilot reference"
                    if control
                    else None
                ),
                "sha256": digest,
                "width": width,
                "height": height,
                "original_path": f"originals/{asset_id}.png",
                "gameplay_path": f"gameplay/{asset_id}.webp",
                "source_bbox_xyxy": item["source_bbox_xyxy"],
            }
        )
    demos = [
        {
            "asset_id": next(
                item["id"] for item in entries if item["source_id"] == source_id
            ),
            "label": label,
            "explanation": explanation,
        }
        for source_id, label, explanation in DEMONSTRATIONS
    ]
    catalog = {
        "reference_version": REFERENCE_VERSION,
        "assets": entries,
        "demonstrations": demos,
        "attribution": "Sultana, Jahan & Uddin (2022), Mendeley Data, doi:10.17632/bdd69gyhv8.1, CC BY 4.0. Cutouts segmented, cropped and resized; original source photographs unchanged.",
    }
    seed_path = ASSET_ROOT / "catalog.json"
    if seed_path.exists():
        previous = json.loads(seed_path.read_text())
        if previous["reference_version"] == REFERENCE_VERSION:
            signature = lambda value: {
                (a["id"], a["role"], a["reference_label"]) for a in value["assets"]
            }
            if signature(previous) != signature(catalog):
                raise ValueError(
                    "Bump REFERENCE_VERSION before changing frozen reference membership"
                )
    (ASSET_ROOT / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    print(
        f"Imported {len(entries)} sprites: {sum(a['role']=='control' for a in entries)} controls, {sum(a['role']=='target' for a in entries)} targets"
    )


if __name__ == "__main__":
    main()
