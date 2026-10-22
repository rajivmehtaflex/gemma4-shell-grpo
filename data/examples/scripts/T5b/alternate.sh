#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
first=""
last=""
while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] || continue
    [ -z "$first" ] && first="$line"
    last="$line"
done < "$1"
if [ -n "$first" ]; then
    printf '%s\t%s\n' "$first" "$last"
fi
exit 0
