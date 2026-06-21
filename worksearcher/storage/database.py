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
    before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.executemany(
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
    after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    return after - before


def get_seen_fingerprints(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT fingerprint FROM jobs").fetchall()
    return {row[0] for row in rows}
