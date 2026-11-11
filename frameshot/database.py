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
from typing import Any

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

    # ------------------------------------------------------------ cache methods

    def get_cache(self, key: str) -> str | None:
        """Retrieve cached JSON response if not expired."""
        row = self.connection.execute(
            "SELECT response_json FROM online_cache "
            "WHERE cache_key = ? AND datetime(fetched_at, ttl_seconds || ' seconds') > datetime('now')",
            (key,),
        ).fetchone()
        return str(row["response_json"]) if row is not None else None

    def set_cache(
        self,
        key: str,
        source: str,
        response_json: str,
        ttl_seconds: int = 604800,
    ) -> None:
        """Store or update cached JSON response with TTL."""
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO online_cache (cache_key, source, response_json, fetched_at, ttl_seconds) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) "
                "ON CONFLICT(cache_key) DO UPDATE SET "
                "source = excluded.source, "
                "response_json = excluded.response_json, "
                "fetched_at = CURRENT_TIMESTAMP, "
                "ttl_seconds = excluded.ttl_seconds",
                (key, source, response_json, ttl_seconds),
            )

    def purge_expired_cache(self) -> int:
        """Remove all expired cache entries and return the number of deleted rows."""
        with self.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM online_cache "
                "WHERE datetime(fetched_at, ttl_seconds || ' seconds') <= datetime('now')"
            )
            return cur.rowcount

    # ------------------------------------------------------------ journal methods

    def save_journal_entry(
        self,
        word: str,
        definition: str | None = None,
        context: str | None = None,
        movie_title: str | None = None,
        timestamp_ms: int | None = None,
    ) -> int:
        """Save a vocabulary word entry to the journal.

        If the exact word and context already exist, updates the definition and returns the id.
        """
        clean_word = word.strip().lower()
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM vocabulary_journal WHERE lower(word) = ? AND (context = ? OR (context IS NULL AND ? IS NULL))",
                (clean_word, context, context),
            ).fetchone()
            if existing is not None:
                entry_id = int(existing["id"])
                conn.execute(
                    "UPDATE vocabulary_journal SET definition = coalesce(?, definition), "
                    "movie_title = coalesce(?, movie_title), timestamp_ms = coalesce(?, timestamp_ms) WHERE id = ?",
                    (definition, movie_title, timestamp_ms, entry_id),
                )
                return entry_id

            cur = conn.execute(
                "INSERT INTO vocabulary_journal (word, definition, context, movie_title, timestamp_ms) VALUES (?, ?, ?, ?, ?)",
                (clean_word, definition, context, movie_title, timestamp_ms),
            )
            return int(cur.lastrowid or 0)

    def is_word_saved(self, word: str) -> bool:
        """Check if a word is already in the vocabulary journal."""
        row = self.connection.execute(
            "SELECT 1 FROM vocabulary_journal WHERE lower(word) = ? LIMIT 1",
            (word.strip().lower(),),
        ).fetchone()
        return row is not None

    def get_journal_entries(self, query: str | None = None) -> list[dict[str, Any]]:
        """Retrieve vocabulary journal entries, newest first, optionally filtered by search query."""
        if query and query.strip():
            pattern = f"%{query.strip().lower()}%"
            rows = self.connection.execute(
                "SELECT id, word, definition, context, movie_title, timestamp_ms, saved_at FROM vocabulary_journal "
                "WHERE lower(word) LIKE ? OR lower(definition) LIKE ? OR lower(context) LIKE ? OR lower(movie_title) LIKE ? "
                "ORDER BY id DESC",
                (pattern, pattern, pattern, pattern),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id, word, definition, context, movie_title, timestamp_ms, saved_at FROM vocabulary_journal ORDER BY id DESC"
            ).fetchall()

        return [dict(row) for row in rows]

    def delete_journal_entry(self, entry_id: int) -> bool:
        """Delete a vocabulary journal entry by id."""
        with self.transaction() as conn:
            cur = conn.execute("DELETE FROM vocabulary_journal WHERE id = ?", (entry_id,))
            return cur.rowcount > 0

    def export_journal_to_csv(self, dest_path: str | Path) -> int:
        """Export all journal entries to a standard CSV file. Returns number of rows exported."""
        import csv

        entries = self.get_journal_entries()
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        with dest.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["ID", "Word", "Definition", "Context", "Movie Title", "Timestamp (ms)", "Date Saved"]
            )
            for e in entries:
                writer.writerow([
                    e.get("id"),
                    e.get("word"),
                    e.get("definition") or "",
                    e.get("context") or "",
                    e.get("movie_title") or "",
                    e.get("timestamp_ms") or "",
                    e.get("saved_at") or "",
                ])
        return len(entries)

    def close(self) -> None:
        """Close this thread's connection. Other threads must close their own."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
