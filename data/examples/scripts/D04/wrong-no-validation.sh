#!/bin/bash
find "$1" -maxdepth 1 -type f -exec cp -p -t "$2/" -- {} +
exit 0
