#!/bin/bash
src="$1"
dst="$2"
while IFS= read -r -d '' f; do
    rel="${f#"$src"/}"
    mkdir -p "$(dirname "$dst/$rel")"
    cp -p -- "$f" "$dst/$rel"
done < <(find "$src" -type f -name '*.log' -print0)
