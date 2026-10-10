# Scores how risky the agent's recent behaviour looks.
#
# The point: we cannot see a mass file read coming. Each open arrives on its
# own, and on the first one there is nothing to notice. So instead of judging
# one file, we keep a short history and look at the shape of it.

import os
import time


WINDOW = 10.0        # seconds of history we keep
FILE_LIMIT = 15      # opens in the window before it looks like enumeration
FOLDER_LIMIT = 4     # distinct folders before it looks like wandering
BLOCK_AT = 40        # score that gets an operation refused

# One history per supervised root, each a list of (when, which folder).
# The whole agent tree shares a single window on purpose: if every process
# had its own, an agent could stay under the limit by forking a few children
# and splitting the reads between them.
history = {}


def record(root, path):
    now = time.time()
    history.setdefault(root, []).append((now, os.path.dirname(path)))
    trim(now)


def trim(now):
    # Drop opens that have aged out, then drop roots left with nothing, so
    # the dict cannot grow for ever. There are only ever a handful of roots,
    # so sweeping all of them is cheaper than tracking which need attention.
    cutoff = now - WINDOW
    for root in list(history):
        opens = history[root]
        while opens and opens[0][0] < cutoff:
            opens.pop(0)
        if not opens:
            del history[root]


def forget(root):
    # Called by the daemon when a root's process has exited.
    history.pop(root, None)


def score(root):
    # Called after record(), so the current open is already counted.
    opens = history.get(root, [])
    files = len(opens)
    folders = len(set(folder for when, folder in opens))

    points = 0
    reasons = []

    if files > FILE_LIMIT:
        points = points + 40
        reasons.append("%d files in %ds" % (files, int(WINDOW)))

    if folders > FOLDER_LIMIT:
        points = points + 30
        reasons.append("%d folders" % folders)

    return points, ", ".join(reasons)


def is_risky(points):
    return points >= BLOCK_AT


if __name__ == "__main__":
    # Quick check without the daemon: pretend an agent reads 30 files fast.
    for i in range(30):
        p = "/home/test/notes/file%d.txt" % i
        record(1234, p)
        points, why = score(1234)
        if i % 10 == 0 or is_risky(points):
            print("file %-3d score %-4d %s" % (i, points, why))
            if is_risky(points):
                break
