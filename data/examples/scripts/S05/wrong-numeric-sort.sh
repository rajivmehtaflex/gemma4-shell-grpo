#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
awk -F'\t' '{ sum[$1] += $2 } END { for (k in sum) print k "\t" sum[k] }' "$1" \
  | sort -t "$(printf '\t')" -k1,1n
