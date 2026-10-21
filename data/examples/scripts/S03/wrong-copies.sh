#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <source-dir> <archive-dir>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "source is not a directory" >&2
    exit 2
fi
if [ ! -d "$2" ]; then
    echo "archive is not a directory" >&2
    exit 2
fi
if [ -n "$(ls -A "$2")" ]; then
    echo "archive is not empty" >&2
    exit 2
fi
src_abs=$(cd "$1" && pwd) || exit 2
arc_abs=$(cd "$2" && pwd) || exit 2
inside() {
    case "$2/" in
        "$1"/*) return 0 ;;
        *) return 1 ;;
    esac
}
if [ "$arc_abs" = "$src_abs" ] || inside "$src_abs" "$arc_abs" || inside "$arc_abs" "$src_abs"; then
    echo "directories overlap" >&2
    exit 2
fi
shopt -s nullglob
for f in "$src_abs"/*.bak; do
    [ -f "$f" ] && [ ! -L "$f" ] && cp -p -- "$f" "$arc_abs/"
done
exit 0
