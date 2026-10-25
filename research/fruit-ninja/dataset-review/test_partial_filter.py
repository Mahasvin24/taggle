"""Regression cases for the partial-fruit filter's important tradeoffs."""

import json
from pathlib import Path
import unittest

import cv2
import numpy as np

from filter_partials import decide, measure_mask

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT/"partial-filter-policy.json").read_text())


def decision(mask, fruit="apple", relative_area=1.0):
    metrics = measure_mask(mask, POLICY["body_opening_fraction"])
    metrics["relative_area"] = relative_area
    return decide(metrics, fruit, POLICY)


class PartialFilterGeometry(unittest.TestCase):
    def test_whole_fruit_is_kept(self):
        mask = np.zeros((200,200),np.uint8)
        cv2.circle(mask,(100,100),50,1,-1)
        self.assertEqual(decision(mask)["decision"],"kept")

    def test_half_fruit_at_frame_is_excluded(self):
        mask = np.zeros((200,200),np.uint8)
        cv2.circle(mask,(0,100),50,1,-1)
        result = decision(mask,relative_area=.5)
        self.assertEqual(result["decision"],"excluded_partial")
        self.assertIn("frame_crop",result["reason_codes"])

    def test_stem_touching_frame_keeps_whole_fruit(self):
        mask = np.zeros((200,200),np.uint8)
        cv2.circle(mask,(100,100),45,1,-1)
        cv2.line(mask,(135,100),(199,100),1,3)
        self.assertEqual(decision(mask)["decision"],"kept")

    def test_small_complete_grape_is_not_a_fragment(self):
        mask = np.zeros((200,200),np.uint8)
        cv2.ellipse(mask,(100,100),(12,20),0,0,360,1,-1)
        self.assertEqual(decision(mask,fruit="grape",relative_area=.08)["decision"],"kept")

    def test_large_missing_section_is_excluded(self):
        mask = np.zeros((200,200),np.uint8)
        cv2.circle(mask,(100,100),55,1,-1)
        cv2.circle(mask,(125,100),47,0,-1)
        self.assertEqual(decision(mask,relative_area=.4)["decision"],"excluded_partial")

    def test_natural_banana_curvature_is_kept(self):
        mask = np.zeros((240,300),np.uint8)
        cv2.ellipse(mask,(150,100),(90,55),0,0,180,1,22)
        self.assertEqual(decision(mask,fruit="banana",relative_area=.4)["decision"],"kept")

    def test_thin_sliver_is_excluded(self):
        mask = np.zeros((200,200),np.uint8)
        cv2.ellipse(mask,(100,100),(7,55),0,0,360,1,-1)
        self.assertIn("sliver",decision(mask,relative_area=.15)["reason_codes"])

    def test_smoothing_does_not_crash_on_one_pixel_fragment(self):
        mask = np.zeros((200,200),np.uint8)
        mask[30:170,100] = 1
        self.assertEqual(decision(mask,relative_area=.01)["decision"],"excluded_partial")


if __name__ == "__main__":
    unittest.main()
