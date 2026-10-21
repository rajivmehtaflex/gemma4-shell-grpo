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
    NF != 2 || $1 == "" || $2 !~ /^[0-9]+$/ { bad = 1; exit 1 }
    { sum[$1] += $2 }
    END {
        if (bad) exit 2
        for (k in sum) print k "\t" sum[k]
    }
' "$1" | LC_ALL=C sort -t "$(printf '\t')" -k1,1
status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ]; then
    echo "malformed row" >&2
    exit 2
fi
