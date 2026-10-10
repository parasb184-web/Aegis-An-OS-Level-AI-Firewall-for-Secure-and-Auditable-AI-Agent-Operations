-- Build actions_exp: a scratch copy of the audit log with 2,000,000
-- synthetic rows, for the index and trigger experiments.
--
-- Run with:
--   PGPASSWORD=aegis psql -U aegis -d aegis -h localhost -f sql/generate_dataset.sql
--
-- Why a separate table and not actions itself:
--   * actions now has the verdict_counts trigger; 2M fake rows would fire
--     it 2M times and leave fake totals on the live dashboard.
--   * "before indexes" means dropping indexes, which we do not want to do
--     on the table the daemon writes to.
--
-- Why timestamps relative to now():
--   The old script also used now(), but those rows have aged, so "last 10
--   minutes" now finds nothing. Rows here span the 7 days ending at the
--   moment this script runs (one row every 0.3024 s = 7 days / 2M), so
--   recent-window queries return rows as long as you run them soon after.
--   ids grow with time, like the real log.
--
-- No random(): every column is arithmetic on i, so re-running gives the
-- same rows (only shifted to the new now()).

\timing on

DROP TABLE IF EXISTS verdict_counts_exp;
DROP TABLE IF EXISTS actions_exp;

-- Column for column the same as actions in schema.sql.
CREATE TABLE actions_exp (
    id             SERIAL PRIMARY KEY,
    ts             TIMESTAMP NOT NULL DEFAULT now(),
    pid            INTEGER NOT NULL,
    process_name   TEXT,
    path           TEXT NOT NULL,
    operation      TEXT NOT NULL DEFAULT 'open',
    verdict        TEXT NOT NULL,
    reason         TEXT,
    parent_action  INTEGER REFERENCES actions_exp(id)
);

-- Paths and process names follow the original index_experiment.sql so the
-- shape of the data is the same. Note the path formula only produces 1,800
-- distinct paths (dir and file numbers must agree mod 100), about 1,111
-- rows each. Verdicts: 5% block, 5% warn (Paras's new verdict), 90% allow.
INSERT INTO actions_exp (ts, pid, process_name, path, operation, verdict, reason)
SELECT
    now() - make_interval(secs => (2000000 - i) * 0.3024),
    (i % 5000) + 1000,
    CASE WHEN i % 3 = 0 THEN 'python3'
         WHEN i % 3 = 1 THEN 'cat'
         ELSE 'bash' END,
    '/home/acerparas/demo/notes/dir' || (i % 200) || '/file' || (i % 900) || '.txt',
    'open',
    CASE WHEN i % 20 = 0  THEN 'block'
         WHEN i % 20 = 10 THEN 'warn'
         ELSE 'allow' END,
    CASE WHEN i % 20 = 0  THEN 'risk 70: burst read'
         WHEN i % 20 = 10 THEN 'risk 40: unusual path'
         ELSE 'no rule' END
FROM generate_series(1, 2000000) AS i;

-- The summary table the new /counts reads, seeded from the scratch data.
CREATE TABLE verdict_counts_exp (
    verdict  TEXT PRIMARY KEY,
    n        BIGINT NOT NULL DEFAULT 0
);
INSERT INTO verdict_counts_exp (verdict, n)
SELECT verdict, COUNT(*) FROM actions_exp GROUP BY verdict;

VACUUM ANALYZE actions_exp;
VACUUM ANALYZE verdict_counts_exp;

SELECT COUNT(*) AS n_rows, MIN(ts) AS oldest, MAX(ts) AS newest,
       COUNT(DISTINCT path) AS distinct_paths
FROM actions_exp;
SELECT verdict, n FROM verdict_counts_exp ORDER BY verdict;
SELECT pg_size_pretty(pg_relation_size('actions_exp')) AS table_size;
