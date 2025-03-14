#!/bin/bash

for i in {0..14}; do
    # Find and replace `|0|` with `|i|` in each matching file
    sed -i "s/|0|/|$i|/g" ${i}cuser_unsat_*.log
done

# Concatenate all modified log files into a single file
cat *cuser_unsat_*.log > ../../cuser_unsat.log