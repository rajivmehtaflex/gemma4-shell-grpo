#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -r "$1" ] || [ ! -x "$1" ]; then
    echo "not a readable directory: $1" >&2
    exit 2
fi
cd "$1" || exit 2
find . -name '*.csv' -type f -printf '%P\0' | LC_ALL=C sort -z
