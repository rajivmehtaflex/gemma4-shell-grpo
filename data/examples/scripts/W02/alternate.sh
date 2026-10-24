#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
(
    cd "$1" || exit 2
    collect() {
        local e
        for e in "$1"/*; do
            [ -e "$e" ] || continue
            if [ -d "$e" ]; then
                collect "$e"
            elif [ -f "$e" ]; then
                printf '%s\n' "${e#./}"
            fi
        done
    }
    collect . | LC_ALL=C sort | while IFS= read -r rel; do
        [ -n "$rel" ] && sha256sum -- "$rel"
    done
)
exit 0
