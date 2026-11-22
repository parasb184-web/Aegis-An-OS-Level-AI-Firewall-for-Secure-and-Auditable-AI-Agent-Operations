
\timing on

SELECT count(*) AS rows_before FROM actions;

INSERT INTO actions (ts, pid, process_name, path, operation, verdict, reason)
SELECT
    now() - (i || ' seconds')::interval,
    (i % 5000) + 1000,
    CASE WHEN i % 3 = 0 THEN 'python3'
         WHEN i % 3 = 1 THEN 'cat'
         ELSE 'bash' END,
    '/home/acerparas/demo/notes/dir' || (i % 200) || '/file' || (i % 900) || '.txt',
    'open',
    CASE WHEN i % 20 = 0 THEN 'block' ELSE 'allow' END,
    CASE WHEN i % 20 = 0 THEN 'risk 70: burst read' ELSE 'no rule' END
FROM generate_series(1, 2000000) AS i;

SELECT count(*) AS rows_after FROM actions;

ANALYZE actions;

EXPLAIN ANALYZE
SELECT ts, process_name, path, verdict
FROM actions
WHERE ts > now() - interval '10 minutes'
ORDER BY ts DESC
LIMIT 50;

EXPLAIN ANALYZE
SELECT ts, verdict, reason
FROM actions
WHERE path = '/home/acerparas/demo/notes/dir7/file123.txt';

EXPLAIN ANALYZE
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict;