#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
count=$(find "$1" -type f -empty -printf 'x' | wc -c)
printf '%d\n' "$count"
find "$1" -type f -empty -delete
