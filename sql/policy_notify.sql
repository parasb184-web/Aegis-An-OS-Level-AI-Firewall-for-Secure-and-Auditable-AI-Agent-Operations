-- Tell listeners when the policy rules change, so a running daemon could
-- reload them instead of needing a restart.
--
-- Run once on an existing database (a fresh one gets this from schema.sql):
--   PGPASSWORD=aegis psql -U aegis -d aegis -h localhost -f sql/policy_notify.sql
-- Then watch it with: python3 sql/listen_demo.py

-- FOR EACH STATEMENT, not FOR EACH ROW: a listener only needs to know
-- that something changed, then it reloads everything. NOTIFY is only
-- delivered when the transaction commits, and identical notifications in
-- one transaction are merged, so a rolled-back change sends nothing.
CREATE OR REPLACE FUNCTION notify_policies_changed() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('policies_changed', TG_OP);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS policies_notify ON policies;
CREATE TRIGGER policies_notify
    AFTER INSERT OR UPDATE OR DELETE ON policies
    FOR EACH STATEMENT EXECUTE FUNCTION notify_policies_changed();
