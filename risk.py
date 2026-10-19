import os
import time


WINDOW = 10.0
FILE_LIMIT = 15
FOLDER_LIMIT = 4
WARN_AT = 30
BLOCK_AT = 40

history = {}


def record(root, path):
    now = time.time()
    history.setdefault(root, []).append((now, os.path.dirname(path)))
    trim(now)


def trim(now):
    cutoff = now - WINDOW
    for root in list(history):
        opens = history[root]
        while opens and opens[0][0] < cutoff:
            opens.pop(0)
        if not opens:
            del history[root]


def forget(root):
    history.pop(root, None)


def score(root):
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


def is_warning(points):
    return WARN_AT <= points < BLOCK_AT


def is_risky(points):
    return points >= BLOCK_AT


if __name__ == "__main__":
    for i in range(30):
        p = "/home/test/notes/file%d.txt" % i
        record(1234, p)
        points, why = score(1234)
        if i % 10 == 0 or is_risky(points):
            print("file %-3d score %-4d %s" % (i, points, why))
            if is_risky(points):
                break
