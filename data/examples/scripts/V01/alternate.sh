#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <source-dir> <dest-dir>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -d "$2" ]; then
    echo "invalid source or destination" >&2
    exit 2
fi
dupes=$(find "$1" -type f -name '*.log' -printf '%f\n' | sort | uniq -d)
if [ -n "$dupes" ]; then
    echo "basename collision:" >&2
    printf '%s\n' "$dupes" >&2
    exit 2
fi
find "$1" -type f -name '*.log' -exec cp -p -t "$2" -- {} +
