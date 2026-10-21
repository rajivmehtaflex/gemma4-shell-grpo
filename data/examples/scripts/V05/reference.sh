#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
find "$1" -type f -name '*.log' -printf '%s\t%P\n' \
  | sort -t "$(printf '\t')" -k1,1nr -k2,2 \
  | head -n 1 | cut -f2-
