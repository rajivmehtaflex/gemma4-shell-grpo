#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory" >&2
    exit 2
fi
shopt -s nullglob
for f in "$1"/*; do
    printf '%s\n' "${f##*/}"
done
exit 0
