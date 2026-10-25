"""Local, transactional storage of raw judgments and synthetic review pairs."""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

BACKEND_ROOT = Path(__file__).resolve().parents[3]

SCHEMA = """
CREATE TABLE IF NOT EXISTS wavelength_submissions (
 submission_id TEXT PRIMARY KEY,
 kind TEXT NOT NULL CHECK (kind IN ('annotation', 'synthetic_pair')),
 payload TEXT NOT NULL,
 response TEXT NOT NULL,
 received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wavelength_annotations (
 annotation_id TEXT PRIMARY KEY REFERENCES wavelength_submissions(submission_id),
 session_id TEXT NOT NULL,
 review_id TEXT NOT NULL,
 text TEXT NOT NULL,
 category TEXT NOT NULL,
 source TEXT NOT NULL,
 score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
 confidence TEXT NOT NULL CHECK (confidence IN ('sure', 'unsure')),
 elapsed_ms INTEGER NOT NULL,
 reference_score INTEGER NOT NULL,
 reference_note TEXT NOT NULL,
 reference_version TEXT NOT NULL,
 independent INTEGER NOT NULL,
 received_at TEXT NOT NULL,
 axis_id TEXT NOT NULL DEFAULT 'satisfaction'
);
CREATE TABLE IF NOT EXISTS wavelength_synthetic_pairs (
 pair_id TEXT PRIMARY KEY REFERENCES wavelength_submissions(submission_id),
 session_id TEXT NOT NULL,
 text TEXT NOT NULL,
 category TEXT NOT NULL,
 source TEXT NOT NULL,
 intended_score INTEGER NOT NULL CHECK (intended_score BETWEEN 0 AND 100),
 guessed_score INTEGER NOT NULL CHECK (guessed_score BETWEEN 0 AND 100),
 elapsed_ms INTEGER NOT NULL,
 received_at TEXT NOT NULL,
 axis_id TEXT NOT NULL DEFAULT 'satisfaction'
);
CREATE INDEX IF NOT EXISTS wavelength_review_session
 ON wavelength_annotations(review_id, session_id);
"""


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or os.environ.get("WAVELENGTH_DB_PATH", str(BACKEND_ROOT / "wavelength.db")))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)
            # Existing local collections predate emotion dimensions. Preserve
            # their meaning by migrating every old record to satisfaction.
            for table in ("wavelength_annotations", "wavelength_synthetic_pairs"):
                columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
                if "axis_id" not in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN axis_id TEXT NOT NULL DEFAULT 'satisfaction'")
            connection.execute("CREATE INDEX IF NOT EXISTS wavelength_review_session_axis "
                               "ON wavelength_annotations(review_id, session_id, axis_id)")

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
