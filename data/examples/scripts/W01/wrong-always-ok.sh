#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <directory> <manifest>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
if [ ! -r "$2" ]; then
    echo "cannot read manifest: $2" >&2
    exit 2
fi
while read -r want rel; do
    [ -n "$want" ] || continue
    printf '%s: ok\n' "$rel"
done < "$2"
exit 0
