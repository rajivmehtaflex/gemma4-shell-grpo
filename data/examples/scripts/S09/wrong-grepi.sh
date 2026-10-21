#!/bin/bash
term="$1"
file="$2"
grep -F -e "$term" -- "$file"
exit 0
