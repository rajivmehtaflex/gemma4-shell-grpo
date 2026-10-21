#!/bin/bash
shopt -s nullglob
total=0
for f in "$1"/*.txt; do
    if [ -f "$f" ] && [ ! -L "$f" ]; then
        total=$((total + $(stat -c %s -- "$f")))
    fi
done
printf '%d\n' "$total"
