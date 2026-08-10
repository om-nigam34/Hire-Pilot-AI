import sqlite3
import json
import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "instance" / "hirepilot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    created_at        TEXT NOT NULL,
    jd_title          TEXT NOT NULL,
    resume_text       TEXT NOT NULL,
    jd_text           TEXT NOT NULL,
    similarity_score  REAL NOT NULL,
    evaluation_json   TEXT NOT NULL,
    generation_json   TEXT NOT NULL
);
"""


class UsernameTakenError(Exception):
    # Raised when a signup tries a username that's already registered.
    pass


class EmailTakenError(Exception):
    # Raised when a signup tries an email that's already registered.
    pass


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    # Create tables if they don't exist yet.
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


#  Users 

def create_user(username: str, email: str, password_hash: str) -> int:
    # Password is hashed by the caller (utils/auth.py) - this function only
    # ever touches the hash, never the plaintext password.
    with _connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise UsernameTakenError("That username is already taken.")
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise EmailTakenError("An account with that email already exists.")

        cursor = conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, datetime.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return cursor.lastrowid


def get_user_by_username(username: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


#  Sessions --> every read and write is scoped to a user_id 

def save_session(user_id: int, resume_text: str, jd_text: str, similarity_score: float,
                  evaluation: dict, generation: dict) -> int:
    # Persist one completed analysis run for a specific user. Returns the new row's id.
    jd_title = _derive_jd_title(jd_text)
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sessions
                (user_id, created_at, jd_title, resume_text, jd_text,
                 similarity_score, evaluation_json, generation_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
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


def list_sessions(user_id: int, limit: int = 20) -> list[dict]:
    # Recent sessions for ONE user, most recent first. WITHOUT the full text
    # fields (keeps the history list endpoint lightweight).
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, jd_title, similarity_score
            FROM sessions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_session(session_id: int, user_id: int) -> dict | None:
    # user_id is required here, not optional - this is what stops one
    # account from loading another account's session by guessing/incrementing.
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
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