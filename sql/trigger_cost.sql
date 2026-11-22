
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
