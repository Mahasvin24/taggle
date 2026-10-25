#!/usr/bin/env python3
"""Download a small, repeatable sample of the raw fruit dataset.

Uses curl for HTTPS and Python's standard library; no dataset SDK is needed.
Original JPEG bytes are preserved. Run build_review.py separately for previews.
"""

import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.parse

ROOT = Path(__file__).resolve().parent
DATASET = "Project-AgML/fresh_rotten_fruit_classification"
SOURCE = "https://data.mendeley.com/datasets/bdd69gyhv8/1"
POSITIONS = (17, 83, 149)


def curl(url):
    return subprocess.check_output(
        ["curl", "-sS", "-L", "--fail", "--retry", "2", "--max-time", "60", url]
    )


def fetch(row_idx):
    query = urllib.parse.urlencode(
        {"dataset": DATASET, "config": "raw", "split": "train", "offset": row_idx, "length": 1}
    )
    payload = json.loads(curl("https://datasets-server.huggingface.co/rows?" + query))
    assert payload["num_rows_total"] == 3200, "Dataset changed; recheck sampling."
    record = payload["rows"][0]
    assert record["row_idx"] == row_idx
    row = record["row"]
    state = ("fresh", "rotten")[row["label"]]
    image = row["image"]
    stem = f"{row['fruit_type']}-{state}-{row_idx:04d}"
    path = ROOT / "originals" / (stem + ".jpg")
    if not path.exists():
        path.write_bytes(curl(image["src"]))
    data = path.read_bytes()
    print(f"{stem}: {image['width']} x {image['height']}, {len(data):,} bytes", flush=True)
    return {
        "id": stem,
        "row_idx": row_idx,
        "fruit": row["fruit_type"],
        "state": state,
        "action": "collect" if state == "fresh" else "slash",
        "width": image["width"],
        "height": image["height"],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "original": f"originals/{stem}.jpg",
        "preview": f"previews/{stem}.jpg",
        "row_url": f"https://huggingface.co/datasets/{DATASET}/viewer/raw/train?row={row_idx}",
        "row_api": "https://datasets-server.huggingface.co/rows?" + query,
        "mirror_revision": image["src"].split("/--/")[1],
    }


def main():
    (ROOT / "originals").mkdir(parents=True, exist_ok=True)
    indices = [block * 200 + position for block in range(16) for position in POSITIONS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = sorted(pool.map(fetch, indices), key=lambda item: item["row_idx"])
    classes = {(row["fruit"], row["state"]) for row in rows}
    assert len(classes) == 16
    assert all(sum((r["fruit"], r["state"]) == c for r in rows) == 3 for c in classes)
    manifest = {
        "source": SOURCE,
        "authors": ["Nusrat Sultana", "Musfika Jahan", "Mohammad Shorif Uddin"],
        "doi": "10.17632/bdd69gyhv8.1",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "mirror": f"https://huggingface.co/datasets/{DATASET}",
        "config": "raw",
        "split": "train",
        "sampling": "Three fixed row positions (17, 83, 149) within each 200-row class block; selected before visual inspection. This is a feasibility sample, not a statistical quality audit.",
        "rows": rows,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Saved {len(rows)} originals and manifest.json", flush=True)


if __name__ == "__main__":
    main()
