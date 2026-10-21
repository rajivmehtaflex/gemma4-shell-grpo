#!/bin/bash
src="$1"
dst="$2"
find "$src" -type f -name '*.log' -exec cp -p -t "$dst" -- {} +
exit 0
