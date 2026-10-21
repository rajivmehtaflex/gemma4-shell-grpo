#!/bin/bash
declare -A sum
while IFS=$'\t' read -r k v || [ -n "$k" ]; do
    [ -n "$k" ] || continue
    sum["$k"]=$(( ${sum["$k"]:-0} + 10#$v ))
done < "$1"
for k in "${!sum[@]}"; do
    printf '%s\t%d\n' "$k" "${sum[$k]}"
done | LC_ALL=C sort -t "$(printf '\t')" -k1,1
