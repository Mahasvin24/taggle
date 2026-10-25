#!/usr/bin/env python3
"""Append reproducible point/box-guided masks for difficult source boundaries."""

import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME",str(ROOT/".cache/huggingface"))
os.environ.setdefault("HF_HUB_OFFLINE","1")

import cv2
import numpy as np
from PIL import Image,ImageOps
import torch
from transformers import SamModel,SamProcessor

from generate_proposals import proposal_sheet


def main():
    torch.set_num_threads(4)
    processor=SamProcessor.from_pretrained(ROOT/".models/slimsam",local_files_only=True)
    model=SamModel.from_pretrained(ROOT/".models/slimsam",local_files_only=True).eval()
    rows={row["id"]:row for row in json.loads((ROOT/"manifest.json").read_text())["rows"]}
    prompts=json.loads((ROOT/"guided_prompts.json").read_text())
    for stem,prompt in prompts.items():
        row=rows[stem]
        folder=ROOT/".cache/proposals"/stem
        metadata=json.loads((folder/"metadata.json").read_text())
        photo=ImageOps.exif_transpose(Image.open(ROOT/row["original"])).convert("RGB").resize(metadata["inference_size"],Image.Resampling.LANCZOS)
        w,h=photo.size
        points=[[[x*w,y*h] for x,y,_ in prompt["points"]]]
        labels=[[label for _,_,label in prompt["points"]]]
        x0,y0,x1,y1=prompt["box"]
        inputs=processor(photo,input_points=points,input_labels=labels,input_boxes=[[[x0*w,y0*h,x1*w,y1*h]]],return_tensors="pt")
        with torch.inference_mode():
            output=model(pixel_values=inputs["pixel_values"],input_points=inputs["input_points"],input_labels=inputs["input_labels"],input_boxes=inputs["input_boxes"])
        masks=processor.image_processor.post_process_masks(output.pred_masks,inputs["original_sizes"],inputs["reshaped_input_sizes"])[0][0].numpy()
        scores=output.iou_scores[0,0].tolist()
        metadata["proposals"]=[p for p in metadata["proposals"] if p["index"]<1000]
        for offset,(mask,score) in enumerate(zip(masks,scores)):
            index=1000+offset
            Image.fromarray(mask.astype(np.uint8)*255).save(folder/f"mask-{index:03d}.png")
            x,y,width,height=cv2.boundingRect(mask.astype(np.uint8))
            metadata["proposals"].append({"index":index,"score":score,"area":int(mask.sum()),"bbox":[x,y,x+width,y+height],"guided_prompt":prompt})
        (folder/"metadata.json").write_text(json.dumps(metadata,indent=2)+"\n")
        proposal_sheet(row,photo,list(masks),scores,folder)
        (folder/"proposals.jpg").rename(folder/"guided-proposals.jpg")
        print(stem,"guided masks",[1000+i for i in range(len(masks))],flush=True)


if __name__=="__main__":
    main()
