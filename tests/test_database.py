"""Tests for the SQLite schema and connection handling."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from frameshot.database import SCHEMA_VERSION, Database

EXPECTED_TABLES = {
    "meta",
    "word_frequency",
    "dictionary",
    "vocabulary_journal",
    "online_cache",
}


def test_initialize_creates_schema(tmp_path: Path) -> None:
    db = Database(tmp_path / "data" / "test.db")
    try:
        assert set(db.table_names()) == EXPECTED_TABLES
        assert db.schema_version == SCHEMA_VERSION
    finally:
        db.close()
    assert (tmp_path / "data" / "test.db").is_file()


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    try:
        db.initialize()
        db.initialize()
        assert db.schema_version == SCHEMA_VERSION
        rows = db.connection.execute("SELECT COUNT(*) AS n FROM meta").fetchone()
        assert rows["n"] == 1
    finally:
        db.close()


def test_vocabulary_journal_insert_and_read(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO vocabulary_journal (word, definition, context, movie_title, timestamp_ms)"
                " VALUES (?, ?, ?, ?, ?)",
                ("resplendent", "shining brightly", "The edifice was resplendent", "Example", 1234),
            )
        row = db.connection.execute("SELECT word, movie_title FROM vocabulary_journal").fetchone()
        assert row["word"] == "resplendent"
        assert row["movie_title"] == "Example"
    finally:
        db.close()


def test_transaction_rolls_back_on_error(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    try:
        with pytest.raises(RuntimeError), db.transaction() as conn:
            conn.execute("INSERT INTO vocabulary_journal (word) VALUES (?)", ("doomed",))
            raise RuntimeError("boom")
        count = db.connection.execute("SELECT COUNT(*) AS n FROM vocabulary_journal").fetchone()[
            "n"
        ]
        assert count == 0
    finally:
        db.close()


def test_wal_mode_is_enabled(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    try:
        mode = db.connection.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        db.close()


def test_connection_is_per_thread(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    main_conn = db.connection
    captured: dict[str, sqlite3.Connection] = {}

    def worker() -> None:
        captured["conn"] = db.connection
        db.close()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    try:
        assert captured["conn"] is not main_conn
    finally:
        db.close()
