import sqlite3
import logging
from pathlib import Path

from worksearcher.core.models import Job, JobSource

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
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            notified    INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Migrate existing DBs that predate the notified column
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN notified INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists
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


def get_unnotified_jobs(conn: sqlite3.Connection) -> list[Job]:
    rows = conn.execute(
        "SELECT title, company, location, url, source, is_remote, description "
        "FROM jobs WHERE notified=0"
    ).fetchall()
    jobs = []
    for row in rows:
        try:
            jobs.append(Job(
                title=row[0],
                company=row[1],
                location=row[2],
                url=row[3],
                source=JobSource(row[4]),
                is_remote=bool(row[5]),
                description=row[6] or "",
            ))
        except Exception:
            continue
    return jobs


def mark_jobs_notified(fingerprints: list[str], conn: sqlite3.Connection) -> None:
    if not fingerprints:
        return
    placeholders = ",".join("?" * len(fingerprints))
    conn.execute(
        f"UPDATE jobs SET notified=1 WHERE fingerprint IN ({placeholders})",
        fingerprints,
    )
    conn.commit()


def get_seen_fingerprints(candidates: list[str], conn: sqlite3.Connection) -> set[str]:
    if not candidates:
        return set()
    placeholders = ",".join("?" * len(candidates))
    rows = conn.execute(
        f"SELECT fingerprint FROM jobs WHERE fingerprint IN ({placeholders})",
        candidates,
    ).fetchall()
    return {row[0] for row in rows}
