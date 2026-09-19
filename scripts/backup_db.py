"""SQLite database backup: VACUUM INTO produces a consistent snapshot, keeps the most recent KEEP copies

Usage: /usr/bin/python3 backup_db.py (can be scheduled via cron, once a day)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB = Path(__file__).parent / "cmdb.db"
BACKUP_DIR = Path(__file__).parent / "backups"
KEEP = 14


def main() -> None:
    if not DB.exists():
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    dest = BACKUP_DIR / f"cmdb-{datetime.now():%Y%m%d-%H%M}.db"
    src = sqlite3.connect(DB)
    src.execute("VACUUM INTO ?", (str(dest),))  # consistent snapshot, includes -wal content
    src.close()
    cutoff = datetime.now() - timedelta(days=KEEP)
    for f in BACKUP_DIR.glob("cmdb-*.db"):
        try:
            if datetime.strptime(f.stem, "cmdb-%Y%m%d-%H%M") < cutoff:
                f.unlink()
        except ValueError:
            continue


if __name__ == "__main__":
    main()
