#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
awk '$0 != "" { if (!seen) { first = $0; seen = 1 } last = $0 } END { if (seen) printf "%s\t%s\n", first, last }' "$1"
