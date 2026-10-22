#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
count=0
walk() {
    local entry
    for entry in "$1"/*; do
        [ -e "$entry" ] || continue
        if [ -L "$entry" ]; then
            continue
        elif [ -d "$entry" ]; then
            walk "$entry"
        elif [ -f "$entry" ] && [ ! -s "$entry" ]; then
            count=$((count + 1))
        fi
    done
}
walk "$1"
printf '%d\n' "$count"
