\echo == atomicity: insert 3 rows on the live actions table, then ROLLBACK
BEGIN;
INSERT INTO actions (pid, path, verdict) VALUES (1, '/t/a', 'allow'), (1, '/t/b', 'block'), (1, '/t/w', 'warn');
\echo -- inside the transaction
SELECT verdict, n FROM verdict_counts ORDER BY verdict;
ROLLBACK;
\echo -- after ROLLBACK: counter changes are undone with the log rows
SELECT verdict, n FROM verdict_counts ORDER BY verdict;
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict ORDER BY verdict;
