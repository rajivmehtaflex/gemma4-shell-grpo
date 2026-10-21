#!/bin/bash
for f in $1/*; do
    cp $f "$2"
done
