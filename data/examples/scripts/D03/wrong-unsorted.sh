#!/bin/bash
awk -F'\t' '{ sum[$1] += $2 } END { for (k in sum) print k "\t" sum[k] }' "$1"
