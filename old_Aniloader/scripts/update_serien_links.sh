#!/usr/bin/env bash
# update_s_to_links.sh
# Usage:
#   ./update_s_to_links.sh                 # uses default data/AniLoader.db
#   ./update_s_to_links.sh /path/to/db.db  # use custom DB path

set -euo pipefail
DB=${1:-data/AniLoader.db}

if [ ! -f "$DB" ]; then
  echo "Database not found: $DB" >&2
  exit 2
fi

TS=$(date +%Y%m%d%H%M%S)
BACKUP="${DB}.${TS}.bak"
cp "$DB" "$BACKUP"
echo "Backup created: $BACKUP"

SELECT_SQL="SELECT COUNT(*) FROM anime WHERE url LIKE '%/serie/stream/%';"
UPDATE_SQL="UPDATE anime SET url = REPLACE(url, '/serie/stream/', '/serie/') WHERE url LIKE '%/serie/stream/%';"

if command -v sqlite3 >/dev/null 2>&1; then
  before=$(sqlite3 "$DB" "$SELECT_SQL")
  echo "Entries matching before: $before"
  sqlite3 "$DB" "$UPDATE_SQL"
  after=$(sqlite3 "$DB" "$SELECT_SQL")
  echo "Entries matching after: $after"
  echo "Done."
  exit 0
fi

# Fallback to Python if sqlite3 CLI is not available
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  PY=$(command -v python3 2>/dev/null || command -v python)
  echo "Using Python fallback: $PY"
  # write python snippet to temp file to avoid quoting issues
  tmp=$(mktemp /tmp/update_s_to_links.XXXXXX.py)
  cat > "$tmp" <<'PY'
import sqlite3,sys
db=sys.argv[1]
conn=sqlite3.connect(db)
c=conn.cursor()
before=c.execute("SELECT COUNT(*) FROM anime WHERE url LIKE '%/serie/stream/%'").fetchone()[0]
print(before)
c.execute("UPDATE anime SET url = REPLACE(url, '/serie/stream/', '/serie/') WHERE url LIKE '%/serie/stream/%'")
conn.commit()
after=c.execute("SELECT COUNT(*) FROM anime WHERE url LIKE '%/serie/stream/%'").fetchone()[0]
print(after)
conn.close()
PY
  "$PY" "$DB" "$tmp"
  rv=$?
  rm -f "$tmp"
  if [ $rv -ne 0 ]; then
    echo "Python fallback failed with exit code $rv" >&2
    exit $rv
  fi
  exit 0
fi

echo "Neither 'sqlite3' CLI nor Python found in PATH. Install sqlite3 or python to run this script." >&2
exit 3
