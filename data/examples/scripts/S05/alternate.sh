#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <input-file>" >&2
    exit 2
fi
if [ ! -f "$1" ] || [ ! -r "$1" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
declare -A sum
while IFS= read -r line || [ -n "$line" ]; do
    key=${line%%$'\t'*}
    value=${line#*$'\t'}
    if [ -z "$key" ] || [ "$key" = "$line" ]; then
        echo "malformed row" >&2
        exit 2
    fi
    if [[ ! $value =~ ^[0-9]+$ ]]; then
        echo "malformed value" >&2
        exit 2
    fi
    sum["$key"]=$(( ${sum["$key"]:-0} + 10#$value ))
done < "$1"
for k in "${!sum[@]}"; do
    printf '%s\t%d\n' "$k" "${sum[$k]}"
done | LC_ALL=C sort -t "$(printf '\t')" -k1,1
