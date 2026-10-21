#!/bin/bash
src="$1"
dst="$2"
cp -rL "$src/." "$dst/" 2>/dev/null
exit 0
