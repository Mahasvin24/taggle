#!/usr/bin/env python3
"""Generate cached SlimSAM instance-mask proposals for the sampled originals.

These are proposals, not semantic fruit detections. Export only reviewed fruit
instances with export_segments.py. Source JPEGs are never changed.
"""

import argparse
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import torch
from transformers import pipeline
from transformers.pipelines import MaskGenerationPipeline

MODEL_REVISION = "d67c795ed0caaec7423d799da25cdeded48aac40"


class Float32MaskPipeline(MaskGenerationPipeline):
    """The stock crop grid uses float64, which Apple MPS does not support."""

    def preprocess(self, *args, **kwargs):
        for batch in super().preprocess(*args, **kwargs):
            for key, value in batch.items():
                if isinstance(value, np.ndarray) and value.dtype == np.float64:
                    batch[key] = value.astype(np.float32)
                elif isinstance(value, torch.Tensor) and value.dtype == torch.float64:
                    batch[key] = value.float()
            yield batch


def checker(size):
    y, x = np.indices((size[1], size[0]))
    colors = np.where(((x // 12 + y // 12) % 2)[..., None], 225, 250).astype(np.uint8)
    return Image.fromarray(np.repeat(colors, 3, axis=2), "RGB")


def proposal_sheet(row, photo, masks, scores, folder):
    columns, width, height = 8, 190, 190
    canvas = Image.new("RGB", (columns * width, 70 + ((len(masks) + columns - 1) // columns) * height), "#eef3f8")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
    draw.text((10, 8), f"{row['id']}: raw mask proposals (including background / parts)", fill="black", font=font)
    for index, (mask, score) in enumerate(zip(masks, scores)):
        x, y = (index % columns) * width, 65 + (index // columns) * height
        rgba = photo.convert("RGBA")
        rgba.putalpha(Image.fromarray(mask.astype(np.uint8) * 255))
        bbox = rgba.getbbox()
        if bbox:
            cutout = ImageOps.contain(rgba.crop(bbox), (width - 12, height - 36))
            background = checker((width - 8, height - 30))
            background.paste(cutout, ((background.width-cutout.width)//2,(background.height-cutout.height)//2), cutout)
            canvas.paste(background, (x+4, y+24))
        draw.text((x+6,y), f"{index}: {score:.2f}", fill="black", font=font)
    canvas.save(folder / "proposals.jpg", quality=88)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, nargs="*")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    rows = json.loads((ROOT / "manifest.json").read_text())["rows"]
    rows = [row for row in rows if args.rows is None or row["row_idx"] in args.rows]
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    torch.set_num_threads(4)
    print("Loading SlimSAM on", device, flush=True)
    generator = pipeline("mask-generation", model=str(ROOT / ".models" / "slimsam"), device=device,
                         pipeline_class=Float32MaskPipeline, use_fast=False)
    for row in rows:
        folder = ROOT / ".cache" / "proposals" / row["id"]
        if (folder / "metadata.json").exists() and not args.force:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        photo = ImageOps.exif_transpose(Image.open(ROOT / row["original"])).convert("RGB")
        photo.thumbnail((960,960), Image.Resampling.LANCZOS)
        start = time.time()
        points = 32 if row["row_idx"] in (149, 1483, 3017) else 16
        output = generator(photo, points_per_batch=16, points_per_crop=points,
                           pred_iou_thresh=0.78, stability_score_thresh=0.88,
                           crops_nms_thresh=0.7)
        scores = [float(score) for score in output["scores"]]
        masks = [np.asarray(mask, dtype=bool) for mask in output["masks"]]
        # Keep meaningful connected masks. Parts and background remain visible for
        # deliberate review rather than being mislabeled automatically as fruit.
        kept_masks, kept_scores, metadata = [], [], []
        for mask, score in zip(masks, scores):
            if mask.sum() < 120:
                continue
            index = len(kept_masks)
            Image.fromarray(mask.astype(np.uint8)*255).save(folder / f"mask-{index:03d}.png")
            x,y,w,h = cv2.boundingRect(mask.astype(np.uint8))
            metadata.append({"index":index, "score":score, "area":int(mask.sum()), "bbox":[x,y,x+w,y+h]})
            kept_masks.append(mask); kept_scores.append(score)
        (folder / "metadata.json").write_text(json.dumps({
            "source_id":row["id"], "inference_size":list(photo.size),
            "model":"Zigeng/SlimSAM-uniform-50", "revision":MODEL_REVISION,
            "grid_points_per_side":points, "proposals":metadata,
        }, indent=2)+"\n")
        proposal_sheet(row, photo, kept_masks, kept_scores, folder)
        print(f"{row['id']}: {len(metadata)} proposals in {time.time()-start:.1f}s", flush=True)
        if device == "mps":
            torch.mps.empty_cache()


if __name__ == "__main__":
    main()
