-- Remove policy rows that drifted from schema.sql.
--
-- Run with:
--   psql -U aegis -d aegis -h localhost -f sql/cleanup.sql
--
-- At one point a 6th rule '%/.ssh/%' was added by hand to a live database.
-- It is not in schema.sql and rule 1 ('/home/%/.ssh/%') already covers it.
-- We delete by pattern, not by id, because ids differ between machines.
-- Safe to run again: if the row is already gone it deletes 0 rows.

BEGIN;

DELETE FROM policies WHERE path_pattern = '%/.ssh/%';

-- Should list exactly the 5 rules from schema.sql.
SELECT id, path_pattern, sensitivity, action FROM policies ORDER BY id;

COMMIT;
