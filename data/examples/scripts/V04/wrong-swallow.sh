#!/bin/bash
lines=$(sed -n '2,4p' -- "$1" 2>/dev/null)
printf '%s\n' "$lines"
