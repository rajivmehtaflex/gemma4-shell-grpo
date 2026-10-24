#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
cd "$1" || exit 2
find . -type f -printf '%P\0' | LC_ALL=C sort -z | while IFS= read -r -d '' rel; do
    h=$(sha256sum -- "$rel")
    h=${h%%[[:space:]]*}
    printf '%s %s\n' "$h" "$rel"
done
exit 0
