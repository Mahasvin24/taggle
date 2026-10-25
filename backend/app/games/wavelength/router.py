"""POC API. Reference scores are feedback anchors, never human labels."""

import csv
from datetime import datetime, timezone
import io
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .reviews import AXES, AXES_BY_ID, BY_ID, REFERENCE_VERSION, SOURCE, public_reviews

router = APIRouter(prefix="/api/games/wavelength", tags=["wavelength"])

Score = Annotated[int, Field(strict=True, ge=0, le=100)]
Elapsed = Annotated[int, Field(strict=True, ge=0, le=3_600_000)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_id: UUID
    session_id: UUID
    elapsed_ms: Elapsed
    axis_id: Literal["satisfaction", "anger", "happiness", "excitement"] = "satisfaction"


class Annotation(Submission):
    review_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    score: Score
    confidence: Literal["sure", "unsure"]


class Clue(Submission):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]
    category: Category
    target: Score
    guess: Score


def store(request: Request):
    return request.app.state.wavelength_store


def result_points(score: int, target: int):
    distance = abs(score - target)
    return {"distance": distance, "points": 100 if distance <= 3 else max(0, 100 - distance * 3)}


def now():
    return datetime.now(timezone.utc).isoformat()


def existing(connection, submission_id, kind, payload):
    row = connection.execute("SELECT * FROM wavelength_submissions WHERE submission_id=?", (submission_id,)).fetchone()
    if row is None:
        return None
    prior = json.loads(row["payload"])
    prior.setdefault("axis_id", "satisfaction")
    if row["kind"] != kind or prior != json.loads(payload):
        raise HTTPException(409, "This submission ID was already used with different data.")
    response = json.loads(row["response"])
    response.setdefault("axis_id", "satisfaction")
    return response


@router.get("")
def info():
    return {"title": "Common Ground", "status": "playable", "review_count": len(BY_ID), "reference_version": REFERENCE_VERSION,
            "source": SOURCE, "axes": AXES,
            "scale": {"min": 0, "max": 100, "left": "Disappointed customer", "right": "Satisfied customer"}}


@router.get("/reviews")
def reviews():
    return {"reviews": public_reviews(), "reference_version": REFERENCE_VERSION, "axes": AXES}


@router.post("/annotations")
def annotate(data: Annotation, request: Request):
    payload = data.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True)
    identity = payload["submission_id"]
    with store(request).connect() as connection:
        # Acquire the write lock before checking idempotency: concurrent retries
        # must not race between a lookup and the primary-key insert.
        connection.execute("BEGIN IMMEDIATE")
        duplicate = existing(connection, identity, "annotation", encoded)
        if duplicate is not None:
            return duplicate
        review = BY_ID.get(data.review_id)
        if review is None:
            raise HTTPException(404, "Review not found.")
        independent = not connection.execute(
            "SELECT 1 FROM wavelength_annotations WHERE session_id=? AND review_id=? AND axis_id=? LIMIT 1",
            (payload["session_id"], data.review_id, data.axis_id),
        ).fetchone()
        reference = review["references"][data.axis_id]
        response = {"saved": True, "annotation_id": identity, "axis_id": data.axis_id,
                    "reference_score": reference["score"],
                    "reference_note": reference["note"], "reference_version": REFERENCE_VERSION,
                    **result_points(data.score, reference["score"])}
        received = now()
        connection.execute("INSERT INTO wavelength_submissions VALUES(?,?,?,?,?)",
                           (identity, "annotation", encoded, json.dumps(response), received))
        connection.execute("""INSERT INTO wavelength_annotations
                           (annotation_id,session_id,review_id,text,category,source,score,confidence,elapsed_ms,
                            reference_score,reference_note,reference_version,independent,received_at,axis_id)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (identity, payload["session_id"], data.review_id, review["text"], review["category"], SOURCE,
                            data.score, data.confidence, data.elapsed_ms, reference["score"], reference["note"],
                            REFERENCE_VERSION, int(independent), received, data.axis_id))
    return response


@router.post("/clues")
def clue(data: Clue, request: Request):
    payload = data.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True)
    identity = payload["submission_id"]
    with store(request).connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        duplicate = existing(connection, identity, "synthetic_pair", encoded)
        if duplicate is not None:
            return duplicate
        response = {"saved": True, "pair_id": identity, "axis_id": data.axis_id, "target": data.target, "guess": data.guess,
                    **result_points(data.guess, data.target)}
        received = now()
        connection.execute("INSERT INTO wavelength_submissions VALUES(?,?,?,?,?)",
                           (identity, "synthetic_pair", encoded, json.dumps(response), received))
        connection.execute("""INSERT INTO wavelength_synthetic_pairs
                           (pair_id,session_id,text,category,source,intended_score,guessed_score,elapsed_ms,received_at,axis_id)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                           (identity, payload["session_id"], data.text, data.category, "player_authored_synthetic",
                            data.target, data.guess, data.elapsed_ms, received, data.axis_id))
    return response


def dataset(store):
    with store.connect() as connection:
        annotations = [dict(row) for row in connection.execute("SELECT * FROM wavelength_annotations ORDER BY received_at, annotation_id")]
        synthetic = [dict(row) for row in connection.execute("SELECT * FROM wavelength_synthetic_pairs ORDER BY received_at, pair_id")]
    for row in annotations:
        row["independent"] = bool(row["independent"])
        row["first_exposure"] = row["independent"]
        row["feedback_conditioned"] = not row["first_exposure"]
        row["kind"] = "annotation"
    for row in synthetic:
        row["kind"] = "synthetic_pair"
    for row in annotations + synthetic:
        axis = AXES_BY_ID[row["axis_id"]]
        row["axis_left"] = axis["left"]
        row["axis_right"] = axis["right"]
    return {
        "reference_version": REFERENCE_VERSION,
        "axes": AXES,
        "scale": {"min": 0, "max": 100, "left": "Disappointed customer", "right": "Satisfied customer"},
        "summary": {"annotations": len(annotations), "synthetic_pairs": len(synthetic),
                    "unique_reviews": len({r["review_id"] for r in annotations}),
                    "unsure_annotations": sum(r["confidence"] == "unsure" for r in annotations),
                    "independent_annotations": sum(r["independent"] for r in annotations)},
        "annotations": annotations,
        "synthetic_pairs": synthetic,
        "notes": ["Demo review text and game reference scores are authored, not real customer reviews or crowd consensus.",
                  "Raw human scores are retained independently of game reference scores.",
                  "Repeated review ratings on the same emotion axis within a session are marked independent=false because feedback was previously revealed.",
                  "Scores are positions from axis_left (0) to axis_right (100), not probabilities or calibrated emotion measurements.",
                  "Emotion references are separately authored interpretations, not conversions of overall satisfaction.",
                  "Two-player pairs are synthetic; intended_score is the clue writer's target and guessed_score is the partner's interpretation.",
                  "Session IDs identify browser sessions, not verified distinct people. This local POC has no authentication."],
    }


@router.get("/dataset")
def get_dataset(request: Request):
    return dataset(store(request))


@router.get("/exports/{format}")
def export(format: Literal["json", "csv"], request: Request):
    data = dataset(store(request))
    if format == "json":
        content = json.dumps(data, indent=2)
        media_type = "application/json"
    else:
        fields = ["kind", "annotation_id", "pair_id", "session_id", "review_id", "text", "category", "source", "score",
                  "confidence", "elapsed_ms", "reference_score", "reference_note", "reference_version", "independent",
                  "first_exposure", "feedback_conditioned",
                  "intended_score", "guessed_score", "received_at", "axis_id", "axis_left", "axis_right"]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in data["annotations"] + data["synthetic_pairs"]:
            # Spreadsheet applications interpret these text prefixes as formulas.
            # The JSON export remains the lossless original data.
            safe = {key: ("'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value)
                    for key, value in row.items()}
            writer.writerow(safe)
        content = buffer.getvalue()
        media_type = "text/csv"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="common-ground-dataset.{format}"'})
