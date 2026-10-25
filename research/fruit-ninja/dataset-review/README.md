# Fruit Ninja dataset review

**Current result:** the 48 sampled photos produced 236 fruit-cutout candidates. The partial-fruit filter keeps **183** and excludes **53** from the kept count. Click a photo to compare kept fruit with excluded partials and inspect each exclusion reason. All candidate PNGs and inherited labels are preserved.

## Look at the images

- [Local gallery](http://127.0.0.1:8765/): filter by fruit, condition, and photos with excluded partials. A photo opens **Kept**, **Excluded**, and **Both** views; every excluded cutout has a reason. **All masks**, **Kept masks**, and **Excluded masks** overlays use matching, stable fruit numbers. Cutouts can still be enlarged or downloaded.
- [Kept labels CSV](segment-labels.csv): only the 183 kept candidates.
- [All cutouts and decisions CSV](segment-review.csv): all 236 candidates, including excluded partials and reasons.
- [Segmentation manifest](segmentation-manifest.json): parent/child lineage, inherited labels, masks, geometry measurements, and inclusion decisions.
- [Contact sheet 1](contact-sheet-1.jpg): apple, banana, grape, guava; three fresh and three rotten examples each.
- [Contact sheet 2](contact-sheet-2.jpg): jujube, orange, pomegranate, strawberry; the same sampling.
- [Eight proposed cutout candidates](candidate-sheet.jpg): fresh and rotten pairs for apple, banana, orange, and guava.
- [Browse the full raw dataset online](https://huggingface.co/datasets/Project-AgML/fresh_rotten_fruit_classification/viewer/raw/train).

To restart the gallery from the repository root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory research/fruit-ninja/dataset-review
```

The gallery also opens directly from `index.html` in a browser. It uses local previews and does not require a dataset account.

## Partial-fruit filter

This filter targets severe cropping and occlusion while tolerating small edge touches. It measures full-image source masks, so the transparent padding around a PNG cannot be mistaken for the photo boundary. Narrow stems are removed from a temporary body mask for measurement; original masks and PNGs are unchanged.

The automatic rules exclude substantial cuts at the source frame, thin slivers relative to other fruit in the same photo, and large missing sections or long straight cut edges. A large frame cut currently requires at least 20% of the measured outline to lie at the frame and a sufficiently long continuous contact run. A minor stem or tip touching the edge is retained. Banana shape rules allow natural curvature and elongation; a complete small grape is not rejected just because it is smaller than its neighbors.

Thresholds are in [partial-filter-policy.json](partial-filter-policy.json). Twenty recorded visual exclusions in [partial-filter-overrides.json](partial-filter-overrides.json) handle ambiguous, heavily occluded regions in the fruit piles. Overrides include a reason and preserve the automatic decision in the manifest. These are practical geometric heuristics plus visual curation, not a calibrated estimate of how much physical fruit is missing.

- Each source's `instances` array remains the complete candidate inventory. `quality.decision` is `kept` or `excluded_partial`; `quality.reasons` explains exclusions and `quality.metrics` records the measurements.
- `kept_count` and `excluded_count` partition each source's candidates. Top-level `instance_count` remains 236; `kept_instance_count` is 183 and `excluded_instance_count` is 53.
- The default labels CSV contains kept candidates only. The review CSV contains every candidate and its decision. Fresh/rotten labels, game actions, IDs, PNGs, masks, and source hashes remain intact in both groups.
- Green overlay regions are kept; orange regions are excluded. Fruit numbers are never renumbered after filtering, so the overlay, enlarged view, manifest, and CSV refer to the same instances.

To change filtering without rerunning the segmentation model:

```sh
research/fruit-ninja/dataset-review/.venv/bin/python research/fruit-ninja/dataset-review/filter_partials.py
research/fruit-ninja/dataset-review/.venv/bin/python research/fruit-ninja/dataset-review/build_review.py
research/fruit-ninja/dataset-review/.venv/bin/python -m unittest discover -s research/fruit-ninja/dataset-review -p 'test_*.py' -v
```

Reload the gallery after rebuilding. Examples checked: a half apple is excluded; all five bananas in row 283 remain kept; stem-only edge contact is tolerated; an intact small grape stays kept. Borderline shapes still require visual review.

## Segmentation trial

All 48 sources were processed with the local [SlimSAM-uniform-50 model](https://huggingface.co/Zigeng/SlimSAM-uniform-50), revision `d67c795ed0caaec7423d799da25cdeded48aac40`. A regular point grid generated proposals at up to 960 pixels on the longest image side. Fruit-instance proposals were selected visually; background, leaf-only, seed, shadow, and duplicate proposals were excluded. Point/box prompts refined the difficult rotten-apple boundary; separate shadow proposals were subtracted in two pomegranate images. Small disconnected mask speckles were cleaned up. This was a model-assisted, visually curated trial, not a fully automatic fruit detector.

- **One image per fruit:** the outputs include 17 visible apple regions from row 149, five bananas from row 283, two individual grapes from row 549, 72 berry candidates from row 1483, and two separate rotten strawberries from row 3149.
- **Label inheritance:** every output copies its parent's `state`, `fruit`, and `action`. A source labeled `fresh` produces only `fresh` outputs; `rotten` produces only `rotten` outputs. Fresh maps to collect and rotten maps to slash. The model does not reclassify freshness per fruit.
- **Actual transparency:** each cutout is an RGBA PNG with an alpha mask, cropped around one selected instance and resized only when needed to fit 768 × 768 pixels, plus eight transparent pixels of padding per side. Color content comes from the original photograph; no hidden fruit pixels are invented.
- **Review limitations:** a visible portion of an occluded fruit may be an incomplete shape. Crops clipped by the original frame are flagged in the manifest and gallery. Source-level `coverage: partial` identifies crowded photos with uncertain completeness. Edge flags do not detect every form of occlusion. These candidates have not been approved as game sprites or ground-truth training masks.
- **Provenance:** `source_bbox_xyxy` uses oriented original-image coordinates; `source_mask` covers the full inference image at `source_mask_size`. `alpha_mask` has the same cropped, resized, padded dimensions as the PNG. Model mask scores are raw quality predictions, not probabilities of fruit identity or freshness.

The canonical results are the exported masks, PNGs, and manifest. `selected_masks.json` records visual choices against the cached proposal ordering; regenerating proposals on another device or library version can change that ordering, so review new proposals before reusing the selections.

### Files and rerunning

| File or folder | Purpose |
| --- | --- |
| `segments/cutouts/` | One transparent PNG per selected fruit instance. |
| `segments/masks/` | Cropped alpha channels matching those PNGs. |
| `segments/source-masks/` | Canonical full-image binary masks in inference-image coordinates. |
| `segments/overlays/` | Numbered masks on the source photos, matching cutout numbering. |
| `segments/sheets/` | Per-source visual QA contact sheets. |
| `selected_masks.json` | Visually selected proposal indices, source notes, and coverage flags. |
| `guided_prompts.json` | Reproducible normalized point/box prompts for boundary refinement. |
| `segmentation-manifest.json` | Parent/child lineage, source labels, crops, masks, dimensions, and hashes. |
| `segment-labels.csv` | Flat labels for kept cutouts only. |
| `segment-review.csv` | Every candidate, inherited label, inclusion decision, and exclusion reason. |
| `partial-filter-policy.json` | Geometric thresholds and fruit-shape allowances. |
| `partial-filter-overrides.json` | Documented visual decisions for ambiguous heavy partials. |

The segmentation environment, model weights, and raw proposals stay local and are ignored by Git. The game runtime does not need these dependencies. From the repository root:

```sh
python3 -m venv research/fruit-ninja/dataset-review/.venv
research/fruit-ninja/dataset-review/.venv/bin/python -m pip install -r research/fruit-ninja/dataset-review/requirements-segmentation.txt
python3 research/fruit-ninja/dataset-review/fetch_model.py
research/fruit-ninja/dataset-review/.venv/bin/python research/fruit-ninja/dataset-review/generate_proposals.py
research/fruit-ninja/dataset-review/.venv/bin/python research/fruit-ninja/dataset-review/refine_masks.py
# Review cached proposals before reusing selected_masks.json on a different device.
research/fruit-ninja/dataset-review/.venv/bin/python research/fruit-ninja/dataset-review/export_segments.py
research/fruit-ninja/dataset-review/.venv/bin/python research/fruit-ninja/dataset-review/build_review.py
research/fruit-ninja/dataset-review/.venv/bin/python -m unittest discover -s research/fruit-ninja/dataset-review -p 'test_*.py' -v
```

The checks cover all source photos, multi-fruit splitting, per-child label/action inheritance, PNG transparency, matching alpha masks, kept-only CSV exports, complete review records, and untouched original JPEGs. Synthetic regression cases check whole fruit, frame cuts, stems at the edge, small intact grapes, curved bananas, and slivers. Visual QA remains necessary for shape quality.

## Dataset choice

| Dataset | Contents | Published license | Assessment |
| --- | --- | --- | --- |
| [Fresh and Rotten Fruits, Sultana et al.](https://data.mendeley.com/datasets/bdd69gyhv8/1) | 3,200 originals; eight fruits, each fresh/rotten. Another 12,335 images are augmentations. | CC BY 4.0 | Preferred; original-photo samples inspected below. |
| [Spoiled and fresh fruit inspection](https://data.mendeley.com/datasets/6ps7gtp2wg/1) | 16,000 images; banana, lemon, lulo, mango, orange, strawberry, tamarillo, tomato; half fresh, half spoiled. | CC BY 4.0 | Backup with additional fruit types; photos not inspected in this review. |
| [Fruits fresh and rotten for classification, Kaggle](https://www.kaggle.com/sriramr/fruits-fresh-and-rotten-for-classification/metadata) | Apple, banana, orange. | Unknown on the source page | Prefer the dataset with explicit image permissions. |
| [FruitVision](https://data.mendeley.com/datasets/xkbjx8959c/2) | Five fruits; fresh, rotten, formalin-mixed; 10,154 original images. | CC BY-NC-ND 4.0 | More restrictive license; photos not inspected in this review. |

The preferred dataset's eight fruits are apple, banana, grape, guava, jujube, orange, pomegranate, and strawberry. Its authors report expert-assisted freshness classification. The [Project-AgML mirror](https://huggingface.co/datasets/Project-AgML/fresh_rotten_fruit_classification) offers the original images under its **raw** configuration. The mirror exposes image, condition, and fruit type; it does not supply segmentation masks.

## What the samples show

These are observations from the downloaded photos, not claims about the entire dataset.

| Fruit | Segmentation considerations | Gameplay considerations |
| --- | --- | --- |
| Apple | Rows 17 and 83 show a single fruit on a simple background. Row 149 is a pile; row 1617 contains two fruit. | Row 1683 has obvious rot but soft focus. Row 1749 is labeled rotten but looks comparatively intact from this view; exclude it from an initial visually obvious set. |
| Banana | Rows 349, 1817, and 1883 offer single-fruit silhouettes. Rows 283 and 1949 contain several fruit. Shadows and ragged stems need care. | Row 1883 is visibly dark; fresh row 217 is already spotty, making the binary distinction less clear during fast play. |
| Grape | Bunches have thin stems and gaps; some rotten photos contain disconnected individual grapes. The sampled fresh images are also relatively low resolution. | A bunch could be one game object, but extracting one grape and making rot obvious will require more curation. Defer for the first pass. |
| Guava | Row 617 has a useful fruit body, though the stem reaches the image edge. Row 749 includes leaves; row 683 has touching fruit. | The rotten examples have relatively visible damaged areas; a promising second fruit family after the simplest silhouettes. |
| Jujube | Several single-fruit photos have plain backgrounds. Row 949 contains a group; pronounced shadows occur elsewhere. | Green-to-brown changes may read as a different variety or ripeness rather than obvious rot. Review at game size. |
| Orange | Rows 1083, 1149, and 2749 show compact, separate outlines. Row 1017 has a strong cast shadow. | Row 2749 has dark marks; row 2683 is partly peeled or missing flesh, which may confuse a freshness-only rule. |
| Pomegranate | Several single fruit, but strong lighting and hard shadows recur. Row 1283 is a group. | Some rotten lesions are localized and may disappear at small sizes or certain rotations. |
| Strawberry | Row 1549 is a single fruit; other fresh samples are piles. Leaf edges and overlapping fruit make masks harder. | Row 3083 is a potential single rotten fruit candidate, but the dark appearance needs checking at game size. |

**Conclusion:** there is enough promising material to try segmentation on selected photos. Simple backgrounds do not guarantee clean masks: shadows, stems, leaves, and touching fruit still need inspection. Dataset labels alone do not guarantee an unambiguous game sprite.

## Initial eight-photo shortlist

| Fruit | Fresh / collect | Rotten / slash | Check |
| --- | --- | --- | --- |
| Apple | [Row 17](previews/apple-fresh-0017.jpg) | [Row 1683](previews/apple-rotten-1683.jpg) | Rotten image focus. |
| Banana | [Row 349](previews/banana-fresh-0349.jpg) | [Row 1883](previews/banana-rotten-1883.jpg) | Shadow removal and fresh-fruit bruising. |
| Orange | [Row 1083](previews/orange-fresh-1083.jpg) | [Row 2749](previews/orange-rotten-2749.jpg) | Spot visibility at game size. |
| Guava | [Row 617](previews/guava-fresh-0617.jpg) | [Row 2349](previews/guava-rotten-2349.jpg) | Stem boundary. |

These eight sources, along with the other 40 samples, now have masks and cutouts in the gallery. Next, choose suitable sprites and check them at the intended display size (for example 96–160 pixels). Reject clipped, blurry, or visually ambiguous examples.

## Sampling and provenance

48 photos were selected before visual inspection: row positions 17, 83, and 149 in each 200-row class block of the raw mirror. This provides three examples per fruit/condition combination. It is not a random sample or an estimate of the dataset's usable percentage. Different photos may show the same physical fruit.

- `originals/`: downloaded JPEG bytes, retained locally and ignored by Git (about 18 MB).
- `previews/`: images resized to fit within 1,200 × 1,200 pixels and JPEG-reencoded. They preserve the full framing, with EXIF orientation applied.
- [manifest.json](manifest.json): labels, gameplay actions, dimensions, row links, mirror revision, original-file sizes, and SHA-256 hashes.
- [fetch_samples.py](fetch_samples.py): retrieves this fixed selection using Python 3 and curl.
- [build_review.py](build_review.py): validates photo dimensions and generates the previews, contact sheets, and HTML gallery; requires Pillow.
- [review.template.html](review.template.html): editable gallery source. Regenerate `index.html` with `build_review.py` after changes.

To recreate the files:

```sh
python3 research/fruit-ninja/dataset-review/fetch_samples.py
python3 research/fruit-ninja/dataset-review/build_review.py
```

Use a Python environment with Pillow for the second command. If `segmentation-manifest.json` is present, its cutouts are embedded into the rebuilt gallery. The full original dataset has not been downloaded. No source images or game behavior were changed.

## Attribution

Nusrat Sultana, Musfika Jahan, and Mohammad Shorif Uddin (2022), “Fresh and Rotten Fruits Dataset for Machine-Based Evaluation of Fruit Quality,” Mendeley Data, V1, DOI: [10.17632/bdd69gyhv8.1](https://doi.org/10.17632/bdd69gyhv8.1). Images downloaded via the Project-AgML mirror. Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), which permits adaptation and commercial reuse with appropriate attribution, a license link, and an indication of changes. Review previews were resized and JPEG-reencoded. Cutouts add segmentation alpha masks, cropping, and resizing; overlays add colored mask annotations. Original source files are unchanged.

Dataset pages and licenses checked October 24, 2026.
