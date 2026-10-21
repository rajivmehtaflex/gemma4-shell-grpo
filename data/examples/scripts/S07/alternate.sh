#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
exec python3 - "$1" <<'PYEOF'
import csv
import sys

path = sys.argv[1]
try:
    raw = open(path, "rb").read()
except OSError:
    sys.exit(2)
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    sys.exit(2)
try:
    rows = list(csv.reader(text.splitlines(True)))
except csv.Error:
    sys.exit(2)
if not rows or rows[0] != ["id", "name", "amount"]:
    sys.exit(2)
sys.stdout.write("id,name\n")
writer = csv.writer(sys.stdout, lineterminator="\n", quoting=csv.QUOTE_ALL)
for row in rows[1:]:
    if len(row) < 2:
        sys.exit(2)
    writer.writerow(row[:2])
PYEOF
