#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -r "$1" ] || [ ! -x "$1" ]; then
    echo "not a readable directory: $1" >&2
    exit 2
fi
shopt -s nullglob
count=0
for f in "$1"/*; do
    [ -f "$f" ] && [ ! -L "$f" ] || continue
    case "${f##*/}" in
        *.txt) count=$((count + 1)) ;;
    esac
done
printf '%d\n' "$count"
