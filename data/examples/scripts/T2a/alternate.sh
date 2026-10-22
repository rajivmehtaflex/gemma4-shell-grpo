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
    case "$line" in
        *$'\t'*) ;;
        *)  echo "every row must have exactly two fields" >&2
            exit 2
            ;;
    esac
    rest=${line#*$'\t'}
    case "$rest" in
        *$'\t'*)
            echo "every row must have exactly two fields" >&2
            exit 2
            ;;
    esac
    printf '%s\n' "$rest"
done < "$1"
