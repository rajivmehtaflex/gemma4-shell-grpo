#!/bin/bash
dir="$1"
count=$(find "$dir/." -maxdepth 1 -type f -name '*.txt' -printf 'x' | wc -c)
printf '%d\n' "$count"
