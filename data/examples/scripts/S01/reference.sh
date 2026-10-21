#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -r "$1" ] || [ ! -x "$1" ]; then
    echo "not a readable directory: $1" >&2
    exit 2
fi
count=$(find "$1/." -maxdepth 1 -type f -name '*.txt' -printf 'x' | wc -c)
printf '%d\n' "$count"
