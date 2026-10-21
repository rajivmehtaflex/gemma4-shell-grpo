#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <source-dir> <dest-dir>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "source is not a directory" >&2
    exit 2
fi
if [ ! -d "$2" ] || [ -n "$(ls -A "$2")" ]; then
    echo "destination must be an empty directory" >&2
    exit 2
fi
find "$1" -maxdepth 1 -type f -exec cp -p -t "$2" -- {} +
