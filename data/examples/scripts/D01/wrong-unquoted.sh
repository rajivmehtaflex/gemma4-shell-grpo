#!/bin/bash
dir="$1"
count=0
for f in $(ls "$dir"); do
    case $f in
        *.txt) count=$((count + 1)) ;;
    esac
done
echo "$count"
