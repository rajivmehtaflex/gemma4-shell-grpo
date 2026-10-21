#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <source-dir> <dest-dir>" >&2
    exit 2
fi
src="$1"
dst="$2"
if [ ! -d "$src" ]; then
    echo "source is not a directory" >&2
    exit 2
fi
if [ ! -d "$dst" ] || [ -n "$(ls -A "$dst")" ]; then
    echo "destination must be an empty directory" >&2
    exit 2
fi
src_abs=$(cd "$src" && pwd) || exit 2
dst_abs=$(cd "$dst" && pwd) || exit 2
inside() {
    case "$2/" in
        "$1"/*) return 0 ;;
        *) return 1 ;;
    esac
}
if [ "$dst_abs" = "$src_abs" ] || inside "$src_abs" "$dst_abs"; then
    echo "destination inside or equal to source" >&2
    exit 2
fi
find "$src_abs" -type f -name '*.log' -print0 |
while IFS= read -r -d '' f; do
    rel="${f#"$src_abs"/}"
    mkdir -p "$dst_abs/$(dirname "$rel")"
    cp -p -- "$f" "$dst_abs/$rel"
done
exit 0
