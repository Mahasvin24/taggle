"""Server-owned sampling, scoring and auditable effective appearance votes."""

from datetime import datetime, timezone
import json
import random
import unicodedata
import uuid

from fastapi import HTTPException
from .catalog import wave_schedule


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


def require(value, message, status=409):
    if not value:
        raise HTTPException(status, message)


def fetch(c, table, identity):
    row = c.execute(f"SELECT * FROM {table} WHERE id=?", (identity,)).fetchone()
    require(row is not None, "Not found", 404)
    return dict(row)


def image(asset):
    data = json.loads(asset["metadata"]) if "metadata" in asset.keys() else asset
    return {
        "asset_id": data["id"],
        "url": f"/api/games/fruit-ninja/assets/{data['id']}?v={data['sha256'][:12]}",
        "width": data["width"],
        "height": data["height"],
    }


def profile(c, player_id, version):
    p = fetch(c, "players", player_id)
    history = [
        dict(r)
        for r in c.execute(
            "SELECT id,kind,status,first_pass_correct,first_pass_total,score,eligible,finished_at FROM rounds WHERE player_id=? AND status='completed' AND kind='game' ORDER BY finished_at DESC LIMIT 8",
            (player_id,),
        )
    ]
    return {
        "id": p["id"],
        "name": p["name"],
        "calibration_required": bool(
            p["needs_calibration"] or p["calibration_version"] != version
        ),
        "history": history,
        "targets_remaining": len(json.loads(p["decks"]).get("target", [])),
    }


def player(store, name):
    name = " ".join(unicodedata.normalize("NFKC", name).split())
    require(1 <= len(name) <= 40, "Use a name between 1 and 40 characters", 422)
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        existing = c.execute(
            "SELECT id FROM players WHERE normalized_name=?", (name.casefold(),)
        ).fetchone()
        identity = existing["id"] if existing else uid()
        if not existing:
            c.execute(
                "INSERT INTO players(id,name,normalized_name,created_at,last_seen) VALUES(?,?,?,?,?)",
                (identity, name, name.casefold(), now(), now()),
            )
        else:
            c.execute("UPDATE players SET last_seen=? WHERE id=?", (now(), identity))
        return profile(c, identity, store.reference_version)


def public_round(c, round_id):
    r = fetch(c, "rounds", round_id)
    presentations = []
    for p in c.execute(
        "SELECT * FROM presentations WHERE round_id=? ORDER BY ordinal", (round_id,)
    ):
        asset = fetch(c, "assets", p["asset_id"])
        presentations.append(
            {
                **image(asset),
                **{
                    k: p[k]
                    for k in (
                        "id",
                        "ordinal",
                        "section",
                        "spawn_ms",
                        "flight_ms",
                        "lane",
                        "drift",
                        "rotation",
                        "spin",
                    )
                },
            }
        )
    return {
        "id": r["id"],
        "kind": r["kind"],
        "duration_ms": r["duration_ms"],
        "presentations": presentations,
    }


def abandon(c, r):
    if r["status"] not in ("prepared", "running"):
        return
    c.execute(
        "UPDATE rounds SET status='abandoned',finished_at=?,exclusion_reason='abandoned' WHERE id=?",
        (now(), r["id"]),
    )
    # Return only unresolved targets to the front of the persistent deck.
    pending = [
        p["asset_id"]
        for p in c.execute(
            "SELECT p.asset_id FROM presentations p LEFT JOIN label_events e ON e.presentation_id=p.id AND e.phase='initial' WHERE p.round_id=? AND p.role='target' AND e.event_id IS NULL ORDER BY p.ordinal",
            (r["id"],),
        )
    ]
    p = fetch(c, "players", r["player_id"])
    decks = json.loads(p["decks"])
    decks["target"] = pending + [a for a in decks.get("target", []) if a not in pending]
    c.execute("UPDATE players SET decks=? WHERE id=?", (json.dumps(decks), p["id"]))


def create_round(store, player_id, kind):
    require(kind in ("game", "calibration", "demonstration"), "Invalid round kind", 422)
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        p = fetch(c, "players", player_id)
        if kind == "game":
            require(
                not profile(c, player_id, store.reference_version)[
                    "calibration_required"
                ],
                "Complete calibration first",
            )
        for old in c.execute(
            "SELECT * FROM rounds WHERE player_id=? AND status IN ('prepared','running')",
            (player_id,),
        ).fetchall():
            abandon(c, dict(old))
        p = fetch(c, "players", player_id)
        decks = json.loads(p["decks"])
        assets = {a["id"]: dict(a) for a in c.execute("SELECT * FROM assets")}

        def draw(key, count, pool):
            bag = decks.get(key, [])
            chosen = []
            while len(chosen) < count:
                if not bag:
                    bag = list(pool)
                    random.SystemRandom().shuffle(bag)
                candidate = bag.pop(0)
                if candidate in chosen:
                    bag.append(candidate)
                    continue
                chosen.append(candidate)
            decks[key] = bag
            return chosen

        if kind == "demonstration":
            chosen = [d["asset_id"] for d in store.catalog["demonstrations"]]
            duration = 0
        elif kind == "calibration":
            demos = {d["asset_id"] for d in store.catalog["demonstrations"]}
            chosen = []
            for label in ("fresh", "rotten"):
                chosen += draw(
                    "control_" + label,
                    5,
                    [
                        a["id"]
                        for a in assets.values()
                        if a["role"] == "control"
                        and a["reference_label"] == label
                        and a["id"] not in demos
                    ],
                )
            random.SystemRandom().shuffle(chosen)
            duration = 35000
        else:
            targets = draw(
                "target",
                16,
                [a["id"] for a in assets.values() if a["role"] == "target"],
            )
            fresh = draw(
                "control_fresh",
                8,
                [
                    a["id"]
                    for a in assets.values()
                    if a["role"] == "control" and a["reference_label"] == "fresh"
                ],
            )
            rotten = draw(
                "control_rotten",
                8,
                [
                    a["id"]
                    for a in assets.values()
                    if a["role"] == "control" and a["reference_label"] == "rotten"
                ],
            )
            chosen = []
            for section in range(4):
                group = (
                    targets[section * 4 : section * 4 + 4]
                    + fresh[section * 2 : section * 2 + 2]
                    + rotten[section * 2 : section * 2 + 2]
                )
                random.SystemRandom().shuffle(group)
                chosen += group
            duration = 60000
        identity = uid()
        c.execute(
            "INSERT INTO rounds(id,player_id,kind,status,reference_version,duration_ms,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                identity,
                player_id,
                kind,
                "prepared",
                store.reference_version,
                duration,
                now(),
            ),
        )
        schedule = (
            wave_schedule()
            if kind == "game"
            else [(300 + i * 3500, 0.5) for i in range(len(chosen))]
        )
        for i, asset_id in enumerate(chosen):
            a = assets[asset_id]
            spawn, lane = schedule[i]
            c.execute(
                "INSERT INTO presentations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    uid(),
                    identity,
                    asset_id,
                    i,
                    i // 8,
                    spawn,
                    3200,
                    lane,
                    random.uniform(-0.05, 0.05),
                    random.uniform(-0.3, 0.3),
                    random.uniform(-0.3, 0.3),
                    a["role"],
                    a["reference_label"],
                ),
            )
        c.execute(
            "UPDATE players SET decks=? WHERE id=?", (json.dumps(decks), player_id)
        )
        result = public_round(c, identity)
        if kind == "demonstration":
            for p, demo in zip(
                result["presentations"], store.catalog["demonstrations"]
            ):
                p.update(label=demo["label"], explanation=demo["explanation"])
        return result


def start(store, identity):
    with store.connect() as c:
        r = fetch(c, "rounds", identity)
        require(r["status"] in ("prepared", "running"), "Round is closed")
        c.execute(
            "UPDATE rounds SET status='running',started_at=COALESCE(started_at,?) WHERE id=?",
            (now(), identity),
        )
        return {"saved": True}


def record(store, identity, data):
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r = fetch(c, "rounds", identity)
        p = fetch(c, "presentations", data["presentation_id"])
        require(p["round_id"] == identity, "Presentation does not belong to round", 422)
        phase = "demonstration" if r["kind"] == "demonstration" else "initial"
        action = data["action"]
        require(action in ("slice", "pass", "acknowledge"), "Invalid action", 422)
        require(
            (action == "acknowledge") == (phase == "demonstration"),
            "Invalid action for this phase",
            422,
        )
        label = (
            p["reference_label"]
            if phase == "demonstration"
            else ("rotten" if action == "slice" else "fresh")
        )
        old = c.execute(
            "SELECT * FROM label_events WHERE event_id=?", (data["event_id"],)
        ).fetchone()
        if old:
            require(
                old["presentation_id"] == p["id"]
                and old["action"] == action
                and old["elapsed_ms"] == data["elapsed_ms"]
                and old["exposure_ms"] == data["exposure_ms"]
                and old["client_timestamp"] == data["client_timestamp"],
                "Event ID was already used",
            )
        else:
            require(r["status"] == "running", "Round is not running")
            elapsed = data["elapsed_ms"]
            if phase != "demonstration":
                require(
                    p["spawn_ms"] <= elapsed <= r["duration_ms"],
                    "Invalid active-play timestamp",
                    422,
                )
                if action == "pass":
                    require(
                        elapsed >= p["spawn_ms"] + p["flight_ms"]
                        and data["exposure_ms"] >= p["flight_ms"],
                        "Healthy requires a completed visible flight",
                        422,
                    )
                else:
                    require(
                        elapsed < p["spawn_ms"] + p["flight_ms"]
                        and data["exposure_ms"] >= 0,
                        "Fruit is not in flight",
                        422,
                    )
            require(
                not c.execute(
                    "SELECT 1 FROM label_events WHERE presentation_id=? AND phase=?",
                    (p["id"], phase),
                ).fetchone(),
                "Presentation already has a judgment",
            )
            c.execute(
                "INSERT INTO label_events(event_id,presentation_id,phase,action,label,client_timestamp,received_at,elapsed_ms,exposure_ms) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    data["event_id"],
                    p["id"],
                    phase,
                    action,
                    label,
                    data["client_timestamp"],
                    now(),
                    data["elapsed_ms"],
                    data["exposure_ms"],
                ),
            )
        result = {"saved": True, "event_id": data["event_id"]}
        if r["kind"] == "calibration":
            result.update(
                correct=label == p["reference_label"],
                expected_label=p["reference_label"],
            )
        return result


def section_score(c, identity, section):
    rows = c.execute(
        "SELECT p.*,e.label FROM presentations p LEFT JOIN label_events e ON e.presentation_id=p.id AND e.phase='initial' WHERE p.round_id=? AND p.section=?",
        (identity, section),
    ).fetchall()
    require(
        len(rows) == 8 and all(p["label"] for p in rows), "Section is not fully saved"
    )
    points = sum(
        (
            10
            if p["role"] == "target"
            else 100 if p["label"] == p["reference_label"] else 0
        )
        for p in rows
    )
    c.execute(
        "INSERT OR IGNORE INTO section_scores VALUES(?,?,?,?)",
        (identity, section, points, now()),
    )
    return points


def close_section(store, identity, section, elapsed):
    with store.connect() as c:
        r = fetch(c, "rounds", identity)
        require(
            r["kind"] == "game" and r["status"] in ("running", "completed"),
            "Invalid round",
        )
        end = c.execute(
            "SELECT MAX(spawn_ms+flight_ms) FROM presentations WHERE round_id=? AND section=?",
            (identity, section),
        ).fetchone()[0]
        require(end is not None and elapsed >= end, "Section is still in flight")
        points = section_score(c, identity, section)
        total = c.execute(
            "SELECT SUM(points) FROM section_scores WHERE round_id=?", (identity,)
        ).fetchone()[0]
        return {"section": section, "points": points, "total": total}


def result(c, identity):
    r = fetch(c, "rounds", identity)
    counts = dict(
        c.execute(
            "SELECT label,COUNT(*) FROM label_events WHERE presentation_id IN (SELECT id FROM presentations WHERE round_id=?) AND sequence=(SELECT MAX(e.sequence) FROM label_events e WHERE e.presentation_id=label_events.presentation_id) GROUP BY label",
            (identity,),
        ).fetchall()
    )
    review_count = c.execute(
        "SELECT COUNT(*) FROM review_submissions WHERE round_id=?", (identity,)
    ).fetchone()[0]
    return {
        "id": identity,
        "kind": r["kind"],
        "status": r["status"],
        "correct": r["first_pass_correct"],
        "total": r["first_pass_total"],
        "eligible": bool(r["eligible"]),
        "passed": bool(
            r["first_pass_correct"] is not None
            and r["exclusion_reason"] != "reference_version_changed"
            and r["first_pass_correct"] >= (8 if r["kind"] == "calibration" else 13)
        ),
        "score": r["score"],
        "review_bonus": review_count * 10,
        "counts": {"fresh": counts.get("fresh", 0), "rotten": counts.get("rotten", 0)},
        "exclusion_reason": r["exclusion_reason"],
    }


def finish(store, identity, elapsed):
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r = fetch(c, "rounds", identity)
        if r["status"] == "completed":
            return result(c, identity)
        require(r["status"] == "running", "Round is not running")
        require(elapsed >= r["duration_ms"], "Round has not ended")
        phase = "demonstration" if r["kind"] == "demonstration" else "initial"
        rows = c.execute(
            "SELECT p.*,e.label FROM presentations p LEFT JOIN label_events e ON e.presentation_id=p.id AND e.phase=? WHERE p.round_id=?",
            (phase, identity),
        ).fetchall()
        require(
            all(p["label"] for p in rows),
            "All presentations must be saved before completion",
        )
        controls = [p for p in rows if p["role"] == "control"]
        correct = sum(p["label"] == p["reference_label"] for p in controls)
        current_version = r["reference_version"] == store.reference_version
        passed = (
            correct >= (8 if r["kind"] == "calibration" else 13) and current_version
        )
        eligible = r["kind"] == "game" and passed
        score = (
            sum(section_score(c, identity, i) for i in range(4))
            if r["kind"] == "game"
            else 0
        )
        c.execute(
            "UPDATE rounds SET status='completed',finished_at=?,first_pass_correct=?,first_pass_total=?,eligible=?,score=?,exclusion_reason=? WHERE id=?",
            (
                now(),
                correct,
                len(controls),
                int(eligible),
                score,
                (
                    "reference_version_changed"
                    if not current_version
                    else (
                        None
                        if eligible
                        else (
                            "training"
                            if r["kind"] != "game"
                            else "accuracy_below_13_of_16"
                        )
                    )
                ),
                identity,
            ),
        )
        if r["kind"] == "calibration":
            c.execute(
                "UPDATE players SET calibration_version=?,needs_calibration=? WHERE id=?",
                (r["reference_version"], int(not passed), r["player_id"]),
            )
        elif r["kind"] == "game" and not passed:
            c.execute(
                "UPDATE players SET needs_calibration=1 WHERE id=?", (r["player_id"],)
            )
        return result(c, identity)


def review_state(store, identity):
    with store.connect() as c:
        r = fetch(c, "rounds", identity)
        require(
            r["kind"] == "game" and r["status"] == "completed",
            "Complete the round first",
        )
        saved = [
            r[0]
            for r in c.execute(
                "SELECT section FROM review_submissions WHERE round_id=?", (identity,)
            )
        ]
        out = public_round(c, identity)
        for p in out["presentations"]:
            p["label"] = c.execute(
                "SELECT label FROM label_events WHERE presentation_id=? ORDER BY sequence DESC LIMIT 1",
                (p["id"],),
            ).fetchone()[0]
        return {**out, "submitted_sections": saved}


def review(store, identity, section, data):
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        r = fetch(c, "rounds", identity)
        require(
            r["status"] == "completed" and r["kind"] == "game",
            "Complete the round first",
        )
        payload = json.dumps(data["judgments"], sort_keys=True)
        old = c.execute(
            "SELECT * FROM review_submissions WHERE submission_id=?",
            (data["submission_id"],),
        ).fetchone()
        if old:
            require(
                old["round_id"] == identity
                and old["section"] == section
                and old["payload"] == payload,
                "Submission ID was already used",
            )
            return result(c, identity)
        require(
            not c.execute(
                "SELECT 1 FROM review_submissions WHERE round_id=? AND section=?",
                (identity, section),
            ).fetchone(),
            "Section already reviewed",
        )
        expected = {
            r["id"]
            for r in c.execute(
                "SELECT id FROM presentations WHERE round_id=? AND section=?",
                (identity, section),
            )
        }
        require(
            len(expected) == 8
            and set(data["judgments"]) == expected
            and all(v in ("fresh", "rotten") for v in data["judgments"].values()),
            "Submit all eight judgments",
            422,
        )
        c.execute(
            "INSERT INTO review_submissions VALUES(?,?,?,?,?)",
            (data["submission_id"], identity, section, payload, now()),
        )
        for presentation_id, label in data["judgments"].items():
            event_id = uuid.uuid5(
                uuid.NAMESPACE_URL, data["submission_id"] + presentation_id
            ).hex
            c.execute(
                "INSERT INTO label_events(event_id,presentation_id,phase,action,label,client_timestamp,received_at,elapsed_ms,exposure_ms) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    presentation_id,
                    "review",
                    "confirm",
                    label,
                    data["client_timestamp"],
                    now(),
                    r["duration_ms"],
                    0,
                ),
            )
        c.execute("UPDATE rounds SET score=score+10 WHERE id=?", (identity,))
        return result(c, identity)


def public_photo_id(source):
    # Preserve source-photo grouping without leaking condition-bearing filenames.
    return uuid.uuid5(uuid.NAMESPACE_URL, "taggle-source-photo:" + source).hex


def public_provenance(row):
    metadata = json.loads(row.pop("metadata"))
    row["source_photo_id"] = public_photo_id(row["source_photo_id"])
    row["source_photo_sha256"] = metadata["source_photo_sha256"]
    row["cutout_sha256"] = metadata["sha256"]
    row["source_bbox_xyxy"] = metadata["source_bbox_xyxy"]
    return row


def dataset(store, audit=False):
    with store.connect() as c:
        if audit:
            rows = c.execute(
                """SELECT e.*,p.asset_id,p.round_id,p.ordinal,r.player_id,pl.name AS player_name,
                r.kind,r.status,r.reference_version,r.eligible AS round_accuracy_eligible,
                (r.eligible=1 AND p.role='target' AND e.sequence=(SELECT MAX(sequence) FROM label_events e2 WHERE e2.presentation_id=p.id)) AS effective_vote,
                CASE WHEN r.status!='completed' THEN COALESCE(r.exclusion_reason,'round_incomplete')
                  WHEN r.kind!='game' THEN 'training'
                  WHEN r.eligible=0 THEN r.exclusion_reason
                  WHEN p.role!='target' THEN 'outside_target_dataset'
                  WHEN e.sequence!=(SELECT MAX(sequence) FROM label_events e2 WHERE e2.presentation_id=p.id) THEN 'superseded_by_review'
                  ELSE NULL END AS exclusion_reason,
                a.source_photo_id,a.metadata
                FROM label_events e JOIN presentations p ON p.id=e.presentation_id JOIN rounds r ON r.id=p.round_id JOIN players pl ON pl.id=r.player_id JOIN assets a ON a.id=p.asset_id ORDER BY e.sequence"""
            ).fetchall()
            return [public_provenance(dict(r)) for r in rows]
        votes = [
            dict(v)
            for v in c.execute(
                """SELECT p.asset_id,p.id AS presentation_id,r.id AS round_id,r.player_id,r.reference_version,e.label,e.event_id,e.phase,e.client_timestamp,e.received_at,a.source_photo_id,a.metadata FROM presentations p JOIN rounds r ON r.id=p.round_id JOIN assets a ON a.id=p.asset_id JOIN label_events e ON e.presentation_id=p.id WHERE p.role='target' AND r.eligible=1 AND r.status='completed' AND e.sequence=(SELECT MAX(e2.sequence) FROM label_events e2 WHERE e2.presentation_id=p.id) ORDER BY e.sequence"""
            )
        ]
        votes = [public_provenance(vote) for vote in votes]
        assets = []
        for a in c.execute("SELECT * FROM assets WHERE role='target' ORDER BY id"):
            own = [v for v in votes if v["asset_id"] == a["id"]]
            assets.append(
                {
                    **image(a),
                    "source_photo_id": public_photo_id(a["source_photo_id"]),
                    "fresh": sum(v["label"] == "fresh" for v in own),
                    "rotten": sum(v["label"] == "rotten" for v in own),
                    "contributions": len(own),
                }
            )
        return {
            "assets": assets,
            "votes": votes,
            "total_votes": len(votes),
            "reference_version": store.reference_version,
            "attribution": store.catalog["attribution"],
        }
