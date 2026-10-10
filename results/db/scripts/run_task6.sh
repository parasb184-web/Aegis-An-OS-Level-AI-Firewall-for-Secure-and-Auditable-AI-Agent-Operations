#!/bin/bash
# End-to-end check of LISTEN/NOTIFY: run the listener, change policies
# from psql, and print what the listener saw. Leaves policies as it found them.
cd ~/aegis
# Needs the database password in PGPASSWORD or ~/.pgpass.
P="psql -U aegis -d aegis -h localhost -X -q"

$P -f sql/policy_notify.sql

# Both the listener and step() append, so their lines interleave in order.
: > /tmp/listen_out.txt
timeout 14 python3 -u sql/listen_demo.py >> /tmp/listen_out.txt 2>&1 &
sleep 2

step() { echo "--- $1"; echo "--- $1" >> /tmp/listen_out.txt; sleep 0.3; }

step "1. INSERT a test rule, then ROLLBACK (expect nothing)"
$P -c "BEGIN" -c "INSERT INTO policies (path_pattern, sensitivity, action, note) VALUES ('/tmp/aegis-notify-test/%', 'low', 'block', 'notify test')" -c "ROLLBACK"
sleep 1
step "2. INSERT the test rule, committed (expect INSERT, 6 rules)"
$P -c "INSERT INTO policies (path_pattern, sensitivity, action, note) VALUES ('/tmp/aegis-notify-test/%', 'low', 'block', 'notify test')"
sleep 1
step "3. three UPDATEs in one transaction (expect one UPDATE: duplicates merge)"
$P -c "BEGIN" -c "UPDATE policies SET note = note WHERE path_pattern = '/tmp/aegis-notify-test/%'" -c "UPDATE policies SET note = note WHERE path_pattern = '/tmp/aegis-notify-test/%'" -c "UPDATE policies SET note = note WHERE path_pattern = '/tmp/aegis-notify-test/%'" -c "COMMIT"
sleep 1
step "4. DELETE the test rule (expect DELETE, back to 5 rules)"
$P -c "DELETE FROM policies WHERE path_pattern = '/tmp/aegis-notify-test/%'"
sleep 1

wait
echo "=== listener output"
cat /tmp/listen_out.txt
echo "=== policies afterwards"
$P -c "SELECT id, path_pattern, action FROM policies ORDER BY id"
