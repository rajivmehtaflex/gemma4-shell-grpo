#!/bin/bash
set -e
count=$(grep "ERROR" "$1" | wc -l)
echo "$count"
