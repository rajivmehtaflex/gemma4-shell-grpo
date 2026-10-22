#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
if [ -s "$1" ]; then
    first=$(head -n 1 -- "$1")
    last=$(tail -n 1 -- "$1")
    printf '%s\t%s\n' "$first" "$last"
fi
exit 0
