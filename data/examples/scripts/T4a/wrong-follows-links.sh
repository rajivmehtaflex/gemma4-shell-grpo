#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
cd "$1" || exit 2
find -L . -type f -empty -printf '%P\n' -delete | LC_ALL=C sort
exit 0
