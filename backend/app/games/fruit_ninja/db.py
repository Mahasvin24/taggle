"""SQLite storage for local profiles and an append-only labeling history."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3

from .catalog import ASSET_ROOT, BACKEND_ROOT

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
 id TEXT PRIMARY KEY, source_id TEXT UNIQUE NOT NULL, source_photo_id TEXT NOT NULL,
 fruit_type TEXT NOT NULL, source_label TEXT NOT NULL, role TEXT NOT NULL,
 reference_label TEXT, reference_version TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL UNIQUE,
 calibration_version TEXT, needs_calibration INTEGER NOT NULL DEFAULT 1,
 decks TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rounds (
 id TEXT PRIMARY KEY, player_id TEXT NOT NULL REFERENCES players(id), kind TEXT NOT NULL,
 status TEXT NOT NULL, reference_version TEXT NOT NULL, duration_ms INTEGER NOT NULL,
 created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
 first_pass_correct INTEGER, first_pass_total INTEGER, eligible INTEGER NOT NULL DEFAULT 0,
 score INTEGER NOT NULL DEFAULT 0, exclusion_reason TEXT
);
CREATE TABLE IF NOT EXISTS presentations (
 id TEXT PRIMARY KEY, round_id TEXT NOT NULL REFERENCES rounds(id),
 asset_id TEXT NOT NULL REFERENCES assets(id), ordinal INTEGER NOT NULL,
 section INTEGER NOT NULL, spawn_ms INTEGER NOT NULL, flight_ms INTEGER NOT NULL,
 lane REAL NOT NULL, drift REAL NOT NULL, rotation REAL NOT NULL, spin REAL NOT NULL,
 role TEXT NOT NULL, reference_label TEXT,
 UNIQUE(round_id, ordinal)
);
CREATE TABLE IF NOT EXISTS label_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
 presentation_id TEXT NOT NULL REFERENCES presentations(id),
 phase TEXT NOT NULL, action TEXT NOT NULL, label TEXT NOT NULL,
 client_timestamp TEXT NOT NULL, received_at TEXT NOT NULL,
 elapsed_ms INTEGER NOT NULL, exposure_ms INTEGER NOT NULL,
 UNIQUE(presentation_id, phase)
);
CREATE TABLE IF NOT EXISTS section_scores (
 round_id TEXT NOT NULL REFERENCES rounds(id), section INTEGER NOT NULL,
 points INTEGER NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(round_id, section)
);
CREATE TABLE IF NOT EXISTS review_submissions (
 submission_id TEXT PRIMARY KEY, round_id TEXT NOT NULL REFERENCES rounds(id),
 section INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(round_id, section)
);
CREATE INDEX IF NOT EXISTS presentation_round ON presentations(round_id);
CREATE INDEX IF NOT EXISTS event_presentation ON label_events(presentation_id);
CREATE INDEX IF NOT EXISTS round_player ON rounds(player_id);
"""


class Store:
    def __init__(self, path: Path | str | None = None, asset_root: Path = ASSET_ROOT):
        self.path = Path(
            path or os.environ.get("FRUIT_SHIFT_DB_PATH", str(BACKEND_ROOT / "data.db"))
        )
        self.asset_root = asset_root
        self.catalog = json.loads((asset_root / "catalog.json").read_text())
        self.reference_version = self.catalog["reference_version"]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)
            for asset in self.catalog["assets"]:
                connection.execute(
                    """INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET role=excluded.role,
                    reference_label=excluded.reference_label, reference_version=excluded.reference_version,
                    metadata=excluded.metadata""",
                    (
                        asset["id"],
                        asset["source_id"],
                        asset["source_photo_id"],
                        asset["fruit_type"],
                        asset["source_label"],
                        asset["role"],
                        asset["reference_label"],
                        asset["reference_version"],
                        json.dumps(asset),
                    ),
                )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
