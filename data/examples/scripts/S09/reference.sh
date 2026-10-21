#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <term> <input-file>" >&2
    exit 2
fi
term="$1"
file="$2"
case "$term" in
    ""|*'
'*)
        echo "invalid term" >&2
        exit 2
        ;;
esac
if [ ! -f "$file" ] || [ ! -r "$file" ]; then
    echo "missing or unreadable input" >&2
    exit 2
fi
exec grep -F -e "$term" -- "$file"
