#!/bin/bash
src="$1"
dst="$(pwd)/$2"
cd "$src" || exit 1
find . -type f -name '*.log' -print0 |
while IFS= read -r -d '' f; do
    rel="${f#./}"
    mkdir -p "$dst/$(dirname "$rel")"
    cp -p -- "$f" "$dst/$rel"
done
