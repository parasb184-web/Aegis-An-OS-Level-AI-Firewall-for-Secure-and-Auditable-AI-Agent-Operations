-- Aegis database schema

-- The rules. Which paths are sensitive and what to do about them.
CREATE TABLE policies (
    id            SERIAL PRIMARY KEY,
    path_pattern  TEXT NOT NULL,
    sensitivity   TEXT NOT NULL,
    action        TEXT NOT NULL,
    note          TEXT
);

-- Every decision the daemon makes.
CREATE TABLE actions (
    id             SERIAL PRIMARY KEY,
    ts             TIMESTAMP NOT NULL DEFAULT now(),
    pid            INTEGER NOT NULL,
    process_name   TEXT,
    path           TEXT NOT NULL,
    operation      TEXT NOT NULL DEFAULT 'open',
    verdict        TEXT NOT NULL,
    reason         TEXT,
    parent_action  INTEGER REFERENCES actions(id)
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

-- Starting rules.
INSERT INTO policies (path_pattern, sensitivity, action, note) VALUES
  ('/home/%/.ssh/%',     'high', 'block', 'SSH private keys'),
  ('/home/%/.aws/%',     'high', 'block', 'cloud credentials'),
  ('%/.env',             'high', 'block', 'environment secrets'),
  ('/home/%/.gnupg/%',   'high', 'block', 'GPG keys'),
  ('/home/%/project/%',  'low',  'allow', 'the agent workspace');