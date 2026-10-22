#!/bin/bash
shopt -s nullglob
for f in "$1"/*.htm; do
    [ -f "$f" ] && [ ! -L "$f" ] && mv -- "$f" "${f%.htm}.html"
done
exit 0
