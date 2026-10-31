"""Build the word-frequency SQLite database from a corpus word list.

Status: stub — task 1.17. Expects a SUBTLEXus-style ``.txt``/``.csv`` word list
(one ``word<sep>frequency`` pair per line) and writes the ``word_frequency``
table defined in architecture.md §7.1.

    python scripts/build_freq_db.py path/to/SUBTLEXus.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from frameshot.config import AppConfig, ConfigError  # noqa: E402
from frameshot.database import Database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="word list file (word + frequency)")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"source file not found: {args.source}", file=sys.stderr)
        return 2

    try:
        config = AppConfig.load(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    database = Database(config.paths.word_freq)
    try:
        print(f"target database: {database.path}")
        print("Not implemented yet (tasks.md 1.17).")
        print("Pending decision from spike 0.6: which corpus, which licence.")
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
