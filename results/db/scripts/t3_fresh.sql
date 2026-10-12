\echo == fresh setup from schema.sql inside a throwaway schema, rolled back at the end
BEGIN;
CREATE SCHEMA fresh_test;
SET LOCAL search_path = fresh_test;
\i schema.sql
SELECT * FROM verdict_counts ORDER BY verdict;
INSERT INTO actions (pid, path, verdict) VALUES (1, '/a', 'allow'), (1, '/b', 'block'), (1, '/c', 'block'), (1, '/d', 'warn'), (1, '/e', 'review');
\echo == trigger counts vs real GROUP BY
SELECT verdict, n FROM verdict_counts ORDER BY verdict;
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict ORDER BY verdict;
ROLLBACK;
