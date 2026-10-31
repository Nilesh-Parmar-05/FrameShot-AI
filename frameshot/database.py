"""SQLite persistence: schema, thread-local connections, transactions.

Two rules keep this safe with the threading model in ``architecture.md`` §9:

1. one connection per thread (``sqlite3`` objects are not thread-safe);
2. WAL journaling plus a busy timeout so a writer on one thread does not
   fail a reader on another.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- architecture.md §7.1 — pre-populated from SUBTLEXus (§ tasks 1.17)
CREATE TABLE IF NOT EXISTS word_frequency (
    word      TEXT PRIMARY KEY,
    rank      INTEGER NOT NULL,
    frequency REAL NOT NULL,
    pos       TEXT
);
CREATE INDEX IF NOT EXISTS idx_word_frequency_rank ON word_frequency(rank);

-- architecture.md §7.2 — materialised WordNet lookups
CREATE TABLE IF NOT EXISTS dictionary (
    word          TEXT PRIMARY KEY,
    definition    TEXT NOT NULL,
    synonyms      TEXT,
    pronunciation TEXT,
    pos           TEXT
);

-- architecture.md §7.3
CREATE TABLE IF NOT EXISTS vocabulary_journal (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    word         TEXT NOT NULL,
    definition   TEXT,
    context      TEXT,
    movie_title  TEXT,
    timestamp_ms INTEGER,
    saved_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_vocabulary_journal_word ON vocabulary_journal(word);

-- architecture.md §7.4
CREATE TABLE IF NOT EXISTS online_cache (
    cache_key     TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    response_json TEXT NOT NULL,
    fetched_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ttl_seconds   INTEGER NOT NULL DEFAULT 604800
);
CREATE INDEX IF NOT EXISTS idx_online_cache_source ON online_cache(source);
"""


class Database:
    """Handle for the application database file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self.initialize()

    # ------------------------------------------------------------ plumbing

    @property
    def connection(self) -> sqlite3.Connection:
        """This thread's connection, created on first use."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a unit of work atomically; rolls back on any exception."""
        conn = self.connection
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    # ------------------------------------------------------------ lifecycle

    def initialize(self) -> None:
        """Create the schema (idempotent) and record the schema version."""
        conn = self.connection
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()

    @property
    def schema_version(self) -> int | None:
        row = self.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"]) if row is not None else None

    def table_names(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return sorted(row["name"] for row in rows)

    def close(self) -> None:
        """Close this thread's connection. Other threads must close their own."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
