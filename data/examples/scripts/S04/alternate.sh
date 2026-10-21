#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -r "$1" ] || [ ! -x "$1" ]; then
    echo "not a readable directory: $1" >&2
    exit 2
fi
shopt -s globstar nullglob
cd "$1" || exit 2
entries=()
for f in **/*.csv; do
    [ -f "$f" ] && [ ! -L "$f" ] && entries+=("$f")
done
if [ "${#entries[@]}" -gt 0 ]; then
    printf '%s\0' "${entries[@]}" | LC_ALL=C sort -z
fi
