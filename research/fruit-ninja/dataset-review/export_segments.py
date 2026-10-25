#!/usr/bin/env python3
"""Export reviewed fruit instances as transparent PNGs with inherited labels."""

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
COLORS = [(222,57,102),(30,144,205),(68,170,75),(230,155,30),(139,87,187),(16,167,154)]


def clean_mask(mask):
    """Discard disconnected speckles, retaining the main visible fruit body."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if count <= 1:
        raise ValueError("Empty selected mask")
    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    result = labels == main
    # Retain nearby substantial pieces such as a selected stem, not distant noise.
    radius = max(3, round(max(mask.shape)*.025))
    nearby = cv2.dilate(result.astype(np.uint8), np.ones((radius*2+1,radius*2+1),np.uint8)) > 0
    for label in range(1,count):
        if label != main and stats[label,cv2.CC_STAT_AREA] >= stats[main,cv2.CC_STAT_AREA]*.003:
            component = labels == label
            if np.any(component & nearby):
                result |= component
    return result


def main():
    source = json.loads((ROOT/"manifest.json").read_text())
    selections = json.loads((ROOT/"selected_masks.json").read_text())
    output = ROOT/"segments"
    previous_path = ROOT/"segmentation-manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {"sources":[]}
    for name in ("cutouts","masks","source-masks","overlays","sheets"):
        (output/name).mkdir(parents=True,exist_ok=True)
    records = []
    flat = []
    for row in source["rows"]:
        selection = selections[row["id"]]
        cache = ROOT/".cache"/"proposals"/row["id"]
        metadata = json.loads((cache/"metadata.json").read_text())
        lookup = {proposal["index"]:proposal for proposal in metadata["proposals"]}
        full = ImageOps.exif_transpose(Image.open(ROOT/row["original"])).convert("RGB")
        size = tuple(metadata["inference_size"])
        overlay = full.resize(size,Image.Resampling.LANCZOS).convert("RGBA")
        selected = []
        for order, indices in enumerate(selection["instances"]):
            exclude = []
            if isinstance(indices,dict):
                exclude = indices.get("exclude",[])
                indices = indices["include"]
            if isinstance(indices,int):
                indices = [indices]
            masks = [np.array(Image.open(cache/f"mask-{p:03d}.png")) > 0 for p in indices]
            mask = np.logical_or.reduce(masks)
            for proposal in exclude:
                mask &= np.array(Image.open(cache/f"mask-{proposal:03d}.png")) == 0
            mask = clean_mask(mask)
            selected.append((order, indices, mask, exclude))
        # Automatic proposals can contain stray remote islands and near-duplicate
        # versions of one fruit. Compare the cleaned masks before numbering crops.
        unique = []
        for candidate in sorted(selected,key=lambda item:-item[2].sum()):
            mask = candidate[2]
            if any((mask & previous[2]).sum()/min(mask.sum(),previous[2].sum()) > .88 for previous in unique):
                continue
            unique.append(candidate)
        instances = []
        for index, (_, indices, mask, exclude) in enumerate(sorted(unique,key=lambda item:item[0]), 1):
            x,y,w,h = cv2.boundingRect(mask.astype(np.uint8))
            edge = x <= 1 or y <= 1 or x+w >= size[0]-1 or y+h >= size[1]-1
            # Upscale only the alpha mask to the source coordinate system. Fruit
            # RGB pixels come from the original photograph, never a generator.
            alpha = Image.fromarray(mask.astype(np.uint8)*255).resize(full.size,Image.Resampling.BILINEAR)
            sx,sy = full.width/size[0],full.height/size[1]
            box = [max(0,int(x*sx)-2), max(0,int(y*sy)-2), min(full.width,int((x+w)*sx)+3), min(full.height,int((y+h)*sy)+3)]
            rgba = full.convert("RGBA").crop(box)
            alpha = alpha.crop(box)
            rgba.putalpha(alpha)
            rgba.thumbnail((768,768),Image.Resampling.LANCZOS)
            # Transparent padding makes the outline easy to inspect and prevents
            # an opaque fruit edge from touching the exported image boundary.
            padded = Image.new("RGBA",(rgba.width+16,rgba.height+16))
            padded.paste(rgba,(8,8))
            instance_id = f"{row['id']}-fruit-{index:02d}"
            cutout_path = f"segments/cutouts/{instance_id}.png"
            mask_path = f"segments/masks/{instance_id}.png"
            source_mask_path = f"segments/source-masks/{instance_id}.png"
            padded.save(ROOT/cutout_path,optimize=True)
            padded.getchannel("A").save(ROOT/mask_path,optimize=True)
            Image.fromarray(mask.astype(np.uint8)*255).save(ROOT/source_mask_path,optimize=True)
            color = COLORS[(index-1)%len(COLORS)]
            tint = Image.new("RGBA",size,(*color,0))
            tint.putalpha(Image.fromarray(mask.astype(np.uint8)*95))
            overlay = Image.alpha_composite(overlay,tint)
            outline = ImageDraw.Draw(overlay)
            contours,_ = cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                points = [tuple(point[0]) for point in contour]
                if len(points)>1:
                    outline.line(points+[points[0]],fill=(*color,255),width=2)
            outline.rectangle((x,y,min(x+29,size[0]-1),min(y+24,size[1]-1)),fill=(*color,255))
            outline.text((x+5,y+3),str(index),fill="white",font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",16))
            record = {
                "id":instance_id, "source_id":row["id"], "source_row_idx":row["row_idx"],
                "fruit":row["fruit"], "state":row["state"], "action":row["action"],
                "label_origin":"inherited_from_source_image",
                "cutout":cutout_path, "alpha_mask":mask_path,
                "source_mask":source_mask_path, "source_mask_size":list(size),
                "width":padded.width, "height":padded.height,
                "source_bbox_xyxy":box, "source_image_size":list(full.size),
                "proposal_indices":indices,
                "excluded_proposal_indices":exclude,
                "model_mask_scores":[lookup[p]["score"] for p in indices],
                "source_edge_clipped":bool(edge),
                "review_status":"partial_source_edge" if edge else "candidate",
                "sha256":hashlib.sha256((ROOT/cutout_path).read_bytes()).hexdigest(),
            }
            instances.append(record); flat.append(record)
        overlay_path = f"segments/overlays/{row['id']}.jpg"
        overlay.convert("RGB").save(ROOT/overlay_path,quality=87)
        records.append({"source_id":row["id"], "state":row["state"], "fruit":row["fruit"],
                        "source_sha256":row["sha256"],
                        "action":row["action"], "overlay":overlay_path,
                        "coverage":selection.get("coverage","reviewed"),
                        "notes":selection.get("notes",""), "instances":instances})
        # Compact per-source contact sheet for visual QA of every exported crop.
        columns = min(6,max(1,len(instances)))
        sheet = Image.new("RGB",(columns*180,55+((len(instances)+columns-1)//columns)*204),"#eef3f8")
        draw = ImageDraw.Draw(sheet)
        textfont = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",15)
        draw.text((8,8),f"{row['id']}: {len(instances)} fruit",fill="black",font=textfont)
        for index,instance in enumerate(instances):
            x,y=(index%columns)*180,45+(index//columns)*204
            tile = Image.new("RGB",(172,166),"#dfe4ea")
            photo=ImageOps.contain(Image.open(ROOT/instance["cutout"]),(164,158))
            tile.paste(photo,((172-photo.width)//2,(166-photo.height)//2),photo)
            sheet.paste(tile,(x+4,y))
            draw.text((x+5,y+170),f"{index+1}: {row['state']}"+(" / partial" if instance["source_edge_clipped"] else ""),fill="black",font=textfont)
        sheet.save(output/"sheets"/f"{row['id']}.jpg",quality=88)
    document = {
        "model":"Zigeng/SlimSAM-uniform-50", "model_revision":"d67c795ed0caaec7423d799da25cdeded48aac40",
        "method":"Automatic SAM proposals, visual fruit-instance selection, guided point/box refinement where recorded, cast-shadow subtraction where recorded, speckle cleanup, and duplicate removal. Cropped RGBA PNGs preserve source-photo color content.",
        "label_policy":"Every exported fruit inherits the exact source image state and gameplay action. Labels are not re-predicted per fruit.",
        "limitations":"Visible pixels only; occluded fruit is not reconstructed. Candidate masks are not ground truth. Source-edge clipping is flagged. Model mask scores are not probabilities of fruit identity or freshness.",
        "source_count":len(records), "instance_count":len(flat), "sources":records,
    }
    (ROOT/"segmentation-manifest.json").write_text(json.dumps(document,indent=2)+"\n")
    current_assets={instance[key] for instance in flat for key in ("cutout","alpha_mask","source_mask")}
    for previous_source in previous["sources"]:
        for instance in previous_source["instances"]:
            for key in ("cutout","alpha_mask","source_mask"):
                if key not in instance:
                    continue
                path=ROOT/instance[key]
                if instance[key] not in current_assets and path.parent in (output/"cutouts",output/"masks",output/"source-masks"):
                    path.unlink(missing_ok=True)
    from filter_partials import apply_filter
    apply_filter(ROOT)
    print(f"Exported {len(flat)} separate fruit PNGs from {len(records)} source photos")


if __name__ == "__main__":
    main()
