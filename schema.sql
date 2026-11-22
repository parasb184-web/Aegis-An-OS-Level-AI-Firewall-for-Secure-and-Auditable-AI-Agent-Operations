-- Aegis database schema
-- Apply with: psql -U aegis -d aegis -f schema.sql

-- ---------------------------------------------------------------------------
-- policies: rule table — which file-path patterns are sensitive and what to do
-- ---------------------------------------------------------------------------
CREATE TABLE policies (
    id            SERIAL PRIMARY KEY,
    path_pattern  TEXT NOT NULL,   -- glob pattern matched against accessed paths
    sensitivity   TEXT NOT NULL,   -- 'high' | 'low'
    action        TEXT NOT NULL,   -- 'block' | 'warn' | 'allow'
    note          TEXT             -- human-readable rule label shown in dashboard
);

-- ---------------------------------------------------------------------------
-- actions: audit log — every file-open decision the daemon records
-- ---------------------------------------------------------------------------
CREATE TABLE actions (
    id             SERIAL PRIMARY KEY,
    ts             TIMESTAMP NOT NULL DEFAULT now(),   -- wall-clock time of event
    pid            INTEGER NOT NULL,                   -- process ID of the agent
    process_name   TEXT,                               -- e.g. "python3"
    path           TEXT NOT NULL,                      -- absolute path accessed
    operation      TEXT NOT NULL DEFAULT 'open',       -- currently always 'open'
    verdict        TEXT NOT NULL,                      -- 'allow' | 'warn' | 'block'
    reason         TEXT,                               -- matched rule note or risk reason
    parent_action  INTEGER REFERENCES actions(id)      -- reserved for future chaining
);

-- Running count per verdict, so the dashboard does not scan the whole log.
-- Kept up to date by the trigger below, in the same transaction as each
-- insert, so it can never disagree with actions.
CREATE TABLE verdict_counts (
    verdict  TEXT PRIMARY KEY,
    n        BIGINT NOT NULL DEFAULT 0
);

INSERT INTO verdict_counts (verdict, n) VALUES
  ('allow', 0), ('block', 0), ('warn', 0);

CREATE FUNCTION count_verdict() RETURNS trigger AS $$
BEGIN
    INSERT INTO verdict_counts (verdict, n) VALUES (NEW.verdict, 1)
    ON CONFLICT (verdict) DO UPDATE SET n = verdict_counts.n + 1;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER actions_count_verdict
    AFTER INSERT ON actions
    FOR EACH ROW EXECUTE FUNCTION count_verdict();

-- Tell listeners (sql/listen_demo.py) when the rules change. Sent only on
-- commit, once per statement.
CREATE FUNCTION notify_policies_changed() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('policies_changed', TG_OP);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER policies_notify
    AFTER INSERT OR UPDATE OR DELETE ON policies
    FOR EACH STATEMENT EXECUTE FUNCTION notify_policies_changed();

-- Starting rules.
INSERT INTO policies (path_pattern, sensitivity, action, note) VALUES
  ('/home/%/.ssh/%',     'high', 'block', 'SSH private keys'),
  ('/home/%/.aws/%',     'high', 'block', 'cloud credentials'),
  ('%/.env',             'high', 'block', 'environment secrets'),
  ('/home/%/.gnupg/%',   'high', 'block', 'GPG keys'),
  ('/home/%/project/%',  'low',  'allow', 'the agent workspace');