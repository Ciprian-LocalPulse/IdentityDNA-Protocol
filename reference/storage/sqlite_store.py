"""
Reference persistence layer — SQLite-backed storage for the two pieces of
state that RFC-0001 requires to survive across sessions:

  1. Subject baselines (enrolled Identity Vector per subject) — used by
     identity-engine/relationship.py for d(IV(t), IV_baseline).
  2. Trust history (accept/step-up/deny outcomes per subject) — used by
     trust-engine/history.py for S_history.

This is a REFERENCE persistence layer: single SQLite file, no
connection pooling, no encryption-at-rest wired in by default (though
RFC-0001 §10 requires raw signals never be stored here — only derived,
non-reversible IV floats and digests are persisted, never raw device/
behavior/context input).

Schema:

    subjects(subject_id TEXT PRIMARY KEY, vector_json TEXT, iv_digest TEXT, identity_vector_id TEXT)
    history(id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id TEXT, accepted INTEGER, recorded_at TEXT)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".identitydna" / "identitydna_demo.db"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


class SQLiteStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        _ensure_parent(self.db_path)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS subjects (
                    subject_id TEXT PRIMARY KEY,
                    identity_vector_id TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    iv_digest TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_subject ON history(subject_id)")

    # --- subjects / baselines ---

    def get_baseline(self, subject_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT identity_vector_id, vector_json, iv_digest FROM subjects WHERE subject_id = ?",
                (subject_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "identity_vector_id": row[0],
            "vector": json.loads(row[1]),
            "iv_digest": row[2],
        }

    def put_baseline(self, subject_id: str, identity_vector_id: str, vector: list[float], iv_digest: str) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO subjects (subject_id, identity_vector_id, vector_json, iv_digest, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subject_id) DO UPDATE SET
                    identity_vector_id = excluded.identity_vector_id,
                    vector_json = excluded.vector_json,
                    iv_digest = excluded.iv_digest,
                    updated_at = excluded.updated_at
            """, (subject_id, identity_vector_id, json.dumps(vector), iv_digest,
                  datetime.now(timezone.utc).isoformat()))

    # --- history ---

    def record_history(self, subject_id: str, accepted: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO history (subject_id, accepted, recorded_at) VALUES (?, ?, ?)",
                (subject_id, 1 if accepted else 0, datetime.now(timezone.utc).isoformat()),
            )

    def get_history(self, subject_id: str, limit: int = 20) -> list[bool]:
        """Returns most-recent-last, matching TrustHistory's deque ordering."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT accepted FROM history WHERE subject_id = ? ORDER BY id DESC LIMIT ?",
                (subject_id, limit),
            ).fetchall()
        return [bool(r[0]) for r in reversed(rows)]

    def reset(self, subject_id: str | None = None) -> None:
        """Demo/testing helper: wipe stored state (RFC-0001 §10.5 deletion
        mechanism, simplified for the reference implementation)."""
        with self._conn() as conn:
            if subject_id:
                conn.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
                conn.execute("DELETE FROM history WHERE subject_id = ?", (subject_id,))
            else:
                conn.execute("DELETE FROM subjects")
                conn.execute("DELETE FROM history")
