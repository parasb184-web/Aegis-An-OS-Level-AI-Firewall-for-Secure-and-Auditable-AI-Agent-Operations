"""
fake_agent.py — Demo AI agent for Aegis firewall testing.

Simulates three realistic agent behaviours:
  normal      — reads a small set of project source files (benign).
  credentials — reads a source file then attempts to open an SSH private key.
  massread    — iterates over many note files across several subdirectories.

Usage:
    python3 fake_agent.py [normal|credentials|massread]

The daemon intercepts these file-open calls via fanotify and logs verdicts.
"""

import os
import sys
import time

# Base directory for all demo file operations
HOME = os.path.expanduser("~")
DEMO = os.path.join(HOME, "demo")


def read_file(path):
    """Attempt to open and read a file, printing the outcome."""
    try:
        f = open(path)
        f.read()
        f.close()
        print("  read    %s" % path)
    except PermissionError:
        print("  BLOCKED %s" % path)
    except OSError as e:
        print("  failed  %s (%s)" % (path, e))


def normal():
    """Read a small set of project source files — represents benign agent work."""
    print("scenario: normal work")
    for name in ["src/app.py", "src/utils.py", "src/app.py"]:
        read_file(os.path.join(DEMO, "project", name))
        time.sleep(1.5)


def credentials():
    """Access a project file then attempt to read an SSH key — triggers block policy."""
    print("scenario: credential access")
    read_file(os.path.join(DEMO, "project", "src/app.py"))
    time.sleep(1)
    read_file(os.path.join(DEMO, ".ssh", "id_rsa"))


def massread():
    """Enumerate and read files across many note subdirectories — triggers risk engine."""
    print("scenario: mass file read")
    folders = ["notes", "notes/a", "notes/b", "notes/c", "notes/d", "notes/e"]
    for folder in folders:
        full = os.path.join(DEMO, folder)
        if not os.path.isdir(full):
            continue
        for name in sorted(os.listdir(full)):
            p = os.path.join(full, name)
            if os.path.isfile(p):
                read_file(p)
                time.sleep(0.05)


scenarios = {"normal": normal, "credentials": credentials, "massread": massread}

if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
    print("usage: python3 fake_agent.py [normal|credentials|massread]")
    sys.exit(1)

scenarios[sys.argv[1]]()
print("done")
