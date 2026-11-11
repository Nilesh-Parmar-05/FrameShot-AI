"""Build the word-frequency SQLite database from a corpus word list or default source.

Task 1.17 in ``tasks.md``.
Supports importing SUBTLEXus/COCA word frequency files, or seeding from NLTK:

    python scripts/build_freq_db.py --seed-default
    python scripts/build_freq_db.py path/to/SUBTLEXus.txt
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frameshot.config import AppConfig, ConfigError  # noqa: E402
from frameshot.database import Database  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def seed_from_nltk(db: Database) -> int:
    """Populate word_frequency using NLTK Brown corpus."""
    logger.info("Seeding word frequency database from NLTK Brown corpus...")
    try:
        from nltk.corpus import brown

        tokens = brown.words()
    except Exception as exc:
        logger.error("Could not load NLTK Brown corpus: %s", exc)
        return 1

    counts = Counter(token.lower() for token in tokens if token.isalpha())
    total_tokens = sum(counts.values())

    rows: list[tuple[str, int, float, str | None]] = []
    for rank, (word, count) in enumerate(counts.most_common(), start=1):
        freq_per_million = (count / total_tokens) * 1_000_000.0
        rows.append((word, rank, round(freq_per_million, 2), None))

    with db.transaction() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO word_frequency (word, rank, frequency, pos) VALUES (?, ?, ?, ?)",
            rows,
        )

    logger.info("Successfully seeded %d words into %s", len(rows), db.path)
    return 0


def import_word_list(db: Database, file_path: Path) -> int:
    """Import word list from CSV/TSV file (e.g. SUBTLEXus)."""
    logger.info("Importing word frequencies from %s...", file_path)
    rows: list[tuple[str, int, float, str | None]] = []

    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        # Detect delimiter (tab or comma or space)
        sample = f.read(2048)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters="\t, ")
        reader = csv.reader(f, dialect)

        _header = next(reader, None)
        # Attempt to detect columns or assume col 0 is word, col 1 is freq/count
        for idx, line in enumerate(reader, start=1):
            if not line:
                continue
            word = line[0].strip().lower()
            if not word or not word.isalpha():
                continue
            try:
                freq = float(line[1]) if len(line) > 1 else 1.0
            except ValueError:
                freq = 1.0
            rows.append((word, idx, freq, None))

    if not rows:
        logger.error("No valid word frequency entries found in %s", file_path)
        return 1

    with db.transaction() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO word_frequency (word, rank, frequency, pos) VALUES (?, ?, ?, ?)",
            rows,
        )

    logger.info("Successfully imported %d words into %s", len(rows), db.path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, help="word list file (word + frequency)")
    parser.add_argument(
        "--seed-default",
        action="store_true",
        help="seed from NLTK Brown corpus instead of a source file",
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    if not args.seed_default and (args.source is None or not args.source.is_file()):
        parser.print_help()
        print("\nError: Please specify a valid source file or pass --seed-default", file=sys.stderr)
        return 2

    try:
        config = AppConfig.load(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    config.paths.word_freq.parent.mkdir(parents=True, exist_ok=True)
    db = Database(config.paths.word_freq)

    try:
        if args.seed_default:
            return seed_from_nltk(db)
        return import_word_list(db, args.source)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
