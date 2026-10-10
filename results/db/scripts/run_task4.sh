#!/bin/bash
# Regenerate the dataset, then run the experiment while logging memory.
cd ~/aegis
# Needs the database password in PGPASSWORD or ~/.pgpass.
P="psql -U aegis -d aegis -h localhost -X"
$P -f sql/generate_dataset.sql > results/db/task4_generate.txt 2>&1
vmstat -S M 1 > results/db/task4_vmstat.txt &
vm=$!
$P -f sql/index_experiment_v2.sql > results/db/task4_explain_raw.txt 2>&1
kill $vm
python3 results/db/scripts/medians.py results/db/task4_explain_raw.txt > results/db/task4_medians.txt
cat results/db/task4_medians.txt
