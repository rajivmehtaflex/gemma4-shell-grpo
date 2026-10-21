#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
find "$1" -type f -name '*.log' -printf '%P\n' | head -n 1
