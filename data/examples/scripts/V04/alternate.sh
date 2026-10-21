#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
awk 'NR >= 2 && NR <= 4 { print }' "$1"
