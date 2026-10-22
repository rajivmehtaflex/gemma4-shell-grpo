#!/bin/bash
shopt -s nullglob
for f in "$1"/*.conf; do
    [ -f "$f" ] && [ ! -L "$f" ] && mv -- "$f" "${f}.bak"
done
exit 0
