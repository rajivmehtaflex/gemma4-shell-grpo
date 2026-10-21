#!/bin/bash
src=$1
dst=$2
for f in $src/*; do
    cp $f "$dst"
done
