"""Checks for the failure modes that would invalidate this small-data experiment."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import numpy as np
from PIL import Image

from run_experiment import (
    aggregate_votes,
    extract_features,
    train_weights,
    read_snapshot,
)


class ExperimentTests(unittest.TestCase):
    def test_repeat_votes_form_one_example_and_ties_are_excluded(self):
        votes = [
            {"asset_id": "agreed", "label": "fresh"},
            {"asset_id": "agreed", "label": "fresh"},
            {"asset_id": "tie", "label": "fresh"},
            {"asset_id": "tie", "label": "rotten"},
            {"asset_id": "majority", "label": "fresh"},
            {"asset_id": "majority", "label": "rotten"},
            {"asset_id": "majority", "label": "rotten"},
        ]
        labels, ties, groups = aggregate_votes(votes)
        self.assertEqual(labels, {"agreed": 0, "majority": 1})
        self.assertEqual(ties, ["tie"])
        self.assertEqual(len(groups["agreed"]), 2)

    def test_transparent_rgb_cannot_leak_background_into_features(self):
        with tempfile.TemporaryDirectory() as folder:
            rgba = np.zeros((24, 24, 4), dtype=np.uint8)
            rgba[4:20, 4:20] = [190, 40, 30, 255]
            a = Path(folder) / "a.png"
            b = Path(folder) / "renamed-rotten.png"
            Image.fromarray(rgba).save(a)
            rgba[rgba[:, :, 3] == 0, :3] = [20, 250, 240]
            Image.fromarray(rgba).save(b)
            x, names = extract_features(a)
            y, other_names = extract_features(b)
            np.testing.assert_array_equal(x, y)
            self.assertEqual(names, other_names)
            self.assertTrue(np.isfinite(x).all())
            self.assertFalse(any("filename" in n or "source" in n for n in names))

    def test_weighting_does_not_let_a_large_source_photo_dominate(self):
        labels = np.array([0, 0, 0, 0, 1, 1, 1])
        photos = np.array(["a", "a", "a", "b", "c", "c", "d"])
        weights = train_weights(labels, photos)
        self.assertAlmostEqual(weights[labels == 0].sum(), weights[labels == 1].sum())
        self.assertAlmostEqual(
            weights[photos == "a"].sum(), weights[photos == "b"].sum()
        )
        self.assertAlmostEqual(
            weights[photos == "c"].sum(), weights[photos == "d"].sum()
        )

    def test_snapshot_excludes_nonqualifying_events_and_keeps_latest_review(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "test.db"
            with sqlite3.connect(database) as c:
                c.executescript(
                    """
                    CREATE TABLE assets(id TEXT,metadata TEXT);
                    CREATE TABLE rounds(id TEXT,player_id TEXT,kind TEXT,status TEXT,eligible INT,
                      first_pass_correct INT,first_pass_total INT,exclusion_reason TEXT,created_at TEXT);
                    CREATE TABLE presentations(id TEXT,asset_id TEXT,round_id TEXT,role TEXT,reference_label TEXT);
                    CREATE TABLE label_events(sequence INTEGER,event_id TEXT,presentation_id TEXT,
                      label TEXT,phase TEXT,received_at TEXT);
                """
                )
                c.execute("INSERT INTO assets VALUES('a','{}')")
                for i, (kind, status, eligible, role) in enumerate(
                    [
                        ("game", "completed", 1, "target"),
                        ("game", "completed", 0, "target"),
                        ("game", "abandoned", 1, "target"),
                        ("calibration", "completed", 1, "target"),
                        ("game", "completed", 1, "control"),
                    ]
                ):
                    c.execute(
                        "INSERT INTO rounds VALUES(?,?,?,?,?,NULL,NULL,NULL,'now')",
                        (str(i), "player", kind, status, eligible),
                    )
                    c.execute(
                        "INSERT INTO presentations VALUES(?, 'a', ?, ?, 'fresh')",
                        (str(i), str(i), role),
                    )
                    c.execute(
                        "INSERT INTO label_events VALUES(?,?,?,'fresh','initial','now')",
                        (i + 1, "initial-" + str(i), str(i)),
                    )
                c.execute(
                    "INSERT INTO label_events VALUES(20,'review','0','rotten','review','now')"
                )
            c.close()
            before = database.read_bytes()
            snapshot, _ = read_snapshot(database)
            self.assertEqual(
                [v["event_id"] for v in snapshot["eligible_target_votes"]], ["review"]
            )
            self.assertEqual(snapshot["eligible_target_votes"][0]["label"], "rotten")
            self.assertEqual(len(snapshot["qualified_first_pass_control_calls"]), 1)
            self.assertEqual(database.read_bytes(), before)

    def test_saved_folds_hold_out_entire_photo_and_never_train_on_controls(self):
        directory = Path(__file__).parent / "results"
        snapshot = json.loads((directory / "snapshot.json").read_text())
        assets = {a["id"]: a for a in snapshot["assets"]}
        labels, ties, _ = aggregate_votes(snapshot["eligible_target_votes"])
        folds = json.loads((directory / "folds.json").read_text())
        tested = []
        for fold in folds:
            held_out = fold["held_out_photo_sha256"]
            tested.extend(fold["test_asset_ids"])
            for asset_id in fold["test_asset_ids"]:
                self.assertEqual(assets[asset_id]["role"], "control")
                self.assertEqual(
                    assets[asset_id]["metadata"]["source_photo_sha256"], held_out
                )
            for asset_id in fold["train_asset_ids"]:
                self.assertEqual(assets[asset_id]["role"], "target")
                self.assertIn(asset_id, labels)
                self.assertNotIn(asset_id, ties)
            for asset_id in fold["train_asset_ids"] + fold["reference_train_asset_ids"]:
                self.assertNotEqual(
                    assets[asset_id]["metadata"]["source_photo_sha256"], held_out
                )
        controls = [a["id"] for a in assets.values() if a["role"] == "control"]
        self.assertCountEqual(tested, controls)
        self.assertEqual(len(tested), len(set(tested)))


if __name__ == "__main__":
    unittest.main()
