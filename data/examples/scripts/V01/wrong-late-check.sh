#!/bin/bash
declare -A seen
find "$1" -type f -name '*.log' -print0 |
while IFS= read -r -d '' f; do
    base="${f##*/}"
    if [ -n "${seen[$base]+x}" ]; then
        echo "basename collision: $base" >&2
        exit 3
    fi
    seen[$base]=1
    cp -p -- "$f" "$2/"
done
