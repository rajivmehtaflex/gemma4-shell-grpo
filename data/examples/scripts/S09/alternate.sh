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
found=0
while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        *"$term"*)
            printf '%s\n' "$line"
            found=1
            ;;
    esac
done < "$file"
[ "$found" -eq 1 ] || exit 1
