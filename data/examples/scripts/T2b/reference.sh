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
    NF != 2 { bad = 1; exit 1 }
    { print $2 "\t" $1 }
' "$1"
status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ]; then
    echo "every row must have exactly two fields" >&2
    exit 2
fi
