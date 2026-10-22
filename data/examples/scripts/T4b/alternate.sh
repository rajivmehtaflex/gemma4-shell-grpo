#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
shopt -s nullglob globstar
count=0
for f in "$1"/**/*; do
    [ -f "$f" ] && [ ! -L "$f" ] && [ ! -s "$f" ] && count=$((count + 1))
done
printf '%d\n' "$count"
