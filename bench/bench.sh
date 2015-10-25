#!/bin/bash

GITTAGS=${@:-v1.5.1 v1.6 master}
SUITES=$(ls $PWD/suites/*.py)
RESULTS="results.yaml"

\rm -f ${RESULTS}

for tag in $GITTAGS
do

    # Checkout
    git checkout -q $tag

    # Run
    echo "${tag}:"
    for suite in $SUITES
    do
        PYTHONPATH=.:${PYTHONPATH} python ${suite} $tag || exit 1
    done

done

# Compare them
echo
./UnitBench.py list $GITTAGS
