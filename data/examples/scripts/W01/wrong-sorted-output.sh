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
status=0
while read -r want rel; do
    [ -n "$want" ] || continue
    if [ ! -f "$1/$rel" ]; then
        printf '%s: missing\n' "$rel"
        status=1
    elif [ "$(sha256sum -- "$1/$rel" | cut -d' ' -f1)" = "$want" ]; then
        printf '%s: ok\n' "$rel"
    else
        printf '%s: mismatch\n' "$rel"
        status=1
    fi
done < "$2" | LC_ALL=C sort
exit $status
