import sqlite3
import logging
from pathlib import Path

from worksearcher.core.models import Job

logger = logging.getLogger(__name__)

# Absolute path derived from module location — safe regardless of cwd (cron, etc.)
DB_PATH = Path(__file__).resolve().parent.parent.parent / "worksearcher.db"


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            fingerprint TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            company     TEXT NOT NULL,
            location    TEXT,
            url         TEXT NOT NULL,
            source      TEXT NOT NULL,
            is_remote   INTEGER NOT NULL,
            description TEXT,
            posted_at   TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def save_jobs(jobs: list[Job], conn: sqlite3.Connection) -> int:
    if not jobs:
        return 0
    cursor = conn.executemany(
        """
        INSERT OR IGNORE INTO jobs
            (fingerprint, title, company, location, url, source, is_remote, description, posted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                j.fingerprint,
                j.title,
                j.company,
                j.location,
                j.url,
                j.source.value,
                int(j.is_remote),
                j.description,
                j.posted_at.isoformat() if j.posted_at else None,
            )
            for j in jobs
        ],
    )
    conn.commit()
    return cursor.rowcount


def get_seen_fingerprints(candidates: list[str], conn: sqlite3.Connection) -> set[str]:
    if not candidates:
        return set()
    placeholders = ",".join("?" * len(candidates))
    rows = conn.execute(
        f"SELECT fingerprint FROM jobs WHERE fingerprint IN ({placeholders})",
        candidates,
    ).fetchall()
    return {row[0] for row in rows}
