#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
shopt -s nullglob globstar
best_size=-1
best=""
for f in "$1"/**/*.log; do
    [ -f "$f" ] && [ ! -L "$f" ] || continue
    rel="${f#"$1"/}"
    size=$(stat -c %s -- "$f")
    if [ "$size" -gt "$best_size" ] || { [ "$size" -eq "$best_size" ] && [[ "$rel" < "$best" ]]; }; then
        best_size=$size
        best="$rel"
    fi
done
[ -n "$best" ] && printf '%s\n' "$best"
exit 0
