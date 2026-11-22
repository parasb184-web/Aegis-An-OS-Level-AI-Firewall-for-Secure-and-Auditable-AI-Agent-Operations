

BEGIN;

LOCK TABLE actions IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS verdict_counts (
    verdict  TEXT PRIMARY KEY,
    n        BIGINT NOT NULL DEFAULT 0
);

TRUNCATE verdict_counts;

INSERT INTO verdict_counts (verdict, n)
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict;

INSERT INTO verdict_counts (verdict, n) VALUES
  ('allow', 0), ('block', 0), ('warn', 0)
ON CONFLICT (verdict) DO NOTHING;

CREATE OR REPLACE FUNCTION count_verdict() RETURNS trigger AS $$
BEGIN
    INSERT INTO verdict_counts (verdict, n) VALUES (NEW.verdict, 1)
    ON CONFLICT (verdict) DO UPDATE SET n = verdict_counts.n + 1;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS actions_count_verdict ON actions;
CREATE TRIGGER actions_count_verdict
    AFTER INSERT ON actions
    FOR EACH ROW EXECUTE FUNCTION count_verdict();

COMMIT;

SELECT verdict, n FROM verdict_counts ORDER BY verdict;
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict ORDER BY verdict;
