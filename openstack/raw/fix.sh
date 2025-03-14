#!/bin/bash

for i in {0..14}; do
    # Find and replace `|0|` with `|i|` in each matching file
    sed -i "s/|0|/|$i|/g" ${i}openstack_*.log
done
