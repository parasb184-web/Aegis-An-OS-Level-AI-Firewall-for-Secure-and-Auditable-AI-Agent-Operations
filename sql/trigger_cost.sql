-- How much does the verdict_counts trigger cost on inserts?
--
-- Run after sql/generate_dataset.sql and sql/counts_table.sql:
--   psql -U aegis -d aegis -h localhost -X \
--       -f sql/trigger_cost.sql > results/db/task5_sql_raw.txt
--   python3 results/db/scripts/medians.py results/db/task5_sql_raw.txt
--
-- Inserts 10,000 rows in one statement, trigger on vs off, on two tables:
--   live_* : the real actions table (45 rows, pkey + path index)
--   exp_*  : actions_exp, same columns, 2M rows, pkey + ts + path indexes
-- Every run is inside BEGIN ... ROLLBACK, so no rows are kept. "Off" uses
-- DISABLE TRIGGER inside the same transaction, so it is rolled back too.
-- Rounds alternate on/off so slow drift hits both sides equally.
-- Side effect: rolled-back inserts still use up sequence values, so ids in
-- actions will jump. Nothing depends on ids being gap-free.

-- Same trigger as on actions, but counting into the scratch table.
CREATE OR REPLACE FUNCTION count_verdict_exp() RETURNS trigger AS $$
BEGIN
    INSERT INTO verdict_counts_exp (verdict, n) VALUES (NEW.verdict, 1)
    ON CONFLICT (verdict) DO UPDATE SET n = verdict_counts_exp.n + 1;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS actions_exp_count_verdict ON actions_exp;
CREATE TRIGGER actions_exp_count_verdict
    AFTER INSERT ON actions_exp
    FOR EACH ROW EXECUTE FUNCTION count_verdict_exp();

-- 10,000 rows with the same verdict mix as the dataset (90/5/5).
\set rows 'SELECT 0, ''bench'', ''/home/kusha/demo/project/src/f'' || (i % 500) || ''.py'', CASE WHEN i % 20 = 0 THEN ''block'' WHEN i % 20 = 10 THEN ''warn'' ELSE ''allow'' END, ''bench'' FROM generate_series(1, 10000) AS i'

\set run 1
\ir trigger_cost_round.sql
\set run 2
\ir trigger_cost_round.sql
\set run 3
\ir trigger_cost_round.sql
\set run 4
\ir trigger_cost_round.sql
\set run 5
\ir trigger_cost_round.sql
\set run 6
\ir trigger_cost_round.sql
