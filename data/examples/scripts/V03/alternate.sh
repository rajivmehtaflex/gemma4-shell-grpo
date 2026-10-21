#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 <directory>" >&2
    exit 2
fi
if [ ! -d "$1" ]; then
    echo "not a directory" >&2
    exit 2
fi
find "$1" -maxdepth 1 -mindepth 1 -printf '%f\n'
