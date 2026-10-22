#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
while IFS= read -r line || [ -n "$line" ]; do
    f1=${line%%$'\t'*}
    f2=${line#*$'\t'}
    if [ "$f1" = "$line" ] || [ -z "${f2%%$'\t'*}" ]; then
        echo "every row must have exactly two fields" >&2
        exit 2
    fi
    printf '%s\t%s\n' "$f2" "$f1"
done < "$1"
