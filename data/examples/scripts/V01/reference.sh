#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <source-dir> <dest-dir>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -d "$2" ]; then
    echo "invalid source or destination" >&2
    exit 2
fi
declare -A seen
files=()
while IFS= read -r -d '' f; do
    base="${f##*/}"
    if [ -n "${seen[$base]+x}" ]; then
        echo "basename collision: $base" >&2
        exit 2
    fi
    seen[$base]=1
    files+=("$f")
done < <(find "$1" -type f -name '*.log' -print0)
for f in "${files[@]}"; do
    cp -p -- "$f" "$2/"
done
