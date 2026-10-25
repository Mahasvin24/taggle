import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from fastapi.testclient import TestClient
from app.main import create_app
from app.games.fruit_ninja.catalog import wave_schedule, CONTROL_IDS
from app.games.fruit_ninja.db import Store


class FruitShiftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "data.db"
        self.client = TestClient(create_app(self.path))
        self.client.__enter__()
        self.store = self.client.app.state.fruit_store
        self.player = self.post("/players", {"name": "  Test   Player "})

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def post(self, path, data=None, status=200):
        r = self.client.post("/api/games/fruit-ninja" + path, json=data)
        self.assertEqual(r.status_code, status, r.text)
        return r.json()

    def create(self, kind="calibration"):
        r = self.post("/rounds", {"player_id": self.player["id"], "kind": kind})
        self.post("/rounds/" + r["id"] + "/start")
        return r

    def labels(self, r):
        with self.store.connect() as c:
            return {
                p["id"]: dict(p)
                for p in c.execute(
                    "SELECT * FROM presentations WHERE round_id=?", (r["id"],)
                )
            }

    def resolve(self, r, wrong=0, reference_version=None):
        private = self.labels(r)
        controls = [
            p for p in r["presentations"] if private[p["id"]]["role"] == "control"
        ]
        flipped = {p["id"] for p in controls[:wrong]}
        events = []
        for p in r["presentations"]:
            label = private[p["id"]]["reference_label"] or "fresh"
            if p["id"] in flipped:
                label = "rotten" if label == "fresh" else "fresh"
            action = "slice" if label == "rotten" else "pass"
            data = {
                "event_id": uuid.uuid4().hex,
                "presentation_id": p["id"],
                "action": action,
                "client_timestamp": "2026-10-24T00:00:00Z",
                "elapsed_ms": p["spawn_ms"] + (1000 if action == "slice" else 3200),
                "exposure_ms": 1000 if action == "slice" else 3200,
            }
            self.post("/rounds/" + r["id"] + "/events", data)
            events.append(data)
        if reference_version:
            self.store.reference_version = reference_version
        result = self.post(
            "/rounds/" + r["id"] + "/complete", {"elapsed_ms": r["duration_ms"]}
        )
        return result, events

    def calibrate(self):
        result, _ = self.resolve(self.create())
        self.assertTrue(result["passed"])

    def test_strawberry_guide_is_balanced_and_does_not_create_votes(self):
        guide = self.create("demonstration")
        fruit = guide["presentations"]
        self.assertEqual(len(fruit), 10)
        self.assertEqual(sum(p["label"] == "fresh" for p in fruit), 5)
        self.assertEqual(sum(p["label"] == "rotten" for p in fruit), 5)
        with self.store.connect() as c:
            for p in fruit:
                asset = c.execute("SELECT * FROM assets WHERE id=?", (p["asset_id"],)).fetchone()
                self.assertEqual(asset["fruit_type"], "strawberry")
                self.assertEqual(asset["role"], "control")
                self.assertEqual(asset["reference_label"], p["label"])
                self.assertTrue(p["explanation"])
        for p in fruit:
            self.post("/rounds/" + guide["id"] + "/events", {
                "event_id": uuid.uuid4().hex,
                "presentation_id": p["id"], "action": "acknowledge",
                "client_timestamp": "2026-10-24T00:00:00Z",
                "elapsed_ms": 0, "exposure_ms": 0,
            })
        self.post("/rounds/" + guide["id"] + "/complete", {"elapsed_ms": 0})
        self.assertEqual(self.client.get("/api/games/fruit-ninja/dataset").json()["total_votes"], 0)
        practice = self.create()
        self.assertTrue({p["asset_id"] for p in fruit}.isdisjoint(
            {p["asset_id"] for p in practice["presentations"]}
        ))
        self.assertTrue(all("label" not in p for p in practice["presentations"]))

    def test_catalog_schedule_and_profiles(self):
        with self.store.connect() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 183
            )
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM assets WHERE role='target'").fetchone()[
                    0
                ],
                92,
            )
            self.assertEqual(
                c.execute(
                    "SELECT COUNT(*) FROM assets WHERE reference_label='fresh'"
                ).fetchone()[0],
                52,
            )
        schedule = wave_schedule()
        self.assertEqual(len(schedule), 32)
        self.assertEqual(schedule[-1][0] + 3200, 60000)
        for t in range(0, 60001, 100):
            self.assertLessEqual(sum(sp <= t < sp + 3200 for sp, _ in schedule), 3)
        self.assertEqual(
            self.player["id"], self.post("/players", {"name": "test player"})["id"]
        )
        self.assertTrue(self.player["calibration_required"])

    def test_reference_change_requires_new_calibration(self):
        self.calibrate()
        self.store.reference_version = "future-standard"
        self.assertTrue(
            self.client.get(
                "/api/games/fruit-ninja/players/" + self.player["id"]
            ).json()["calibration_required"]
        )
        self.post("/rounds", {"player_id": self.player["id"], "kind": "game"}, 409)
        self.store.reference_version = self.store.catalog["reference_version"]
        r = self.create()
        result, _ = self.resolve(r, reference_version="future-standard")
        self.assertEqual(result["correct"], 10)
        self.assertFalse(result["passed"])
        self.assertEqual(result["exclusion_reason"], "reference_version_changed")
        self.assertTrue(
            self.client.get(
                "/api/games/fruit-ninja/players/" + self.player["id"]
            ).json()["calibration_required"]
        )

    def test_imported_assets_match_only_kept_cutouts(self):
        from PIL import Image

        manifest = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "research/fruit-ninja/dataset-review/segmentation-manifest.json"
            ).read_text()
        )
        kept = {
            a["id"]: a
            for source in manifest["sources"]
            for a in source["instances"]
            if a["quality"]["decision"] == "kept"
        }
        assets = self.store.catalog["assets"]
        self.assertEqual({a["source_id"] for a in assets}, set(kept))
        self.assertEqual(
            {a["source_id"] for a in assets if a["role"] == "control"}, CONTROL_IDS
        )
        for a in assets:
            original = self.store.asset_root / a["original_path"]
            self.assertEqual(
                hashlib.sha256(original.read_bytes()).hexdigest(),
                kept[a["source_id"]]["sha256"],
            )
            with Image.open(self.store.asset_root / a["gameplay_path"]) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertLessEqual(max(image.size), 384)
            self.assertEqual(len(a["source_photo_sha256"]), 64)

    def test_thresholds_balancing_privacy_and_review(self):
        failed, _ = self.resolve(self.create(), 3)
        self.assertFalse(failed["passed"])
        passed, _ = self.resolve(self.create(), 2)
        self.assertTrue(passed["passed"])
        r = self.create("game")
        self.assertEqual(len(r["presentations"]), 32)
        serialized = json.dumps(r)
        for forbidden in (
            "reference_label",
            "source_id",
            "control",
            "fresh",
            "rotten",
            "original_path",
        ):
            self.assertNotIn(forbidden, serialized)
        private = self.labels(r)
        for section in range(4):
            group = [p for p in private.values() if p["section"] == section]
            self.assertEqual(sum(p["role"] == "target" for p in group), 4)
            self.assertEqual(sum(p["reference_label"] == "fresh" for p in group), 2)
            self.assertEqual(sum(p["reference_label"] == "rotten" for p in group), 2)
        self.post("/rounds/" + r["id"] + "/sections/0", {"elapsed_ms": 60000}, 409)
        result, events = self.resolve(r, 3)
        self.assertEqual(result["correct"], 13)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["score"], 1460)
        ack = self.post("/rounds/" + r["id"] + "/events", events[0])
        self.assertEqual(set(ack), {"saved", "event_id"})
        section = self.post("/rounds/" + r["id"] + "/sections/0", {"elapsed_ms": 60000})
        self.assertEqual(set(section), {"section", "points", "total"})
        before = self.client.get("/api/games/fruit-ninja/dataset").json()
        self.assertEqual(before["total_votes"], 16)
        group = [p for p in r["presentations"] if p["section"] == 0]
        labels = {p["id"]: "rotten" for p in group}
        submission = {
            "submission_id": uuid.uuid4().hex,
            "client_timestamp": "now",
            "judgments": labels,
        }
        reviewed = self.post("/rounds/" + r["id"] + "/review/0", submission)
        self.assertEqual(reviewed["correct"], 13)
        self.assertEqual(reviewed["score"], 1470)
        self.assertEqual(
            reviewed, self.post("/rounds/" + r["id"] + "/review/0", submission)
        )
        after = self.client.get("/api/games/fruit-ninja/dataset").json()
        self.assertEqual(after["total_votes"], 16)
        self.assertEqual(sum(v["label"] == "rotten" for v in after["votes"]), 4)
        audit = self.client.get("/api/games/fruit-ninja/exports/json?audit=true").json()
        self.assertEqual(sum(v["phase"] == "review" for v in audit), 8)
        self.assertEqual(len(audit), 60)
        self.assertEqual(sum(row["effective_vote"] for row in audit), 16)
        for row in audit:
            self.assertNotIn("source_label", row)
            self.assertNotIn("reference_label", row)
            self.assertNotIn("role", row)
            self.assertNotIn("source_id", row)
            self.assertEqual(len(row["source_photo_id"]), 32)

    def test_fail_abandon_and_event_validation(self):
        self.calibrate()
        r = self.create("game")
        p = r["presentations"][0]
        data = {
            "event_id": uuid.uuid4().hex,
            "presentation_id": p["id"],
            "action": "pass",
            "client_timestamp": "now",
            "elapsed_ms": p["spawn_ms"] + 100,
            "exposure_ms": 100,
        }
        self.post("/rounds/" + r["id"] + "/events", data, 422)
        self.post("/rounds/" + r["id"] + "/complete", {"elapsed_ms": 60000}, 409)
        self.post("/rounds/" + r["id"] + "/abandon")
        self.assertEqual(
            self.client.get("/api/games/fruit-ninja/dataset").json()["total_votes"], 0
        )
        r = self.create("game")
        result, _ = self.resolve(r, 4)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["correct"], 12)
        group = [p for p in r["presentations"] if p["section"] == 0]
        self.post(
            "/rounds/" + r["id"] + "/review/0",
            {
                "submission_id": uuid.uuid4().hex,
                "client_timestamp": "now",
                "judgments": {p["id"]: "fresh" for p in group},
            },
        )
        self.assertFalse(
            self.client.get(
                "/api/games/fruit-ninja/rounds/" + r["id"] + "/result"
            ).json()["eligible"]
        )
        self.assertEqual(
            self.client.get("/api/games/fruit-ninja/dataset").json()["total_votes"], 0
        )
        self.post("/rounds", {"player_id": self.player["id"], "kind": "game"}, 409)
        # Restarting the store retains flags and raw events.
        restarted = Store(self.path)
        with restarted.connect() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM label_events").fetchone()[0], 50
            )
            self.assertEqual(
                c.execute("SELECT needs_calibration FROM players").fetchone()[0], 1
            )

    def test_persistent_target_deck_repeats_count_and_export(self):
        self.calibrate()
        seen = []
        for i in range(7):
            r = self.create("game")
            private = self.labels(r)
            targets = [p["asset_id"] for p in private.values() if p["role"] == "target"]
            seen += targets
            self.resolve(r)
        self.assertEqual(len(set(seen[:80])), 80)
        # First 92 draws cover the deck, even when round six crosses its boundary.
        self.assertEqual(len(set(seen[:92])), 92)
        self.assertEqual(
            self.client.get("/api/games/fruit-ninja/dataset").json()["total_votes"], 112
        )
        csv = self.client.get("/api/games/fruit-ninja/exports/csv")
        self.assertIn("source_photo_id", csv.text)
        self.assertEqual(len(csv.text.splitlines()), 113)


if __name__ == "__main__":
    unittest.main()
