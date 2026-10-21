#!/bin/bash
dir="$1"
count=$(find "$dir/." -maxdepth 1 -type f -name '*.txt' | wc -l)
printf '%d\n' "$count"
