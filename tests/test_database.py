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


def test_vocabulary_journal_api_methods(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    try:
        # 1. Save entry
        id1 = db.save_journal_entry(
            word="ephemeral",
            definition="lasting a very short time",
            context="Life is ephemeral.",
            movie_title="Sample Film",
            timestamp_ms=45000,
        )
        assert id1 > 0
        assert db.is_word_saved("ephemeral") is True
        assert db.is_word_saved("EPHEMERAL") is True
        assert db.is_word_saved("unrelated") is False

        # 2. Duplicate word + context updates definition
        id2 = db.save_journal_entry(
            word="ephemeral",
            definition="updated definition",
            context="Life is ephemeral.",
        )
        assert id2 == id1

        # 3. Add second word
        id3 = db.save_journal_entry(
            word="ubiquitous",
            definition="present everywhere",
            context="Smartphones are ubiquitous.",
            movie_title="Tech Doc",
            timestamp_ms=12000,
        )
        assert id3 != id1

        # 4. Search queries
        all_entries = db.get_journal_entries()
        assert len(all_entries) == 2
        assert all_entries[0]["id"] == id3  # newest first

        search_res = db.get_journal_entries(query="ubiquitous")
        assert len(search_res) == 1
        assert search_res[0]["word"] == "ubiquitous"

        search_context = db.get_journal_entries(query="Life is")
        assert len(search_context) == 1
        assert search_context[0]["word"] == "ephemeral"

        # 5. Export to CSV
        csv_path = tmp_path / "journal_export.csv"
        count = db.export_journal_to_csv(csv_path)
        assert count == 2
        assert csv_path.is_file()
        content = csv_path.read_text(encoding="utf-8")
        assert "ephemeral" in content
        assert "ubiquitous" in content
        assert "Sample Film" in content

        # 6. Delete entry
        assert db.delete_journal_entry(id1) is True
        assert db.is_word_saved("ephemeral") is False
        assert len(db.get_journal_entries()) == 1
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
