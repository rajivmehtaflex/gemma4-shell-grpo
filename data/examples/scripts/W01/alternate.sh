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
bad=0
while read -r want rel; do
    [ -n "$want" ] || continue
    if [ ! -f "$1/$rel" ]; then
        printf '%s: missing\n' "$rel"
        bad=$((bad + 1))
    elif [ "$(sha256sum -- "$1/$rel" | cut -d' ' -f1)" = "$want" ]; then
        printf '%s: ok\n' "$rel"
    else
        printf '%s: mismatch\n' "$rel"
        bad=$((bad + 1))
    fi
done < "$2"
if [ "$bad" -eq 0 ]; then
    exit 0
fi
exit 1
