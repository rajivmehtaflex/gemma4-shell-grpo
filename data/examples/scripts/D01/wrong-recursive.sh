#!/bin/bash
dir="$1"
find "$dir" -type f -name '*.txt' | wc -l
