
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
