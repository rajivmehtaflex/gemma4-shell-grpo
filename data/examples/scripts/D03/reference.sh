#!/bin/bash
awk -F'\t' '{ sum[$1] += $2 } END { for (k in sum) print k "\t" sum[k] }' "$1" \
  | LC_ALL=C sort -t "$(printf '\t')" -k1,1
