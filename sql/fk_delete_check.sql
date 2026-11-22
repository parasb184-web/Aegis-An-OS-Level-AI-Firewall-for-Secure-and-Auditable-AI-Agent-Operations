

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
