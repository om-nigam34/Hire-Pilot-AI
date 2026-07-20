import sqlite3
import json
import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "instance" / "hirepilot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT NOT NULL,
    jd_title          TEXT NOT NULL,
    resume_text       TEXT NOT NULL,
    jd_text           TEXT NOT NULL,
    similarity_score  REAL NOT NULL,
    evaluation_json   TEXT NOT NULL,
    generation_json   TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    # Create the sessions table if it doesn't exist yet. Safe to call every app startup.
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def save_session(resume_text: str, jd_text: str, similarity_score: float,
                  evaluation: dict, generation: dict) -> int:
    # Persist one completed analysis run. Returns the new row's id.
    jd_title = _derive_jd_title(jd_text)
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions
                (created_at, jd_title, resume_text, jd_text,
                 similarity_score, evaluation_json, generation_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.datetime.now().isoformat(timespec="seconds"),
                jd_title,
                resume_text,
                jd_text,
                similarity_score,
                json.dumps(evaluation),
                json.dumps(generation),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_sessions(limit: int = 20) -> list[dict]:
    # Return recent sessions, most recent first, WITHOUT the full text
    # fields (keeps the history list endpoint lightweight).
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, jd_title, similarity_score
            FROM sessions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_session(session_id: int) -> dict | None:
    # Return the full record for one session, or None if it doesn't exist.
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None

        record = dict(row)
        record["evaluation"] = json.loads(record.pop("evaluation_json"))
        record["generation"] = json.loads(record.pop("generation_json"))
        return record


def _derive_jd_title(jd_text: str, max_len: int = 60) -> str:
    # Use the first non-empty line of the JD as a human-readable label for
    # the history list.
    for line in jd_text.splitlines():
        line = line.strip()
        if line:
            return line[:max_len] + ("..." if len(line) > max_len else "")
    return "Untitled job description"