import csv
import io
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from . import service as s

router = APIRouter(prefix="/api/games/fruit-ninja", tags=["fruit-shift"])


class Name(BaseModel):
    name: str


class Create(BaseModel):
    player_id: str
    kind: Literal["game", "calibration", "demonstration"] = "game"


class Event(BaseModel):
    event_id: str = Field(min_length=8, max_length=80)
    presentation_id: str
    action: Literal["slice", "pass", "acknowledge"]
    client_timestamp: str = Field(max_length=80)
    elapsed_ms: int = Field(ge=0, le=60000)
    exposure_ms: int = Field(ge=0, le=60000)


class Clock(BaseModel):
    elapsed_ms: int = Field(ge=0, le=60000)


class Review(BaseModel):
    submission_id: str = Field(min_length=8, max_length=80)
    client_timestamp: str = Field(max_length=80)
    judgments: dict[str, Literal["fresh", "rotten"]]


def store(req):
    return req.app.state.fruit_store


@router.get("")
def info(request: Request):
    st = store(request)
    return {
        "title": "Fruit Shift",
        "status": "playable",
        "asset_count": 183,
        "target_count": 92,
        "reference_version": st.reference_version,
        "previews": [
            s.image(a) for source in (
                "strawberry-fresh-1483-fruit-47",
                "strawberry-rotten-3017-fruit-08",
                "strawberry-fresh-1483-fruit-12",
            ) for a in st.catalog["assets"] if a["source_id"] == source
        ],
    }


@router.post("/players")
def player(data: Name, request: Request):
    return s.player(store(request), data.name)


@router.get("/players/{identity}")
def profile(identity: str, request: Request):
    st = store(request)
    with st.connect() as c:
        return s.profile(c, identity, st.reference_version)


@router.post("/rounds")
def create(data: Create, request: Request):
    return s.create_round(store(request), data.player_id, data.kind)


@router.post("/rounds/{identity}/start")
def start(identity: str, request: Request):
    return s.start(store(request), identity)


@router.post("/rounds/{identity}/events")
def event(identity: str, data: Event, request: Request):
    return s.record(store(request), identity, data.model_dump())


@router.post("/rounds/{identity}/sections/{section}")
def section(identity: str, section: int, data: Clock, request: Request):
    return s.close_section(store(request), identity, section, data.elapsed_ms)


@router.post("/rounds/{identity}/complete")
def complete(identity: str, data: Clock, request: Request):
    return s.finish(store(request), identity, data.elapsed_ms)


@router.post("/rounds/{identity}/abandon")
def abandon(identity: str, request: Request):
    with store(request).connect() as c:
        s.abandon(c, s.fetch(c, "rounds", identity))
    return {"saved": True}


@router.get("/rounds/{identity}/result")
def result(identity: str, request: Request):
    with store(request).connect() as c:
        return s.result(c, identity)


@router.get("/rounds/{identity}/review")
def review_state(identity: str, request: Request):
    return s.review_state(store(request), identity)


@router.post("/rounds/{identity}/review/{section}")
def review(identity: str, section: int, data: Review, request: Request):
    return s.review(store(request), identity, section, data.model_dump())


@router.get("/assets/{identity}")
def asset(identity: str, request: Request, original: bool = False):
    st = store(request)
    with st.connect() as c:
        a = s.fetch(c, "assets", identity)
    import json

    meta = json.loads(a["metadata"])
    path = st.asset_root / meta["original_path" if original else "gameplay_path"]
    if not Path(path).is_file():
        raise HTTPException(404, "Asset unavailable")
    return FileResponse(
        path,
        media_type="image/png" if original else "image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/dataset")
def dataset(request: Request):
    return s.dataset(store(request))


@router.get("/exports/{format}")
def export(format: Literal["json", "csv"], request: Request, audit: bool = False):
    import json

    data = s.dataset(store(request), audit)
    if format == "json":
        content = json.dumps(data, indent=2)
    else:
        rows = data if audit else data["votes"]
        buf = io.StringIO()
        fields = (
            list(rows[0])
            if rows
            else [
                "asset_id",
                "presentation_id",
                "round_id",
                "player_id",
                "reference_version",
                "label",
                "event_id",
                "phase",
                "client_timestamp",
                "received_at",
                "source_photo_id",
                "source_photo_sha256",
                "cutout_sha256",
                "source_bbox_xyxy",
            ]
        )
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        # Spreadsheet applications must treat player names as text, not formulas.
        writer.writerows(
            {
                key: (
                    "'" + value
                    if isinstance(value, str)
                    and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value
                )
                for key, value in row.items()
            }
            for row in rows
        )
        content = buf.getvalue()
    return Response(
        content,
        media_type="application/json" if format == "json" else "text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="fruit-shift-{"audit" if audit else "dataset"}.{format}"'
        },
    )
