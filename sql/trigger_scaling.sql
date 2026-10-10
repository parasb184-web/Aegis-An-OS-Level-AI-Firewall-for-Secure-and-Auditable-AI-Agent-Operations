-- Does the trigger's cost per row grow with the number of rows inserted
-- in ONE transaction? Each upsert makes a new version of a counter row,
-- and versions made by a transaction that is still open cannot be cleaned
-- up, so later upserts may have to step over more and more old versions.
--
--   psql -U aegis -d aegis -h localhost -X \
--       -f sql/trigger_scaling.sql > results/db/task5_scaling_raw.txt
--   python3 results/db/scripts/medians.py results/db/task5_scaling_raw.txt
--
-- Real actions table, every run rolled back.

\set n 50
\ir trigger_scaling_size.sql
\set n 1000
\ir trigger_scaling_size.sql
\set n 5000
\ir trigger_scaling_size.sql
\set n 10000
\ir trigger_scaling_size.sql
\set n 20000
\ir trigger_scaling_size.sql
