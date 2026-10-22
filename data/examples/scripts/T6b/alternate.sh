#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
n=0
while IFS= read -r line || [ -n "$line" ]; do
    if [ -z "$line" ]; then
        printf '\n'
    else
        n=$((n + 1))
        printf '%d:%s\n' "$n" "$line"
    fi
done < "$1"
