#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
declare -A seen
while IFS= read -r line || [ -n "$line" ]; do
    if [ -z "${seen[$line]+x}" ]; then
        seen[$line]=1
        printf '%s\n' "$line"
    fi
done < "$1"
