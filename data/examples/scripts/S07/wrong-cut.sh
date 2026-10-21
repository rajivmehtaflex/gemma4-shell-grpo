#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
[ -f "$1" ] && [ -r "$1" ] || exit 2
head -n 1 "$1" | cut -d, -f1,2
tail -n +2 "$1" | cut -d, -f1,2
