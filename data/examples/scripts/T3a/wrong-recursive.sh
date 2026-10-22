#!/bin/bash
find "$1" -type f -name '*.htm' -exec bash -c 'mv -- "$1" "${1%.htm}.html"' _ {} \;
exit 0
