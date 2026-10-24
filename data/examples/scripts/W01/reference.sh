#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "usage: $0 <directory> <manifest>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory: $1" >&2
    exit 2
fi
if [ ! -f "$2" ] || [ ! -r "$2" ]; then
    echo "manifest missing or unreadable: $2" >&2
    exit 2
fi
status=0
while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] || continue
    want=${line%%[[:space:]]*}
    rel=${line#*  }
    if [ ! -f "$1/$rel" ]; then
        printf '%s: missing\n' "$rel"
        status=1
    else
        got=$(sha256sum -- "$1/$rel")
        got=${got%%[[:space:]]*}
        if [ "$got" = "$want" ]; then
            printf '%s: ok\n' "$rel"
        else
            printf '%s: mismatch\n' "$rel"
            status=1
        fi
    fi
done < "$2"
exit $status
