#!/bin/bash
find "$1" -type f -name '*.log' -exec cp -p -- {} "$2/" \;
exit 0
