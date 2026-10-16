#!/usr/bin/env bash
# Finds the Aegis daemon Python process and sends SIGKILL.
# Run this from a tab that is NOT the daemon and NOT the loop.
#
#   bash tests/fp_kill_daemon.sh

set -uo pipefail

pids=$(pgrep -f 'python3 .*daemon.py' || true)
if [ -z "$pids" ]; then
    echo "Daemon is not running. Start it first and do not type in that window."
    exit 1
fi

echo "These PIDs will be killed:"
ps -fp $pids
echo
sudo kill -9 $pids
echo "sent kill -9 to $pids"
