#!/bin/bash
# Two sessions insert into the live actions table at the same time.
# Both ROLLBACK, so no data is left behind.
export PGPASSWORD=aegis
Q="psql -U aegis -d aegis -h localhost -X -q"
t0=$(date +%s.%N)
since() { echo "$(date +%s.%N) - $t0" | bc | cut -c1-5; }

(
  $Q <<'EOF' > /dev/null
BEGIN;
INSERT INTO actions (pid, path, verdict) VALUES (1, '/t/A', 'allow');
SELECT pg_sleep(3);
ROLLBACK;
EOF
  echo "[A] t=$(since)s  inserted 'allow', held 3 s, rolled back"
) &

sleep 0.5

(
  $Q <<'EOF'
\timing on
BEGIN;
\echo [B] insert 'block' (different counter row):
INSERT INTO actions (pid, path, verdict) VALUES (2, '/t/B1', 'block');
\echo [B] insert 'allow' (same counter row A has locked):
INSERT INTO actions (pid, path, verdict) VALUES (2, '/t/B2', 'allow');
ROLLBACK;
EOF
  echo "[B] t=$(since)s  finished"
) &

sleep 1.5
echo "== at t=$(since)s, sessions waiting on a lock:"
$Q -c "SELECT a.wait_event_type, a.wait_event, l.locktype, l.mode, l.granted,
              left(a.query, 70) AS query
       FROM pg_stat_activity a JOIN pg_locks l ON l.pid = a.pid
       WHERE NOT l.granted"
wait
echo "== counts afterwards (unchanged, both rolled back):"
$Q -c "SELECT verdict, n FROM verdict_counts ORDER BY verdict"
