#!/bin/bash
shopt -s nullglob
count=0
for f in "$1"/*; do
    if [ -f "$f" ] && [ ! -L "$f" ]; then
        case "${f##*/}" in
            *.txt) count=$((count + 1)) ;;
        esac
    fi
done
printf '%d\n' "$count"
