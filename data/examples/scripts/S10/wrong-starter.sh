#!/bin/bash
count=$(grep "ERROR" "$1" | wc -l)
echo "$count"
