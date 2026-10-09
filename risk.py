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
BLOCK_AT = 40       # score that gets an operation refused

# One entry per open: (when, which folder). Trimmed as it ages out.
history = []


def record(path):
    now = time.time()
    history.append((now, os.path.dirname(path)))

    # Drop anything older than the window. Done here so the list never grows.
    cutoff = now - WINDOW
    while history and history[0][0] < cutoff:
        history.pop(0)


def score(path, path_is_sensitive):
    # Called after record(), so the current open is already counted.
    files = len(history)
    folders = len(set(folder for when, folder in history))

    points = 0
    reasons = []

    if files > FILE_LIMIT:
        points = points + 40
        reasons.append("%d files in %ds" % (files, int(WINDOW)))

    if folders > FOLDER_LIMIT:
        points = points + 30
        reasons.append("%d folders" % folders)

    if path_is_sensitive:
        points = points + 50
        reasons.append("sensitive file")

    return points, ", ".join(reasons)


def is_risky(points):
    return points >= BLOCK_AT


if __name__ == "__main__":
    # Quick check without the daemon: pretend an agent reads 30 files fast.
    for i in range(30):
        p = "/home/test/notes/file%d.txt" % i
        record(p)
        points, why = score(p, False)
        if i % 10 == 0 or is_risky(points):
            print("file %-3d score %-4d %s" % (i, points, why))
            if is_risky(points):
                break