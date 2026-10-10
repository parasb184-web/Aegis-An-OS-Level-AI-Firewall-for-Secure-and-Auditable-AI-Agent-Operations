-- Helper for trigger_scaling.sql: insert :n rows in one transaction,
-- 6 times, rolled back each time.
\set q 'INSERT INTO actions (pid, process_name, path, verdict, reason) SELECT 0, ''bench'', ''/bench/f'' || i, CASE WHEN i % 20 = 0 THEN ''block'' WHEN i % 20 = 10 THEN ''warn'' ELSE ''allow'' END, ''bench'' FROM generate_series(1, ' :n ') AS i'
\set r 1
\echo === rows_:n run 1
BEGIN; EXPLAIN (ANALYZE) :q; ROLLBACK;
\echo === rows_:n run 2
BEGIN; EXPLAIN (ANALYZE) :q; ROLLBACK;
\echo === rows_:n run 3
BEGIN; EXPLAIN (ANALYZE) :q; ROLLBACK;
\echo === rows_:n run 4
BEGIN; EXPLAIN (ANALYZE) :q; ROLLBACK;
\echo === rows_:n run 5
BEGIN; EXPLAIN (ANALYZE) :q; ROLLBACK;
\echo === rows_:n run 6
BEGIN; EXPLAIN (ANALYZE) :q; ROLLBACK;
