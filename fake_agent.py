# A script that pretends to be an AI coding agent.
#
# It is NOT a real AI agent. It just opens files in the same patterns a real
# one would, so we can test whether Aegis reacts correctly. Three scenarios,
# run separately so each can be shown on its own during a demo.
#
#   python3 fake_agent.py normal
#   python3 fake_agent.py credentials
#   python3 fake_agent.py massread

import os
import sys
import time

HOME = os.path.expanduser("~")
DEMO = os.path.join(HOME, "demo")


def read_file(path):
    # We do not care what is in the file. We only care that opening it
    # makes the kernel ask Aegis for permission.
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
    # What a well behaved agent does: a few files, inside its own workspace,
    # with pauses in between like it is thinking.
    print("scenario: normal work")
    for name in ["src/app.py", "src/utils.py", "src/app.py"]:
        read_file(os.path.join(DEMO, "project", name))
        time.sleep(1.5)


def credentials():
    # The agent has been misled and goes for something outside its job.
    print("scenario: credential access")
    read_file(os.path.join(DEMO, "project", "src/app.py"))
    time.sleep(1)
    read_file(os.path.join(DEMO, ".ssh", "id_rsa"))


def massread():
    # Enumerating everything it can reach, across several folders. Each open
    # looks fine on its own. Only the rate and the spread give it away.
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