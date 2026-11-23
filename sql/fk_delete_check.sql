-- Why is DELETE on the audit log so slow?
--
-- parent_action REFERENCES actions(id). When a row is deleted, PostgreSQL
-- must check that no other row points at it (SELECT ... WHERE
-- parent_action = <deleted id>). There is no index on parent_action, so
-- that check is a full scan of the table, once per deleted row.
--
--   psql -U aegis -d aegis -h localhost -X \
--       -f sql/fk_delete_check.sql > results/db/task5_fk_delete.txt
--
-- Runs on actions_exp (2M rows). Deletes 20 rows, rolled back.

\echo === without an index on parent_action
BEGIN;
EXPLAIN (ANALYZE)
DELETE FROM actions_exp WHERE id IN (SELECT id FROM actions_exp WHERE pid = 0 LIMIT 20);
ROLLBACK;

\echo === with an index on parent_action (index dropped again afterwards)
BEGIN;
CREATE INDEX idx_exp_parent ON actions_exp (parent_action);
EXPLAIN (ANALYZE)
DELETE FROM actions_exp WHERE id IN (SELECT id FROM actions_exp WHERE pid = 0 LIMIT 20);
ROLLBACK;
