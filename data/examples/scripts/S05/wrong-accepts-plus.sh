#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
awk -F'\t' '
    NF != 2 || $1 == "" { bad = 1; exit 1 }
    {
        v = $2 + 0
        if (v < 0 || v != int(v)) { bad = 1; exit 1 }
        sum[$1] += v
    }
    END {
        if (bad) exit 2
        for (k in sum) print k "\t" sum[k]
    }
' "$1" | LC_ALL=C sort -t "$(printf '\t')" -k1,1
status=${PIPESTATUS[0]}
[ "$status" -ne 0 ] && { echo "malformed row" >&2; exit 2; }
exit 0
