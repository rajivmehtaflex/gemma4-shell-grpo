#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
shopt -s nullglob
files=()
for f in "$1"/*.conf; do
    [ -f "$f" ] && [ ! -L "$f" ] && files+=("$f")
done
for f in "${files[@]}"; do
    t="$(dirname "$f")/backup-${f##*/}"
    [ -e "$t" ] && { echo "collision: $t" >&2; exit 2; }
done
for f in "${files[@]}"; do
    command mv -- "$f" "$(dirname "$f")/backup-${f##*/}"
done
exit 0
