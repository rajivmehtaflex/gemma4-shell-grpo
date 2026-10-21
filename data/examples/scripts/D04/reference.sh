#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <source-dir> <dest-dir>" >&2
    exit 2
fi
if [ ! -d "$1" ] || [ ! -d "$2" ]; then
    echo "invalid source or destination" >&2
    exit 2
fi
shopt -s nullglob dotglob
status=0
for f in "$1"/*; do
    if [ -f "$f" ] && [ ! -L "$f" ]; then
        cp -p -- "$f" "$2/" || status=1
    fi
done
exit $status
