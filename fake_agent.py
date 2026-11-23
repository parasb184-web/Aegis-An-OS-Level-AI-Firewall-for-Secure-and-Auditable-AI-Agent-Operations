import os
import sys
import time

HOME = os.path.expanduser("~")
DEMO = os.path.join(HOME, "demo")


def read_file(path):
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
    print("scenario: normal work")
    for name in ["src/app.py", "src/utils.py", "src/app.py"]:
        read_file(os.path.join(DEMO, "project", name))
        time.sleep(1.5)


def credentials():
    print("scenario: credential access")
    read_file(os.path.join(DEMO, "project", "src/app.py"))
    time.sleep(1)
    read_file(os.path.join(DEMO, ".ssh", "id_rsa"))


def massread():
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


def wander():
    print("scenario: wandering across folders")
    folders = [os.path.join(DEMO, "notes", f) for f in ["a", "b", "c", "d", "e"]]
    for i in range(3):
        for folder in folders:
            read_file(os.path.join(folder, sorted(os.listdir(folder))[i]))
            time.sleep(0.3)


scenarios = {"normal": normal, "credentials": credentials, "massread": massread,
             "wander": wander}

if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
    print("usage: python3 fake_agent.py [normal|credentials|massread|wander]")
    sys.exit(1)

scenarios[sys.argv[1]]()
print("done")
