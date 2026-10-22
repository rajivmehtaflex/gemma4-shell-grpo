#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
cd "$1" || exit 2
list=$(find . -type f -empty -printf '%P\n' | LC_ALL=C sort)
if [ -n "$list" ]; then
    printf '%s\n' "$list"
    while IFS= read -r rel; do
        rm -- "./$rel"
    done <<< "$list"
fi
exit 0
