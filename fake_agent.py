"""Aegis Demo Agent Simulation.

Simulates agent filesystem activity across three distinct operational profiles:
  1. normal:      Standard developer activity within authorized workspace.
  2. credentials: Malicious attempt to read private SSH keys / cloud secrets.
  3. massread:    Rapid bulk exfiltration attempt across multiple directories.
"""

import os
import sys
import time
from typing import Callable, Dict

HOME: str = os.path.expanduser("~")
DEMO: str = os.path.join(HOME, "demo")


def read_file(path: str) -> None:
    """Attempt to open and read a target file, handling permission verdicts."""
    try:
        with open(path) as f:
            f.read()
        print("  read    %s" % path)
    except PermissionError:
        print("  BLOCKED %s" % path)
    except OSError as e:
        print("  failed  %s (%s)" % (path, e))


def normal() -> None:
    """Execute benign developer agent workflow reading workspace source files."""
    print("scenario: normal work")
    for name in ["src/app.py", "src/utils.py", "src/app.py"]:
        read_file(os.path.join(DEMO, "project", name))
        time.sleep(1.5)


def credentials() -> None:
    """Execute credential access scenario targeting private SSH keys."""
    print("scenario: credential access")
    read_file(os.path.join(DEMO, "project", "src/app.py"))
    time.sleep(1)
    read_file(os.path.join(DEMO, ".ssh", "id_rsa"))


def massread() -> None:
    """Execute high-velocity multi-directory scan to trigger risk rate-limits."""
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


scenarios: Dict[str, Callable[[], None]] = {
    "normal": normal,
    "credentials": credentials,
    "massread": massread,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
        print("usage: python3 fake_agent.py [normal|credentials|massread]")
        sys.exit(1)

    scenarios[sys.argv[1]]()
    print("done")
