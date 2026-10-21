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
    print("missing or unreadable input", file=sys.stderr)
    sys.exit(2)
try:
    text = raw.decode("utf-8")
except UnicodeDecodeError:
    print("input is not valid UTF-8", file=sys.stderr)
    sys.exit(2)
try:
    rows = list(csv.reader(text.splitlines(True)))
except csv.Error:
    print("input is not parseable CSV", file=sys.stderr)
    sys.exit(2)
if not rows or rows[0] != ["id", "name", "amount"]:
    print("header must be exactly id,name,amount", file=sys.stderr)
    sys.exit(2)
writer = csv.writer(sys.stdout, lineterminator="\n")
writer.writerow(["id", "name"])
for row in rows[1:]:
    if len(row) < 2:
        print("row has fewer than two columns", file=sys.stderr)
        sys.exit(2)
    writer.writerow(row[:2])
PYEOF
