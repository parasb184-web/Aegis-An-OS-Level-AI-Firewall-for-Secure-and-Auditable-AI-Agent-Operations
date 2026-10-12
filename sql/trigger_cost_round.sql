-- One round of sql/trigger_cost.sql: each of the four cases once.

\echo === live_trigger_on run :run
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO actions (pid, process_name, path, verdict, reason) :rows;
ROLLBACK;

\echo === live_trigger_off run :run
BEGIN;
ALTER TABLE actions DISABLE TRIGGER actions_count_verdict;
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO actions (pid, process_name, path, verdict, reason) :rows;
ROLLBACK;

\echo === exp_trigger_on run :run
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO actions_exp (pid, process_name, path, verdict, reason) :rows;
ROLLBACK;

\echo === exp_trigger_off run :run
BEGIN;
ALTER TABLE actions_exp DISABLE TRIGGER actions_exp_count_verdict;
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO actions_exp (pid, process_name, path, verdict, reason) :rows;
ROLLBACK;
