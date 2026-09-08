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

-- Starting rules.
INSERT INTO policies (path_pattern, sensitivity, action, note) VALUES
  ('/home/%/.ssh/%',     'high', 'block', 'SSH private keys'),
  ('/home/%/.aws/%',     'high', 'block', 'cloud credentials'),
  ('%/.env',             'high', 'block', 'environment secrets'),
  ('/home/%/.gnupg/%',   'high', 'block', 'GPG keys'),
  ('/home/%/project/%',  'low',  'allow', 'the agent workspace');