#!/bin/bash
find "$1" -type f -name '*.txt' -printf '%s\n' \
  | awk '{ s += $1 } END { print s + 0 }'
