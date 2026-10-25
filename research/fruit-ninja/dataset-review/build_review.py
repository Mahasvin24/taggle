#!/usr/bin/env python3
"""Build image review artifacts. Requires Pillow; never crops the source photos."""

import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text())
ROWS = MANIFEST["rows"]
FRUITS = sorted({row["fruit"] for row in ROWS})
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default(size=size)


def photo(row):
    with Image.open(ROOT / row["original"]) as image:
        assert image.size == (row["width"], row["height"]), row["id"]
        return ImageOps.exif_transpose(image).convert("RGB")


def sheet(fruits, filename, samples):
    columns = 2 * samples
    tile_w, photo_h, row_h = (282, 232, 300) if samples == 3 else (440, 300, 368)
    canvas = Image.new("RGB", (columns * tile_w + 48, 146 + len(fruits) * row_h), "#eef3f8")
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), "Fresh / rotten fruit: original-image review", fill="#202e3c", font=font(30))
    draw.text((24, 62), "Fresh = collect     |     Rotten = slash     |     Photos resized to fit; no cropping", fill="#43566a", font=font(19))
    draw.text((24, 94), "Sultana, Jahan & Uddin (2022), doi:10.17632/bdd69gyhv8.1, CC BY 4.0", fill="#43566a", font=font(17))
    for y, fruit in enumerate(fruits):
        selected = [r for state in ("fresh", "rotten") for r in ROWS if r["fruit"] == fruit and r["state"] == state]
        if samples == 1:
            selected = [selected[0], selected[3]]
        for x, row in enumerate(selected):
            left, top = 24 + x * tile_w, 140 + y * row_h
            label = f"{fruit.title()} / {row['state']}"
            draw.text((left + 6, top), label, fill="#256248" if row["state"] == "fresh" else "#984223", font=font(19))
            image = ImageOps.contain(photo(row), (tile_w - 16, photo_h))
            image_x = left + (tile_w - image.width) // 2
            image_y = top + 30 + (photo_h - image.height) // 2
            draw.rectangle((left + 3, top + 28, left + tile_w - 7, top + 28 + photo_h), fill="white")
            canvas.paste(image, (image_x, image_y))
            draw.text((left + 6, top + 38 + photo_h), f"Row {row['row_idx']}  |  {row['width']} x {row['height']}", fill="#43566a", font=font(15))
    canvas.save(ROOT / filename)


def candidate_sheet():
    indices = [17, 349, 1083, 617, 1683, 1883, 2749, 2349]
    lookup = {row["row_idx"]: row for row in ROWS}
    canvas = Image.new("RGB", (1160, 780), "#eef3f8")
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), "Eight photos to try as fruit sprites", fill="#202e3c", font=font(31))
    draw.text((24, 62), "Fresh: collect (top) / Rotten: slash (bottom). Backgrounds still present; no segmentation yet.", fill="#43566a", font=font(19))
    draw.text((24, 94), "Sultana, Jahan & Uddin (2022), doi:10.17632/bdd69gyhv8.1, CC BY 4.0. Resized, uncropped previews.", fill="#43566a", font=font(16))
    for index, row_idx in enumerate(indices):
        row = lookup[row_idx]
        left, top = 24 + (index % 4) * 280, 140 + (index // 4) * 314
        draw.text((left + 6, top), f"{row['fruit'].title()} / {row['state']}", fill="#256248" if row["state"] == "fresh" else "#984223", font=font(20))
        draw.rectangle((left + 3, top + 29, left + 270, top + 267), fill="white")
        image = ImageOps.contain(photo(row), (260, 232))
        canvas.paste(image, (left + 6 + (260 - image.width) // 2, top + 32 + (232 - image.height) // 2))
        draw.text((left + 6, top + 278), f"Row {row['row_idx']} / {row['width']} x {row['height']}", fill="#43566a", font=font(15))
    canvas.save(ROOT / "candidate-sheet.jpg", quality=90)


def main():
    (ROOT / "previews").mkdir(exist_ok=True)
    for row in ROWS:
        image = photo(row)
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        image.save(ROOT / row["preview"], quality=88, optimize=True)
    sheet(FRUITS[:4], "contact-sheet-1.jpg", 3)
    sheet(FRUITS[4:], "contact-sheet-2.jpg", 3)
    # A compact overview with one fresh and one rotten sample per fruit.
    sheet(FRUITS, "overview.jpg", 1)
    candidate_sheet()
    template = (ROOT / "review.template.html").read_text()
    segment_file = ROOT / "segmentation-manifest.json"
    segments = json.loads(segment_file.read_text()) if segment_file.exists() else {"sources":[]}
    template = template.replace("__ROWS__", json.dumps(ROWS).replace("</", "<\\/"))
    template = template.replace("__SEGMENTS__", json.dumps(segments).replace("</", "<\\/"))
    template = template.replace("__FRUIT_OPTIONS__", "".join(f'<option value="{html.escape(f)}">{f.title()}</option>' for f in FRUITS))
    (ROOT / "index.html").write_text(template)
    print(f"Built {len(ROWS)} previews, four contact sheets, and index.html")


if __name__ == "__main__":
    main()
