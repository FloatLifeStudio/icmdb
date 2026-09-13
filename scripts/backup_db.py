"""SQLite 数据库备份:VACUUM INTO 生成一致性快照,保留最近 KEEP 份。

用法:/usr/bin/python3 backup_db.py(可挂 cron,每日一次)
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
    src.execute("VACUUM INTO ?", (str(dest),))  # 一致性快照,含 -wal 内容
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
