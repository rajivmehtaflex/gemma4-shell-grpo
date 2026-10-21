#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -r "$1" ] || [ ! -x "$1" ]; then
    echo "not a readable directory: $1" >&2
    exit 2
fi
find "$1/." -maxdepth 1 -name '*.txt' ! -type d | wc -l
