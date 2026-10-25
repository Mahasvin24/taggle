import csv
import io
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient

from app.main import create_app
from app.games.wavelength.db import SCHEMA
from app.games.wavelength.reviews import AXES, BY_ID, REFERENCE_VERSION
from app.games.wavelength.router import result_points


class WavelengthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "wavelength.db"
        self.client = TestClient(
            create_app(Path(self.temp.name) / "fruit.db", self.database)
        )
        self.client.__enter__()
        self.session = str(uuid.uuid4())

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def post(self, path, data, status=200):
        response = self.client.post("/api/games/wavelength" + path, json=data)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def annotation(self, **values):
        return {
            "submission_id": str(uuid.uuid4()),
            "session_id": self.session,
            "review_id": "review-01",
            "score": 43,
            "confidence": "sure",
            "elapsed_ms": 5200,
            **values,
        }

    def clue(self, **values):
        return {
            "submission_id": str(uuid.uuid4()),
            "session_id": self.session,
            "text": "It works, but only after three restarts.",
            "category": "Apps",
            "target": 24,
            "guess": 30,
            "elapsed_ms": 14500,
            **values,
        }

    def dataset(self):
        response = self.client.get("/api/games/wavelength/dataset")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_reviews_withhold_feedback_and_disclose_demo_provenance(self):
        response = self.client.get("/api/games/wavelength/reviews").json()
        self.assertEqual(response["reference_version"], REFERENCE_VERSION)
        self.assertEqual({a["id"] for a in response["axes"]}, {"satisfaction", "anger", "happiness", "excitement"})
        self.assertEqual(len(response["reviews"]), 24)
        for review in response["reviews"]:
            self.assertEqual(set(review), {"id", "text", "category", "source"})
            self.assertEqual(review["source"], "authored_demo")
        serialized = json.dumps(response)
        self.assertNotIn("reference_score", serialized)
        self.assertNotIn("reference_note", serialized)
        self.assertNotIn('"references"', serialized)
        self.assertGreaterEqual(len({r["category"] for r in response["reviews"]}), 6)
        self.assertLess(min(r["reference_score"] for r in BY_ID.values()), 10)
        self.assertGreater(max(r["reference_score"] for r in BY_ID.values()), 90)
        for review in BY_ID.values():
            self.assertEqual(set(review["references"]), {axis["id"] for axis in AXES})
            for reference in review["references"].values():
                self.assertIs(type(reference["score"]), int)
                self.assertTrue(0 <= reference["score"] <= 100)
                self.assertTrue(reference["note"])

    def test_feedback_keeps_human_judgment_and_reference_separate(self):
        payload = self.annotation(score=80, confidence="unsure")
        response = self.post("/annotations", payload)
        self.assertTrue(response["saved"])
        self.assertEqual(response["reference_score"], 42)
        self.assertEqual(response["distance"], 38)
        self.assertEqual(response["points"], 0)
        data = self.dataset()
        self.assertEqual(data["summary"]["annotations"], 1)
        self.assertEqual(data["summary"]["unsure_annotations"], 1)
        saved = data["annotations"][0]
        self.assertEqual(saved["score"], 80)
        self.assertEqual(saved["reference_score"], 42)
        self.assertEqual(saved["confidence"], "unsure")
        self.assertTrue(saved["independent"])
        self.assertTrue(saved["first_exposure"])
        self.assertFalse(saved["feedback_conditioned"])
        self.assertEqual(saved["source"], "authored_demo")
        self.assertEqual(saved["text"], BY_ID["review-01"]["text"])
        self.assertEqual(data["synthetic_pairs"], [])
        self.post("/annotations", self.annotation())
        repeated = self.dataset()["annotations"][1]
        self.assertFalse(repeated["independent"])
        self.assertFalse(repeated["first_exposure"])
        self.assertTrue(repeated["feedback_conditioned"])
        self.assertEqual(self.dataset()["summary"]["independent_annotations"], 1)

    def test_idempotency_conflicts_and_restart_persistence(self):
        payload = self.annotation()
        original = self.post("/annotations", payload)
        self.assertEqual(original, self.post("/annotations", payload))
        self.post("/annotations", {**payload, "score": 44}, 409)
        self.post("/clues", self.clue(submission_id=payload["submission_id"]), 409)
        self.assertEqual(self.dataset()["summary"]["annotations"], 1)
        clue = self.clue()
        original_clue = self.post("/clues", clue)
        self.assertEqual(original_clue, self.post("/clues", clue))
        self.post("/clues", {**clue, "text": "A different review entirely."}, 409)
        self.assertEqual(self.dataset()["summary"]["synthetic_pairs"], 1)
        with TestClient(
            create_app(Path(self.temp.name) / "fruit2.db", self.database)
        ) as restarted:
            persisted = restarted.get("/api/games/wavelength/dataset").json()
            self.assertEqual(persisted["summary"]["annotations"], 1)
            self.assertEqual(persisted["summary"]["synthetic_pairs"], 1)
            self.assertEqual(
                persisted["annotations"][0]["annotation_id"], original["annotation_id"]
            )

    def test_synthetic_intent_is_not_a_customer_annotation(self):
        result = self.post("/clues", self.clue())
        self.assertEqual(result["distance"], 6)
        self.assertEqual(result["points"], 82)
        data = self.dataset()
        self.assertEqual(data["summary"]["annotations"], 0)
        self.assertEqual(data["summary"]["unique_reviews"], 0)
        row = data["synthetic_pairs"][0]
        self.assertEqual(row["kind"], "synthetic_pair")
        self.assertEqual(row["source"], "player_authored_synthetic")
        self.assertEqual(row["intended_score"], 24)
        self.assertEqual(row["guessed_score"], 30)
        self.assertNotIn("score", row)
        self.assertNotIn("reference_score", row)

    def test_emotion_references_and_exposure_history_stay_on_their_axis(self):
        # A pleasant, ordinary weekend has high satisfaction and happiness but
        # little excitement. These dimensions must not alias one another.
        expected = {"satisfaction": 74, "anger": 2, "happiness": 78, "excitement": 20}
        for axis_id, reference_score in expected.items():
            result = self.post("/annotations", self.annotation(
                review_id="review-21", axis_id=axis_id, score=reference_score))
            self.assertEqual(result["axis_id"], axis_id)
            self.assertEqual(result["reference_score"], reference_score)
            self.assertEqual(result["points"], 100)
        data = self.dataset()
        self.assertEqual(data["summary"]["independent_annotations"], 4)
        self.assertEqual(len({r["reference_note"] for r in data["annotations"]}), 4)
        repeated = self.post("/annotations", self.annotation(review_id="review-21", axis_id="anger"))
        self.assertEqual(repeated["reference_score"], 2)
        self.assertEqual(self.dataset()["summary"]["independent_annotations"], 4)
        for row in self.dataset()["annotations"]:
            axis = next(a for a in AXES if a["id"] == row["axis_id"])
            self.assertEqual(row["axis_left"], axis["left"])
            self.assertEqual(row["axis_right"], axis["right"])
        pair = self.post("/clues", self.clue(axis_id="happiness"))
        self.assertEqual(pair["axis_id"], "happiness")
        saved_pair = self.dataset()["synthetic_pairs"][0]
        self.assertEqual(saved_pair["axis_left"], "Sad")
        self.assertEqual(saved_pair["axis_right"], "Happy")
        payload = self.annotation(axis_id="anger")
        self.post("/annotations", payload)
        self.post("/annotations", {**payload, "axis_id": "happiness"}, 409)
        for invalid in ("love", "", None):
            self.post("/annotations", self.annotation(axis_id=invalid), 422)
            self.post("/clues", self.clue(axis_id=invalid), 422)

    def test_legacy_database_migrates_without_losing_records_or_pending_retries(self):
        path = Path(self.temp.name) / "legacy.db"
        old_schema = SCHEMA.replace(",\n axis_id TEXT NOT NULL DEFAULT 'satisfaction'", "")
        annotation = self.annotation()
        clue = self.clue()
        old_annotation_response = {"saved": True, "annotation_id": annotation["submission_id"],
                                   "reference_score": 42, "reference_note": "Original note.",
                                   "reference_version": "demo-v1", "distance": 1, "points": 100}
        old_clue_response = {"saved": True, "pair_id": clue["submission_id"],
                             "target": 24, "guess": 30, "distance": 6, "points": 82}
        received = "2026-10-24T00:00:00+00:00"
        with sqlite3.connect(path) as connection:
            connection.executescript(old_schema)
            for kind, payload, response in (("annotation", annotation, old_annotation_response),
                                            ("synthetic_pair", clue, old_clue_response)):
                connection.execute("INSERT INTO wavelength_submissions VALUES(?,?,?,?,?)", (
                    payload["submission_id"], kind, json.dumps(payload, sort_keys=True), json.dumps(response), received))
            connection.execute("INSERT INTO wavelength_annotations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                annotation["submission_id"], self.session, "review-01", "Legacy review text", "Dining", "authored_demo",
                43, "sure", 5200, 42, "Original note.", "demo-v1", 1, received))
            connection.execute("INSERT INTO wavelength_synthetic_pairs VALUES(?,?,?,?,?,?,?,?,?)", (
                clue["submission_id"], self.session, clue["text"], "Apps", "player_authored_synthetic", 24, 30, 14500, received))
        with TestClient(create_app(Path(self.temp.name) / "migration-fruit.db", path)) as client:
            migrated = client.get("/api/games/wavelength/dataset").json()
            self.assertEqual(migrated["summary"]["annotations"], 1)
            self.assertEqual(migrated["summary"]["synthetic_pairs"], 1)
            row = migrated["annotations"][0]
            self.assertEqual(row["text"], "Legacy review text")
            self.assertEqual(row["reference_version"], "demo-v1")
            self.assertEqual(row["axis_id"], "satisfaction")
            self.assertEqual(migrated["synthetic_pairs"][0]["axis_id"], "satisfaction")
            for route, payload, response in (("annotations", annotation, old_annotation_response),
                                              ("clues", clue, old_clue_response)):
                retry = client.post("/api/games/wavelength/" + route, json=payload)
                self.assertEqual(retry.status_code, 200, retry.text)
                self.assertEqual(retry.json(), {**response, "axis_id": "satisfaction"})
                explicit = client.post("/api/games/wavelength/" + route, json={**payload, "axis_id": "satisfaction"})
                self.assertEqual(explicit.json(), retry.json())
            self.assertEqual(client.get("/api/games/wavelength/dataset").json()["summary"]["annotations"], 1)

    def test_validation_and_scoring_boundaries(self):
        for value in (-1, 101, 3.5, True, "80"):
            self.post("/annotations", self.annotation(score=value), 422)
            self.post("/clues", self.clue(target=value), 422)
            self.post("/clues", self.clue(guess=value), 422)
        self.post("/annotations", self.annotation(review_id="missing"), 404)
        self.post("/annotations", self.annotation(confidence="maybe"), 422)
        self.post("/annotations", self.annotation(elapsed_ms=-1), 422)
        self.post("/annotations", self.annotation(elapsed_ms=3_600_001), 422)
        self.post("/annotations", self.annotation(submission_id="not-a-uuid"), 422)
        self.post("/annotations", self.annotation(session_id="not-a-uuid"), 422)
        self.post("/clues", self.clue(text=" " * 20), 422)
        self.post("/clues", self.clue(text="a" * 501), 422)
        self.post("/clues", self.clue(category="  "), 422)
        self.post("/annotations", {**self.annotation(), "reference_score": 42}, 422)
        self.assertEqual(self.dataset()["summary"]["annotations"], 0)
        for distance, points in (
            (0, 100),
            (3, 100),
            (4, 88),
            (33, 1),
            (34, 0),
            (100, 0),
        ):
            self.assertEqual(
                result_points(distance, 0), {"distance": distance, "points": points}
            )
        self.post("/annotations", self.annotation(score=0))
        self.post("/annotations", self.annotation(score=100))

    def test_exports_keep_provenance_and_escape_spreadsheet_formulas(self):
        empty = self.client.get("/api/games/wavelength/exports/csv")
        self.assertIn("kind,annotation_id,pair_id", empty.text)
        self.post("/annotations", self.annotation())
        text = '=HYPERLINK("https://example.com", "Click")'
        self.post("/clues", self.clue(text=text, axis_id="happiness"))
        exported = self.client.get("/api/games/wavelength/exports/json")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()["synthetic_pairs"][0]["text"], text)
        self.assertIn("common-ground-dataset.json", exported.headers["content-disposition"])
        exported_csv = self.client.get("/api/games/wavelength/exports/csv")
        rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["kind"], "annotation")
        self.assertEqual(rows[1]["kind"], "synthetic_pair")
        self.assertEqual(rows[1]["text"], "'" + text)
        self.assertEqual(rows[0]["axis_id"], "satisfaction")
        self.assertEqual(rows[1]["axis_id"], "happiness")
        self.assertEqual(rows[1]["axis_left"], "Sad")
        self.assertEqual(rows[1]["axis_right"], "Happy")
        self.assertEqual(
            self.client.get("/api/games/wavelength/exports/xml").status_code, 422
        )


if __name__ == "__main__":
    unittest.main()
