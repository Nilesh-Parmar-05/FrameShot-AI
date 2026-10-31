"""Create or migrate the application database.

python scripts/init_db.py [--config config.yaml]
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
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    try:
        config = AppConfig.load(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    database = Database(config.paths.database)
    try:
        print(f"database: {database.path}")
        print(f"schema version: {database.schema_version}")
        print(f"tables: {', '.join(database.table_names())}")
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
