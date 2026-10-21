#!/bin/bash
dir="$1"
total=$(find "$dir/." -maxdepth 1 -type f -name '*.txt' -printf '%s\n' \
  | awk '{ s += $1 } END { print s + 0 }')
printf '%d\n' "$total"
