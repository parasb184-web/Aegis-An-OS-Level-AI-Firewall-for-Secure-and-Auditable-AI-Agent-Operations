#!/usr/bin/env bash
# Aegis Agent Launcher
#
# Registers the shell's PID in the Aegis roots file so daemon.py recognises this
# process and its children as a supervised agent tree.
set -e

ROOTS="${AEGIS_ROOTS:-/tmp/aegis_roots}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -ne 1 ]; then
    echo "Usage: $0 [normal|credentials|massread]"
    echo ""
    echo "Available Scenarios:"
    echo "  normal       Standard developer operations within workspace (expected: ALLOW)"
    echo "  credentials  Attempted access to sensitive SSH keys (expected: BLOCK)"
    echo "  massread     Rapid bulk directory traversal (expected: BLOCK by rate-limit)"
    exit 1
fi

SCENARIO="$1"
case "$SCENARIO" in
    normal|credentials|massread)
        ;;
    *)
        echo "Error: Unknown scenario '$SCENARIO'"
        echo "Valid choices are: normal, credentials, massread"
        exit 1
        ;;
esac

# Register process ID with Aegis supervision registry
echo $$ >> "$ROOTS"

# Execute agent simulation script in project directory
cd "$SCRIPT_DIR"
exec python3 fake_agent.py "$SCENARIO"
