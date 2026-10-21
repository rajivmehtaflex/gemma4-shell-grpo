#!/bin/bash
src="$1"
dst="$2"
find "$src" -type f -name '*.log' -print0 |
while IFS= read -r -d '' f; do
    rel="${f#"$src"/}"
    mkdir -p "$(dirname "$dst/$rel")" 2>/dev/null
    cp -p -- "$f" "$dst/$rel" 2>/dev/null
done
exit 0
