#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
shopt -s nullglob
targets=()
for f in "$1"/*.conf; do
    [ -f "$f" ] && [ ! -L "$f" ] || continue
    t="$(dirname "$f")/backup-${f##*/}"
    if [ -e "$t" ]; then
        echo "target already exists: $t" >&2
        exit 2
    fi
    targets+=("$f" "$t")
done
for ((i=0; i<${#targets[@]}; i+=2)); do
    mv -- "${targets[$i]}" "${targets[$((i+1))]}"
done
exit 0
