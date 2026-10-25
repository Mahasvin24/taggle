"""Artifact checks for label inheritance, source lineage, and actual RGBA files.

Run after export_segments.py: python -m unittest discover -s <this directory>.
No model inference or network access is required.
"""

import csv
import hashlib
import json
from pathlib import Path
import unittest

from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parent


class SegmentationArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources={row["id"]:row for row in json.loads((ROOT/"manifest.json").read_text())["rows"]}
        cls.export=json.loads((ROOT/"segmentation-manifest.json").read_text())
        cls.instances=[instance for source in cls.export["sources"] for instance in source["instances"]]

    def test_every_sample_is_processed_and_multi_fruit_images_split(self):
        groups={source["source_id"]:source for source in self.export["sources"]}
        self.assertEqual(set(groups),set(self.sources))
        self.assertEqual(self.export["source_count"],len(self.sources))
        self.assertEqual(self.export["instance_count"],len(self.instances))
        for source in groups.values():
            self.assertGreater(len(source["instances"]),0,source["source_id"])
            self.assertTrue((ROOT/source["overlay"]).is_file())
        self.assertGreater(len(groups["apple-fresh-0149"]["instances"]),1)
        self.assertEqual(len(groups["grape-fresh-0549"]["instances"]),2)
        self.assertEqual(len(groups["strawberry-rotten-3149"]["instances"]),2)

    def test_every_child_inherits_its_parent_label_and_action(self):
        ids=set()
        for instance in self.instances:
            parent=self.sources[instance["source_id"]]
            with self.subTest(instance=instance["id"]):
                self.assertNotIn(instance["id"],ids)
                ids.add(instance["id"])
                for key in ("state","fruit","action"):
                    self.assertEqual(instance[key],parent[key])
                self.assertEqual(instance["source_row_idx"],parent["row_idx"])
                self.assertEqual(instance["label_origin"],"inherited_from_source_image")
                self.assertEqual(instance["action"],{"fresh":"collect","rotten":"slash"}[instance["state"]])

    def test_cutouts_have_real_transparency_and_matching_masks(self):
        for instance in self.instances:
            with self.subTest(instance=instance["id"]):
                path=ROOT/instance["cutout"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),instance["sha256"])
                with Image.open(ROOT/instance["source_mask"]) as source_mask:
                    self.assertEqual(list(source_mask.size),instance["source_mask_size"])
                    self.assertEqual(source_mask.getextrema(),(0,255))
                with Image.open(path) as image,Image.open(ROOT/instance["alpha_mask"]) as mask:
                    self.assertEqual(image.mode,"RGBA")
                    self.assertEqual(image.size,(instance["width"],instance["height"]))
                    self.assertEqual(mask.size,image.size)
                    alpha=image.getchannel("A")
                    self.assertEqual(alpha.getextrema(),(0,255))
                    self.assertIsNone(ImageChops.difference(alpha,mask).getbbox())
                    x0,y0,x1,y1=alpha.getbbox()
                    self.assertGreaterEqual(x0,8)
                    self.assertGreaterEqual(y0,8)
                    self.assertLessEqual(x1,image.width-8)
                    self.assertLessEqual(y1,image.height-8)

    def test_default_csv_contains_only_kept_children(self):
        with (ROOT/"segment-labels.csv").open() as stream:
            records={row["id"]:row for row in csv.DictReader(stream)}
        kept=[instance for instance in self.instances if instance["quality"]["decision"] == "kept"]
        self.assertEqual(set(records),{instance["id"] for instance in kept})
        for instance in kept:
            for key in ("source_id","state","fruit","action","cutout","label_origin"):
                self.assertEqual(records[instance["id"]][key],instance[key])
            self.assertEqual(records[instance["id"]]["decision"],"kept")

    def test_all_candidates_and_exclusion_reasons_are_preserved(self):
        kept=excluded=0
        with (ROOT/"segment-review.csv").open() as stream:
            audit={row["id"]:row for row in csv.DictReader(stream)}
        self.assertEqual(set(audit),{instance["id"] for instance in self.instances})
        for source in self.export["sources"]:
            source_kept=source_excluded=0
            for instance in source["instances"]:
                quality=instance["quality"]
                self.assertIn(quality["decision"],("kept","excluded_partial"))
                self.assertEqual(audit[instance["id"]]["state"],instance["state"])
                if quality["decision"] == "kept":
                    source_kept+=1
                else:
                    source_excluded+=1
                    self.assertTrue(quality["reasons"])
                    self.assertTrue(audit[instance["id"]]["exclusion_reason"])
            self.assertEqual(source["kept_count"],source_kept)
            self.assertEqual(source["excluded_count"],source_excluded)
            self.assertTrue((ROOT/source["kept_overlay"]).is_file())
            self.assertTrue((ROOT/source["excluded_overlay"]).is_file())
            kept+=source_kept;excluded+=source_excluded
        self.assertEqual(self.export["kept_instance_count"],kept)
        self.assertEqual(self.export["excluded_instance_count"],excluded)
        self.assertEqual(kept+excluded,self.export["instance_count"])

    def test_original_photographs_are_unchanged(self):
        for row in self.sources.values():
            self.assertEqual(hashlib.sha256((ROOT/row["original"]).read_bytes()).hexdigest(),row["sha256"])


if __name__=="__main__":
    unittest.main()
